"""
LLMAgentArgumentCorrectness: Evaluates whether the agent passed correct arguments to each tool call.

Performs referenceless LLM-judge evaluation — no ground-truth arguments are required.
The judge assesses argument quality based on the task objective and the expected
semantics of each tool.
"""

from typing import List

from dingo.io.input import Data, RequiredField
from dingo.model import Model
from dingo.model.llm.agent_eval.base_llm_agent_eval import BaseLLMAgentEval


@Model.llm_register("LLMAgentArgumentCorrectness")
class LLMAgentArgumentCorrectness(BaseLLMAgentEval):
    """
    Evaluates the correctness of tool arguments in an agent's execution.

    Input:
        prompt  - The task objective or user request
        content - JSON-formatted sequence of tool calls with their arguments

    Performs referenceless evaluation: the LLM judge determines whether
    each tool received correct, well-formed, and contextually appropriate
    arguments, without requiring ground-truth argument values.
    """

    eval_layer = "action"
    input_data_type = "tool_calls"
    default_threshold = 0.6

    _required_fields = [RequiredField.PROMPT, RequiredField.CONTENT]

    prompt = """You are an expert evaluator assessing whether an AI agent passed correct arguments to its tool calls.

For each tool call in the sequence, evaluate the arguments:
- Are the argument values correct and appropriate for the task context?
- Are required arguments present and non-null?
- Are argument types and formats valid?
- Do the arguments make semantic sense given what the tool does?

Count:
- **correct_args**: Tool calls where arguments were fully correct
- **total_calls**: Total number of tool calls evaluated

List specific argument issues found (wrong value, missing required argument, type mismatch, semantically incorrect argument, etc.).

A score of 10 means all tool calls had perfectly correct arguments.
A score of 0 means all tool calls had wrong or missing arguments.

Return your evaluation as a JSON object with this exact schema:
{
  "correct_args": <integer>,
  "total_calls": <integer>,
  "issues": ["<issue description, e.g. tool X received wrong value for param Y>", ...],
  "score": <integer 0-10>,
  "reason": "<concise summary of argument correctness across all tool calls>"
}

Do not include any text outside the JSON object."""

    @classmethod
    def build_messages(cls, input_data: Data) -> List[dict]:
        """Build LLM messages for argument correctness evaluation."""
        lang_hint = cls.language_hint_for(input_data)
        user_content = f"""{cls.prompt}

## Task Objective
{input_data.prompt}

## Tool Call Sequence with Arguments
{input_data.content}

Evaluate the tool arguments and return the JSON evaluation.{lang_hint}"""

        return [{"role": "user", "content": user_content}]
