from dingo.model import Model
from dingo.model.llm.llm_security import LLMSecurity
from dingo.model.prompt.prompt_prohibition import PromptProhibition


@Model.llm_register('LLMSecurityProhibition')
class LLMSecurityProhibition(LLMSecurity):
    prompt = PromptProhibition
