# Agent-Based Evaluation Development Guide

## Overview

This guide explains how to create custom agent-based evaluators and tools in Dingo. Agent-based evaluation enhances traditional rule and LLM evaluators by adding multi-step reasoning, tool usage, and adaptive context gathering.

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Creating Custom Tools](#creating-custom-tools)
3. [Creating Custom Agents](#creating-custom-agents)
4. [Configuration](#configuration)
5. [Testing](#testing)
6. [Best Practices](#best-practices)
7. [Examples](#examples)

---

## Architecture Overview

### How Agents Fit in Dingo

Agents extend Dingo's evaluation capabilities:

```
Traditional Evaluation:
Data → Rule/LLM → EvalDetail

Agent-Based Evaluation:
Data → Agent → [Tool 1, Tool 2, ...] → LLM Reasoning → EvalDetail
```

**Key Components:**

1. **BaseAgent**: Abstract base class for all agents (extends `BaseOpenAI`)
2. **Tool Registry**: Manages available tools for agents
3. **BaseTool**: Abstract interface for tool implementations
4. **Auto-Discovery**: Agents registered via `@Model.llm_register()` decorator

**Execution Model:**

- Agents run in **ThreadPoolExecutor** (same as LLMs) for I/O-bound operations
- Tools are called synchronously within the agent's execution
- Configuration injected via `dynamic_config` attribute

---

## Creating Custom Tools

### Step 1: Define Tool Configuration

Create a Pydantic model for type-safe configuration:

```python
from pydantic import BaseModel, Field
from typing import Optional

class MyToolConfig(BaseModel):
    """Configuration for MyTool"""
    api_key: Optional[str] = None
    max_results: int = Field(default=10, ge=1, le=100)
    timeout: int = Field(default=30, ge=1)
```

### Step 2: Implement Tool Class

```python
from typing import Dict, Any
from dingo.model.llm.agent.tools.base_tool import BaseTool
from dingo.model.llm.agent.tools.tool_registry import tool_register

@tool_register
class MyTool(BaseTool):
    """
    Brief description of what your tool does.

    This tool provides... [detailed description]

    Configuration:
        api_key: API key for the service
        max_results: Maximum number of results
        timeout: Request timeout in seconds
    """

    name = "my_tool"  # Unique tool identifier
    description = "Brief one-line description for agents"
    config: MyToolConfig = MyToolConfig()  # Default config

    @classmethod
    def execute(cls, **kwargs) -> Dict[str, Any]:
        """
        Execute the tool with given parameters.

        Args:
            **kwargs: Tool-specific parameters

        Returns:
            Dict with:
                - success: bool indicating if tool succeeded
                - result: Tool output (format depends on tool)
                - error: Error message if success=False
        """
        try:
            # Validate inputs
            if not kwargs.get('query'):
                return {
                    'success': False,
                    'error': 'Query parameter is required'
                }

            # Access configuration
            api_key = cls.config.api_key
            max_results = cls.config.max_results

            # Execute tool logic
            result = cls._perform_operation(kwargs['query'], api_key, max_results)

            return {
                'success': True,
                'result': result,
                'metadata': {
                    'query': kwargs['query'],
                    'timestamp': '...'
                }
            }

        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'error_type': type(e).__name__
            }

    @classmethod
    def _perform_operation(cls, query: str, api_key: str, max_results: int):
        """Private helper method for core logic"""
        # Implementation details...
        pass
```

### Tool Best Practices

1. **Error Handling**: Always return `{'success': False, 'error': ...}` rather than raising exceptions
2. **Validation**: Validate inputs early and return clear error messages
3. **Configuration**: Use Pydantic models with sensible defaults and validation
4. **Documentation**: Include docstrings explaining parameters and return format
5. **Testing**: Write comprehensive unit tests (see examples)

---

## Creating Custom Agents

### Step 1: Create Agent Class

```python
from typing import List, Dict, Any
from dingo.io import Data
from dingo.io.output.eval_detail import EvalDetail, QualityLabel
from dingo.model import Model
from dingo.model.llm.agent.base_agent import BaseAgent
from dingo.utils import log

@Model.llm_register("MyAgent")
class MyAgent(BaseAgent):
    """
    Brief description of your agent's purpose.

    This agent evaluates... [detailed description]

    Features:
        - Feature 1
        - Feature 2
        - Feature 3

    Configuration Example:
    {
        "name": "MyAgent",
        "config": {
            "key": "openai-api-key",
            "api_url": "https://api.openai.com/v1",
            "model": "gpt-4",
            "parameters": {
                "agent_config": {
                    "max_iterations": 3,
                    "tools": {
                        "my_tool": {
                            "api_key": "tool-api-key",
                            "max_results": 5
                        }
                    }
                }
            }
        }
    }
    """

    # Metadata for documentation
    _metric_info = {
        "category": "Your Category",
        "metric_name": "MyAgent",
        "description": "Brief description",
        "features": [
            "Feature 1",
            "Feature 2"
        ]
    }

    # Tools this agent can use
    available_tools = ["my_tool", "another_tool"]

    # Maximum reasoning iterations
    max_iterations = 5

    # Optional: Evaluation threshold
    threshold = 0.5

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        """
        Main evaluation method.

        Args:
            input_data: Data object with content and optional fields

        Returns:
            EvalDetail with evaluation results
        """
        try:
            # Step 1: Initialize
            cls.create_client()

            # Step 2: Execute agent logic
            result = cls._execute_workflow(input_data)

            # Step 3: Return evaluation
            return result

        except Exception as e:
            log.error(f"{cls.__name__} failed: {e}")
            result = EvalDetail(metric=cls.__name__)
            result.status = True  # Error condition
            result.label = [f"{QualityLabel.QUALITY_BAD_PREFIX}AGENT_ERROR"]
            result.reason = [f"Agent workflow failed: {str(e)}"]
            return result

    @classmethod
    def _execute_workflow(cls, input_data: Data) -> EvalDetail:
        """
        Core workflow implementation.

        This is where you implement your agent's reasoning logic.
        """
        # Example workflow:
        # 1. Analyze input
        analysis = cls._analyze_input(input_data)

        # 2. Use tools if needed
        if analysis['needs_tool']:
            tool_result = cls.execute_tool('my_tool', query=analysis['query'])

            if not tool_result['success']:
                # Handle tool failure
                result = EvalDetail(metric=cls.__name__)
                result.status = True
                result.label = [f"{QualityLabel.QUALITY_BAD_PREFIX}TOOL_FAILED"]
                result.reason = [f"Tool execution failed: {tool_result['error']}"]
                return result

        # 3. Make final decision using LLM
        final_decision = cls._make_decision(input_data, tool_result)

        # 4. Format result
        result = EvalDetail(metric=cls.__name__)
        result.status = final_decision['is_bad']
        result.label = final_decision['labels']
        result.reason = final_decision['reasons']

        return result

    @classmethod
    def _analyze_input(cls, input_data: Data) -> Dict[str, Any]:
        """Analyze input to determine next steps"""
        # Use LLM to analyze
        prompt = f"Analyze this content: {input_data.content}"
        messages = [{"role": "user", "content": prompt}]
        response = cls.send_messages(messages)

        # Parse response
        return {'needs_tool': True, 'query': '...'}

    @classmethod
    def _make_decision(cls, input_data: Data, tool_result: Dict) -> Dict[str, Any]:
        """Make final evaluation decision"""
        # Combine all information and decide
        return {
            'is_bad': False,
            'labels': [QualityLabel.QUALITY_GOOD],
            'reasons': ["Evaluation passed"]
        }

    @classmethod
    def plan_execution(cls, input_data: Data) -> List[Dict[str, Any]]:
        """
        Optional: Define execution plan for complex workflows.

        Not required if you implement eval() directly.
        """
        return []

    @classmethod
    def aggregate_results(cls, input_data: Data, results: List[Any]) -> EvalDetail:
        """
        Optional: Aggregate results from plan_execution.

        Not required if you implement eval() directly.
        """
        return EvalDetail(metric=cls.__name__)
```

### Agent Design Patterns

#### Pattern 1: Simple Workflow (Like AgentHallucination)

```python
@classmethod
def eval(cls, input_data: Data) -> EvalDetail:
    # Check preconditions
    if cls._has_required_data(input_data):
        # Direct path
        return cls._simple_evaluation(input_data)
    else:
        # Agent workflow with tools
        return cls._agent_workflow(input_data)
```

#### Pattern 2: Multi-Step Reasoning

```python
@classmethod
def eval(cls, input_data: Data) -> EvalDetail:
    steps = []

    for i in range(cls.max_iterations):
        # Analyze current state
        analysis = cls._analyze_state(input_data, steps)

        # Decide next action
        action = cls._decide_action(analysis)

        # Execute action (may call tools)
        result = cls._execute_action(action)
        steps.append(result)

        # Check if done
        if result['is_final']:
            break

    return cls._synthesize_result(steps)
```

#### Pattern 3: Delegation Pattern

```python
@classmethod
def eval(cls, input_data: Data) -> EvalDetail:
    # Use existing evaluator when appropriate
    if cls._can_use_existing(input_data):
        from dingo.model.llm.existing_model import ExistingModel
        result = ExistingModel.eval(input_data)
        # Add metadata
        result.reason.append("Delegated to ExistingModel")
        return result

    # Otherwise use agent workflow
    return cls._agent_workflow(input_data)
```

---

## Configuration

### Agent Configuration Structure

```json
{
  "evaluator": [{
    "fields": {
      "content": "response",
      "prompt": "question",
      "context": "contexts"
    },
    "evals": [{
      "name": "MyAgent",
      "config": {
        "key": "openai-api-key",
        "api_url": "https://api.openai.com/v1",
        "model": "gpt-4-turbo",
        "parameters": {
          "temperature": 0.1,
          "agent_config": {
            "max_iterations": 3,
            "tools": {
              "my_tool": {
                "api_key": "my-tool-api-key",
                "max_results": 10,
                "timeout": 30
              },
              "another_tool": {
                "config_key": "value"
              }
            }
          }
        }
      }
    }]
  }]
}
```

### Accessing Configuration in Agent

```python
# In your agent class
@classmethod
def some_method(cls):
    # Access LLM configuration
    model = cls.dynamic_config.model  # "gpt-4-turbo"
    temperature = cls.dynamic_config.parameters.get('temperature', 0)

    # Access agent-specific configuration
    agent_config = cls.dynamic_config.parameters.get('agent_config', {})
    max_iterations = agent_config.get('max_iterations', 5)

    # Get tool configuration
    tool_config = cls.get_tool_config('my_tool')
    # Returns: {"api_key": "...", "max_results": 10, "timeout": 30}
```

### Accessing Configuration in Tool

```python
# Configuration is injected automatically via config attribute
@classmethod
def execute(cls, **kwargs):
    api_key = cls.config.api_key  # From tool's config model
    max_results = cls.config.max_results

    # Use configuration...
```

### LangChain 1.0 Agent Configuration

Dingo supports two execution paths for agents:

1. **Legacy Path** (default): Manual loop with `plan_execution()` and `aggregate_results()`
2. **LangChain Path**: Uses LangChain 1.0's `create_agent` (enable with `use_agent_executor = True`)

#### Iteration Limits in LangChain 1.0

In LangChain 1.0, the `max_iterations` parameter is automatically converted to `recursion_limit` at runtime:

```python
class MyAgent(BaseAgent):
    use_agent_executor = True  # Enable LangChain path
    max_iterations = 10  # Converted to recursion_limit=10

    _metric_info = {"metric_name": "MyAgent", "description": "..."}
```

**Configuration in JSON:**
```json
{
  "name": "MyAgent",
  "config": {
    "parameters": {
      "agent_config": {
        "max_iterations": 10
      }
    }
  }
}
```

**How it works:**
- `max_iterations` in config → passed as `recursion_limit` to LangChain
- Default: 25 iterations (LangChain default)
- Range: 1-100 (adjust based on task complexity)

**Note**: LangChain 1.0 uses "recursion_limit" internally, but Dingo maintains the `max_iterations` terminology for consistency across both execution paths.

---

## Testing

### Testing Custom Tools

```python
import pytest
from unittest.mock import patch, MagicMock
from my_tool import MyTool, MyToolConfig

class TestMyTool:

    def setup_method(self):
        """Setup for each test"""
        MyTool.config = MyToolConfig(api_key="test_key")

    def test_successful_execution(self):
        """Test successful tool execution"""
        result = MyTool.execute(query="test query")

        assert result['success'] is True
        assert 'result' in result

    def test_missing_query(self):
        """Test error handling for missing query"""
        result = MyTool.execute()

        assert result['success'] is False
        assert 'Query parameter is required' in result['error']

    @patch('external_api.Client')
    def test_with_mocked_api(self, mock_client):
        """Test with mocked external API"""
        mock_response = {"data": "test"}
        mock_client_instance = MagicMock()
        mock_client_instance.search.return_value = mock_response
        mock_client.return_value = mock_client_instance

        result = MyTool.execute(query="test")

        assert result['success'] is True
        mock_client_instance.search.assert_called_once()
```

### Testing Custom Agents

```python
import pytest
from unittest.mock import patch
from dingo.io import Data
from my_agent import MyAgent
from dingo.config.input_args import EvaluatorLLMArgs

class TestMyAgent:

    def setup_method(self):
        """Setup for each test"""
        MyAgent.dynamic_config = EvaluatorLLMArgs(
            key="test_key",
            api_url="https://api.test.com",
            model="gpt-4"
        )

    def test_agent_registration(self):
        """Test that agent is properly registered"""
        from dingo.model import Model
        Model.load_model()
        assert "MyAgent" in Model.llm_name_map

    @patch.object(MyAgent, 'execute_tool')
    @patch.object(MyAgent, 'send_messages')
    def test_workflow_execution(self, mock_send, mock_tool):
        """Test complete agent workflow"""
        # Mock LLM responses
        mock_send.return_value = "Analysis result"

        # Mock tool responses
        mock_tool.return_value = {
            'success': True,
            'result': 'Tool output'
        }

        # Execute
        data = Data(content="Test content")
        result = MyAgent.eval(data)

        # Verify
        assert result.status is not None
        assert mock_send.called
        assert mock_tool.called
```

---

## Best Practices

### Agent Development

1. **Start Simple**: Begin with basic workflow, add complexity as needed
2. **Error Handling**: Wrap workflow in try/except, return meaningful error messages
3. **Logging**: Use `log.info()`, `log.warning()`, `log.error()` for debugging
4. **Delegation**: Reuse existing evaluators when possible
5. **Documentation**: Include comprehensive docstrings and configuration examples
6. **Metadata**: Add `_metric_info` for documentation generation

### Tool Development

1. **Single Responsibility**: Each tool should do one thing well
2. **Configuration**: Use Pydantic models with validation
3. **Return Format**: Always return dict with `success` boolean
4. **Error Messages**: Provide actionable error messages
5. **Testing**: Write unit tests covering success and error cases

### Performance

1. **Limit Iterations**: Set reasonable `max_iterations` to prevent infinite loops
2. **Batch Operations**: If calling tool multiple times, consider batching
3. **Caching**: Consider caching expensive operations
4. **Timeouts**: Set appropriate timeouts for external API calls

### Security

1. **API Keys**: Never hardcode API keys, use configuration
2. **Input Validation**: Validate all inputs before passing to external services
3. **Rate Limiting**: Respect API rate limits in tools
4. **Error Information**: Don't expose sensitive information in error messages

---

## Examples

### Complete Example Files

- **AgentHallucination**: `dingo/model/llm/agent/agent_hallucination.py` - Production agent with web search
- **AgentFactCheck**: `examples/agent/agent_executor_example.py` - LangChain 1.0 agent example
- **TavilySearch Tool**: `dingo/model/llm/agent/tools/tavily_search.py` - Web search tool implementation

**Note**: For complete implementation examples, refer to the files above. They demonstrate real-world patterns for agent and tool development.

### Quick Start: Custom Fact Checker

```python
from dingo.model.llm.agent.base_agent import BaseAgent
from dingo.model import Model
from dingo.io import Data
from dingo.io.output.eval_detail import EvalDetail

@Model.llm_register("FactChecker")
class FactChecker(BaseAgent):
    """Simple fact checker using web search"""

    available_tools = ["tavily_search"]
    max_iterations = 1

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        cls.create_client()

        # Search for facts
        search_result = cls.execute_tool(
            'tavily_search',
            query=input_data.content
        )

        if not search_result['success']:
            return cls._create_error_result("Search failed")

        # Verify with LLM
        prompt = f"""
        Content: {input_data.content}
        Search Results: {search_result['answer']}

        Are there any factual errors? Respond with YES or NO.
        """

        response = cls.send_messages([
            {"role": "user", "content": prompt}
        ])

        result = EvalDetail(metric="FactChecker")
        result.status = "YES" in response.upper()
        result.reason = [f"Verification: {response}"]

        return result
```

### Running Your Agent

```python
from dingo.config import InputArgs
from dingo.exec import Executor

config = {
    "input_path": "data.jsonl",
    "output_path": "outputs/",
    "dataset": {"source": "local", "format": "jsonl"},
    "evaluator": [{
        "fields": {"content": "text"},
        "evals": [{
            "name": "FactChecker",
            "config": {
                "key": "openai-key",
                "api_url": "https://api.openai.com/v1",
                "model": "gpt-4",
                "parameters": {
                    "agent_config": {
                        "tools": {
                            "tavily_search": {"api_key": "tavily-key"}
                        }
                    }
                }
            }
        }]
    }]
}

input_args = InputArgs(**config)
executor = Executor.exec_map["local"](input_args)
summary = executor.execute()
```

---

## Troubleshooting

### Common Issues

**Agent not found:**
- Ensure file is in `dingo/model/llm/agent/` directory
- Check `@Model.llm_register("Name")` decorator is present
- Run `Model.load_model()` to trigger auto-discovery

**Tool not found:**
- Ensure `@tool_register` decorator is present
- Check tool name matches string in `available_tools`
- Verify tool file is imported in `dingo/model/llm/agent/tools/__init__.py`

**Configuration not working:**
- Check JSON structure matches expected format
- Verify `parameters.agent_config.tools.{tool_name}` structure
- Use Pydantic validation to catch config errors early

**Tests failing:**
- Patch at correct import path (where object is used, not defined)
- Mock external APIs to avoid network calls
- Check test isolation (use `setup_method` to reset state)

---

## Additional Resources

- [AgentHallucination Implementation](../dingo/model/llm/agent/agent_hallucination.py)
- [BaseAgent Source](../dingo/model/llm/agent/base_agent.py)
- [Tool Registry Source](../dingo/model/llm/agent/tools/tool_registry.py)
- [Tavily Search Example](../dingo/model/llm/agent/tools/tavily_search.py)
- [Example Usage](../examples/agent/agent_hallucination_example.py)

---

## Contributing

When contributing new agents or tools:

1. Follow existing code style (flake8, isort)
2. Add comprehensive tests (aim for >80% coverage)
3. Include docstrings and type hints
4. Update this guide if adding new patterns
5. Add examples in `examples/agent/`
6. Update metrics documentation in `docs/metrics.md`

For questions or suggestions, please open an issue on GitHub.
