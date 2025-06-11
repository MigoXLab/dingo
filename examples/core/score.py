from dingo.config.config import DynamicLLMConfig
from dingo.io.input.Data import Data
from dingo.model.llm.llm_text_quality_model_base import LLMTextQualityModelBase
from dingo.model.rule.rule_common import RuleEnterAndSpace


def llm():
    data = Data(
        data_id='123',
        prompt="hello, introduce the world",
        content="Hello! The world is a vast and diverse place, full of wonders, cultures, and incredible natural beauty."
    )

    LLMTextQualityModelBase.dynamic_config = DynamicLLMConfig(
        key='',
        api_url='',
        # model='',
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
