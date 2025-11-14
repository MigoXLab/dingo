from dingo.model import Model
from dingo.model.llm.security.llm_security import LLMSecurity


@Model.llm_register("LLMSecurityPolitics")
class LLMSecurityPolitics(LLMSecurity):
    # Metadata for documentation generation
    _metric_info = {
        "category": "Pretrain Text Quality Assessment Metrics",
        "metric_name": "PromptPolitics",
        "description": "Evaluates whether the text contains politics-related content",
        "paper_title": "",
        "paper_url": "",
        "paper_authors": "",
        "evaluation_results": ""
    }

    prompt = """
你是一名内容安全审查员，可以用英语流利沟通，会站在中国人的角度思考问题。我将提供一段文字，需要你判断其内容是否属于政治敏感内容，并且立场是否为负面。政治敏感内容包括以下五个方面，以下内容解释了对应方面的负面立场：

1.(terrorism_and_extremism)宣扬恐怖主义、极端主义。

对于某个方面，如果语料有所涉及并持负面立场标记为"neg",如果语料有所涉及并持正面立场标记为"pos", 如果语料不涉及标记为"none"。
请使用json格式进行回答，并仅输出json内容。具体格式如下:

回答：
{{
    "terrorism_and_extremism": "neg"|"pos"|"none",
}}

需要审查的语料：
    """
