"""Bundled retrieval evaluation datasets."""

import re
from pathlib import Path

_TASK_NAME = re.compile(r"^[A-Za-z0-9_-]+$")


def resolve_builtin_task(task_name: str) -> Path | None:
    """Resolve a task name to a bundled JSON dataset, if one exists."""
    if not _TASK_NAME.fullmatch(task_name):
        return None
    path = Path(__file__).with_name(f"{task_name}.json")
    return path if path.is_file() else None
