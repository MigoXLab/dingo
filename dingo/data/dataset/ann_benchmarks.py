"""Context-managed ANN dataset with HDF5-backed arrays"""

import hashlib
import json

from dingo.data.dataset.base import Dataset


@Dataset.register()
class ANNBenchmarksDataset(Dataset):
    def __init__(self, source, name=None, digest=None):
        super().__init__(source=source, name=name, digest=digest)
        self._file = None
        self._active = False

    @staticmethod
    def get_dataset_type():
        return "ann_benchmarks"

    def _compute_digest(self):
        config = json.dumps(self.source.to_dict(), sort_keys=True)
        return hashlib.sha256(config.encode()).hexdigest()[:8]

    @property
    def profile(self):
        return self.source.to_dict()

    def to_dict(self):
        result = super().to_dict()
        result["profile"] = json.dumps(self.profile)
        return result

    def __enter__(self):
        if self._active:
            raise RuntimeError("ANN dataset context is already active")
        self._active = True
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def close(self):
        if self._file is not None:
            self._file.close()
            self._file = None
        self._active = False

    def get_data(self):
        # HDF5 数组在 with 作用域内有效，按切片读取数据
        if not self._active:
            raise RuntimeError("Use ANNBenchmarksDataset inside a with block")
        try:
            if self._file is None:
                self._file = self.source.load()
            data = self.converter(self._file)
        except Exception:
            self.close()
            raise
        yield data
