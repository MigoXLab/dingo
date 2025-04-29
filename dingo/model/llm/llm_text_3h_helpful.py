from dingo.model import Model
from dingo.model.llm.llm_text_3h import LLMText3H
from dingo.model.prompt.prompt_text_3h import PromptTextHelpful


@Model.llm_register('LLMText3HHelpful')
class LLMText3HHelpful(LLMText3H):
    prompt = PromptTextHelpful
