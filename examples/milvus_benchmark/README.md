# 一、Milvus 向量检索评测

这套示例包含四步：数据准备 → 数据导入 → 查询执行 → 结果评测
从仓库根目录运行命令，先安装依赖：

```bash
pip install -e ".[retrieval]" pymilvus
```

## 1.1 数据准备

准备已有的 HDF5 文件，以下以三个数组为例，键名可通过参数更换：

| 键 | 用途 |
| --- | --- |
| `train` | 基础向量，每行一条 |
| `test` | 查询向量，每行一条，维度与基础向量相同 |
| `neighbors` | 每条查询的真值近邻 ID，ID 为 `train` 从 0 开始的行号 |

```bash
SOURCE=local
INPUT_PATH=data/vectors.hdf5

python examples/milvus_benchmark/0-data-loading/load_ann_dataset.py \
    --source "$SOURCE" --input-path "$INPUT_PATH" --keys train test neighbors
```

预览会打印数组形状、类型和首行样本
预览可以传入本地目录或 S3 前缀，按文件顺序读取；`--keys` 应指定各文件共有的数组
导入、查询和评测分别接收单个 HDF5 文件
读取 S3 时，将 `SOURCE` 改为 `s3`，`INPUT_PATH` 改为完整的 S3 URI，并设置 `S3_ACCESS_KEY`、`S3_SECRET_KEY` 和 `S3_ENDPOINT_URL`
读取接口见 [HDF5 读取指南](../../docs/dataset/hdf5.md)

## 1.2 数据导入

使用已有的 Milvus 数据库和空 collection，主键为显式整数 ID，向量字段的维度与 `train` 一致
替换以下连接参数和 `BASE_COUNT`；这里以 `train` 恰好有 100 行的小数据集为例
实例需要认证时，设置环境变量 `MILVUS_TOKEN`

```bash
MILVUS_URI=http://milvus.example:19530
MILVUS_DB=benchmark
MILVUS_COLLECTION=vectors
BASE_COUNT=100

python examples/milvus_benchmark/1-data-import/import_ann_dataset.py \
    --source "$SOURCE" --input-path "$INPUT_PATH" --vector-key train \
    --count "$BASE_COUNT" --batch-size 100 --write-milvus \
    --milvus-uri "$MILVUS_URI" --milvus-db-name "$MILVUS_DB" --milvus-collection "$MILVUS_COLLECTION"
```

脚本按批输出写入结果，字段名默认是 `id` 和 `vector`，可用 `--milvus-id-field` 和 `--milvus-vector-field` 覆盖；省略 `--write-milvus` 可以先预览批次
小规模写入只用于联调
正式计算 Recall 时，导入的基础向量必须与真值对应；用全量真值评测时，应导入完整的 `train` 并保留原始行号

[导入验收脚本](4-vector-db-import/run_import_test.py)使用专用非 `default` 数据库中的空 collection，执行写入和逐条回读，并通过 `--output-dir` 保存报告

## 1.3 查询执行

查询使用与导入相同的 collection 和字段名，距离类型须与数据集真值一致
输出文件应尚不存在

```bash
python examples/milvus_benchmark/2-query-execution/run_queries.py \
    --source "$SOURCE" --input-path "$INPUT_PATH" --query-key test \
    --milvus-uri "$MILVUS_URI" --milvus-db-name "$MILVUS_DB" --milvus-collection "$MILVUS_COLLECTION" \
    --count 1 --top-k 10 --output queries.jsonl
```

`queries.jsonl` 每行记录一次查询的 ID、命中、延迟和状态

## 1.4 结果评测

用同一份 HDF5 的真值给查询结果打分；K 默认从 JSONL 获取，真值每行至少包含 K 个近邻

```bash
python examples/milvus_benchmark/3-evaluation/evaluate_queries.py \
    --input queries.jsonl --source "$SOURCE" --input-path "$INPUT_PATH" \
    --base-key train --ground-truth-key neighbors --metrics recall latency --output-dir report
```

`report/` 中的 `per_query.jsonl` 记录逐查询结果，`summary.json` 汇总指标
只选 `latency` 或 `requests` 时，传查询 JSONL 即可
