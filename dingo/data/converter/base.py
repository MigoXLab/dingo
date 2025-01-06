import json
from functools import reduce, wraps
from typing import Callable, Dict, List, Protocol, Union

from dingo.data.converter.img_utils import find_s3_image
from dingo.io import InputArgs, MetaData


class ConverterProto(Protocol):
    @classmethod
    def convertor(cls, input_args: InputArgs) -> Callable:
        ...


class BaseConverter(ConverterProto):
    converters = {}

    def __init__(self):
        pass

    @classmethod
    def convertor(cls, input_args: InputArgs) -> Callable:
        raise NotImplementedError()

    @classmethod
    def register(cls, type_name: str):
        def decorator(root_class):
            cls.converters[type_name] = root_class

            @wraps(root_class)
            def wrapped_function(*args, **kwargs):
                return root_class(*args, **kwargs)

            return wrapped_function

        return decorator

    @classmethod
    def find_levels_data(cls, data: json, levels: str) -> str:
        res = reduce(lambda x, y: x[y], levels.split('.'), data)
        return str(res)

    @classmethod
    def find_levels_image(cls, data: json, levels: str) -> List:
        res = reduce(lambda x, y: x[y], levels.split('.'), data)
        return res if isinstance(res, List) else [res]

@BaseConverter.register("chatml-jsonl")
class ChatMLConvertor(BaseConverter):
    """
    ddm chatml file converter.
    """

    def __init__(self):
        super().__init__()

    @classmethod
    def convertor(cls, input_args: InputArgs) -> Callable:
        def _convert(raw: Union[str, Dict]):
            j = raw
            if isinstance(raw, str):
                j = json.loads(raw)

            dialogs: list = j["dialogs"]
            prompt = ""
            content = ""

            for i in dialogs[:-1]:
                prompt += f"{i['role']:}\n\n"
                prompt += f"{i['content']}\n\n"

            if len(dialogs) > 1:
                prompt += dialogs[-1]["role"]
                content += dialogs[-1]["content"]

            return MetaData(**{
                'data_id': j["_id"],
                'prompt': prompt,
                'content': content,
                'raw_data': j
            })

        return _convert


@BaseConverter.register('json')
class JsonConverter(BaseConverter):
    """
    Json file converter.
    """

    def __init__(self):
        super().__init__()

    @classmethod
    def convertor(cls, input_args: InputArgs) -> Callable:
        def _convert(raw: Union[str, Dict]):
            j = raw
            if isinstance(raw, str):
                j = json.loads(raw)
            for k, v in j.items():
                yield MetaData(**{
                    'data_id': cls.find_levels_data(v, input_args.column_id) if input_args.column_id != '' else str(k),
                    'prompt': cls.find_levels_data(v, input_args.column_prompt) if input_args.column_prompt != '' else '',
                    'content': cls.find_levels_data(v, input_args.column_content) if input_args.column_content != '' else '',
                    'raw_data': v
                })

        return _convert


@BaseConverter.register('plaintext')
class PlainConverter(BaseConverter):
    """
    Plain text file converter
    """
    data_id = 0

    def __init__(self):
        super().__init__()

    @classmethod
    def convertor(cls, input_args: InputArgs) -> Callable:
        def _convert(raw: Union[str, Dict]):
            if isinstance(raw, Dict):
                raw = json.dumps(raw)
            data = MetaData(**{
                'data_id': str(cls.data_id),
                'prompt': '',
                'content': raw,
                'raw_data': {'content': raw}
            })
            cls.data_id += 1
            return data

        return _convert


@BaseConverter.register('jsonl')
class JsonLineConverter(BaseConverter):
    """
    Json line file converter.
    """
    data_id = 0

    def __init__(self):
        super().__init__()

    @classmethod
    def convertor(cls, input_args: InputArgs) -> Callable:
        def _convert(raw: Union[str, Dict]):
            j = raw
            if isinstance(raw, str):
                j = json.loads(raw)
            cls.data_id += 1
            return MetaData(**{
                'data_id': cls.find_levels_data(j, input_args.column_id) if input_args.column_id != '' else str(cls.data_id),
                'prompt': cls.find_levels_data(j, input_args.column_prompt) if input_args.column_prompt != '' else '',
                'content': cls.find_levels_data(j, input_args.column_content) if input_args.column_content != '' else '',
                'raw_data': j
            })

        return _convert


@BaseConverter.register('listjson')
class ListJsonConverter(BaseConverter):
    """
    List json file converter.
    """

    data_id = 0

    def __init__(self):
        super().__init__()

    @classmethod
    def convertor(cls, input_args: InputArgs) -> Callable:
        def _convert(raw: Union[str, Dict]):
            l_j = raw
            if isinstance(raw, str):
                l_j = json.loads(raw)
            for j in l_j:
                yield MetaData(**{
                    'data_id': cls.find_levels_data(j, input_args.column_id) if input_args.column_id != '' else str(cls.data_id),
                    'prompt': cls.find_levels_data(j, input_args.column_prompt) if input_args.column_prompt != '' else '',
                    'content': cls.find_levels_data(j, input_args.column_content) if input_args.column_content != '' else '',
                    'raw_data': j
                })
                cls.data_id += 1

        return _convert


@BaseConverter.register('image')
class ImageConverter(BaseConverter):
    """
    Image converter.
    """

    data_id = 0

    def __init__(self):
        super().__init__()

    @classmethod
    def convertor(cls, input_args: InputArgs) -> Callable:
        def _convert(raw: Union[str, Dict]):
            j = raw
            if isinstance(raw, str):
                j = json.loads(raw)
            cls.data_id += 1
            return MetaData(**{
                'data_id': cls.find_levels_data(j, input_args.column_id) if input_args.column_id != '' else str(cls.data_id),
                'prompt': cls.find_levels_data(j, input_args.column_prompt) if input_args.column_prompt != '' else '',
                'content': cls.find_levels_data(j, input_args.column_content) if input_args.column_content != '' else '',
                'image': cls.find_levels_image(j, input_args.column_image) if input_args.column_image != '' else '',
                'raw_data': j
            })

        return _convert


@BaseConverter.register('s3_image')
class S3ImageConverter(BaseConverter):
    """
    S3 Image converter.
    """

    data_id = 0

    def __init__(self):
        super().__init__()

    @classmethod
    def convertor(cls, input_args: InputArgs) -> Callable:
        def _convert(raw: Union[str, Dict]):
            j = raw
            if isinstance(raw, str):
                j = json.loads(raw)
            cls.data_id += 1
            return MetaData(**{
                'data_id': cls.find_levels_data(j, input_args.column_id) if input_args.column_id != '' else str(cls.data_id),
                'prompt': cls.find_levels_data(j, input_args.column_prompt) if input_args.column_prompt != '' else '',
                'content': cls.find_levels_data(j, input_args.column_content) if input_args.column_content != '' else '',
                'image': find_s3_image(j, input_args) if input_args.column_image != '' else '',
                'raw_data': j
            })

        return _convert
