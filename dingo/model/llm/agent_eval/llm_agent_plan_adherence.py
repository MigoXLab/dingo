"""
LLMAgentPlanAdherence: Evaluates how closely the agent followed its stated plan during execution.

Compares the original plan (prompt) against the actual execution steps (content),
with the task goal available as context. Justified deviations are scored more
leniently than unjustified ones.
"""

from typing import List

from dingo.io.input import Data, RequiredField
from dingo.model import Model
from dingo.model.llm.agent_eval.base_llm_agent_eval import BaseLLMAgentEval


@Model.llm_register("LLMAgentPlanAdherence")
class LLMAgentPlanAdherence(BaseLLMAgentEval):
    """
    Evaluates how closely the agent adhered to its original plan.

    Input:
        prompt  - The agent's original plan (steps or strategy)
        content - The actual execution steps taken by the agent
        context - The overarching task goal or user objective

    Deviations are classified as justified (e.g., adapting to unexpected
    obstacles) or unjustified (e.g., skipping steps without reason).
    """

    eval_layer = "reasoning"
    input_data_type = "plan_vs_execution"
    default_threshold = 0.5

    _required_fields = [RequiredField.PROMPT, RequiredField.CONTENT, RequiredField.CONTEXT]

    prompt = """You are an expert evaluator assessing how closely an AI agent followed its original plan during execution.

Compare the original plan against the actual execution steps and classify any deviations:
- **Justified deviations**: The agent deviated from the plan for a valid reason (e.g., encountered an obstacle, discovered new information, adapted to dynamic conditions).
- **Unjustified deviations**: The agent deviated from the plan without apparent reason (e.g., skipped steps, added unplanned steps unrelated to the goal).

Count:
- **followed_steps**: Number of planned steps that were executed as intended
- **total_planned**: Total number of steps in the original plan
- **justified_deviations**: Deviations with valid justification
- **unjustified_deviations**: Deviations without justification

A score of 10 means perfect adherence (or all deviations were justified).
A score of 0 means the agent completely ignored its plan without justification.

Return your evaluation as a JSON object with this exact schema:
{
  "followed_steps": <integer>,
  "total_planned": <integer>,
  "justified_deviations": <integer>,
  "unjustified_deviations": <integer>,
  "score": <integer 0-10>,
  "reason": "<concise explanation of adherence quality and notable deviations>"
}

Do not include any text outside the JSON object."""

    @classmethod
    def build_messages(cls, input_data: Data) -> List[dict]:
        """Build LLM messages for plan adherence evaluation."""
        task_goal = getattr(input_data, "context", "") or ""
        lang_hint = cls.language_hint_for(input_data)
        user_content = f"""{cls.prompt}

## Task Goal
{task_goal}

## Original Plan
{input_data.prompt}

## Actual Execution Steps
{input_data.content}

Evaluate how closely the agent followed its plan and return the JSON evaluation.{lang_hint}"""

        return [{"role": "user", "content": user_content}]
