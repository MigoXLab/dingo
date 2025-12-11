"""
LLM models for Meta-rater PRRC dimensions evaluation.

This module contains LLM-based evaluators for assessing the quality of text data
across four dimensions: Professionalism, Readability, Reasoning, and Cleanliness.
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


@Model.llm_register('LLMMetaRaterProfessionalism')
class LLMMetaRaterProfessionalism(BaseOpenAI):
    """
    Unified LLM model for Meta-rater PRRC dimensions evaluation.

    This model provides a single interface for evaluating multiple aspects
    of text quality based on the Meta-rater paper's PRRC framework:
    - Professionalism: Degree of expertise required
    - Readability: Clarity and coherence
    - Reasoning: Logical depth and complexity
    - Cleanliness: Formatting and content appropriateness

    The specific evaluation type is determined by the prompt used.
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

    prompt = """
# CONTEXT #
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
        Process the LLM response for Meta-rater evaluation.

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
