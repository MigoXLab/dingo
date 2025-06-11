from dingo.exec import Executor
from dingo.io import InputArgs


def huggingface_plaintext():
    input_data = {
        "eval_group": "sft",
        "input_path": "chupei/format-text",  # huggingface dataset
        "data_format": "plaintext",
        "column_content": "text",
    }

    input_args = InputArgs(**input_data)
    executor = Executor.exec_map["local"](input_args)
    result = executor.execute()
    print(result)


def huggingface_json():
    input_data = {
        "eval_group": "sft",
        "input_path": "chupei/format-json",  # huggingface dataset
        "data_format": "json",
        "column_content": "prediction",
        "column_prompt": "origin_prompt",
    }

    input_args = InputArgs(**input_data)
    executor = Executor.exec_map["local"](input_args)
    result = executor.execute()
    print(result)


def huggingface_jsonl():
    input_data = {
        "eval_group": "sft",
        "input_path": "chupei/format-jsonl",  # huggingface dataset
        "data_format": "jsonl",
        "column_content": "content",
    }

    input_args = InputArgs(**input_data)
    executor = Executor.exec_map["local"](input_args)
    result = executor.execute()
    print(result)


def huggingface_listjson():
    input_data = {
        "eval_group": "sft",
        "input_path": "chupei/format-listjson",  # huggingface dataset
        "data_format": "listjson",
        "column_content": "output",
        "column_prompt": "instruction",
    }

    input_args = InputArgs(**input_data)
    executor = Executor.exec_map["local"](input_args)
    result = executor.execute()
    print(result)


if __name__ == '__main__':
    huggingface_plaintext()
    huggingface_json()
    huggingface_jsonl()
    huggingface_listjson()
