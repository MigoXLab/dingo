"""
LLMAgentStepEfficiency: Evaluates whether the agent executed its task with minimal redundant steps.

Detects wasted steps, execution loops, and unnecessary operations in the agent trace,
scoring higher for lean and purposeful execution.
"""

from typing import List

from dingo.io.input import Data, RequiredField
from dingo.model import Model
from dingo.model.llm.agent_eval.base_llm_agent_eval import BaseLLMAgentEval, evidence_discipline


@Model.llm_register("LLMAgentStepEfficiency")
class LLMAgentStepEfficiency(BaseLLMAgentEval):
    """
    Evaluates the step efficiency of an agent's execution trace.

    Input:
        prompt  - The task objective or user request
        content - The agent execution trace or step-by-step summary

    Output score reflects how efficiently the agent reached its goal,
    penalizing redundant steps, loops, and unnecessary operations.
    """

    eval_layer = "execution"
    input_data_type = "trace_summary"
    default_threshold = 0.5

    _required_fields = [RequiredField.PROMPT, RequiredField.CONTENT]

    prompt = """You are an expert evaluator assessing the step efficiency of an AI agent's execution.

Analyze the agent's execution trace and identify:
- **Total steps**: Count all steps/actions taken by the agent
- **Necessary steps**: Steps that directly contribute to completing the task
- **Wasted steps**: Redundant, repeated, or unnecessary steps
- **Loops detected**: Whether the agent got stuck in a repetitive pattern

A score of 10 means perfectly efficient execution with no wasted steps.
A score of 0 means the agent was completely stuck in loops or took entirely unnecessary actions.

""" + evidence_discipline(
        "A step whose call returned nothing did not establish what it was\n"
        "  there to establish, whatever the summary says it established."
    ) + """

Return your evaluation as a JSON object with this exact schema:
{
  "total_steps": <integer>,
  "necessary_steps": <integer>,
  "wasted_steps": <integer>,
  "loops_detected": <boolean>,
  "score": <integer 0-10>,
  "reason": "<concise explanation including specific examples of inefficiency if found>"
}

Do not include any text outside the JSON object."""

    @classmethod
    def build_messages(cls, input_data: Data) -> List[dict]:
        """Build LLM messages for step efficiency evaluation."""
        lang_hint = cls.language_hint_for(input_data)
        user_content = f"""{cls.prompt}

## Task Objective
{input_data.prompt}

## Agent Execution Trace
{input_data.content}

Analyze the execution efficiency and return the JSON evaluation.{lang_hint}"""

        return [{"role": "user", "content": user_content}]
