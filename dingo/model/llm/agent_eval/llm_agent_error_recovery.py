"""
LLMAgentErrorRecovery: Evaluates the agent's ability to recover from errors encountered during execution.

If no error events are present in the input, returns score=1.0 (pass) immediately,
since perfect execution with no errors requires no recovery.
"""

import json
from typing import List

from dingo.io.input import Data, RequiredField
from dingo.io.output.eval_detail import EvalDetail, QualityLabel
from dingo.model import Model
from dingo.model.llm.agent_eval.base_llm_agent_eval import BaseLLMAgentEval
from dingo.utils import log


@Model.llm_register("LLMAgentErrorRecovery")
class LLMAgentErrorRecovery(BaseLLMAgentEval):
    """
    Evaluates the error recovery capability of an agent.

    Input:
        prompt  - The task objective or user request
        content - The error events or failure log from the agent execution

    If no errors are found in the content, the evaluator short-circuits
    and returns score=1.0 (pass) without calling the LLM.
    """

    eval_layer = "recovery"
    input_data_type = "error_events"
    default_threshold = 0.5

    _required_fields = [RequiredField.PROMPT, RequiredField.CONTENT]

    _NO_ERROR_INDICATORS = [
        "no error", "no errors", "no failures", "no exception",
        "0 errors", "zero errors", "none", "n/a", "[]", "{}",
    ]

    prompt = """You are an expert evaluator assessing how well an AI agent recovered from errors during task execution.

For each error event, evaluate:
- Did the agent detect the error?
- Did the agent attempt recovery?
- Was the recovery successful?
- Was the recovery strategy appropriate?

Count:
- **errors_encountered**: Total number of distinct errors or failures
- **recovered_count**: Number of errors from which the agent successfully recovered

Assess the overall recovery **score** from 0 to 10:
- 10: Agent recovered from all errors with optimal strategies
- 7-9: Agent recovered from most errors with reasonable strategies
- 4-6: Agent recovered from some errors but used suboptimal approaches
- 1-3: Agent attempted recovery but largely failed
- 0: Agent did not attempt recovery or made errors worse

Return your evaluation as a JSON object with this exact schema:
{
  "errors_encountered": <integer>,
  "recovered_count": <integer>,
  "score": <integer 0-10>,
  "reason": "<concise explanation of recovery behavior for each error type>"
}

Do not include any text outside the JSON object."""

    @classmethod
    def _has_error_events(cls, content: str) -> bool:
        """Check if the content contains actual error events.

        The structured payload is ``{"error_events": [...], "steps": [...]}`` —
        whether errors occurred is the ``error_events`` list, not the wrapper
        (which is never literally ``{}``/``[]``). Parse it so a clean run
        short-circuits to a pass instead of spending an LLM call on an empty
        error list. Falls back to phrase matching for free-text inputs.
        """
        if not content or not content.strip():
            return False
        try:
            parsed = json.loads(content)
            if isinstance(parsed, dict) and "error_events" in parsed:
                return bool(parsed.get("error_events"))
            if isinstance(parsed, list):
                return bool(parsed)
        except (ValueError, TypeError):
            pass
        stripped = content.strip().lower()
        return stripped not in cls._NO_ERROR_INDICATORS

    @classmethod
    def build_messages(cls, input_data: Data) -> List[dict]:
        """Build LLM messages for error recovery evaluation."""
        lang_hint = cls.language_hint_for(input_data)
        user_content = f"""{cls.prompt}

## Task Objective
{input_data.prompt}

## Error Events / Failure Log
{input_data.content}

Evaluate the agent's error recovery and return the JSON evaluation.{lang_hint}"""

        return [{"role": "user", "content": user_content}]

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        """Override eval() to handle the no-error special case.

        When the trace contains no error events, recovery is vacuously perfect,
        so we short-circuit to a pass without an LLM call. Otherwise we delegate
        to the shared retry/parse pipeline in ``BaseOpenAI.eval``, which drives
        this class's ``build_messages`` and inherited ``process_response`` — no
        need to duplicate the retry loop and error fallback here.
        """
        content = getattr(input_data, "content", "") or ""

        if not cls._has_error_events(content):
            log.info(f"{cls.__name__}: No error events detected, marking N/A")
            result = EvalDetail(metric=cls.__name__)
            result.status = False
            result.applicable = False      # N/A：从聚合分母剔除，而非给满分
            # Decided before the model was called: this check does not
            # apply to a run of this shape, which says nothing about the
            # run's quality either way.
            result.not_applicable_kind = "structural"
            # …and which reason, in a form the UI can translate. The prose below
            # is English by construction, and a reader on a Chinese page was
            # shown it verbatim. Set here because the branch that declines is
            # the only place that knows why.
            result.not_applicable_code = "no_errors"
            result.score = None
            result.verdict = "n/a"
            result.reason = ["No error events found in execution trace; recovery not applicable."]
            return result

        return super().eval(input_data)
