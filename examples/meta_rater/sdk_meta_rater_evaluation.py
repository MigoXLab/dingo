from dingo.config import InputArgs
from dingo.exec import Executor

if __name__ == '__main__':
    input_data = {
        "input_path": "../../test/data/test_meta_rater.jsonl",
        "dataset": {
            "source": "local",
            "format": "jsonl",
            "field": {
                "content": "content"
            }
        },
        "executor": {
            "prompt_list": ["PromptMetaRaterProfessionalism"],  # options: "PromptMetaRaterReadability", "PromptMetaRaterReasoning", "PromptMetaRaterCleanliness"
            "result_save": {
                "bad": True,
                "good": True
            }
        },
        "evaluator": {
            "llm_config": {
                "LLMMetaRaterEvaluation": {
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
