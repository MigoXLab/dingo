import json
import time
from typing import Dict, List

from pydantic import ValidationError

from dingo.config.config import DynamicLLMConfig
from dingo.io import Data
from dingo.model.llm.base import BaseLLM
from dingo.model.modelres import ModelRes
from dingo.model.prompt.base import BasePrompt
from dingo.model.response.response_class import ResponseScoreReason
from dingo.utils import log
from dingo.utils.exception import ConvertJsonError, ExceedMaxTokens


class BaseOpenAI(BaseLLM):
    prompt = None
    client = None
    dynamic_config = DynamicLLMConfig()

    @classmethod
    def set_prompt(cls, prompt: BasePrompt):
        cls.prompt = prompt

    @classmethod
    def create_client(cls):
        from openai import OpenAI

        if not cls.dynamic_config.key:
            raise ValueError("key cannot be empty in llm config.")
        elif not cls.dynamic_config.api_url:
            raise ValueError("api_url cannot be empty in llm config.")
        else:
            cls.client = OpenAI(
                api_key=cls.dynamic_config.key, base_url=cls.dynamic_config.api_url
            )

    @classmethod
    def build_messages(cls, input_data: Data) -> List:
        messages = [
            {"role": "user", "content": cls.prompt.content + input_data.content}
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
    def process_response(cls, response: str) -> ModelRes:
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

        result = ModelRes()
        # error_status
        if response_model.score == 1:
            result.reason = [response_model.reason]
        else:
            result.error_status = True
            result.type = cls.prompt.metric_type
            result.name = cls.prompt.__name__
            result.reason = [response_model.reason]

        return result

    @classmethod
    def eval(cls, input_data: Data) -> ModelRes:
        if cls.client is None:
            cls.create_client()

        messages = cls.build_messages(input_data)

        attempts = 0
        except_msg = ""
        except_name = Exception.__class__.__name__
        while attempts < 3:
            try:
                response = cls.send_messages(messages)
                return cls.process_response(response)
            except (ValidationError, ExceedMaxTokens, ConvertJsonError) as e:
                except_msg = str(e)
                except_name = e.__class__.__name__
                break
            except Exception as e:
                attempts += 1
                time.sleep(1)
                except_msg = str(e)
                except_name = e.__class__.__name__

        return ModelRes(
            error_status=True, type="QUALITY_BAD", name=except_name, reason=[except_msg]
        )
