from dingo.config import InputArgs
from dingo.exec import Executor

if __name__ == '__main__':
    input_data = {
        "input_path": "test/data/test_document_OCR_recognize.jsonl",
        "dataset": {
            "source": "local",
            "format": "jsonl",
            "field": {
                "id": "id",
                "content": "pred_content",
                "image": "pred_bbox_image",
            }
        },
        "executor": {
            "prompt_list": ["PromptMinerURecognizeTrainQuality"],
            "result_save": {
                "bad": True,
                "good": True
            }
        },
        "evaluator": {
            "llm_config": {
                "LLMMinerURecognizeQuality": {
                    "model": "gemini-2.5-pro",
                    "key": "sk-SWPLPHhvXOAT2LRHPTfZqbOb6pI2xhp3UDtwdLBdNUXlZ3l1",
                    "api_url": "http://35.220.164.252:3888/v1"
                }
            }
        }
    }
    input_args = InputArgs(**input_data)
    executor = Executor.exec_map["local"](input_args)
    result = executor.execute()
    print(result)
