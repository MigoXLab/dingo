"""
LLM models for Meta-rater Cleanliness dimension evaluation.

This module contains LLM-based evaluators for assessing the cleanliness and formatting quality of text data.
Based on the Meta-rater paper for data selection in LLM pre-training.
"""

import json
from typing import List

from dingo.io import Data
from dingo.io.output.eval_detail import EvalDetail
from dingo.model import Model
from dingo.model.llm.base_openai import BaseOpenAI
from dingo.utils import log
from dingo.utils.exception import ConvertJsonError


@Model.llm_register('LLMMetaRaterCleanliness')
class LLMMetaRaterCleanliness(BaseOpenAI):
    """
    LLM model for Meta-rater Cleanliness dimension evaluation.

    This model evaluates text formatting, content appropriateness, and completeness,
    assessing whether text appears human-edited and free from noise on a 5-point scale.

    Evaluation criteria:
    - Correct formatting: Human-edited appearance, no inappropriate characters
    - Appropriate content: No links, ads, or irrelevant text
    - Completeness: Natural, complete sentences with clear structure

    Higher scores indicate cleaner, more well-formatted text.
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

    prompt = """# CONTEXT #
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

    @classmethod
    def build_messages(cls, input_data: Data) -> List:
        """
        Build messages for the LLM API call.

        Args:
            input_data: Data object containing text content to evaluate

        Returns:
            List: Formatted messages for LLM API
        """
        messages = [{"role": "user",
                     "content": cls.prompt.format(content=input_data.content)}]
        return messages

    @classmethod
    def process_response(cls, response: str) -> EvalDetail:
        """
        Process the LLM response for Meta-rater Cleanliness evaluation.

        Args:
            response: Raw response string from the LLM

        Returns:
            EvalDetail: Processed evaluation results with score and reason
        """
        log.info(response)

        # Clean up Markdown code block formatting if present
        cleaned_response = response
        if cleaned_response.startswith('```json'):
            cleaned_response = cleaned_response[7:]
        if cleaned_response.startswith('```'):
            cleaned_response = cleaned_response[3:]
        if cleaned_response.endswith('```'):
            cleaned_response = cleaned_response[:-3]

        try:
            response_json = json.loads(cleaned_response)
        except json.JSONDecodeError:
            raise ConvertJsonError(f'Convert to JSON format failed: {cleaned_response}')

        # Extract score and reason from response
        score = response_json.get('score', 0)
        reason = response_json.get('reason', '')

        result = EvalDetail(metric=cls.__name__)

        # Meta-rater uses 1-5 scoring, with higher scores being better;
        # We normalize this to binary classification for compatibility
        # Scores >= 3 are considered "good quality", < 3 are "low quality"
        if score >= 3:
            result.status = False
            # result.type = cls.prompt.metric_type
            # result.name = "HighQuality"
            # result.reason = [f"Score: {score}/5. {reason}"]
            result.label = [f"{cls.__name__}.HighQuality"]
            result.reason = [f"Score: {score}/5. {reason}"]
        else:
            result.status = True
            # result.type = cls.prompt.metric_type
            # result.name = "LowQuality"
            # result.reason = [f"Score: {score}/5. {reason}"]
            result.label = [f"{cls.__name__}.LowQuality"]
            result.reason = [f"Score: {score}/5. {reason}"]

        return result
