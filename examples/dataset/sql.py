"""
SQL Dataset 使用示例

该示例展示如何使用 SqlDataset 从数据库流式读取数据进行评估。
使用 SQLAlchemy 的服务器游标方式，适合处理大型数据集。

依赖：
    pip install sqlalchemy
    # 根据数据库类型安装对应驱动：
    # PostgreSQL: pip install psycopg2-binary
    # MySQL: pip install pymysql
    # SQLite: 已内置
"""

from dingo.config import DatasetArgs, DatasetSqlArgs, InputArgs
from dingo.data.dataset import SqlDataset
from dingo.data.datasource.sql import SqlDataSource


# ============= 示例 1: PostgreSQL =============
def example_postgresql():
    """PostgreSQL 数据库示例"""
    # 配置 SQL 连接参数
    sql_config = DatasetSqlArgs(
        dialect="postgresql",
        driver="psycopg2",  # 或 "psycopg2" / "pg8000"
        username="your_username",
        password="your_password",
        host="localhost",
        port="5432",
        database="your_database"
    )

    # 配置数据集参数
    dataset_config = DatasetArgs(
        source="sql",
        format="jsonl",  # SQL 每行数据类似 JSONL，使用 jsonl 格式
        sql_config=sql_config
    )

    # SQL 查询语句（放在 input_path 参数中）
    sql_query = "SELECT id, prompt, content, image FROM large_table WHERE status = 'pending'"

    # 创建 InputArgs
    input_args = InputArgs(
        task_name="sql_eval_task",
        input_path=sql_query,  # SQL查询语句
        output_path="outputs/sql_results/",
        dataset=dataset_config,
        evaluator=[]
    )

    # 创建数据源和数据集
    datasource = SqlDataSource(input_args=input_args)
    dataset = SqlDataset(source=datasource, name="postgres_dataset")

    # 流式读取数据
    print("开始读取 PostgreSQL 数据...")
    for idx, data in enumerate(dataset.get_data()):
        print(f"处理第 {idx + 1} 条数据: {data}")
        if idx >= 5:  # 仅展示前5条
            break

    print("完成！")


# ============= 示例 2: MySQL =============
def example_mysql():
    """MySQL 数据库示例"""
    sql_config = DatasetSqlArgs(
        dialect="mysql",
        driver="pymysql",  # 或 "mysqldb" / "mysqlconnector"
        username="root",
        password="password",
        host="localhost",
        port="3306",
        database="test_db",
        connect_args="charset=utf8mb4"  # 连接参数，如字符集配置
    )

    dataset_config = DatasetArgs(
        source="sql",
        format="jsonl",  # SQL 每行数据类似 JSONL，使用 jsonl 格式
        sql_config=sql_config
    )

    sql_query = "SELECT * FROM evaluation_data LIMIT 1000"

    input_args = InputArgs(
        task_name="mysql_eval",
        input_path=sql_query,
        output_path="outputs/mysql_results/",
        dataset=dataset_config,
        evaluator=[]
    )

    datasource = SqlDataSource(input_args=input_args)
    dataset = SqlDataset(source=datasource, name="mysql_dataset")

    print("开始读取 MySQL 数据...")
    for idx, data in enumerate(dataset.get_data()):
        print(f"处理第 {idx + 1} 条数据: {data}")
        if idx >= 5:
            break


# ============= 示例 3: SQLite =============
def example_sqlite():
    """SQLite 数据库示例（最简单，无需额外安装驱动）"""
    sql_config = DatasetSqlArgs(
        dialect="sqlite",
        driver="",  # SQLite 不需要驱动
        username="",  # SQLite 不需要用户名
        password="",  # SQLite 不需要密码
        host="",  # SQLite 使用文件路径
        port="",
        database="test.db"  # 数据库文件路径
    )

    dataset_config = DatasetArgs(
        source="sql",
        format="jsonl",  # SQL 每行数据类似 JSONL，使用 jsonl 格式
        sql_config=sql_config
    )

    sql_query = "SELECT * FROM test_table"

    input_args = InputArgs(
        task_name="sqlite_eval",
        input_path=sql_query,
        output_path="outputs/sqlite_results/",
        dataset=dataset_config,
        evaluator=[]
    )

    datasource = SqlDataSource(input_args=input_args)
    dataset = SqlDataset(source=datasource, name="sqlite_dataset")

    print("开始读取 SQLite 数据...")
    for idx, data in enumerate(dataset.get_data()):
        print(f"处理第 {idx + 1} 条数据: {data}")
        if idx >= 5:
            break


# ============= 示例 4: MySQL with 连接参数 =============
def example_mysql_with_connect_args():
    """MySQL 数据库示例（带连接参数）

    示例连接 URL：mysql+pymysql://data_user:data_user#123@10.161.82.109:8080/ads?charset=utf8mb4
    """
    sql_config = DatasetSqlArgs(
        dialect="mysql",
        driver="pymysql",
        username="data_user",
        password="data_user#123",  # 密码中可以包含特殊字符
        host="10.161.82.109",
        port="8080",
        database="ads",
        connect_args="charset=utf8mb4"  # 连接参数，支持多个参数用 & 连接，如 "charset=utf8mb4&autocommit=true"
    )

    dataset_config = DatasetArgs(
        source="sql",
        format="jsonl",
        sql_config=sql_config
    )

    sql_query = "SELECT * FROM evaluation_data LIMIT 1000"

    input_args = InputArgs(
        task_name="mysql_with_args_eval",
        input_path=sql_query,
        output_path="outputs/mysql_args_results/",
        dataset=dataset_config,
        evaluator=[]
    )

    datasource = SqlDataSource(input_args=input_args)
    dataset = SqlDataset(source=datasource, name="mysql_with_args_dataset")

    print("开始读取 MySQL 数据（带连接参数）...")
    for idx, data in enumerate(dataset.get_data()):
        print(f"处理第 {idx + 1} 条数据: {data}")
        if idx >= 5:
            break


# ============= 示例 5: 复杂 SQL 查询 =============
def example_complex_query():
    """使用复杂 SQL 查询的示例"""
    sql_config = DatasetSqlArgs(
        dialect="postgresql",
        driver="psycopg2",
        username="user",
        password="pass",
        host="localhost",
        port="5432",
        database="mydb"
    )

    dataset_config = DatasetArgs(
        source="sql",
        format="jsonl",  # SQL 每行数据类似 JSONL，使用 jsonl 格式
        sql_config=sql_config
    )

    # 复杂 SQL 查询：JOIN、WHERE、ORDER BY
    sql_query = """
        SELECT
            t1.id,
            t1.prompt,
            t1.content,
            t2.label,
            t2.score
        FROM evaluation_data t1
        LEFT JOIN evaluation_results t2 ON t1.id = t2.data_id
        WHERE t1.created_at > '2024-01-01'
        AND t2.score > 0.5
        ORDER BY t1.id
    """

    input_args = InputArgs(
        task_name="complex_sql_eval",
        input_path=sql_query,
        output_path="outputs/complex_results/",
        dataset=dataset_config,
        evaluator=[]
    )

    datasource = SqlDataSource(input_args=input_args)
    dataset = SqlDataset(source=datasource, name="complex_query_dataset")

    print("开始执行复杂查询...")
    for idx, data in enumerate(dataset.get_data()):
        print(f"处理第 {idx + 1} 条数据: {data}")
        if idx >= 5:
            break


if __name__ == "__main__":
    print("=" * 60)
    print("SQL Dataset 示例")
    print("=" * 60)

    # 根据需要取消注释相应的示例
    # example_postgresql()
    example_mysql()
    # example_sqlite()
    # example_mysql_with_connect_args()
    # example_complex_query()

    print("\n提示: 请根据你的数据库类型修改配置参数并运行相应的示例函数")
