import json
from typing import List

from dingo.io import Data
from dingo.io.output.eval_detail import EvalDetail, QualityLabel
from dingo.model import Model
from dingo.model.llm.base_openai import BaseOpenAI
from dingo.model.response.response_hallucination import HallucinationVerdict, HallucinationVerdicts
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
    3. Returns standardized EvalDetail with eval_status based on threshold
    """
    # Metadata for documentation generation
    _metric_info = {
        "category": "SFT Data Assessment Metrics",
        "metric_name": "PromptHallucination",
        "description": "Evaluates whether the response contains factual contradictions or hallucinations against provided context information",
        "paper_title": "TruthfulQA: Measuring How Models Mimic Human Falsehoods",
        "paper_url": "https://arxiv.org/abs/2109.07958",
        "paper_authors": "Lin et al., 2021",
        "evaluation_results": ""
    }

    threshold = 0.5  # Default threshold for hallucination detection
    prompt = """
    For each context in the provided contexts, please generate a list of JSON objects to indicate whether the given 'actual output' agrees with EACH context. The JSON will have 2 fields: 'verdict' and 'reason'.

    The 'verdict' key should STRICTLY be either 'yes' or 'no', and states whether the given response agrees with the context.
    The 'reason' is the reason for the verdict. When the answer is 'no', try to provide a correction in the reason.

    **IMPORTANT**: Please make sure to only return in JSON format, with the 'verdicts' key as a list of JSON objects.

    Example contexts: ["Einstein won the Nobel Prize for his discovery of the photoelectric effect.", "Einstein won the Nobel Prize in 1968."]
    Example actual output: "Einstein won the Nobel Prize in 1969 for his discovery of the photoelectric effect."

    Example:
    {{
        "verdicts": [
            {{
                "verdict": "yes",
                "reason": "The actual output agrees with the provided context which states that Einstein won the Nobel Prize for his discovery of the photoelectric effect."
            }},
            {{
                "verdict": "no",
                "reason": "The actual output contradicts the provided context which states that Einstein won the Nobel Prize in 1968, not 1969."
            }}
        ]
    }}

    You should NOT incorporate any prior knowledge you have and take each context at face value. Since you are going to generate a verdict for each context, the number of 'verdicts' SHOULD BE STRICTLY EQUAL TO the number of contexts provided.
    You should FORGIVE cases where the actual output is lacking in detail, you should ONLY provide a 'no' answer if IT IS A CONTRADICTION.

    **Input Data:**
    Question/Prompt: {}
    Response: {}
    Contexts: {}

    Please evaluate the response against each context and return the verdicts in JSON format:
    """

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

        prompt_content = cls.prompt.format(question, response, contexts_str)

        messages = [{"role": "user", "content": prompt_content}]
        return messages

    @classmethod
    def process_response(cls, response: str) -> EvalDetail:
        """
        Process LLM response to calculate hallucination score.
        Follows DeepEval's approach:
        1. Parse verdicts from LLM response
        2. Calculate hallucination score = (num_contradictions / total_verdicts)
        3. Set eval_status based on threshold
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

        result = EvalDetail(metric=cls.__name__)

        # Set eval_status based on threshold
        if score > cls.threshold:
            result.status = True
            result.label = ['QUALITY_BAD_HALLUCINATION.HALLUCINATION_DETECTED']
        else:
            result.label = [f'{QualityLabel.QUALITY_GOOD}.NO_HALLUCINATION']

        result.reason = [reason]

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
    def eval(cls, input_data: Data) -> EvalDetail:
        """
        Override eval to add context validation
        """
        # Validate that context is provided
        if not hasattr(input_data, 'context') or not input_data.context:
            result = EvalDetail(metric=cls.__name__)
            result.status = True
            result.label = ["QUALITY_BAD.MISSING_CONTEXT"]
            result.reason = ["Context is required for hallucination detection but was not provided"]
            return result

        # Call parent eval method
        return super().eval(input_data)
