from dingo.exec import Executor
from dingo.io import InputArgs


def local_plaintext():
    input_data = {
        "eval_group": "sft",
        "input_path": "../../test/data/test_local_plaintext.txt",  # local filesystem dataset
        "dataset": "local",
        "data_format": "plaintext",
    }

    input_args = InputArgs(**input_data)
    executor = Executor.exec_map["local"](input_args)
    result = executor.execute()
    print(result)


def local_json():
    input_data = {
        "eval_group": "sft",
        "input_path": "../../test/data/test_local_json.json",  # local filesystem dataset
        "dataset": "local",
        "data_format": "json",
        "column_content": "prediction",
    }

    input_args = InputArgs(**input_data)
    executor = Executor.exec_map["local"](input_args)
    result = executor.execute()
    print(result)


def local_jsonl():
    input_data = {
        "eval_group": "sft",
        "input_path": "../../test/data/test_local_jsonl.jsonl",  # local filesystem dataset
        "dataset": "local",
        "data_format": "jsonl",
        "column_content": "content",
    }

    input_args = InputArgs(**input_data)
    executor = Executor.exec_map["local"](input_args)
    result = executor.execute()
    print(result)


def local_listjson():
    input_data = {
        "eval_group": "sft",
        "input_path": "../../test/data/test_local_listjson.json",  # local filesystem dataset
        "dataset": "local",
        "data_format": "listjson",
        "column_content": "output",
    }

    input_args = InputArgs(**input_data)
    executor = Executor.exec_map["local"](input_args)
    result = executor.execute()
    print(result)


if __name__ == '__main__':
    local_plaintext()
    local_json()
    local_jsonl()
    local_listjson()
