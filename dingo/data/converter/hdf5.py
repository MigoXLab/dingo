from typing import BinaryIO, Callable, Generator

from dingo.config import InputArgs
from dingo.data.converter.base import BaseConverter
from dingo.io import Data


@BaseConverter.register("hdf5")
class HDF5Converter(BaseConverter):
    @classmethod
    def convertor(cls, input_args: InputArgs) -> Callable:
        def convert(open_input: Callable[[], BinaryIO]) -> Generator[Data, None, None]:
            try:
                import h5py
            except ImportError as exc:
                raise ImportError(
                    'HDF5 loading requires pip install "dingo-python[retrieval]"'
                ) from exc

            with open_input() as stream, h5py.File(stream, "r") as hdf5:
                yield Data(hdf5=hdf5)

        return convert
