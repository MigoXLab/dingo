"""Map ANN-Benchmarks HDF5 fields to a Dingo data bundle"""

from dingo.data.converter.base import BaseConverter
from dingo.io import Data


@BaseConverter.register("ann_benchmarks")
class ANNBenchmarksConverter(BaseConverter):
    @classmethod
    def convertor(cls, input_args):
        def convert(raw):
            fields = ("train", "test", "neighbors", "distances")
            missing = [key for key in fields if key not in raw]
            if missing:
                raise ValueError(f"Missing ANN-Benchmarks fields: {missing}")
            base, queries, neighbors, distances = (raw[key] for key in fields)
            if any(getattr(array, "ndim", None) != 2 for array in (base, queries, neighbors, distances)):
                raise ValueError("ANN-Benchmarks fields must be two-dimensional arrays")
            if not all(base.shape) or not all(queries.shape) or not all(neighbors.shape):
                raise ValueError("ANN-Benchmarks arrays must be nonempty")
            if base.shape[1] != queries.shape[1]:
                raise ValueError("Base and query dimensions differ")
            if neighbors.shape[0] != queries.shape[0] or distances.shape != neighbors.shape:
                raise ValueError("Query and ground-truth shapes differ")
            if base.dtype.kind not in "fiu" or queries.dtype.kind not in "fiu":
                raise ValueError("Vectors must have numeric dtypes")
            if neighbors.dtype.kind not in "iu" or distances.dtype.kind not in "fiu":
                raise ValueError("Ground truth requires integer IDs and numeric distances")
            dimension = int(raw.attrs.get("dimension", base.shape[1]))
            metric = raw.attrs.get("distance", "")
            if isinstance(metric, bytes):
                metric = metric.decode("utf-8")
            if dimension != base.shape[1] or metric != "euclidean":
                raise ValueError("Expected matching dimension and euclidean distance")
            # 分批检查近邻 ID，行号对应 base 中的向量
            for start in range(0, len(neighbors), 1024):
                batch = neighbors[start:start + 1024]
                if batch.min() < 0 or batch.max() >= len(base):
                    raise ValueError("Neighbor IDs are outside the base array")
            return Data(
                base=base, queries=queries, ground_truth=neighbors, distances=distances,
                metadata={
                    "name": input_args.input_path.strip(),
                    "dimension": dimension, "distance": metric,
                    "path": str(raw.filename),
                },
            )
        return convert
