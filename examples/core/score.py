from dingo.config.config import DynamicLLMConfig
from dingo.io.input.MetaData import MetaData
from dingo.model.llm.detect_text_quality_detail import DetectTextQualityDetail
from dingo.model.prompt.prompt_common import PromptRepeat
from dingo.model.rule.rule_common import RuleEnterAndSpace


def llm():
    DetectTextQualityDetail.prompt = PromptRepeat()
    DetectTextQualityDetail.dynamic_config = DynamicLLMConfig(
        key='',
        api_url='',
        # model='',
    )
    res = DetectTextQualityDetail.call_api(MetaData(data_id='123', content="hello, introduce the world"))
    print(res)

def rule():
    data = MetaData(data_id = '', content = "hello, introduce the world")
    res = RuleEnterAndSpace().eval(data)
    print(res)

if __name__ == "__main__":
    llm()
    rule()
