# 一、读取 HDF5

## 1.1 配置

安装 HDF5 读取依赖：

```bash
pip install "dingo-python[retrieval]"
```

设置 `input_path` 为已有本地文件或完整的 `s3://bucket/key`，并配置 `dataset.format="hdf5"`
本地文件使用 `dataset.source="local"`；S3 对象使用 `dataset.source="s3"` 和 [S3 连接配置](s3.md)

```python
from contextlib import closing

from dingo.config import InputArgs
from dingo.data import dataset_map, datasource_map

args = InputArgs(input_path="data/sift.hdf5", dataset={"source": "local", "format": "hdf5"})
source = datasource_map[args.dataset.source](input_args=args)
dataset = dataset_map[args.dataset.source](source=source)
with closing(dataset.get_data()) as records:
    hdf5 = next(records).hdf5
    sample = hdf5["train"][:5]
```

关闭迭代器时文件随之关闭，在作用域内完成切片读取

## 1.2 示例参数

```bash
python examples/milvus_benchmark/0-data-loading/load_ann_dataset.py --input-path data/sift.hdf5
python examples/milvus_benchmark/1-data-import/import_ann_dataset.py --input-path data/sift.hdf5 --vector-key train
```

使用 S3 时传 `--source s3 --input-path s3://bucket/path/sift.hdf5`，并设置
`S3_ACCESS_KEY`、`S3_SECRET_KEY` 和 `S3_ENDPOINT_URL`

导入示例读取 `--vector-key` 指定的二维数组，默认是 `train`
加载预览可以用 `--keys` 指定要展示的数组；查询用 `--query-key`（默认 `test`）和 `--top-k` 指定查询数组与返回数量
查询和评测可通过 `--dataset-id` 指定同一个数据集标签，默认取 HDF5 文件名去掉扩展名

评测用 `--metrics` 选择 `recall`、`latency`、`requests` 或 `result_quality`，默认全部计算
Recall 从 `--ground-truth-key`（默认 `neighbors`）读取真值；真值 ID 对应 `--base-key`（默认 `train`）数组的原始行号
评测默认使用 JSONL 中的 K；显式传 `--top-k` 时须与查询一致

```bash
python examples/milvus_benchmark/3-evaluation/evaluate_queries.py \
    --input queries.jsonl --metrics latency requests --output-dir report
```
