import json
from typing import List, Union

from dingo.io import Data
from dingo.model import Model
from dingo.model.llm.base_openai import BaseOpenAI
from dingo.model.modelres import ModelRes
from dingo.model.prompt.prompt_hallucination import PromptHallucination
from dingo.model.response.response_hallucination import HallucinationScoreReason, HallucinationVerdict, HallucinationVerdicts
from dingo.utils import log
from dingo.utils.exception import ConvertJsonError


@Model.llm_register("LLMHallucination")
class LLMHallucination(BaseOpenAI):
    """
    Hallucination detection LLM based on DeepEval's HallucinationMetric.
    Evaluates whether LLM outputs contain factual contradictions against provided contexts.

    This implementation adapts DeepEval's verdict-based approach to Dingo's architecture:
    1. Generates verdicts for each context against the actual output
    2. Calculates hallucination score based on contradiction ratio
    3. Returns standardized ModelRes with error_status based on threshold
    """

    prompt = PromptHallucination
    threshold = 0.5  # Default threshold for hallucination detection

    @classmethod
    def build_messages(cls, input_data: Data) -> List:
        """
        Build messages for hallucination detection.
        Expects input_data to have:
        - prompt: The question/prompt
        - content: The actual response to evaluate
        - context: List of reference contexts (can be string or list)
        """
        question = input_data.prompt or ""
        response = input_data.content

        # Handle context - can be string or list
        if hasattr(input_data, 'context') and input_data.context:
            if isinstance(input_data.context, list):
                contexts = input_data.context
            else:
                # Try to parse as JSON list, fallback to single context
                try:
                    contexts = json.loads(input_data.context)
                    if not isinstance(contexts, list):
                        contexts = [str(input_data.context)]
                except (json.JSONDecodeError, ValueError):
                    contexts = [str(input_data.context)]
        else:
            # No context provided - cannot evaluate hallucination
            log.warning("No context provided for hallucination detection")
            contexts = []

        # Format contexts for display
        contexts_str = json.dumps(contexts, ensure_ascii=False, indent=2)

        prompt_content = cls.prompt.content.format(question, response, contexts_str)

        messages = [{"role": "user", "content": prompt_content}]
        return messages

    @classmethod
    def process_response(cls, response: str) -> ModelRes:
        """
        Process LLM response to calculate hallucination score.
        Follows DeepEval's approach:
        1. Parse verdicts from LLM response
        2. Calculate hallucination score = (num_contradictions / total_verdicts)
        3. Set error_status based on threshold
        """
        log.info(f"Raw LLM response: {response}")

        # Clean response format
        if response.startswith("```json"):
            response = response[7:]
        if response.startswith("```"):
            response = response[3:]
        if response.endswith("```"):
            response = response[:-3]

        try:
            response_json = json.loads(response)
        except json.JSONDecodeError:
            raise ConvertJsonError(f"Convert to JSON format failed: {response}")

        try:
            verdicts_data = HallucinationVerdicts(**response_json)
            verdicts = verdicts_data.verdicts
        except Exception as e:
            raise ConvertJsonError(f"Failed to parse verdicts: {e}")

        # Calculate hallucination score (like DeepEval)
        score = cls._calculate_hallucination_score(verdicts)

        # Generate detailed reason
        reason = cls._generate_reason(verdicts, score)

        result = ModelRes()

        # Set error_status based on threshold
        if score > cls.threshold:
            result.error_status = True
            result.type = "QUALITY_BAD_HALLUCINATION"
            result.name = "HALLUCINATION_DETECTED"
        else:
            result.type = "QUALITY_GOOD"
            result.name = "NO_HALLUCINATION"

        result.reason = [reason]

        # Store additional metadata
        result.score = score
        result.verdict_details = [
            f"{v.verdict}: {v.reason}" for v in verdicts
        ]

        log.info(f"Hallucination score: {score:.3f}, threshold: {cls.threshold}")

        return result

    @classmethod
    def _calculate_hallucination_score(cls, verdicts: List[HallucinationVerdict]) -> float:
        """
        Calculate hallucination score following DeepEval's approach.
        Score = number_of_contradictions / total_verdicts
        Higher score = more hallucinations (worse)
        """
        if not verdicts:
            return 0.0

        hallucination_count = 0
        for verdict in verdicts:
            if verdict.verdict.strip().lower() == "no":
                hallucination_count += 1

        score = hallucination_count / len(verdicts)
        return score

    @classmethod
    def _generate_reason(cls, verdicts: List[HallucinationVerdict], score: float) -> str:
        """Generate human-readable reason for the hallucination assessment"""

        contradictions = []
        alignments = []

        for verdict in verdicts:
            if verdict.verdict.strip().lower() == "no":
                contradictions.append(verdict.reason)
            else:
                alignments.append(verdict.reason)

        reason_parts = [
            f"Hallucination score: {score:.3f} (threshold: {cls.threshold})"
        ]

        if contradictions:
            reason_parts.append(f"Found {len(contradictions)} contradictions:")
            for i, contradiction in enumerate(contradictions, 1):
                reason_parts.append(f"  {i}. {contradiction}")

        if alignments:
            reason_parts.append(f"Found {len(alignments)} factual alignments:")
            for i, alignment in enumerate(alignments, 1):
                reason_parts.append(f"  {i}. {alignment}")

        if score > cls.threshold:
            reason_parts.append("❌ HALLUCINATION DETECTED: Response contains factual contradictions")
        else:
            reason_parts.append("✅ NO HALLUCINATION: Response aligns with provided contexts")

        return "\n".join(reason_parts)

    @classmethod
    def eval(cls, input_data: Data) -> ModelRes:
        """
        Override eval to add context validation
        """
        # Validate that context is provided
        if not hasattr(input_data, 'context') or not input_data.context:
            return ModelRes(
                error_status=True,
                type="QUALITY_BAD",
                name="MISSING_CONTEXT",
                reason=["Context is required for hallucination detection but was not provided"]
            )

        # Call parent eval method
        return super().eval(input_data)
