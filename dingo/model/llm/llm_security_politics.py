from dingo.model import Model
from dingo.model.llm.llm_security import LLMSecurity
from dingo.model.prompt.prompt_politics import PromptPolitics


@Model.llm_register('LLMSecurityPolitics')
class LLMSecurityPolitics(LLMSecurity):
    prompt = PromptPolitics
