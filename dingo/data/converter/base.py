import json
from functools import reduce, wraps
from typing import Callable, Dict, List, Protocol, Union

from dingo.data.converter.img_utils import find_s3_image
from dingo.io import Data, InputArgs


class ConverterProto(Protocol):
    @classmethod
    def convertor(cls, input_args: InputArgs) -> Callable: ...


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
        res = reduce(lambda x, y: x[y], levels.split("."), data)
        return str(res)

    @classmethod
    def find_levels_image(cls, data: json, levels: str) -> List:
        res = reduce(lambda x, y: x[y], levels.split("."), data)
        return res if isinstance(res, List) else [res]


@BaseConverter.register("chatml-jsonl")
class ChatMLConvertor(BaseConverter):
    """Ddm chatml file converter."""

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

            return Data(**{"data_id": j["_id"], "prompt": prompt, "content": content, "raw_data": j})

        return _convert


@BaseConverter.register("multi_turn_dialog")
class MultiTurnDialogConverter(BaseConverter):
    """Unified multi-turn dialog converter for datasets like MT-Bench101 and
    MT-Bench.

    Current supported mode: 'all'.
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

            raw_history: list = (
                j.get(input_args.column_content, []) if input_args.column_content != "" else j.get("history", [])
            )
            keys = list({key for d in raw_history for key in d.keys()})

            # get multi-turn dialogues base on the format of the input data
            if "user" in keys and "bot" in keys:
                # MT-Bench101 format
                history = raw_history
            elif "content" in keys and "role" in keys:
                history = []
                # MT-Bench format
                for turn in raw_history:
                    if turn.get("role") == "assistant":
                        history.append({"bot": turn.get("content")})
                    else:
                        history.append({"user": turn.get("content")})
            else:
                raise ValueError(
                    "The provided data does not conform to the multi-turn dialogue format. Please check the corresponding field."
                )

            if not history:
                # if not multi-turn dialogues, raise error
                raise ValueError(
                    "The provided data does not conform to the multi-turn dialogue format. Please check the corresponding field."
                )

            # process each turn of dialogue based on mode
            if input_args.custom_config and input_args.custom_config.get("multi_turn_mode") == "all":
                content = ""
                for i, turn in enumerate(history):
                    if i > 0:
                        content += "\n\n"
                    content += f"user: {turn.get('user', '')}"
                    content += f"\n\nassistant: {turn.get('bot', '')}"
                yield Data(
                    **{
                        "data_id": (
                            cls.find_levels_data(j, input_args.column_id)
                            if input_args.column_id != ""
                            else str(cls.data_id)
                        ),
                        "prompt": "",
                        "content": content,
                        "raw_data": j,
                    }
                )

        return _convert


@BaseConverter.register("json")
class JsonConverter(BaseConverter):
    """Json file converter."""

    def __init__(self):
        super().__init__()

    @classmethod
    def convertor(cls, input_args: InputArgs) -> Callable:
        def _convert(raw: Union[str, Dict]):
            j = raw
            if isinstance(raw, str):
                j = json.loads(raw)
            for k, v in j.items():
                yield Data(
                    **{
                        "data_id": (
                            cls.find_levels_data(v, input_args.column_id) if input_args.column_id != "" else str(k)
                        ),
                        "prompt": (
                            cls.find_levels_data(v, input_args.column_prompt) if input_args.column_prompt != "" else ""
                        ),
                        "content": (
                            cls.find_levels_data(v, input_args.column_content)
                            if input_args.column_content != ""
                            else ""
                        ),
                        "raw_data": v,
                    }
                )

        return _convert


@BaseConverter.register("plaintext")
class PlainConverter(BaseConverter):
    """Plain text file converter."""

    data_id = 0

    def __init__(self):
        super().__init__()

    @classmethod
    def convertor(cls, input_args: InputArgs) -> Callable:
        def _convert(raw: Union[str, Dict]):
            if isinstance(raw, Dict):
                raw = json.dumps(raw)
            data = Data(**{"data_id": str(cls.data_id), "prompt": "", "content": raw, "raw_data": {"content": raw}})
            cls.data_id += 1
            return data

        return _convert


@BaseConverter.register("jsonl")
class JsonLineConverter(BaseConverter):
    """Json line file converter."""

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
            return Data(
                **{
                    "data_id": (
                        cls.find_levels_data(j, input_args.column_id)
                        if input_args.column_id != ""
                        else str(cls.data_id)
                    ),
                    "prompt": (
                        cls.find_levels_data(j, input_args.column_prompt) if input_args.column_prompt != "" else ""
                    ),
                    "content": (
                        cls.find_levels_data(j, input_args.column_content) if input_args.column_content != "" else ""
                    ),
                    "raw_data": j,
                }
            )

        return _convert


@BaseConverter.register("listjson")
class ListJsonConverter(BaseConverter):
    """List json file converter."""

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
                yield Data(
                    **{
                        "data_id": (
                            cls.find_levels_data(j, input_args.column_id)
                            if input_args.column_id != ""
                            else str(cls.data_id)
                        ),
                        "prompt": (
                            cls.find_levels_data(j, input_args.column_prompt) if input_args.column_prompt != "" else ""
                        ),
                        "content": (
                            cls.find_levels_data(j, input_args.column_content)
                            if input_args.column_content != ""
                            else ""
                        ),
                        "raw_data": j,
                    }
                )
                cls.data_id += 1

        return _convert


@BaseConverter.register("image")
class ImageConverter(BaseConverter):
    """Image converter."""

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
            return Data(
                **{
                    "data_id": (
                        cls.find_levels_data(j, input_args.column_id)
                        if input_args.column_id != ""
                        else str(cls.data_id)
                    ),
                    "prompt": (
                        cls.find_levels_data(j, input_args.column_prompt) if input_args.column_prompt != "" else ""
                    ),
                    "content": (
                        cls.find_levels_data(j, input_args.column_content) if input_args.column_content != "" else ""
                    ),
                    "image": cls.find_levels_image(j, input_args.column_image) if input_args.column_image != "" else "",
                    "raw_data": j,
                }
            )

        return _convert


@BaseConverter.register("s3_image")
class S3ImageConverter(BaseConverter):
    """S3 Image converter."""

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
            return Data(
                **{
                    "data_id": (
                        cls.find_levels_data(j, input_args.column_id)
                        if input_args.column_id != ""
                        else str(cls.data_id)
                    ),
                    "prompt": (
                        cls.find_levels_data(j, input_args.column_prompt) if input_args.column_prompt != "" else ""
                    ),
                    "content": (
                        cls.find_levels_data(j, input_args.column_content) if input_args.column_content != "" else ""
                    ),
                    "image": find_s3_image(j, input_args) if input_args.column_image != "" else "",
                    "raw_data": j,
                }
            )

        return _convert
