import json
from functools import reduce, wraps
from typing import Callable, Dict, List, Protocol, Union

from dingo.config import InputArgs
from dingo.data.converter.img_utils import find_s3_image
from dingo.io import Data


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
        res = reduce(lambda x, y: x[y], levels.split("."), data)
        return str(res)

    @classmethod
    def find_levels_image(cls, data: json, levels: str) -> List:
        res = reduce(lambda x, y: x[y], levels.split("."), data)
        return res if isinstance(res, List) else [res]


# @BaseConverter.register("chatml-jsonl")
# class ChatMLConvertor(BaseConverter):
#     """Ddm chatml file converter."""
#
#     def __init__(self):
#         super().__init__()
#
#     @classmethod
#     def convertor(cls, input_args: InputArgs) -> Callable:
#         def _convert(raw: Union[str, Dict]):
#             j = raw
#             if isinstance(raw, str):
#                 j = json.loads(raw)
#
#             dialogs: list = j["dialogs"]
#             prompt = ""
#             content = ""
#
#             for i in dialogs[:-1]:
#                 prompt += f"{i['role']:}\n\n"
#                 prompt += f"{i['content']}\n\n"
#
#             if len(dialogs) > 1:
#                 prompt += dialogs[-1]["role"]
#                 content += dialogs[-1]["content"]
#
#             return Data(
#                 **{
#                     "data_id": j["_id"],
#                     "prompt": prompt,
#                     "content": content,
#                     "raw_data": j,
#                 }
#             )
#
#         return _convert


@BaseConverter.register("multi_turn_dialog")
class MultiTurnDialogConverter(BaseConverter):
    """Unified multi-turn dialog converter for datasets like MT-Bench101 and
    MT-Bench.

    Reads field configuration from EvalPipline.fields:
    - fields["content"] specifies which raw field contains the dialog (e.g., "history")
    - fields["id"] specifies which raw field contains the ID (e.g., "id")

    Falls back to auto-detection if fields not configured.

    Supported dialog formats:
    - MT-Bench101: [{"user": "...", "bot": "..."}]
    - MT-Bench/OpenAI: [{"role": "user/assistant", "content": "..."}]

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

            # 1. Get field configuration from EvalPipline.fields
            content_field = None
            if input_args.evaluator:
                fields = input_args.evaluator[0].fields
                content_field = fields.get("content")

            # 2. Fallback to auto-detection if not configured
            if not content_field:
                for field_name in ["history", "conversation_a", "conversation_b", "conversations", "messages"]:
                    if field_name in j and isinstance(j[field_name], list):
                        content_field = field_name
                        break

            if not content_field:
                raise ValueError(
                    "Cannot find multi-turn dialog field. "
                    "Please configure 'content' in evaluator.fields or ensure data has one of: "
                    "history, conversation_a, conversation_b, conversations, messages"
                )

            if content_field not in j:
                raise ValueError(
                    f"Configured dialog field '{content_field}' not found in data. "
                    f"Available fields: {list(j.keys())}"
                )

            raw_history = j.get(content_field, [])
            if not isinstance(raw_history, list):
                raise ValueError(
                    f"Dialog field '{content_field}' must be a list, got {type(raw_history).__name__}"
                )

            # 3. Detect format and normalize to user/bot structure
            if not raw_history:
                raise ValueError("Empty dialog history.")

            keys = list({key for d in raw_history for key in d.keys()})

            if "user" in keys and "bot" in keys:
                # MT-Bench101 format: [{"user": "...", "bot": "..."}]
                history = raw_history
            elif "content" in keys and "role" in keys:
                # MT-Bench/OpenAI format: [{"role": "user/assistant", "content": "..."}]
                history = []
                for turn in raw_history:
                    if turn.get("role") == "assistant":
                        history.append({"bot": turn.get("content", "")})
                    else:
                        history.append({"user": turn.get("content", "")})
            else:
                raise ValueError(
                    f"Unsupported dialog format. Keys found: {keys}. "
                    "Expected 'user'/'bot' or 'role'/'content'."
                )

            # 4. Transform based on mode
            multi_turn_mode = input_args.executor.multi_turn_mode

            if multi_turn_mode == "all":
                # Concatenate all turns into single content string
                content_str = ""
                for i, turn in enumerate(history):
                    if i > 0:
                        content_str += "\n\n"
                    content_str += f"user: {turn.get('user', '')}"
                    content_str += f"\n\nassistant: {turn.get('bot', '')}"

                data_dict = {
                    "origin": j,
                    content_field: content_str,
                }
                yield Data(**data_dict)
            else:
                raise ValueError(f"Unsupported multi_turn_mode: {multi_turn_mode}")

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
                # if input_args.dataset.fields:
                #     data_dict = {field: cls.find_levels_data(v, field) for field in input_args.dataset.fields}
                # else:
                #     data_dict = v
                data_dict = v
                yield Data(**data_dict)

        return _convert


@BaseConverter.register("plaintext")
class PlainConverter(BaseConverter):
    """Plain text file converter."""
    def __init__(self):
        super().__init__()

    @classmethod
    def convertor(cls, input_args: InputArgs) -> Callable:
        def _convert(raw: Union[str, Dict]):
            if isinstance(raw, Dict):
                raw = json.dumps(raw)
            # 去除字符串末尾的换行符
            if isinstance(raw, str):
                raw = raw.rstrip('\n')
            data_dict = {"content": raw}
            return Data(**data_dict)

        return _convert


@BaseConverter.register("jsonl")
class JsonLineConverter(BaseConverter):
    """Json line file converter."""

    def __init__(self):
        super().__init__()

    @classmethod
    def convertor(cls, input_args: InputArgs) -> Callable:
        def _convert(raw: Union[str, Dict]):
            j = raw
            if isinstance(raw, str):
                j = json.loads(raw)
            # if input_args.dataset.fields:
            #     data_dict = {field: cls.find_levels_data(j, field) for field in input_args.dataset.fields}
            # else:
            #     data_dict = j
            data_dict = j
            return Data(**data_dict)

        return _convert


@BaseConverter.register("excel")
class ExcelConverter(BaseConverter):
    """Excel file converter."""

    def __init__(self):
        super().__init__()

    @classmethod
    def convertor(cls, input_args: InputArgs) -> Callable:
        def _convert(raw: Union[str, Dict]):
            j = raw
            if isinstance(raw, str):
                j = json.loads(raw)
            data_dict = j
            return Data(**data_dict)

        return _convert


@BaseConverter.register("csv")
class CsvConverter(BaseConverter):
    """CSV file converter."""

    def __init__(self):
        super().__init__()

    @classmethod
    def convertor(cls, input_args: InputArgs) -> Callable:
        def _convert(raw: Union[str, Dict]):
            j = raw
            if isinstance(raw, str):
                j = json.loads(raw)
            data_dict = j
            return Data(**data_dict)

        return _convert


@BaseConverter.register("parquet")
class ParquetConverter(BaseConverter):
    """Parquet file converter."""

    def __init__(self):
        super().__init__()

    @classmethod
    def convertor(cls, input_args: InputArgs) -> Callable:
        def _convert(raw: Union[str, Dict]):
            j = raw
            if isinstance(raw, str):
                j = json.loads(raw)
            data_dict = j
            return Data(**data_dict)

        return _convert


@BaseConverter.register("listjson")
class ListJsonConverter(BaseConverter):
    """List json file converter."""

    def __init__(self):
        super().__init__()

    @classmethod
    def convertor(cls, input_args: InputArgs) -> Callable:
        def _convert(raw: Union[str, Dict]):
            l_j = raw
            if isinstance(raw, str):
                l_j = json.loads(raw)
            for j in l_j:
                # if input_args.dataset.fields:
                #     data_dict = {field: cls.find_levels_data(j, field) for field in input_args.dataset.fields}
                # else:
                #     data_dict = j
                data_dict = j
                yield Data(**data_dict)

        return _convert


@BaseConverter.register("image")
class ImageConverter(BaseConverter):
    """Image converter."""

    def __init__(self):
        super().__init__()

    @classmethod
    def convertor(cls, input_args: InputArgs) -> Callable:
        def _convert(raw: Union[str, Dict]):
            j = raw
            if isinstance(raw, str):
                j = json.loads(raw)
            # if input_args.dataset.fields:
            #     data_dict = {field: cls.find_levels_data(j, field) for field in input_args.dataset.fields}
            # else:
            #     data_dict = j
            data_dict = j
            return Data(**data_dict)

        return _convert


# @BaseConverter.register("s3_image")
# class S3ImageConverter(BaseConverter):
#     """S3 Image converter."""
#
#     data_id = 0
#
#     def __init__(self):
#         super().__init__()
#
#     @classmethod
#     def convertor(cls, input_args: InputArgs) -> Callable:
#         def _convert(raw: Union[str, Dict]):
#             j = raw
#             if isinstance(raw, str):
#                 j = json.loads(raw)
#             cls.data_id += 1
#             return Data(
#                 **{
#                     "data_id": (
#                         cls.find_levels_data(j, input_args.dataset.field.id)
#                         if input_args.dataset.field.id != ""
#                         else str(cls.data_id)
#                     ),
#                     "prompt": (
#                         cls.find_levels_data(j, input_args.dataset.field.prompt)
#                         if input_args.dataset.field.prompt != ""
#                         else ""
#                     ),
#                     "content": (
#                         cls.find_levels_data(j, input_args.dataset.field.content)
#                         if input_args.dataset.field.content != ""
#                         else ""
#                     ),
#                     "image": find_s3_image(j, input_args)
#                     if input_args.dataset.field.image != ""
#                     else "",
#                     "raw_data": j,
#                 }
#             )
#
#         return _convert
