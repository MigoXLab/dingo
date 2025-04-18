import inspect
from abc import ABC, abstractmethod
from functools import wraps
from typing import Any, Dict, List, Protocol, Type, Union

from dingo.io import MetaData, SummaryModel


class ExecProto(Protocol):
    def load_data(self) -> Any:
        ...

    def execute(self) -> SummaryModel:
        ...

    def evaluate(self):
        ...

    def summarize(self, summary: SummaryModel) -> SummaryModel:
        ...


class Executor:
    exec_map: Dict[str, Type[ExecProto]] = {}

    @classmethod
    def register(cls, exec_name: str):

        def decorator(root_exec):
            cls.exec_map[exec_name] = root_exec

            if inspect.isclass(root_exec):
                return root_exec
            else:
                raise ValueError("root_exec must be a class")

        return decorator
