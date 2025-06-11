from dingo.exec import Executor
from dingo.io import InputArgs


def exec_first():
    input_data = {
        "eval_group": "sft",
        "input_path": "../../test/data/test_local_jsonl.jsonl",
        "save_data": True,
        "save_correct": True,
        "dataset": "local",
        "data_format": "jsonl",
        "column_id": "id",
        "column_content": "content",
        "end_index": 1
    }

    input_args = InputArgs(**input_data)
    executor = Executor.exec_map["local"](input_args)
    result = executor.execute()
    print(result)


def exec_second():
    input_data = {
        "eval_group": "sft",
        "input_path": "../../test/data/test_local_jsonl.jsonl",
        "save_data": True,
        "save_correct": True,
        "dataset": "local",
        "data_format": "jsonl",
        "column_id": "id",
        "column_content": "content",
        "start_index": 1
    }

    input_args = InputArgs(**input_data)
    executor = Executor.exec_map["local"](input_args)
    result = executor.execute()
    print(result)


if __name__ == '__main__':
    exec_first()
    exec_second()
