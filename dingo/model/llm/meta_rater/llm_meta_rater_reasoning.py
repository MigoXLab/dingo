"""
LLM models for Meta-rater Reasoning dimension evaluation.

This module contains LLM-based evaluators for assessing the reasoning complexity of text data.
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


@Model.llm_register('LLMMetaRaterReasoning')
class LLMMetaRaterReasoning(BaseOpenAI):
    """
    LLM model for Meta-rater Reasoning dimension evaluation.

    This model evaluates the reasoning complexity and logical depth of text content,
    from simple logical judgments to complex multidimensional analysis on a 5-point scale.

    Evaluation criteria:
    - Reasoning: Logical depth and complexity of argumentation

    Higher scores indicate more complex and sophisticated reasoning.
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

    prompt = """# CONTEXT #
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
        Process the LLM response for Meta-rater Reasoning evaluation.

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
