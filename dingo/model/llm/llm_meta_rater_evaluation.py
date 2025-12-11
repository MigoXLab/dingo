"""
LLM models for Meta-rater PRRC dimensions evaluation.

This module contains LLM-based evaluators for assessing the quality of text data
across four dimensions: Professionalism, Readability, Reasoning, and Cleanliness.
Based on the Meta-rater paper for data selection in LLM pre-training.
"""

import json
from typing import List

from dingo.io import Data
from dingo.model import Model
from dingo.model.llm.base_openai import BaseOpenAI
from dingo.model.modelres import ModelRes
from dingo.model.prompt.prompt_meta_rater import PromptMetaRaterProfessionalism
from dingo.utils import log
from dingo.utils.exception import ConvertJsonError


@Model.llm_register('LLMMetaRaterEvaluation')
class LLMMetaRaterEvaluation(BaseOpenAI):
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
    prompt = PromptMetaRaterProfessionalism  # Default prompt

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
                     "content": cls.prompt.content.format(content=input_data.content)}]
        return messages

    @classmethod
    def process_response(cls, response: str) -> ModelRes:
        """
        Process the LLM response for Meta-rater evaluation.

        Args:
            response: Raw response string from the LLM

        Returns:
            ModelRes: Processed evaluation results with score and reason
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

        result = ModelRes()

        # Meta-rater uses 1-5 scoring, with higher scores being better;
        # We normalize this to binary classification for compatibility
        # Scores >= 3 are considered "good quality", < 3 are "low quality"
        if score >= 3:
            result.error_status = False
            result.type = cls.prompt.metric_type
            result.name = "HighQuality"
            result.reason = [f"Score: {score}/5. {reason}"]
        else:
            result.error_status = True
            result.type = cls.prompt.metric_type
            result.name = "LowQuality"
            result.reason = [f"Score: {score}/5. {reason}"]

        return result
