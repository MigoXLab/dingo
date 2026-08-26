import json
import time
from typing import Dict, List

from pydantic import ValidationError

from dingo.config.input_args import EvaluatorLLMArgs
from dingo.io.input import Data, RequiredField
from dingo.io.output.eval_detail import EvalDetail, QualityLabel, TokenUsage
from dingo.model.llm.base import BaseLLM, LLMCallResult
from dingo.model.response.response_class import ResponseScoreReason
from dingo.utils import log
from dingo.utils.exception import ConvertJsonError, ExceedMaxTokens


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
                api_key=cls.dynamic_config.key, base_url=cls.dynamic_config.api_url
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

        request_timeout = extra_params.pop("request_timeout", 90)
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

    @classmethod
    def get_request_extra_params(cls) -> Dict:
        """Return evaluator extras that should be sent to the LLM provider."""
        return dict(cls.dynamic_config.model_extra or {})

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
