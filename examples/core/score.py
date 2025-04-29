from dingo.config.config import DynamicLLMConfig
from dingo.io.input.MetaData import MetaData
from dingo.model.llm.llm_text_quality_model_base import LlmTextQualityModelBase
from dingo.model.prompt.prompt_common import PromptRepeat
from dingo.model.rule.rule_common import RuleEnterAndSpace


def llm():
    LlmTextQualityModelBase.prompt = PromptRepeat()
    LlmTextQualityModelBase.dynamic_config = DynamicLLMConfig(
        key='',
        api_url='',
        # model='',
    )
    res = LlmTextQualityModelBase.eval(MetaData(
        data_id='123',
        prompt="hello, introduce the world",
        content="Hello! The world is a vast and diverse place, full of wonders, cultures, and incredible natural beauty."
    ))
    print(res)

def rule():
    data = MetaData(
        data_id='123',
        prompt="hello, introduce the world",
        content="Hello! The world is a vast and diverse place, full of wonders, cultures, and incredible natural beauty."
    )
    res = RuleEnterAndSpace().eval(data)
    print(res)

if __name__ == "__main__":
    llm()
    rule()
