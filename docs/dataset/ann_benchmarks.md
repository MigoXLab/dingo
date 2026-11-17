# 一、ANN-Benchmarks 数据加载

## 1.1 加载范围

### 1.1.1 支持的数据集

初期仅支持 `sift-128-euclidean`（SIFT1M，128 维，Euclidean 距离）
本接口提供 ANN 数据集结构加载，经注册的 DataSource → Dataset → Converter
得到一个包含向量、查询、真值和元数据的数据集包

### 1.1.2 安装依赖

```bash
pip install "dingo-python[retrieval]"
```

HDF5 读取使用可选依赖 `h5py>=3.8.0`，在加载 ANN 数据时延迟导入

## 1.2 配置与运行

### 1.2.1 配置字段

| 字段 | 类型 | 默认值 | 使用条件与取值 |
|------|------|--------|----------------|
| `input_path` | str | 需显式设置 | 当前仅 `sift-128-euclidean` |
| `dataset.source` | str | 需显式设置 | `ann_benchmarks` |
| `dataset.format` | str | 需显式设置 | `ann_benchmarks` |
| `dataset.ann_benchmarks_config.cache_dir` | str | `~/.cache/dingo/ann_benchmarks` | 可选下载缓存目录；支持 `~`，相对路径以启动目录为基准 |

```python
from dingo.config import InputArgs
from dingo.data import dataset_map, datasource_map

args = InputArgs(
    input_path="sift-128-euclidean",
    dataset={
        "source": "ann_benchmarks",
        "format": "ann_benchmarks",
        "ann_benchmarks_config": {"cache_dir": "~/.cache/dingo/ann_benchmarks"},
    },
)
source = datasource_map[args.dataset.source](input_args=args)
with dataset_map[args.dataset.source](source=source) as dataset:
    data = next(dataset.get_data())
    print(data.metadata)
    print(data.base.shape, data.queries.shape)
    query_sample = data.queries[:5]
```

首次加载会下载 HDF5 文件，后续使用缓存
`InputArgs.to_dict()` 的安全序列化白名单
包含 `dataset.ann_benchmarks_config.cache_dir`，便于保存配置快照

### 1.2.2 可运行示例

Sciverse 数据加载示例入口为
[load_ann_dataset.py](../../examples/sciverse_benchmark/0-data-loading/load_ann_dataset.py)
从仓库根目录运行：

```bash
python examples/sciverse_benchmark/0-data-loading/load_ann_dataset.py --help
python examples/sciverse_benchmark/0-data-loading/load_ann_dataset.py
python examples/sciverse_benchmark/0-data-loading/load_ann_dataset.py \
    sift-128-euclidean --cache-dir ./ann-cache
```

示例打印元数据、各数组的形状和类型，以及首行的前 10 个值

## 1.3 数据结构与生命周期

### 1.3.1 数据集包

| 字段 | SIFT1M 形状 | 含义 |
|------|------------|------|
| `base` | `(1000000, 128)` | 数据库向量，对应 HDF5 `train` |
| `queries` | `(10000, 128)` | 查询向量，对应 HDF5 `test` |
| `ground_truth` | `(10000, 100)` | 对应 HDF5 `neighbors`，值为从 0 开始的 base 行索引 |
| `distances` | `(10000, 100)` | 真值邻居距离 |
| `metadata` | dict | `name`、`dimension`、`distance`、`path` |

### 1.3.2 按需切片

四个数组保留为可切片的 HDF5 数据集，加载时不会把完整数组复制到内存
在 Dataset 的 `with` 上下文内访问数组；退出上下文后文件关闭，原数组句柄不可继续读取
需要在上下文外使用的数据应在上下文内切片，例如 `query_sample = data.queries[:5]`
