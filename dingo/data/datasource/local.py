import os
from typing import Any, Dict, Generator, List, Optional

from dingo.config import InputArgs
from dingo.data.datasource.base import DataSource


def find_all_files(path: str, file_list: List[str]):
    """
    Find all files in path recursively.
    Args:
        path (str): The path to find all files in.
        file_list (List[str]): The list of files to find.
    """
    for _f in os.listdir(path):
        f = os.path.join(path, _f)
        if os.path.isfile(f):
            file_list.append(f)
        if os.path.isdir(f):
            find_all_files(f, file_list)


def load_local_file(path: str, by_line: bool = True) -> Generator[str, None, None]:
    """
    Load a local file and return its contents.
    Args:
        path (str): The path to load.
        by_line (bool): If True, return content of the file by lines.

    Returns:
        str: The contents of the file.
    """
    import gzip

    if not os.path.exists(path):
        raise RuntimeError(f'"{path}" is not a valid path')
    f_list = []
    if os.path.exists(path) and os.path.isfile(path):
        f_list = [path]
    elif os.path.exists(path) and os.path.isdir(path):
        find_all_files(path, f_list)

    for f in f_list:
        # Check if file is gzipped
        if f.endswith('.gz'):
            try:
                with gzip.open(f, 'rt', encoding='utf-8') as _f:
                    if by_line:
                        for line in _f.readlines():
                            yield line
                    else:
                        yield _f.read()
            except Exception as gz_error:
                raise RuntimeError(
                    f'Failed to read gzipped file "{f}": {str(gz_error)}. '
                    f'Please ensure the file is a valid gzip-compressed text file.'
                )
        else:
            # For regular files, try UTF-8 encoding
            try:
                with open(f, "r", encoding="utf-8") as _f:
                    if by_line:
                        for line in _f.readlines():
                            yield line
                    else:
                        yield _f.read()
            except UnicodeDecodeError as decode_error:
                raise RuntimeError(
                    f'Failed to read file "{f}": Unsupported file format or encoding. '
                    f'Dingo only supports UTF-8 text files (.jsonl, .json, .txt) and .gz compressed text files. '
                    f'Original error: {str(decode_error)}'
                )
            except Exception as e:
                raise RuntimeError(
                    f'Unexpected error reading file "{f}": {str(e)}. '
                    f'Please check if the file exists and is readable.'
                )


@DataSource.register()
class LocalDataSource(DataSource):
    def __init__(
        self,
        input_args: InputArgs = None,
        config_name: Optional[str] = None,
    ):
        """Create a `LocalDataSource` instance.
        Args:
            input_args: A `InputArgs` instance to load the dataset from.
            config_name: The name of the Hugging Face dataset configuration.
        """
        self.path = input_args.input_path
        self.config_name = config_name
        super().__init__(input_args=input_args)

    @staticmethod
    def get_source_type() -> str:
        return "local"

    def load(self, **kwargs) -> Generator[str, None, None]:
        """Load the local file dataset based on `LocalDataSource`.
        Args:
            kwargs: Additional keyword arguments used for loading the dataset.
        Returns:
            An instance of `Iterable`.
        """
        load_kwargs = {
            "path": self.path,
        }
        if self.input_args.dataset.format in ["json", "listjson"]:
            load_kwargs["by_line"] = False
        return load_local_file(**load_kwargs)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "config_name": self.config_name,
        }
