"""
Base class for text quality evaluators with shared response processing logic.
"""

import json

from dingo.io.output.eval_detail import EvalDetail
from dingo.model.llm.base_openai import BaseOpenAI
from dingo.model.response.response_class import ResponseScoreTypeNameReason


class BaseTextQuality(BaseOpenAI):
    """
    Base class for text quality evaluators.
    Provides shared response processing logic for LLMTextQualityV4 and V5.
    """

    @classmethod
    def process_response(cls, response: str) -> EvalDetail:
        """
        Process LLM response and convert to EvalDetail.

        Handles:
        - Cleanup of markdown code blocks (```json and ```)
        - JSON parsing
        - Creation of EvalDetail with proper status, score, label, and reason

        Args:
            response: Raw response string from LLM

        Returns:
            EvalDetail object with evaluation results
        """
        # Cleanup markdown code blocks
        if response.startswith("```json"):
            response = response[7:]
        elif response.startswith("```"):  # Changed to elif for safety
            response = response[3:]
        if response.endswith("```"):
            response = response[:-3]
        response = response.strip()

        # Parse JSON response
        response_json = json.loads(response)
        response_model = ResponseScoreTypeNameReason(**response_json)

        # Create EvalDetail with all required fields
        # status = False for Good quality (no issues found)
        # status = True for Bad quality (issues found)
        is_good = response_model.type == "Good"

        result = EvalDetail(
            metric=cls.__name__,
            status=not is_good,  # True if Bad (issues found), False if Good
            score=response_model.score,
            label=["QUALITY_GOOD"] if is_good else [f"{response_model.type}.{response_model.name}"],
            reason=[response_model.reason]
        )

        return result
