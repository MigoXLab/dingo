"""
Prompt templates for Meta-rater PRRC dimensions evaluation.

This module defines prompts used by LLM models to assess the quality of text data
across four dimensions: Professionalism, Readability, Reasoning, and Cleanliness.
Based on the Meta-rater paper for data selection in LLM pre-training.
"""

from dingo.model.model import Model
from dingo.model.prompt.base import BasePrompt

# Professionalism evaluation prompt
META_RATER_PROFESSIONALISM_PROMPT = """# CONTEXT #
I am a data scientist interested in exploring data in the pre-training stage of large language models.

# OBJECTIVE #
You are an expert evaluator. Below is an extract from a text source such as a web page, book, academic paper, Github, Wikipedia, or StackExchange. Evaluate the PROFESSIONALISM of the text, that is, the degree of expertise and prerequisite knowledge required to comprehend it, using the additive 5-point scoring system described below. Your evaluation should be based on the depth, accuracy, and accessibility of the content, without considering the writing style, grammar, spelling, or punctuation in your scoring.

Points are accumulated based on the satisfaction of each criterion:
- Add 1 point if the text is relatively simple and requires minimal technical knowledge or expertise to understand. The text might include nursery rhymes, children's books, or other basic content that is accessible to a broad audience. The information provided is straightforward and does not delve into complex concepts or specialized topics.
- Add another point if the text is somewhat more complex and might require a basic level of specialized knowledge to comprehend fully. Examples could include popular books, popular science articles, or novels. The content delves a little deeper into the subject matter, but it remains accessible to a reasonably broad audience.
- Award a third point if the text falls in the middle of the spectrum, requiring some degree of expertise to understand but not being overly complex or specialized. The content might encompass more advanced books, detailed articles, or introductions to complex topics. It provides a decent level of depth and detail, but it does not require an extensive background in the subject matter to understand.
- Grant a fourth point if the text is complicated and requires a significant level of expertise and technical knowledge. Examples might include academic papers, advanced textbooks, or detailed technical reports. The content is detailed and accurate, but it could be inaccessible to those without a strong background in the subject matter.
- Bestow a fifth point if the text is extremely high in professionalism, requiring a high degree of subject matter expertise and prerequisite knowledge. The text is likely limited to those with advanced understanding or experience in the field, such as advanced academic papers, complex technical manuals, or patents. The content is deep, accurate, and insightful, but largely inaccessible to those without a significant background in the topic.

Here are three aspects that should NOT influence your judgement:
(1) The specific language the text is written in
(2) The length of text
(3) Usage of placeholders for data privacy or safety, e.g. @CAPS1, [EMAIL_ADDRESS], [PHONE_NUMBER], and so on.

# STYLE #
A formal and clear text including score and reason.
# TONE #
professional, objective, formal, and clear.
# AUDIENCE #
Data scientists and other professionals interested in data for large language models.
# RESPONSE #
Return the results in JSON format: {{"score": x, "reason": "xxx"}}.

Here is the text:
{content}
"""

# Readability evaluation prompt
META_RATER_READABILITY_PROMPT = """# CONTEXT #
I am a data scientist interested in exploring data in the pre-training stage of large language models.

# OBJECTIVE #
You are an expert evaluator. Below is an extract from a text source such as a web page, book, academic paper, Github, Wikipedia, or StackExchange. Evaluate whether the page has a high READABILITY using the additive 5-point scoring system described below.

Points are accumulated based on the satisfaction of each criterion：
- Add 1 point if the text is somewhat readable but contains significant issues with clarity or coherence. It might include complex vocabulary or sentence structures that require advanced reading skills, or it might have numerous grammar and spelling errors.
- Add another point if the text is generally clear and coherent, but there are sections that are difficult to comprehend due to occasional grammar, spelling errors, or convoluted sentence structures.
- Award a third point if the text is clear and coherent for the most part, using appropriate vocabulary and sentence structures that are easy to understand. Minor issues with grammar or spelling might still be present.
- Grant a fourth point if the text is very clear and coherent, with very few or no errors in grammar and spelling. The text uses proper punctuation, vocabulary, and sentence structures that are easy to follow and understand.
- Bestow a fifth point if the text is outstanding in its clarity and coherence. It uses language and sentence structures that are easy to comprehend, while also conveying ideas and nuances effectively. Minor errors in grammar, spelling, and punctuation are allowed, but they should not interfere with the overall understanding of the text.

Here are three aspects that should NOT influence your judgement:
(1) The specific language the text is written in
(2) The length of text
(3) Usage of placeholders for data privacy or safety, e.g. @CAPS1, [EMAIL_ADDRESS], [PHONE_NUMBER], and so on.

# STYLE #
A formal and clear text including score and reason.
# TONE #
professional, objective, formal, and clear.
# AUDIENCE #
Data scientists and other professionals interested in data for large language models.
# RESPONSE #
Return the results in JSON format: {{"score": x, "reason": "xxx"}}.

Here is the text:
{content}"""

# Reasoning evaluation prompt
META_RATER_REASONING_PROMPT = """# CONTEXT #
I am a data scientist interested in exploring data in the pre-training stage of large language models.

# OBJECTIVE #
You are an expert evaluator. Below is an extract from a text source such as a web page, book, academic paper, Github, Wikipedia, or StackExchange. Evaluate whether the page has a high REASONING using the additive 5-point scoring system described below.

Points are accumulated based on the satisfaction of each criterion：
Add 1 point if the content contains preliminary elements of reasoning, possibly involving a single causal relationship or simple logical judgments, but lacks in-depth analysis (e.g., presenting a viewpoint without supporting evidence or detailed explanations).
Add another point if the content demonstrates basic reasoning ability, incorporating some logical relationships that require the reader to engage in a certain level of thought. This may involve simple argumentative structures or examples, but the analysis remains superficial (e.g., providing a problem and a straightforward solution with some examples but lacking depth).
Award a third point if the content exhibits a good level of reasoning complexity, involving multiple reasoning steps that require more complex thought from the reader. The reader should be able to identify several interrelated arguments and may include some depth of analysis (e.g., analyzing how different factors influence an outcome or comparing various viewpoints).
Grant a fourth point if the content has a high level of reasoning complexity, including multi-layered logical reasoning and in-depth analysis. The reader needs to engage in complex thinking and can identify multiple interconnected arguments while conducting a comprehensive evaluation (e.g., analyzing multiple variables or assessing the pros and cons of different solutions).
Bestow a fifth point if the content excels in reasoning complexity, demanding deep analysis and innovative thinking from the reader. The reasoning process is complex and multidimensional, involving interdisciplinary knowledge, requiring the reader to integrate various pieces of information to make comprehensive judgments (e.g., discussing complex mathematical models, designing optimization algorithms, or engaging in high-level strategic thinking).

Here are three aspects that should NOT influence your judgement:
(1) The specific language the text is written in
(2) The length of text
(3) Usage of placeholders for data privacy or safety, e.g. @CAPS1, [EMAIL_ADDRESS], [PHONE_NUMBER], and so on.

# STYLE #
A formal and clear text including score and reason.
# TONE #
professional, objective, formal, and clear.
# AUDIENCE #
Data scientists and other professionals interested in data for large language models.
# RESPONSE #
Return the results in JSON format: {{"score": x, "reason": "xxx"}}.

Here is the text:
{content}"""

# Cleanliness evaluation prompt
META_RATER_CLEANLINESS_PROMPT = """# CONTEXT #
I am a data scientist interested in exploring data in the pre-training stage of large language models.

# OBJECTIVE #
You are an expert evaluator. Below is an extract from a text source such as a web page, book, academic paper, Github, Wikipedia, or StackExchange. Evaluate whether the page has a high CLEANLINESS using the additive 5-point scoring system described below.

Points are accumulated based on the satisfaction of each criterion：
A score of 1 indicates serious issues that affect fluency.
A score of 2 indicates the text has obvious problems that affect fluency.
A score of 3 means that the text has some problems but does not seriously affect reading fluency.
A score of 4 indicates the text has minor problems but does not affect reading.
A score of 5 means points means that the text is perfect on every criteria.
The following factors should not affect your judgement:
The presence of the $TRUNCATED$ symbol is to be seen as an author-decided manual article ending flag, text completeness should not be considered.
High cleanliness is defined by the following four criteria, please score each of the four criteria on a 5-point scale:
- Correct formatting: The text should appear to be edited by a human, rather than extracted by a machine, with no inappropriate characters.
- Appropriate content: The text should not contain links, advertisements, or other irrelevant text that affects reading. The effective content of the text is long enough to extract a clear structure and theme.
- Completeness Content: The body of the article consists of complete sentences written naturally by humans, rather than phrases and lists, containing opinions, facts or stories.
However, if there is a $TRUNCATED$ symbol at the end, it should be considered as a manual article ending flag set by the author, and there is no need to consider completeness.

Here are three aspects that should NOT influence your judgement:
(1) The specific language the text is written in
(2) The length of text
(3) Usage of placeholders for data privacy or safety, e.g. @CAPS1, [EMAIL_ADDRESS], [PHONE_NUMBER], and so on.

# STYLE #
A formal and clear text including score and reason.
# TONE #
professional, objective, formal, and clear.
# AUDIENCE #
Data scientists and other professionals interested in data for large language models.
# RESPONSE #
Return the results in JSON format: {{"score": x, "type": "cleanliness", "correct_formatting": x, "appropriate_content": x, "completeness": x, "reason": "xxx"}}.

Here is the text:
{content}"""


@Model.prompt_register("META_RATER_PROFESSIONALISM", [], ["LLMMetaRaterEvaluation"])
class PromptMetaRaterProfessionalism(BasePrompt):
    """
    Prompt class for Meta-rater Professionalism evaluation.

    Evaluates the degree of expertise and prerequisite knowledge required to
    comprehend text on a 5-point scale.
    """

    # Metadata for documentation generation
    _metric_info = {
        "category": "Meta Rater Evaluation Metrics",
        "metric_name": "PromptMetaRaterProfessionalism",
        "description": "Evaluates the degree of expertise and prerequisite knowledge required to comprehend text on a 5-point scale",
        "paper_title": "Meta-rater: A Multi-dimensional Data Selection Method for Pre-training Language Models",
        "paper_url": "https://arxiv.org/pdf/2504.14194",
        "paper_authors": "Zhuang et al., 2025",
        "evaluation_results": ""
    }

    content = META_RATER_PROFESSIONALISM_PROMPT


@Model.prompt_register("META_RATER_READABILITY", [], ["LLMMetaRaterEvaluation"])
class PromptMetaRaterReadability(BasePrompt):
    """
    Prompt class for Meta-rater Readability evaluation.

    Evaluates the clarity and coherence of text using appropriate vocabulary
    and sentence structures on a 5-point scale.
    """

    # Metadata for documentation generation
    _metric_info = {
        "category": "Meta Rater Evaluation Metrics",
        "metric_name": "PromptMetaRaterReadability",
        "description": "Evaluates the clarity and coherence of text using appropriate vocabulary and sentence structures on a 5-point scale",
        "paper_title": "Meta-rater: A Multi-dimensional Data Selection Method for Pre-training Language Models",
        "paper_url": "https://arxiv.org/pdf/2504.14194",
        "paper_authors": "Zhuang et al., 2025",
        "evaluation_results": ""
    }

    content = META_RATER_READABILITY_PROMPT


@Model.prompt_register("META_RATER_REASONING", [], ["LLMMetaRaterEvaluation"])
class PromptMetaRaterReasoning(BasePrompt):
    """
    Prompt class for Meta-rater Reasoning evaluation.

    Evaluates the reasoning complexity and logical depth of text content,
    from simple logical judgments to complex multidimensional analysis on a 5-point scale.
    """

    # Metadata for documentation generation
    _metric_info = {
        "category": "Meta Rater Evaluation Metrics",
        "metric_name": "PromptMetaRaterReasoning",
        "description": "Evaluates the reasoning complexity and logical depth of text content, from simple logical judgments to complex multidimensional analysis on a 5-point scale",
        "paper_title": "Meta-rater: A Multi-dimensional Data Selection Method for Pre-training Language Models",
        "paper_url": "https://arxiv.org/pdf/2504.14194",
        "paper_authors": "Zhuang et al., 2025",
        "evaluation_results": ""
    }

    content = META_RATER_REASONING_PROMPT


@Model.prompt_register("META_RATER_CLEANLINESS", [], ["LLMMetaRaterEvaluation"])
class PromptMetaRaterCleanliness(BasePrompt):
    """
    Prompt class for Meta-rater Cleanliness evaluation.

    Evaluates text formatting, content appropriateness, and completeness,
    assessing whether text appears human-edited and free from noise on a 5-point scale.
    """

    # Metadata for documentation generation
    _metric_info = {
        "category": "Meta Rater Evaluation Metrics",
        "metric_name": "PromptMetaRaterCleanliness",
        "description": "Evaluates text formatting, content appropriateness, and completeness, assessing whether text appears human-edited and free from noise on a 5-point scale",
        "paper_title": "Meta-rater: A Multi-dimensional Data Selection Method for Pre-training Language Models",
        "paper_url": "https://arxiv.org/pdf/2504.14194",
        "paper_authors": "Zhuang et al., 2025",
        "evaluation_results": ""
    }

    content = META_RATER_CLEANLINESS_PROMPT
