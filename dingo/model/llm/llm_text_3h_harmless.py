from dingo.model import Model
from dingo.model.llm.llm_text_3h import LlmText3H
from dingo.model.prompt.prompt_text_3h import PromptTextHarmless

@Model.llm_register('LlmText3hHarmless')
class LlmText3hHarmless(LlmText3H):
    prompt = PromptTextHarmless
