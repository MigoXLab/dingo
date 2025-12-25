import json
import time
from typing import Dict, List

from pydantic import ValidationError

from dingo.config.input_args import EvaluatorLLMArgs
from dingo.io import Data
from dingo.io.output.eval_detail import EvalDetail, QualityLabel
from dingo.model.llm.base import BaseLLM
from dingo.model.response.response_class import ResponseScoreReason
from dingo.utils import log
from dingo.utils.exception import ConvertJsonError, ExceedMaxTokens


class BaseOpenAI(BaseLLM):
    dynamic_config = EvaluatorLLMArgs()

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

        params = cls.dynamic_config.parameters
        cls.validate_config(params)

        completions = cls.client.chat.completions.create(
            model=model_name,
            messages=messages,
            temperature=params.get("temperature", 0.3) if params else 0.3,
            top_p=params.get("top_p", 1) if params else 1,
            max_tokens=params.get("max_tokens", 4000) if params else 4000,
            presence_penalty=params.get("presence_penalty", 0) if params else 0,
            frequency_penalty=params.get("frequency_penalty", 0) if params else 0,
        )

        if completions.choices[0].finish_reason == "length":
            raise ExceedMaxTokens(
                f"Exceed max tokens: {params.get('max_tokens', 4000) if params else 4000}"
            )

        return str(completions.choices[0].message.content)

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
        while attempts < 3:
            try:
                response = cls.send_messages(messages)
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
        # res.eval_status = True
        # res.eval_details = {
        #     "label": [f"QUALITY_BAD.{except_name}"],
        #     "metric": [cls.__name__],
        #     "reason": [except_msg]
        # }
        res.status = True
        res.label = [f"QUALITY_BAD.{except_name}"]
        res.reason = [except_msg]
        return res
