from dingo.model import Model
from dingo.model.llm.llm_text_3h import LlmText3H
from dingo.model.prompt.prompt_text_3h import PromptTextHonest

@Model.llm_register('LlmText3hHonest')
class LlmText3hHonest(LlmText3H):
    prompt = PromptTextHonest
