from dingo.config import InputArgs
from dingo.exec import Executor


def image_relevant():
    input_data = {
        "input_path": "../../test/data/test_img_jsonl.jsonl",
        "output_path": "output/hallucination_evaluation/",
        "dataset": {
            "source": "local",
            "format": "jsonl",
            "field": {
                "id": "id",
                "prompt": "url_1",
                "content": "url_2"
            }
        },
        "executor": {
            "prompt_list": ["PromptImageRelevant"],
            "result_save": {
                "bad": True,
                "good": True
            }
        },
        "evaluator": {
            "llm_config": {
                # IMPORTANT: VLMImageRelevant requires a vision-language model (VLM)
                "VLMImageRelevant": {
                    "model": "",  # e.g. qwen3-vl, gpt-4o, doubao-seed-vision
                    "key": "",
                    "api_url": "",
                }
            }
        }
    }
    input_args = InputArgs(**input_data)
    executor = Executor.exec_map["local"](input_args)
    result = executor.execute()
    print(result)


if __name__ == '__main__':
    image_relevant()
