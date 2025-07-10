from dingo.model.model import Model
from dingo.model.prompt.base import BasePrompt
from dingo.model.prompt.prompt_text_quality_v2 import TEXT_QUALITY_WITHOUT_ROLE_V2

AR_ROLE = """
    ### Role
    You are an expert in Arabic language model.
    """
CS_ROLE = """
    ### Role
    You are an expert in Czech language model.
    """
DE_ROLE = """
    ### Role
    You are an expert in German language model.
    """
HU_ROLE = """
    ### Role
    You are an expert in Hungarian language model.
    """
KO_ROLE = """
    ### Role
    You are an expert in Korean language model.
    """
RU_ROLE = """
    ### Role
    You are an expert in Russian language model.
    """
SR_ROLE = """
    ### Role
    You are an expert in Serbian language model.
    """
TH_ROLE = """
    ### Role
    You are an expert in Thai language model.
    """
VI_ROLE = """
    ### Role
    You are an expert in Vietnamese language model.
    """


@Model.prompt_register("TEXT_QUALITY_AR", [])
class PromptTextQualityAr(BasePrompt):
    content = AR_ROLE + TEXT_QUALITY_WITHOUT_ROLE_V2


@Model.prompt_register("TEXT_QUALITY_CS", [])
class PromptTextQualityCs(BasePrompt):
    content = CS_ROLE + TEXT_QUALITY_WITHOUT_ROLE_V2


@Model.prompt_register("TEXT_QUALITY_DE", [])
class PromptTextQualityDe(BasePrompt):
    content = DE_ROLE + TEXT_QUALITY_WITHOUT_ROLE_V2


@Model.prompt_register("TEXT_QUALITY_HU", [])
class PromptTextQualityHu(BasePrompt):
    content = HU_ROLE + TEXT_QUALITY_WITHOUT_ROLE_V2


@Model.prompt_register("TEXT_QUALITY_KO", [])
class PromptTextQualityKo(BasePrompt):
    content = KO_ROLE + TEXT_QUALITY_WITHOUT_ROLE_V2


@Model.prompt_register("TEXT_QUALITY_RU", [])
class PromptTextQualityRu(BasePrompt):
    content = RU_ROLE + TEXT_QUALITY_WITHOUT_ROLE_V2


@Model.prompt_register("TEXT_QUALITY_SR", [])
class PromptTextQualitySr(BasePrompt):
    content = SR_ROLE + TEXT_QUALITY_WITHOUT_ROLE_V2


@Model.prompt_register("TEXT_QUALITY_TH", [])
class PromptTextQualityTh(BasePrompt):
    content = TH_ROLE + TEXT_QUALITY_WITHOUT_ROLE_V2


@Model.prompt_register("TEXT_QUALITY_VI", [])
class PromptTextQualityVi(BasePrompt):
    content = VI_ROLE + TEXT_QUALITY_WITHOUT_ROLE_V2
