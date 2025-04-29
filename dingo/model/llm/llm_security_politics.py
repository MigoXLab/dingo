from dingo.model import Model
from dingo.model.llm.llm_security import LlmSecurity
from dingo.model.prompt.prompt_politics import PromptPolitics


@Model.llm_register('LlmSecurityPolitics')
class LlmSecurityPolitics(LlmSecurity):
    prompt = PromptPolitics
