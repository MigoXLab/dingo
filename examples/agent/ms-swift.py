from pathlib import Path

from dingo.config import InputArgs
from dingo.exec import Executor

config = {
    "model": "",
    "key": "",
    "api_url": ""
}

input_data = {
  "input_path": r"",
  "dataset": {"source": "local", "format": "ms_swift"},
  # Keep both threshold matches (status=True) and unmatched/N/A records.
  "executor": {"result_save":{"bad":True, "good":True, "raw":True, "all_labels":True, "merge":True}},
  "evaluator": [
    {
      "fields": {"messages": "messages"},
      "evals": [{"name": "RuleAgentTraceEmptyAssistantTurn"}]
    },
    {
      "fields": {"messages": "messages"},
      "evals": [{"name": "RuleAgentTraceReasoningSparsity", "config": {"threshold": 0.7, "min_assistant_messages": 0}}]
    },
    {
      "fields": {
        "prompt": "LLMAgentTaskCompletion_prompt",
        "content": "LLMAgentTaskCompletion_content"
      },
      "evals": [{"name": "LLMAgentTaskCompletion","config": config}]
    },
    {
      "fields": {"content": "RuleAgentTraceLoopDetection_content"},
      "evals": [{"name": "RuleAgentTraceLoopDetection"}]
    },
    {
      "fields": {
        "prompt": "LLMAgentToolCorrectness_prompt",
        "content": "LLMAgentToolCorrectness_content"
      },
      "evals": [{"name": "LLMAgentToolCorrectness","config": config}]
    },
    {
      "fields": {"content": "RuleAgentTraceDestructiveAction_content"},
      "evals": [{"name": "RuleAgentTraceDestructiveAction"}]
    }
  ]
}

if __name__ == '__main__':
    input_args = InputArgs(**input_data)
    executor = Executor.exec_map["local"](input_args)
    result = executor.execute()
    print(result)
