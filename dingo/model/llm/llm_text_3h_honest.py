from dingo.model import Model
from dingo.model.llm.llm_text_3h import LLMText3H
from dingo.model.prompt.prompt_text_3h import PromptTextHonest


@Model.llm_register('LLMText3HHonest')
class LLMText3HHonest(LLMText3H):
    prompt = PromptTextHonest
