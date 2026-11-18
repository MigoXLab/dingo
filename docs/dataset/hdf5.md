# 一、读取 HDF5

## 1.1 配置

安装 HDF5 读取依赖：

```bash
pip install "dingo-python[retrieval]"
```

设置 `dataset.format="hdf5"`，并将 `input_path` 指向单个已有文件

| 数据源 | dataset.source | input_path 示例 | 连接配置 |
| --- | --- | --- | --- |
| 本地 | `local` | `data/vectors.hdf5` | 无 |
| S3 | `s3` | `s3://bucket/path/vectors.hdf5` | [dataset.s3_config](s3.md) |

## 1.2 按需读取

```python
from contextlib import closing

from dingo.config import InputArgs
from dingo.data import dataset_map, datasource_map

args = InputArgs(input_path="data/vectors.hdf5", dataset={"source": "local", "format": "hdf5"})
source = datasource_map[args.dataset.source](input_args=args)
dataset = dataset_map[args.dataset.source](source=source)

with closing(dataset.get_data()) as records:
    hdf5_file = next(records).hdf5
    sample = hdf5_file["vectors"][:5]
```

`vectors` 是示例数组名，按文件实际内容替换
数组按切片读取，关闭迭代器时释放文件；需要保留的切片在关闭前读出
