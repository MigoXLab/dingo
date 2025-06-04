from dingo.model.model import Model
from dingo.model.prompt.base import BasePrompt

AR_LAN_ROLE = """
### Role
You are an Arabic linguistics expert
### Target language
Arabic
"""
CS_LAN_ROLE = """
### Role
You are an Czech linguistics expert
### Target language
Czech
"""
HU_LAN_ROLE = """
### Role
You are an Hungarian linguistics expert
### Target language
Hungarian
"""
KO_LAN_ROLE = """
### Role
You are an Korean linguistics expert
### Target language
Korean
"""
RU_LAN_ROLE = """
### Role
You are an Russian linguistics expert
### Target language
Russian
"""
SR_LAN_ROLE = """
### Role
You are an Serbian linguistics expert
### Target language
Serbian
"""
TH_LAN_ROLE = """
### Role
You are an Thai linguistics expert
### Target language
Thai
"""
VI_LAN_ROLE = """
### Role
You are an Vietnamese linguistics expert
### Target language
Vietnamese
"""

# Contnet Language
TEXT_LANGUAGE = """
### Task
Your task is to identify whether the text contains a large amount of non-target language.
### Level
Level indicates the percentage of target languages.
Target language :More than 50 percent of the text is in target language.
Mixed: Less than 50 percent of the text is in target language. Text is in mixed languages.
Others language: The text does not contain any target language. Please give the language of the text.
### Ignored
Proper nouns can remain in their original language.
Formulas in professional fields such as mathematics, chemistry, and physics are not considered non-target languages.
Codes are not considered non-target languages.
### JSON FORMAT
Please return the results in the format: {"language": level, "percent": tagert language percent, "reason":reason}
### Workflow
1. Read the given text.
2. Sign a level for the text.
4. Return the answer in JSON format.
"""


@Model.prompt_register('TEXT_LANGUAGE_AR', [])
class PromptTextLanguageAr(BasePrompt):
    content = AR_LAN_ROLE + TEXT_LANGUAGE


@Model.prompt_register('TEXT_LANGUAGE_CS', [])
class PromptTextLanguageCs(BasePrompt):
    content = CS_LAN_ROLE + TEXT_LANGUAGE


@Model.prompt_register('TEXT_LANGUAGE_HU', [])
class PromptTextLanguageHu(BasePrompt):
    content = HU_LAN_ROLE + TEXT_LANGUAGE


@Model.prompt_register('TEXT_LANGUAGE_KO', [])
class PromptTextLanguageKo(BasePrompt):
    content = KO_LAN_ROLE + TEXT_LANGUAGE


@Model.prompt_register('TEXT_LANGUAGE_RU', [])
class PromptTextLanguageRu(BasePrompt):
    content = RU_LAN_ROLE + TEXT_LANGUAGE


@Model.prompt_register('TEXT_LANGUAGE_SR', [])
class PromptTextLanguageSr(BasePrompt):
    content = SR_LAN_ROLE + TEXT_LANGUAGE


@Model.prompt_register('TEXT_LANGUAGE_TH', [])
class PromptTextLanguageTh(BasePrompt):
    content = TH_LAN_ROLE + TEXT_LANGUAGE


@Model.prompt_register('TEXT_LANGUAGE_VI', [])
class PromptTextLanguageVi(BasePrompt):
    content = VI_LAN_ROLE + TEXT_LANGUAGE
