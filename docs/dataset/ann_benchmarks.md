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

## 1.2 SIFT1M 示例

```bash
python examples/milvus_benchmark/0-data-loading/load_ann_dataset.py --input-path data/sift.hdf5
python examples/milvus_benchmark/1-data-import/import_ann_dataset.py --input-path data/sift.hdf5 --vector-key train
```

使用 S3 时传 `--source s3 --input-path s3://bucket/path/sift.hdf5`，并设置
`S3_ACCESS_KEY`、`S3_SECRET_KEY` 和 `S3_ENDPOINT_URL`

导入示例读取 `--vector-key` 指定的二维数组，默认是 `train`
SIFT1M 查询和评测示例读取 `train`、`test`、`neighbors` 和 `distances`，真值 ID 对应 `train` 的原始行号
