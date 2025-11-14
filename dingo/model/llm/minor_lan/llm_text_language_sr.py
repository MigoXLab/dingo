from dingo.model import Model
from dingo.model.llm.base_openai import BaseOpenAI


@Model.llm_register("LLMTextLanguageSr")
class LLMTextLanguageSr(BaseOpenAI):
    prompt = """
### Role
You are an Serbian linguistics expert
### Target language
Serbian
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
