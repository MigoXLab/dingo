# SQL Dataset 使用指南

## 概述

`SqlDataset` 是 Dingo 框架中用于从 SQL 数据库流式读取数据的数据集类。它使用 SQLAlchemy 的服务器游标方式，适合处理大型数据集，不会一次性将所有数据加载到内存中。

## 特性

- ✅ **流式读取**: 使用 SQLAlchemy 的 `stream_results=True` 特性，服务器端游标自动分页
- ✅ **多数据库支持**: 支持 PostgreSQL, MySQL, SQLite 等主流数据库
- ✅ **内存友好**: 逐行处理数据，适合处理大规模数据集
- ✅ **灵活查询**: 支持任意 SQL 查询语句（SELECT、JOIN、WHERE 等）

## 依赖安装

基础依赖：
```bash
pip install sqlalchemy
```

根据数据库类型安装对应驱动：
```bash
# PostgreSQL
pip install psycopg2-binary

# MySQL
pip install pymysql

# SQLite (Python 内置，无需额外安装)
```

## 快速开始

### 1. SQLite 示例（最简单）

```python
from dingo.config import DatasetArgs, DatasetSqlArgs, InputArgs
from dingo.data.dataset.sql import SqlDataset
from dingo.data.datasource.sql import SqlDataSource

# 配置 SQLite 连接
sql_config = DatasetSqlArgs(
    dialect="sqlite",
    driver="",        # SQLite 不需要驱动
    username="",      # SQLite 不需要用户名
    password="",      # SQLite 不需要密码
    host="",          # SQLite 不需要主机
    port="",
    database="test.db"  # 数据库文件路径
)

# 配置数据集
dataset_config = DatasetArgs(
    source="sql",
    format="jsonl",   # SQL 每行数据使用 jsonl 格式
    sql_config=sql_config
)

# SQL 查询语句
sql_query = "SELECT * FROM test_table"

# 创建 InputArgs
input_args = InputArgs(
    task_name="sql_eval",
    input_path=sql_query,  # SQL 查询放在 input_path
    output_path="outputs/",
    dataset=dataset_config,
    evaluator=[]
)

# 创建数据源和数据集
datasource = SqlDataSource(input_args=input_args)
dataset = SqlDataset(source=datasource, name="my_dataset")

# 流式读取数据
for data in dataset.get_data():
    print(data)
```

### 2. PostgreSQL 示例

```python
sql_config = DatasetSqlArgs(
    dialect="postgresql",
    driver="psycopg2",
    username="myuser",
    password="mypassword",
    host="localhost",
    port="5432",
    database="mydb"
)

dataset_config = DatasetArgs(
    source="sql",
    format="jsonl",
    sql_config=sql_config
)

sql_query = """
    SELECT id, prompt, content, label
    FROM evaluation_data
    WHERE created_at > '2024-01-01'
    ORDER BY id
"""

input_args = InputArgs(
    task_name="postgres_eval",
    input_path=sql_query,
    output_path="outputs/",
    dataset=dataset_config,
    evaluator=[]
)

datasource = SqlDataSource(input_args=input_args)
dataset = SqlDataset(source=datasource, name="postgres_dataset")

for data in dataset.get_data():
    print(data)
```

### 3. MySQL 示例

```python
sql_config = DatasetSqlArgs(
    dialect="mysql",
    driver="pymysql",
    username="root",
    password="password",
    host="localhost",
    port="3306",
    database="test_db"
)

dataset_config = DatasetArgs(
    source="sql",
    format="jsonl",
    sql_config=sql_config
)

sql_query = "SELECT * FROM evaluation_data LIMIT 1000"

input_args = InputArgs(
    task_name="mysql_eval",
    input_path=sql_query,
    output_path="outputs/",
    dataset=dataset_config,
    evaluator=[]
)

datasource = SqlDataSource(input_args=input_args)
dataset = SqlDataset(source=datasource, name="mysql_dataset")

for data in dataset.get_data():
    print(data)
```

## 配置说明

### DatasetSqlArgs 参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `dialect` | str | 是 | 数据库类型（如 `postgresql`, `mysql`, `sqlite`） |
| `driver` | str | 否 | 数据库驱动（如 `psycopg2`, `pymysql`） |
| `username` | str | 否* | 数据库用户名（SQLite 不需要） |
| `password` | str | 否 | 数据库密码 |
| `host` | str | 否* | 数据库主机地址（SQLite 不需要） |
| `port` | str | 否 | 数据库端口 |
| `database` | str | 是 | 数据库名称或文件路径（SQLite） |
| `connect_args` | str | 否 | 连接参数，如 `?charset=utf8mb4`、`?sslmode=require` 等 |

*注：对于 SQLite，`username` 和 `host` 不是必填项；对于其他数据库，这些是必填项。

### DatasetArgs 参数

| 参数 | 类型 | 说明 |
|------|------|------|
| `source` | str | 必须设置为 `"sql"` |
| `format` | str | 推荐使用 `"jsonl"`（每行数据作为独立的 JSON 对象） |
| `sql_config` | DatasetSqlArgs | SQL 连接配置 |

## 高级用法

### 1. 复杂 SQL 查询

支持任意复杂的 SQL 查询：

```python
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
    LIMIT 10000
"""
```

### 2. 字段映射

如果数据库列名与 Dingo 期望的字段名不同，可以在 SQL 中使用别名：

```python
sql_query = """
    SELECT
        id,
        question AS prompt,
        answer AS content,
        img_url AS image
    FROM qa_table
"""
```


### 3. 使用连接参数

对于需要特殊连接参数的场景，可以使用 `connect_args` 配置：

```python
# MySQL 使用 UTF-8 编码
sql_config = DatasetSqlArgs(
    dialect="mysql",
    driver="pymysql",
    username="root",
    password="password",
    host="localhost",
    port="3306",
    database="test_db",
    connect_args="?charset=utf8mb4"
)

# PostgreSQL 使用 SSL 连接
sql_config = DatasetSqlArgs(
    dialect="postgresql",
    driver="psycopg2",
    username="myuser",
    password="mypassword",
    host="localhost",
    port="5432",
    database="mydb",
    connect_args="?sslmode=require"
)

# 多个参数组合
sql_config = DatasetSqlArgs(
    dialect="mysql",
    driver="pymysql",
    username="root",
    password="password",
    host="localhost",
    port="3306",
    database="test_db",
    connect_args="?charset=utf8mb4&connect_timeout=10"
)
```

## 工作原理

1. **连接创建**: `SqlDataSource` 使用 SQLAlchemy 创建数据库引擎
2. **流式查询**: 使用 `connection.execution_options(stream_results=True)` 启用服务器端游标
3. **逐行迭代**: SQLAlchemy 自动处理数据分页，逐行返回结果
4. **数据转换**: 每行数据通过 `jsonl` 转换器转换为 `Data` 对象

### 为什么使用 stream_results？

```python
# 传统方式（不推荐，会将所有数据加载到内存）
result = conn.execute("SELECT * FROM large_table")
all_rows = result.fetchall()  # 内存爆炸！

# 流式方式（推荐，内存友好）
result = conn.execution_options(stream_results=True).execute(
    "SELECT * FROM large_table"
)
for row in result:  # 逐行处理，服务器自动分页
    process_row(row)
```

## 支持的数据库

| 数据库 | dialect | driver 示例 | 安装驱动 |
|--------|---------|-------------|----------|
| PostgreSQL | `postgresql` | `psycopg2` | `pip install psycopg2-binary` |
| MySQL | `mysql` | `pymysql` | `pip install pymysql` |
| SQLite | `sqlite` | （不需要） | Python 内置 |
| Oracle | `oracle` | `cx_oracle` | `pip install cx_oracle` |
| SQL Server | `mssql` | `pyodbc` | `pip install pyodbc` |

## 注意事项

1. **格式选择**: 推荐使用 `format="jsonl"`，因为 SQL 查询返回的每行数据相当于一个独立的 JSON 对象
2. **连接字符串**: SQLite 使用文件路径，其他数据库需要网络连接参数
3. **权限**: 确保数据库用户有 SELECT 权限
4. **大数据集**: 对于超大数据集，考虑在 SQL 查询中使用 LIMIT 或 WHERE 条件
5. **资源清理**: 数据源会在 `__del__` 时自动调用 `engine.dispose()` 清理连接

## 示例代码

完整示例代码见：
- `examples/dataset/sql_dataset_example.py`
- `test/scripts/dataset/test_sql_dataset.py`

## 故障排查

### 问题1: ModuleNotFoundError: No module named 'psycopg2'

**解决**: 安装对应的数据库驱动
```bash
pip install psycopg2-binary  # PostgreSQL
pip install pymysql          # MySQL
```

### 问题2: RuntimeError: SQL connection parameters must be set

**解决**: 检查 `DatasetSqlArgs` 中的参数是否正确设置

### 问题3: 连接超时

**解决**:
- 检查数据库服务是否运行
- 检查网络连接和防火墙设置
- 验证主机地址和端口号

### 问题4: TypeError: Data() argument after ** must be a mapping

**解决**: 确保使用 `format="jsonl"` 而不是 `format="json"`

## 性能建议

1. **使用索引**: 确保 SQL 查询中的 WHERE 和 ORDER BY 列有索引
2. **限制结果集**: 使用 LIMIT 或分页查询
3. **选择必要字段**: 避免 `SELECT *`，只选择需要的列
4. **批量处理**: 配合 Dingo 的 `batch_size` 参数使用

## 更多资源

- [SQLAlchemy 文档](https://docs.sqlalchemy.org/)
- [Dingo 文档](../../README.md)
- [配置说明](../config.md)
