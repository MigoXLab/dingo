from dingo.config import DatasetArgs, DatasetSqlArgs, InputArgs
from dingo.data.dataset import SqlDataset
from dingo.data.datasource.sql import SqlDataSource
from dingo.exec import Executor

SQL_CONFIG = {
    'dialect': 'mysql',
    'driver': 'pymysql',
    'username': '',
    'password': '',
    'host': '',
    'port': '',
    'database': '',
    'connect_args': '?charset=utf8mb4'
}
TABLE_NAME = ''


def main():
    input_data = {
        "input_path": f"SELECT * FROM {TABLE_NAME} where isbn is not null and isbn != '' LIMIT 10",
        "dataset": {
            "source": "sql",
            "format": "jsonl",
            "sql_config": SQL_CONFIG
        },
        "executor": {
            "result_save": {
                "bad": True,
                "good": True,
                "raw": True
            }
        },
        "evaluator": [
            {
                "fields": {"content": "isbn"},
                "evals": [
                    {"name": "RuleIsbn"}
                ]
            },
            {
                "fields": {"content": "title"},
                "evals": [
                    {"name": "RuleAbnormalChar"},
                    {"name": "RuleContentNull"},
                ]
            }
        ]
    }
    input_args = InputArgs(**input_data)
    executor = Executor.exec_map["local"](input_args)
    result = executor.execute()
    print(result)


if __name__ == "__main__":
    main()
