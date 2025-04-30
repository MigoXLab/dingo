from dingo.model import Model
from dingo.model.llm.llm_text_3h import LLMText3H
from dingo.model.prompt.prompt_text_3h import PromptTextHarmless


@Model.llm_register('LLMText3HHarmless')
class LLMText3HHarmless(LLMText3H):
    prompt = PromptTextHarmless
