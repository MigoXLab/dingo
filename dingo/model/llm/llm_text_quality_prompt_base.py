from dingo.model import Model
from dingo.model.llm.base_openai import BaseOpenAI
from dingo.model.prompt.prompt_common import PromptRepeat


@Model.llm_register('LLMTextQualityPromptBase')
class LLMTextQualityPromptBase(BaseOpenAI):
    prompt = PromptRepeat
