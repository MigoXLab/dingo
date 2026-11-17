"""Download and open ANN-Benchmarks preprocessed HDF5 datasets"""

import shutil
import tempfile
from pathlib import Path
from urllib.request import Request, urlopen

from dingo.data.datasource.base import DataSource


@DataSource.register()
class ANNBenchmarksDataSource(DataSource):
    URLS = {
        "sift-128-euclidean": "https://ann-benchmarks.com/sift-128-euclidean.hdf5",
    }

    def __init__(self, input_args):
        super().__init__(input_args)
        self.name = input_args.input_path.strip()
        if self.name not in self.URLS:
            raise ValueError(f"Unsupported ANN-Benchmarks dataset: {self.name}")
        self.cache_dir = Path(input_args.dataset.ann_benchmarks_config.cache_dir).expanduser()
        self.path = self.cache_dir / f"{self.name}.hdf5"

    @staticmethod
    def get_source_type():
        return "ann_benchmarks"

    def load(self):
        # 使用时导入 HDF5 依赖
        try:
            import h5py
        except ImportError as exc:
            raise ImportError(
                'ANN-Benchmarks loading requires pip install "dingo-python[retrieval]"'
            ) from exc
        if not self.path.exists():
            self._download(h5py)
        try:
            return h5py.File(self.path, "r")
        except OSError as exc:
            raise ValueError(f"Invalid HDF5 cache: {self.path}") from exc

    def _download(self, h5py):
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        url = self.URLS[self.name]
        request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        partial = None
        try:
            # 临时文件校验通过后再成为正式缓存
            with tempfile.NamedTemporaryFile(
                dir=self.cache_dir, suffix=".part", delete=False,
            ) as output:
                partial = Path(output.name)
                with urlopen(request, timeout=60) as response:
                    shutil.copyfileobj(response, output)
            with h5py.File(partial, "r") as data:
                required = {"train", "test", "neighbors", "distances"}
                if not required.issubset(data.keys()):
                    raise ValueError("Downloaded HDF5 is missing required fields")
            partial.replace(self.path)
        finally:
            if partial is not None:
                partial.unlink(missing_ok=True)

    def to_dict(self):
        return {"name": self.name, "path": str(self.path), "url": self.URLS[self.name]}
