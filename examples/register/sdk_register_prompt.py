from dingo.model import Model
from dingo.model.prompt.base import BasePrompt


@Model.prompt_register("QUALITY_BAD_SIMILARITY", [])
class PromptRepeatDemo(BasePrompt):
    content = """
    请判断一下文本是否存在重复问题。
    返回一个json，如{"score": 0, "type":"xxx", reason": "xxx"}.
    如果存在重复，score是0，否则是1。当score是0时，type是REPEAT。reason是判断的依据。
    除了json不要有其他内容。
    以下是需要判断的文本：
    """


if __name__ == '__main__':
    from dingo.exec import Executor
    from dingo.io import InputArgs

    input_data = {
        "eval_group": "test",
        "input_path": "../../test/data/test_local_jsonl.jsonl",  # local filesystem dataset
        "save_data": True,
        "save_correct": True,
        "dataset": "local",
        "data_format": "jsonl",
        "column_content": "content",
        "custom_config": {
            "prompt_list": ["PromptRepeatDemo"],
            "llm_config": {
                "LLMTextQualityPromptBase": {
                    "key": "",
                    "api_url": ""
                }
            }
        }
    }
    input_args = InputArgs(**input_data)
    executor = Executor.exec_map["local"](input_args)
    result = executor.execute()
    print(result)
