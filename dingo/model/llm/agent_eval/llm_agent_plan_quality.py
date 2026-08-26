"""
LLMAgentPlanQuality: Evaluates the quality of an agent's reasoning plan.

Assesses coherence, completeness, and feasibility of the agent's plan.
If no planning content is found in the trace, defaults to passing (score=1.0).
"""

from typing import List

from dingo.io.input import Data, RequiredField
from dingo.io.output.eval_detail import EvalDetail, QualityLabel
from dingo.model import Model
from dingo.model.llm.agent_eval.base_llm_agent_eval import BaseLLMAgentEval, evidence_discipline
from dingo.utils import log


@Model.llm_register("LLMAgentPlanQuality")
class LLMAgentPlanQuality(BaseLLMAgentEval):
    """
    Evaluates the quality of an agent's reasoning plan.

    Input:
        prompt  - The task objective or user request
        content - The agent trace or plan description

    If no planning content is detected in the trace, the evaluator
    returns score=1.0 (pass) because absence of planning may be
    acceptable for simple tasks.
    """

    eval_layer = "reasoning"
    input_data_type = "trace_summary"
    default_threshold = 0.6

    _required_fields = [RequiredField.PROMPT, RequiredField.CONTENT]

    prompt = """You are an expert evaluator assessing the quality of an AI agent's reasoning plan.

First, determine whether the trace contains any planning content (explicit steps, strategy, or reasoning about how to approach the task). If there is no planning content at all, set score to -1 as a sentinel value.

If planning content exists, evaluate it on three dimensions:
1. **Coherence** (1-5): Is the plan logically structured and internally consistent?
2. **Completeness** (1-5): Does the plan cover all necessary steps to achieve the goal?
3. **Feasibility** (1-5): Are the planned steps realistic and achievable?

Compute an overall **score** from 0 to 10 that is CONSISTENT with the three
dimensions above (e.g. all 5s → 9-10, all 3s → 5-6, all 1s → 0-2). Do not let
the score contradict the dimension ratings.

""" + evidence_discipline(
        "A plan step the record shows never happened is not completed,\n"
        "  whatever the plan's own progress notes say."
    ) + """

Return your evaluation as a JSON object with this exact schema:
{
  "coherence": <integer 1-5, or null if no plan>,
  "completeness": <integer 1-5, or null if no plan>,
  "feasibility": <integer 1-5, or null if no plan>,
  "score": <integer -1 if no plan found, otherwise 0-10>,
  "reason": "<explanation; if no plan, state that planning content was not found>"
}

Do not include any text outside the JSON object."""

    @classmethod
    def build_messages(cls, input_data: Data) -> List[dict]:
        """Build LLM messages for plan quality evaluation."""
        lang_hint = cls.language_hint_for(input_data)
        user_content = f"""{cls.prompt}

## Task Objective
{input_data.prompt}

## Agent Trace / Plan
{input_data.content}

Evaluate the plan quality and return the JSON evaluation.{lang_hint}"""

        return [{"role": "user", "content": user_content}]

    @classmethod
    def process_response(cls, response: str) -> EvalDetail:
        """Handle the no-planning sentinel, else use the standard agent scoring.

        The prompt instructs the model to return ``score = -1`` when the trace
        contains no planning content at all; that is treated as a pass (absence
        of planning can be acceptable for simple tasks). Any other score is
        delegated to ``BaseLLMAgentEval.process_response`` for the standard
        0~10 → 0.0~1.0 normalization and threshold comparison. By only
        overriding ``process_response`` (not ``eval``), the retry loop and error
        fallback in ``BaseOpenAI.eval`` are reused instead of duplicated.
        """
        data = cls._parse_json_response(response)
        raw_score = data.get("score", 0)
        try:
            raw_score = float(raw_score)
        except (TypeError, ValueError):
            raw_score = 0.0

        if raw_score < 0:
            log.info(f"{cls.__name__}: model reports no planning content, marking N/A")
            # TODO(计划②): 用 manifest window.plan 硬确认"确实无计划"，而非只采信模型 -1
            result = EvalDetail(metric=cls.__name__)
            result.status = False
            result.applicable = False      # N/A：不再强转满分 pass
            # Decided before the model was called: this check does not
            # apply to a run of this shape, which says nothing about the
            # run's quality either way.
            result.not_applicable_kind = "structural"
            # …and which reason, in a form the UI can translate. The prose below
            # is English by construction, and a reader on a Chinese page was
            # shown it verbatim. Set here because the branch that declines is
            # the only place that knows why.
            result.not_applicable_code = "no_explicit_plan"
            result.score = None
            result.verdict = "n/a"
            result.reason = [data.get("reason", "No planning content reported; plan quality not applicable.")]
            return result

        return super().process_response(response)
