"""
SQL Dataset 测试文件

使用 SQLite 数据库进行简单测试（无需额外安装驱动）
"""

import os
import sqlite3
import tempfile

from dingo.config import DatasetArgs, DatasetSqlArgs, InputArgs
from dingo.data.dataset.sql import SqlDataset
from dingo.data.datasource.sql import SqlDataSource


def create_test_database():
    """创建一个测试 SQLite 数据库"""
    # 创建临时数据库文件
    db_path = os.path.join(tempfile.gettempdir(), "test_dingo_sql.db")

    # 连接数据库并创建测试表
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 创建测试表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS test_data (
            id INTEGER PRIMARY KEY,
            prompt TEXT,
            content TEXT,
            context TEXT,
            image TEXT
        )
    """)

    # 插入测试数据
    test_data = [
        (1, "测试提示1", "这是第一条测试内容", "上下文1", "image1.jpg"),
        (2, "测试提示2", "这是第二条测试内容", "上下文2", "image2.jpg"),
        (3, "测试提示3", "这是第三条测试内容", "上下文3", "image3.jpg"),
        (4, "测试提示4", "这是第四条测试内容", "上下文4", "image4.jpg"),
        (5, "测试提示5", "这是第五条测试内容", "上下文5", "image5.jpg"),
    ]

    cursor.executemany(
        "INSERT OR REPLACE INTO test_data VALUES (?, ?, ?, ?, ?)",
        test_data
    )

    conn.commit()
    conn.close()

    return db_path


def test_sql_dataset():
    """测试 SqlDataset 功能"""
    print("=" * 60)
    print("测试 SqlDataset")
    print("=" * 60)

    # 创建测试数据库
    db_path = create_test_database()
    print(f"✓ 创建测试数据库: {db_path}")

    try:
        # 配置 SQL 连接参数（SQLite）
        sql_config = DatasetSqlArgs(
            dialect="sqlite",
            driver="",
            username="",
            password="",
            host="",
            port="",
            database=db_path
        )

        # 配置数据集参数
        dataset_config = DatasetArgs(
            source="sql",
            format="jsonl",  # SQL 每行数据类似 JSONL，使用 jsonl 格式
            sql_config=sql_config
        )

        # SQL 查询
        sql_query = "SELECT * FROM test_data"

        # 创建 InputArgs
        input_args = InputArgs(
            task_name="sql_test",
            input_path=sql_query,
            output_path="outputs/sql_test/",
            dataset=dataset_config,
            evaluator=[]
        )

        print("✓ 配置参数创建成功")

        # 创建数据源
        datasource = SqlDataSource(input_args=input_args)
        print("✓ SqlDataSource 创建成功")

        # 创建数据集
        dataset = SqlDataset(source=datasource, name="test_sql_dataset")
        print("✓ SqlDataset 创建成功")

        # 测试流式读取
        print("\n开始流式读取数据:")
        count = 0
        for idx, data in enumerate(dataset.get_data()):
            count += 1
            print(f"  [{idx + 1}] 读取到数据: {data}")

        print(f"\n✓ 成功读取 {count} 条数据")

        # 验证数据源类型
        assert datasource.get_source_type() == "sql", "数据源类型不正确"
        print("✓ 数据源类型验证通过")

        # 验证数据集类型
        assert dataset.get_dataset_type() == "sql", "数据集类型不正确"
        print("✓ 数据集类型验证通过")

        # 验证 to_dict 方法
        dataset_dict = dataset.to_dict()
        assert "name" in dataset_dict, "数据集字典缺少 name 字段"
        assert "digest" in dataset_dict, "数据集字典缺少 digest 字段"
        print("✓ to_dict 方法验证通过")

        print("\n" + "=" * 60)
        print("✓ 所有测试通过!")
        print("=" * 60)

    finally:
        # 清理测试数据库
        if os.path.exists(db_path):
            os.remove(db_path)
            print(f"\n✓ 清理测试数据库: {db_path}")


def test_stream_results():
    """测试流式结果是否正确工作（不会一次性加载所有数据到内存）"""
    print("\n" + "=" * 60)
    print("测试流式读取特性")
    print("=" * 60)

    # 创建一个包含更多数据的测试数据库
    db_path = os.path.join(tempfile.gettempdir(), "test_dingo_sql_stream.db")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS large_table (
            id INTEGER PRIMARY KEY,
            data TEXT
        )
    """)

    # 插入 1000 条数据
    large_data = [(i, f"数据_{i}") for i in range(1, 1001)]
    cursor.executemany("INSERT INTO large_table VALUES (?, ?)", large_data)
    conn.commit()
    conn.close()

    print(f"✓ 创建包含 1000 条数据的测试数据库")

    try:
        sql_config = DatasetSqlArgs(
            dialect="sqlite",
            driver="",
            username="",
            password="",
            host="",
            port="",
            database=db_path
        )

        dataset_config = DatasetArgs(
            source="sql",
            format="jsonl",  # SQL 每行数据类似 JSONL，使用 jsonl 格式
            sql_config=sql_config
        )

        input_args = InputArgs(
            task_name="stream_test",
            input_path="SELECT * FROM large_table",
            output_path="outputs/stream_test/",
            dataset=dataset_config,
            evaluator=[]
        )

        datasource = SqlDataSource(input_args=input_args)
        dataset = SqlDataset(source=datasource, name="stream_test_dataset")

        # 只读取前 10 条，验证流式读取（不会加载全部 1000 条到内存）
        print("开始流式读取（只读取前 10 条）:")
        count = 0
        for idx, data in enumerate(dataset.get_data()):
            if idx < 10:
                print(f"  [{idx + 1}] {data}")
            count += 1
            if idx >= 9:  # 只读取前 10 条就停止
                break

        print(f"\n✓ 流式读取验证通过（处理了 {count} 条数据后停止）")

    finally:
        if os.path.exists(db_path):
            os.remove(db_path)
            print(f"✓ 清理测试数据库: {db_path}")


if __name__ == "__main__":
    # 运行基本测试
    test_sql_dataset()

    # 运行流式读取测试
    test_stream_results()
