# 一、读取 HDF5

## 1.1 配置

安装 HDF5 读取依赖：

```bash
pip install "dingo-python[retrieval]"
```

设置 `dataset.format="hdf5"`，并将 `input_path` 指向文件、本地目录或 S3 前缀

| 数据源 | dataset.source | input_path 示例 | 连接配置 |
| --- | --- | --- | --- |
| 本地 | `local` | `data/vectors.hdf5` 或 `data/` | 无 |
| S3 | `s3` | `s3://bucket/path/vectors.hdf5` 或 `s3://bucket/path/` | [dataset.s3_config](s3.md) |

目录和前缀会递归查找 `.h5` 和 `.hdf5` 文件，按路径排序后逐个读取

## 1.2 按需读取

```python
from contextlib import closing

from dingo.config import InputArgs
from dingo.data import dataset_map, datasource_map

args = InputArgs(input_path="data/vectors.hdf5", dataset={"source": "local", "format": "hdf5"})
source = datasource_map[args.dataset.source](input_args=args)
dataset = dataset_map[args.dataset.source](source=source)

with closing(dataset.get_data()) as records:
    for record in records:
        sample = record.hdf5["vectors"][:5]
        print(sample)
```

`vectors` 是示例数组名，按文件实际内容替换
数组按切片读取；进入下一条记录或关闭迭代器时释放当前文件，需要保留的切片应提前读出
