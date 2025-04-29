from dingo.model import Model
from dingo.model.llm.llm_text_3h import LlmText3H
from dingo.model.prompt.prompt_text_3h import PromptTextHelpful

@Model.llm_register('LlmText3hHelpful')
class LlmText3hHelpful(LlmText3H):
    prompt = PromptTextHelpful
