"""
LLMAgentToolCorrectness: Evaluates whether the agent selected the correct tools for each step.

Performs referenceless evaluation — no expected tool sequence is required.
The LLM judge assesses tool choices based on the task objective and the
context of each tool invocation.
"""

from typing import List

from dingo.io.input import Data, RequiredField
from dingo.model import Model
from dingo.model.llm.agent_eval.base_llm_agent_eval import BaseLLMAgentEval


@Model.llm_register("LLMAgentToolCorrectness")
class LLMAgentToolCorrectness(BaseLLMAgentEval):
    """
    Evaluates the correctness of tool selections in an agent's execution.

    Input:
        prompt  - The task objective or user request
        content - JSON-formatted sequence of tool calls made by the agent

    Performs referenceless evaluation: the LLM judge determines whether
    each tool choice was appropriate given the task and execution context,
    without requiring a ground-truth tool sequence.
    """

    eval_layer = "action"
    input_data_type = "tool_calls"
    default_threshold = 0.6

    _required_fields = [RequiredField.PROMPT, RequiredField.CONTENT]

    prompt = """You are an expert evaluator assessing whether an AI agent selected the correct tools during task execution.

For each tool call in the sequence, determine:
- Was this the right tool for the situation?
- Was this tool call necessary, or was it redundant?

Count:
- **correct_calls**: Tool calls that were appropriate and necessary
- **total_calls**: Total number of tool calls made
- **redundant_calls**: Tool calls that were unnecessary or duplicated without reason

List specific issues (wrong tool chosen, tool used out of order, missing tool that should have been called, etc.).

A score of 10 means every tool call was correct and necessary.
A score of 0 means all tool calls were wrong or the agent failed to use required tools.

Return your evaluation as a JSON object with this exact schema:
{
  "correct_calls": <integer>,
  "total_calls": <integer>,
  "redundant_calls": <integer>,
  "score": <integer 0-10>,
  "issues": ["<issue description>", ...],
  "reason": "<concise summary of tool selection quality>"
}

Do not include any text outside the JSON object."""

    @classmethod
    def build_messages(cls, input_data: Data) -> List[dict]:
        """Build LLM messages for tool correctness evaluation."""
        lang_hint = cls.language_hint_for(input_data)
        user_content = f"""{cls.prompt}

## Task Objective
{input_data.prompt}

## Tool Call Sequence
{input_data.content}

Evaluate the tool selections and return the JSON evaluation.{lang_hint}"""

        return [{"role": "user", "content": user_content}]
