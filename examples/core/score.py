import os

from dingo.config.input_args import EvaluatorLLMArgs
from dingo.io.input import Data
from dingo.model.llm.llm_text_quality_model_base import LLMTextQualityModelBase
from dingo.model.rule.rule_common import RuleEnterAndSpace

OPENAI_MODEL = 'deepseek-chat'
OPENAI_URL = 'https://api.deepseek.com/v1'
OPENAI_KEY = os.getenv("OPENAI_KEY")
if not OPENAI_KEY:
    raise ValueError('OPENAI_KEY is not set correctly.')


def llm():
    data = Data(
        data_id='123',
        prompt="hello, introduce the world",
        content="Hello! The world is a vast and diverse place, full of wonders, cultures, and incredible natural beauty."
    )

    LLMTextQualityModelBase.dynamic_config = EvaluatorLLMArgs(
        model=OPENAI_MODEL,
        key=OPENAI_KEY,
        api_url=OPENAI_URL,
    )
    res = LLMTextQualityModelBase.eval(data)
    print(res)


def rule():
    data = Data(
        data_id='123',
        prompt="hello, introduce the world",
        content="Hello! The world is a vast and diverse place, full of wonders, cultures, and incredible natural beauty."
    )

    res = RuleEnterAndSpace().eval(data)
    print(res)


if __name__ == "__main__":
    llm()
    rule()
