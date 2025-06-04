from typing import Protocol

from dingo.io import Data
from dingo.model.modelres import ModelRes
from dingo.model.prompt.base import BasePrompt


class BaseLLM(Protocol):
    @classmethod
    def set_prompt(cls, prompt: BasePrompt): ...

    @classmethod
    def eval(cls, input_data: Data) -> ModelRes: ...
