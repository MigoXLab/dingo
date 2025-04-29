from dingo.model import Model
from dingo.model.llm.llm_security import LlmSecurity
from dingo.model.prompt.prompt_prohibition import PromptProhibition


@Model.llm_register('LlmSecurityProhibition')
class LlmSecurityProhibition(LlmSecurity):
    prompt = PromptProhibition
