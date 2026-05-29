"""MinerU output format converters.

Supports two MinerU structured output files:
  - ``content_list.json`` (format: ``"mineru"``) — flat array of blocks
  - ``content_list_v2.json`` (format: ``"mineru_v2"``) — pages × blocks
"""

import json
from typing import Callable, Dict, List, Union

from dingo.config import InputArgs
from dingo.data.converter.base import BaseConverter
from dingo.io import Data


def _flatten_spans(spans: List[Dict]) -> str:
    """Concatenate a V2 span list into plain text.

    Spans look like ``[{"type": "text", "content": "..."}, ...]``.
    Hyperlink spans may carry ``children`` with nested text spans;
    when present we use the top-level ``content`` which is already the
    concatenated text.
    """
    parts = []
    for span in spans:
        parts.append(span.get("content", ""))
    return "".join(parts)


def _wrap_image(img_path) -> List[str]:
    """Ensure img_path is a list of strings (Dingo convention)."""
    if not img_path:
        return []
    if isinstance(img_path, list):
        return img_path
    return [img_path]


# ---------------------------------------------------------------------------
# V1: content_list.json
# ---------------------------------------------------------------------------

_V1_TEXT_TYPES = frozenset({
    "text", "equation", "header", "footer",
    "page_number", "aside_text", "page_footnote",
})


def _map_block_v1(block: dict, block_idx: int) -> dict:
    """Map a single content_list.json block to a Data-compatible dict."""
    btype = block.get("type", "")
    page_idx = block.get("page_idx", 0)

    data_dict = dict(block)
    data_dict["data_id"] = f"p{page_idx}-b{block_idx}"

    if btype in _V1_TEXT_TYPES:
        data_dict["content"] = block.get("text", "")

    elif btype == "image":
        data_dict["content"] = ""
        data_dict["image"] = _wrap_image(block.get("img_path"))

    elif btype == "table":
        data_dict["content"] = block.get("table_body", "")
        data_dict["image"] = _wrap_image(block.get("img_path"))

    elif btype == "chart":
        data_dict["content"] = block.get("content", "")
        data_dict["image"] = _wrap_image(block.get("img_path"))

    elif btype == "code":
        data_dict["content"] = block.get("code_body", "")

    elif btype == "list":
        items = block.get("list_items", [])
        data_dict["content"] = "\n".join(items) if items else ""

    else:
        data_dict.setdefault("content", block.get("text", ""))

    if "img_path" in data_dict and "image" not in data_dict:
        img = _wrap_image(data_dict["img_path"])
        if img:
            data_dict["image"] = img

    return data_dict


@BaseConverter.register("mineru")
class MinerUConverter(BaseConverter):
    """Converter for MinerU ``content_list.json`` (flat block array)."""

    def __init__(self):
        super().__init__()

    @classmethod
    def convertor(cls, input_args: InputArgs) -> Callable:
        include = None
        if hasattr(input_args.dataset, "mineru_config"):
            cfg = input_args.dataset.mineru_config
            if cfg.include_types:
                include = frozenset(cfg.include_types)

        def _convert(raw: Union[str, list]):
            blocks = raw
            if isinstance(raw, str):
                blocks = json.loads(raw)
            for block_idx, block in enumerate(blocks):
                if include and block.get("type", "") not in include:
                    continue
                data_dict = _map_block_v1(block, block_idx)
                yield Data(**data_dict)

        return _convert


# ---------------------------------------------------------------------------
# V2: content_list_v2.json
# ---------------------------------------------------------------------------

def _map_block_v2(block: dict, page_idx: int, block_idx: int) -> dict:
    """Map a single content_list_v2.json block to a Data-compatible dict."""
    btype = block.get("type", "")
    inner = block.get("content")

    if not isinstance(inner, dict):
        data_dict = {
            "data_id": f"p{page_idx}-b{block_idx}",
            "type": btype,
            "page_idx": page_idx,
            "content": inner if isinstance(inner, str) else "",
            "raw_content": inner,
        }
        if "bbox" in block:
            data_dict["bbox"] = block["bbox"]
        return data_dict

    data_dict = {
        "data_id": f"p{page_idx}-b{block_idx}",
        "type": btype,
        "page_idx": page_idx,
    }

    if "bbox" in block:
        data_dict["bbox"] = block["bbox"]
    if "anchor" in block:
        data_dict["anchor"] = block["anchor"]
    if "sub_type" in block:
        data_dict["sub_type"] = block["sub_type"]

    if btype == "title":
        spans = inner.get("title_content", [])
        data_dict["content"] = _flatten_spans(spans)
        data_dict["text_level"] = inner.get("level", 0)

    elif btype == "paragraph":
        spans = inner.get("paragraph_content", [])
        data_dict["content"] = _flatten_spans(spans)

    elif btype == "equation_interline":
        data_dict["content"] = inner.get("math_content", "")
        if "math_type" in inner:
            data_dict["math_type"] = inner["math_type"]

    elif btype == "image":
        data_dict["content"] = ""
        data_dict["image"] = _wrap_image(inner.get("img_path"))
        for key in ("image_caption", "image_footnote"):
            if key in inner:
                data_dict[key] = inner[key]

    elif btype == "table":
        data_dict["content"] = inner.get("table_body", "")
        data_dict["image"] = _wrap_image(inner.get("img_path"))
        for key in ("table_caption", "table_footnote"):
            if key in inner:
                data_dict[key] = inner[key]

    elif btype == "chart":
        data_dict["content"] = inner.get("content", "")
        data_dict["image"] = _wrap_image(inner.get("img_path"))
        for key in ("chart_caption", "chart_footnote"):
            if key in inner:
                data_dict[key] = inner[key]

    elif btype == "code":
        data_dict["content"] = inner.get("code_content", "")
        for key in ("code_caption", "code_footnote", "code_language"):
            if key in inner:
                data_dict[key] = inner[key]

    elif btype == "algorithm":
        data_dict["content"] = inner.get("algorithm_content", "")
        for key in ("algorithm_caption", "algorithm_footnote"):
            if key in inner:
                data_dict[key] = inner[key]

    elif btype in ("list", "index"):
        items = inner.get("list_items", [])
        data_dict["content"] = "\n".join(items) if items else ""
        data_dict["list_items"] = items

    else:
        content_key = f"{btype}_content"
        spans = inner.get(content_key, [])
        if isinstance(spans, list) and spans and isinstance(spans[0], dict):
            data_dict["content"] = _flatten_spans(spans)
        elif isinstance(inner, str):
            data_dict["content"] = inner
        else:
            data_dict["content"] = ""

    data_dict["raw_content"] = inner

    return data_dict


@BaseConverter.register("mineru_v2")
class MinerUV2Converter(BaseConverter):
    """Converter for MinerU ``content_list_v2.json`` (pages x blocks)."""

    def __init__(self):
        super().__init__()

    @classmethod
    def convertor(cls, input_args: InputArgs) -> Callable:
        include = None
        if hasattr(input_args.dataset, "mineru_config"):
            cfg = input_args.dataset.mineru_config
            if cfg.include_types:
                include = frozenset(cfg.include_types)

        def _convert(raw: Union[str, list]):
            pages = raw
            if isinstance(raw, str):
                pages = json.loads(raw)
            for page_idx, page_blocks in enumerate(pages):
                for block_idx, block in enumerate(page_blocks):
                    if include and block.get("type", "") not in include:
                        continue
                    data_dict = _map_block_v2(block, page_idx, block_idx)
                    yield Data(**data_dict)

        return _convert
