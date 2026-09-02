import inspect
import json
import time
from functools import lru_cache
from typing import Dict, List

from pydantic import ValidationError

from dingo.config.input_args import EvaluatorLLMArgs
from dingo.io.input import Data, RequiredField
from dingo.io.output.eval_detail import EvalDetail, QualityLabel, TokenUsage
from dingo.model.llm.base import BaseLLM, LLMCallResult
from dingo.model.response.response_class import ResponseScoreReason
from dingo.utils import log
from dingo.utils.exception import ConvertJsonError, ExceedMaxTokens

#: 单次请求的默认超时（秒）。评估器可以在 config 里用 ``request_timeout`` 覆盖它。
#: 保持 90 是既有行为，不动；输入大、又用推理模型的场景应当显式配大。
DEFAULT_REQUEST_TIMEOUT = 90

#: 一次请求最多重试几次，与 OpenAI SDK 的默认值一致，所以不配就是原来的行为。
#: 它和超时要一起定：超时是单次尝试的代价，重试把这个代价乘起来。
DEFAULT_MAX_RETRIES = 2

#: 已知「给评估器自己看」的配置键。它们和真正的请求参数共用 ``model_extra``
#: 这一个口袋，所以转发给模型服务之前要摘出来。
#:
#: 这张表**不是**过滤的判据——判据是 SDK 签名（见 ``_provider_request_params``）。
#: 它只决定一个被丢弃的键要不要告警：登记过的是有意为之，不必出声；没登记的
#: 多半是键名拼错了，值得说一句。
#:
#: 判据之所以不用这张表：黑名单要靠人记得为每个新增的本地键登记一次，而这些
#: 键分散在各个评估器里（``strictness`` 在 RAG、``agent_config`` 有六处在读），
#: 漏一个的症状是该评估器每次调用必崩——``create()`` 不收未知关键字参数，抛出的
#: TypeError 又会被上层塑形成「评估失败」，与超时长得一模一样。
LOCAL_ONLY_CONFIG_KEYS = frozenset(
    {
        "request_timeout",  # 本模块自己消费，见 send_messages
        "max_retries",  # 构造客户端时消费，不是请求体参数
        "threshold",  # agent_eval / rag / instruction_quality 的判定阈值
        "strictness",  # rag 的答案相关性
        "min_difficulty",
        "max_difficulty",
        "agent_config",  # agent 评估器自己的编排配置
    }
)


class BaseOpenAI(BaseLLM):
    dynamic_config = EvaluatorLLMArgs()
    _required_fields = [RequiredField.CONTENT]  # Default, override in subclasses

    # Embedding 模型配置（用于 RAG 相关评估器）
    embedding_model = None

    # @classmethod
    # def set_prompt(cls, prompt: BasePrompt):
    #     cls.prompt = prompt

    @classmethod
    def create_client(cls):
        """创建 LLM 客户端，如果配置了 embedding_config 则同时初始化 Embedding 客户端"""
        from openai import OpenAI

        if not cls.dynamic_config.key:
            raise ValueError("key cannot be empty in llm config.")
        elif not cls.dynamic_config.api_url:
            raise ValueError("api_url cannot be empty in llm config.")
        else:
            # 创建主 LLM 客户端
            cls.client = OpenAI(
                api_key=cls.dynamic_config.key,
                base_url=cls.dynamic_config.api_url,
                max_retries=cls.get_local_config_value(
                    "max_retries", DEFAULT_MAX_RETRIES
                ),
            )

            # 如果配置了 embedding_config，初始化 Embedding 客户端
            if cls.dynamic_config.embedding_config:
                from dingo.config.input_args import EmbeddingConfigArgs

                embedding_cfg = cls.dynamic_config.embedding_config

                # 处理 embedding_config 可能是字典或对象的情况
                if isinstance(embedding_cfg, dict):
                    # 如果是字典，转换为 EmbeddingConfigArgs 对象
                    embedding_cfg = EmbeddingConfigArgs(**embedding_cfg)

                if not embedding_cfg.api_url:
                    raise ValueError("embedding_config must provide api_url")

                if not embedding_cfg.model:
                    raise ValueError("embedding_config must provide model")

                # 创建独立的 Embedding 客户端
                cls.embedding_client = OpenAI(
                    api_key=embedding_cfg.key or 'dummy-key',
                    base_url=embedding_cfg.api_url
                )

                cls.embedding_model = {
                    'model_name': embedding_cfg.model,
                    'client': cls.embedding_client
                }
                log.info(f"Initialized independent embedding client: {embedding_cfg.model} @ {embedding_cfg.api_url}")

    @classmethod
    def build_messages(cls, input_data: Data) -> List:
        messages = [
            {"role": "user", "content": cls.prompt + input_data.content}
        ]
        return messages

    @classmethod
    def send_messages(cls, messages: List):
        if cls.dynamic_config.model:
            model_name = cls.dynamic_config.model
        else:
            model_name = cls.client.models.list().data[0].id

        extra_params = cls.get_request_extra_params()
        cls.validate_config(extra_params)

        request_timeout = cls.get_local_config_value("request_timeout", DEFAULT_REQUEST_TIMEOUT)
        completions = cls.client.chat.completions.create(
            model=model_name,
            messages=messages,
            timeout=request_timeout,
            **extra_params,
        )

        if completions.choices[0].finish_reason == "length":
            raise ExceedMaxTokens(
                f"Exceed max tokens: {extra_params.get('max_tokens', 4000)}"
            )

        return LLMCallResult(
            content=str(completions.choices[0].message.content),
            usage=cls._extract_token_usage(
                completions,
                model_name=model_name,
                provider="openai",
            ),
        )

    @staticmethod
    @lru_cache(maxsize=1)
    def _provider_request_params() -> frozenset:
        """哪些键是 SDK 真的收的请求参数。取自签名，不靠人维护。"""
        from openai.resources.chat.completions import Completions

        return frozenset(inspect.signature(Completions.create).parameters) - {"self"}

    @classmethod
    def get_request_extra_params(cls) -> Dict:
        """Return evaluator extras that should be sent to the LLM provider.

        放行判据见 ``LOCAL_ONLY_CONFIG_KEYS`` 的说明。过滤只放在这一处：这里是
        唯一回答「什么该发给模型服务」的地方，写在别处的过滤会被下一个调用点忘掉。
        """
        accepted = cls._provider_request_params()
        sendable: Dict = {}
        unexpected: List[str] = []
        for key, value in (cls.dynamic_config.model_extra or {}).items():
            if key in accepted:
                sendable[key] = value
            elif key not in LOCAL_ONLY_CONFIG_KEYS:
                unexpected.append(key)
        if unexpected:
            # 丢弃而不是转发，因为转发必崩；但要出声，否则一个拼错的键名会
            # 安静地不生效，比崩还难查。
            log.warning(
                "evaluator config keys are not request parameters and were not sent: %s",
                ", ".join(sorted(unexpected)),
            )
        return sendable

    @classmethod
    def get_local_config_value(cls, key: str, default=None):
        """Read a knob that steers the evaluator itself, never the request."""
        extras = (cls.dynamic_config.model_extra or {}) if cls.dynamic_config else {}
        return extras.get(key, default)

    @staticmethod
    def _usage_value(data, key: str):
        if data is None:
            return None
        if isinstance(data, dict):
            return data.get(key)
        return getattr(data, key, None)

    @staticmethod
    def _coerce_optional_int(value):
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @classmethod
    def _extract_token_usage(
        cls,
        completion,
        model_name: str,
        provider: str = "openai",
    ) -> TokenUsage | None:
        raw_usage = getattr(completion, "usage", None)
        if raw_usage is None:
            return None

        if hasattr(raw_usage, "model_dump"):
            usage_data = raw_usage.model_dump()
        elif isinstance(raw_usage, dict):
            usage_data = raw_usage
        else:
            usage_data = raw_usage

        completion_details = cls._usage_value(
            usage_data, "completion_tokens_details"
        )
        prompt_details = cls._usage_value(usage_data, "prompt_tokens_details")

        return TokenUsage(
            prompt_tokens=cls._coerce_optional_int(
                cls._usage_value(usage_data, "prompt_tokens")
            ),
            completion_tokens=cls._coerce_optional_int(
                cls._usage_value(usage_data, "completion_tokens")
            ),
            total_tokens=cls._coerce_optional_int(
                cls._usage_value(usage_data, "total_tokens")
            ),
            reasoning_tokens=cls._coerce_optional_int(
                cls._usage_value(completion_details, "reasoning_tokens")
            ),
            cached_tokens=cls._coerce_optional_int(
                cls._usage_value(prompt_details, "cached_tokens")
            ),
            model=model_name,
            provider=provider,
            source="provider",
        )

    @staticmethod
    def _copy_token_usage(usage: TokenUsage) -> TokenUsage:
        if hasattr(usage, "model_copy"):
            return usage.model_copy(deep=True)
        return usage.copy(deep=True)

    @classmethod
    def _merge_token_usage(
        cls,
        current: TokenUsage | None,
        new_usage: TokenUsage | None,
    ) -> TokenUsage | None:
        if new_usage is None:
            return current
        if current is None:
            return cls._copy_token_usage(new_usage)

        def _sum_optional(left, right):
            if left is None and right is None:
                return None
            return int(left or 0) + int(right or 0)

        current.prompt_tokens = _sum_optional(
            current.prompt_tokens, new_usage.prompt_tokens
        )
        current.completion_tokens = _sum_optional(
            current.completion_tokens, new_usage.completion_tokens
        )
        current.total_tokens = _sum_optional(
            current.total_tokens, new_usage.total_tokens
        )
        current.reasoning_tokens = _sum_optional(
            current.reasoning_tokens, new_usage.reasoning_tokens
        )
        current.cached_tokens = _sum_optional(
            current.cached_tokens, new_usage.cached_tokens
        )
        current.calls += int(new_usage.calls or 1)
        if current.model != new_usage.model:
            current.model = current.model or new_usage.model
        if current.source != new_usage.source:
            current.source = current.source or new_usage.source
        return current

    @classmethod
    def validate_numeric_range(cls, value, min_val, max_val, param_name):
        if not isinstance(value, (int, float)):
            raise ValueError(f"{param_name} must be a number")
        if not (min_val <= value <= max_val):
            raise ValueError(f"{param_name} must between {min_val} and {max_val}")

    @classmethod
    def validate_integer_positive(cls, value, param_name):
        if not isinstance(value, int):
            raise ValueError(f"{param_name} must be an integer")
        if value <= 0:
            raise ValueError(f"{param_name} must be greater than 0")

    @classmethod
    def validate_config(cls, parameters: Dict):
        if parameters is None:
            return

        # validate temperature
        if "temperature" in parameters:
            cls.validate_numeric_range(parameters["temperature"], 0, 2, "temperature")

        # validate top_p
        if "top_p" in parameters:
            cls.validate_numeric_range(parameters["top_p"], 0, 1, "top_p")

        # validate max_tokens
        if "max_tokens" in parameters:
            cls.validate_integer_positive(parameters["max_tokens"], "max_tokens")

        # validate presence_penalty
        if "presence_penalty" in parameters:
            cls.validate_numeric_range(
                parameters["presence_penalty"], -2.0, 2.0, "presence_penalty"
            )

        # validate frequency_penalty
        if "frequency_penalty" in parameters:
            cls.validate_numeric_range(
                parameters["frequency_penalty"], -2.0, 2.0, "frequency_penalty"
            )

    @classmethod
    def process_response(cls, response: str) -> EvalDetail:
        log.info(response)

        if response.startswith("```json"):
            response = response[7:]
        if response.startswith("```"):
            response = response[3:]
        if response.endswith("```"):
            response = response[:-3]
        try:
            response_json = json.loads(response)
        except json.JSONDecodeError:
            raise ConvertJsonError(f"Convert to JSON format failed: {response}")

        response_model = ResponseScoreReason(**response_json)

        result = EvalDetail(metric=cls.__name__)
        # eval_status
        if response_model.score == 1:
            # result.eval_details = {
            #     "label": [QualityLabel.QUALITY_GOOD],
            #     "metric": [cls.__name__],
            #     "reason": [response_model.reason]
            # }
            result.label = [QualityLabel.QUALITY_GOOD]
            result.reason = [response_model.reason]
        else:
            # result.eval_status = True
            # result.eval_details = {
            #     "label": [f"QUALITY_BAD.{cls.__name__}"],
            #     "metric": [cls.__name__],
            #     "reason": [response_model.reason]
            # }
            result.status = True
            result.label = [f"QUALITY_BAD.{cls.__name__}"]
            result.reason = [response_model.reason]

        return result

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        if cls.client is None:
            cls.create_client()

        messages = cls.build_messages(input_data)

        attempts = 0
        except_msg = ""
        except_name = Exception.__class__.__name__
        usage: TokenUsage | None = None
        while attempts < 3:
            try:
                response = cls.send_messages(messages)
                if isinstance(response, LLMCallResult):
                    usage = cls._merge_token_usage(usage, response.usage)
                    res: EvalDetail = cls.process_response(response.content)
                    res.usage = usage
                else:
                    res: EvalDetail = cls.process_response(response)
                return res
            except (ValidationError, ExceedMaxTokens, ConvertJsonError) as e:
                except_msg = str(e)
                except_name = e.__class__.__name__
                break
            except Exception as e:
                attempts += 1
                time.sleep(1)
                except_msg = str(e)
                except_name = e.__class__.__name__

        res = EvalDetail(metric=cls.__name__)
        res.status = False  # 执行失败不是质量问题，绝不伪装成 issue（spec §9.3）
        res.applicable = False  # 执行失败 → effective_verdict="n/a"，不是 pass（final-review #2）
        # 但要说清是哪一种"不适用"。只留 applicable=False 时，下游把这条读成
        # "这项检查不适用于你的运行"，而真相是评测器自己挂了——前者是在讲这次
        # 运行，后者只关乎评测器。名字在这里给，因为只有这里知道答案。
        res.not_applicable_kind = "execution_error"
        res.score = None
        res.label = [f"{QualityLabel.REVIEW_EXECUTION_ERROR_PREFIX}{except_name}"]
        res.reason = [except_msg]
        res.usage = usage
        return res
