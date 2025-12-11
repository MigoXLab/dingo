import json
import time
from typing import List

from pydantic import ValidationError

from dingo.config.input_args import EvaluatorLLMArgs
from dingo.io import Data
from dingo.io.output.eval_detail import EvalDetail, QualityLabel
from dingo.model.llm.base import BaseLLM
from dingo.model.response.response_class import ResponseScoreReason
from dingo.utils import log
from dingo.utils.exception import ConvertJsonError, ExceedMaxTokens


class BaseLmdeployApiClient(BaseLLM):
    dynamic_config = EvaluatorLLMArgs()

    # @classmethod
    # def set_prompt(cls, prompt):
    #     cls.prompt = prompt

    @classmethod
    def create_client(cls):
        from lmdeploy.serve.openai.api_client import APIClient

        if not cls.dynamic_config.api_url:
            raise ValueError("api_url cannot be empty in llm config.")
        else:
            cls.client = APIClient(cls.dynamic_config.api_url)

    @classmethod
    def build_messages(cls, input_data: Data) -> List:
        messages = [
            {"role": "user", "content": cls.prompt + input_data.content}
        ]
        return messages

    @classmethod
    def send_messages(cls, messages: List):
        model_name = cls.client.available_models[0]
        for item in cls.client.chat_completions_v1(model=model_name, messages=messages):
            response = item["choices"][0]["message"]["content"]
        return str(response)

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
            result.label = [QualityLabel.QUALITY_GOOD]
            result.reason = [response_model.reason]
        else:
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

        res = EvalDetail(metric=cls.__name__)
        res.status = True
        res.label = [f"QUALITY_BAD.{except_name}"]
        res.reason = [except_msg]
        return res
