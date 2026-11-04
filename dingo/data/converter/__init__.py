import dingo.data.converter.mineru  # noqa: F401  — registers mineru / mineru_v2
import dingo.data.converter.ms_swift  # noqa: F401 — registers ms_swift
import dingo.data.converter.repository_code_jsonl  # noqa: F401 — registers repository_code_jsonl
from dingo.data.converter.base import BaseConverter

converters = BaseConverter.converters
