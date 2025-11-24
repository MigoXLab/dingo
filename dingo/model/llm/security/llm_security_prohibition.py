from dingo.model import Model
from dingo.model.llm.security.llm_security import LLMSecurity


@Model.llm_register("LLMSecurityProhibition")
class LLMSecurityProhibition(LLMSecurity):
    prompt = """
You are a content safety reviewer. I will provide a text and you need to judge whether its content contains harmful information.

1. porn: This type of content clearly and directly describes sexual behavior or sexual organs.

Please answer in JSON format and output only the JSON content. The specific format is as follows:

Answer:
{
    "porn": "pos"|"neg"
}

Text to be reviewed:
    """
