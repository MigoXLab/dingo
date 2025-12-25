"""
LLM models for Meta-rater Readability dimension evaluation.

This module contains LLM-based evaluators for assessing the readability of text data.
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


@Model.llm_register('LLMMetaRaterReadability')
class LLMMetaRaterReadability(BaseOpenAI):
    """
    LLM model for Meta-rater Readability dimension evaluation.

    This model evaluates the clarity and coherence of text using appropriate
    vocabulary and sentence structures on a 5-point scale.

    Evaluation criteria:
    - Readability: Clarity and coherence, proper grammar and spelling

    Higher scores indicate better readability.
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

    prompt = """# CONTEXT #
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
        Process the LLM response for Meta-rater Readability evaluation.

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
