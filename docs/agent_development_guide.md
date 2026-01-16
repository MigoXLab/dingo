# Agent-Based Evaluation Development Guide

## Overview

This guide explains how to create custom agent-based evaluators and tools in Dingo. Agent-based evaluation enhances traditional rule and LLM evaluators by adding multi-step reasoning, tool usage, and adaptive context gathering.

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Agent Implementation Patterns](#agent-implementation-patterns)
3. [Creating Custom Tools](#creating-custom-tools)
4. [Creating Custom Agents](#creating-custom-agents)
5. [Configuration](#configuration)
6. [Testing](#testing)
7. [Best Practices](#best-practices)
8. [Examples](#examples)

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

## Agent Implementation Patterns

Dingo supports two complementary patterns for implementing agent-based evaluators. Both patterns share the same configuration interface and are transparent to users, allowing you to choose the approach that best fits your needs.

### Pattern Comparison

| Aspect | LangChain-Based | Custom Workflow |
|--------|-----------------|-----------------|
| **Control** | Framework-driven | Developer-driven |
| **Complexity** | Simple (declarative) | Moderate (imperative) |
| **Flexibility** | Limited to LangChain patterns | Unlimited |
| **Code Volume** | Low (~100 lines) | Medium (~200 lines) |
| **Best For** | Multi-step reasoning | Workflow composition |
| **Example** | AgentFactCheck | AgentHallucination |

### Pattern 1: LangChain-Based Agents (Framework-Driven)

**Philosophy**: Let the framework handle orchestration, you focus on the task.

#### When to Use

✅ **Complex multi-step reasoning required**
   The agent needs to make multiple decisions and tool calls adaptively

✅ **Benefit from LangChain's battle-tested patterns**
   Leverage proven agent orchestration and error handling

✅ **Prefer declarative over imperative style**
   Define what the agent should do, not how to do it step-by-step

✅ **Want rapid prototyping**
   Get a working agent with minimal code

#### When NOT to Use

❌ **Need fine-grained control over every step**
   You want to control exactly when and how tools are called

❌ **Want to compose with existing Dingo evaluators**
   You need to call other evaluators as part of the workflow

❌ **Have domain-specific workflow requirements**
   Your workflow doesn't fit the ReAct pattern well

#### Key Implementation Steps

1. Set `use_agent_executor = True` to enable LangChain path
2. Override `_format_agent_input()` to structure input for the agent
3. Override `_get_system_prompt()` to provide task-specific instructions
4. Implement `aggregate_results()` to parse agent output into EvalDetail
5. Return empty list in `plan_execution()` (not used with LangChain path)

#### Example: AgentFactCheck

```python
from dingo.model import Model
from dingo.model.llm.agent.base_agent import BaseAgent
from dingo.io import Data
from dingo.io.output.eval_detail import EvalDetail
from typing import Any, List

@Model.llm_register("AgentFactCheck")
class AgentFactCheck(BaseAgent):
    """LangChain-based fact-checking agent."""

    use_agent_executor = True  # Enable LangChain agent mode
    available_tools = ["tavily_search"]
    max_iterations = 5

    @classmethod
    def _format_agent_input(cls, input_data: Data) -> str:
        """Structure input for the agent."""
        parts = []

        if hasattr(input_data, 'prompt') and input_data.prompt:
            parts.append(f"**Question:**\n{input_data.prompt}")

        parts.append(f"**Response to Evaluate:**\\n{input_data.content}")

        if hasattr(input_data, 'context') and input_data.context:
            parts.append(f"**Context:**\\n{input_data.context}")
        else:
            parts.append("**Context:** None - use web search to verify")

        return "\\n\\n".join(parts)

    @classmethod
    def _get_system_prompt(cls, input_data: Data) -> str:
        """Provide task-specific instructions."""
        has_context = hasattr(input_data, 'context') and input_data.context

        base = """You are a fact-checking agent with web search capabilities.

Your task:
1. Analyze the Question and Response provided"""

        context_instruction = (
            "\\n2. Context is provided - evaluate the Response against it"
            "\\n3. You MAY use web search for additional verification if needed"
            if has_context else
            "\\n2. NO Context is available - you MUST use web search to verify facts"
            "\\n3. Search for reliable sources to fact-check the response"
        )

        output_format = """

**Output Format:**
HALLUCINATION_DETECTED: [YES or NO]
EXPLANATION: [Your analysis]
EVIDENCE: [Supporting facts]
SOURCES: [URLs, one per line with - prefix]

Be precise. Start with "HALLUCINATION_DETECTED:" followed by YES or NO."""

        return base + context_instruction + output_format

    @classmethod
    def aggregate_results(cls, input_data: Data, results: List[Any]) -> EvalDetail:
        """Parse agent output into EvalDetail."""
        if not results:
            return cls._create_error_result("No results from agent")

        agent_result = results[0]
        output = agent_result.get('output', '')

        # Parse hallucination status
        has_hallucination = cls._detect_hallucination_from_output(output)

        # Build result
        result = EvalDetail(metric=cls.__name__)
        result.status = has_hallucination
        result.label = ["BAD:HALLUCINATION" if has_hallucination else "GOOD"]
        result.reason = [f"Agent Analysis:\\n{output}"]

        return result

    @classmethod
    def plan_execution(cls, input_data: Data) -> List[Dict]:
        """Not used with LangChain agent (agent handles planning)."""
        return []
```

#### Pros and Cons

**Pros:**
- ✅ Less code to write and maintain
- ✅ Framework handles tool orchestration automatically
- ✅ Automatic retry and error handling
- ✅ Battle-tested ReAct pattern from LangChain

**Cons:**
- ❌ Limited to LangChain's agent patterns
- ❌ Less control over execution flow
- ❌ Debugging can be harder (framework abstraction)
- ❌ Cannot compose with existing Dingo evaluators

---

### Pattern 2: Custom Workflow Agents (Imperative)

**Philosophy**: Explicit control over every step, compose with existing evaluators.

#### When to Use

✅ **Need fine-grained workflow control**
   You want to control exactly what happens at each step

✅ **Want to compose with existing Dingo evaluators**
   Reuse evaluators like LLMHallucination within your workflow

✅ **Prefer explicit over implicit behavior**
   You want to see and control every tool call and LLM interaction

✅ **Have domain-specific requirements**
   Your workflow has unique steps that don't fit standard patterns

✅ **Need conditional logic between steps**
   Different paths based on intermediate results

#### When NOT to Use

❌ **Want framework-managed multi-step reasoning**
   You prefer the agent to figure out the steps autonomously

❌ **Prefer minimal code**
   You want a quick solution without manual orchestration

❌ **Need rapid prototyping**
   You don't want to write explicit workflow logic

❌ **Complex reasoning benefits from ReAct**
   Your task requires adaptive multi-step reasoning

#### Key Implementation Steps

1. Implement custom `eval()` method with explicit workflow logic
2. Manually call `execute_tool()` for each tool operation
3. Manually call `send_messages()` for LLM interactions
4. Optionally delegate to existing evaluators (e.g., LLMHallucination)
5. Return `EvalDetail` directly from `eval()`

#### Example: AgentHallucination

```python
from dingo.model import Model
from dingo.model.llm.agent.base_agent import BaseAgent
from dingo.io import Data
from dingo.io.output.eval_detail import EvalDetail
from typing import List

@Model.llm_register("AgentHallucination")
class AgentHallucination(BaseAgent):
    """Custom workflow hallucination detector."""

    available_tools = ["tavily_search"]
    max_iterations = 3

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        """Main evaluation method with custom workflow."""
        cls.create_client()  # Initialize LLM client

        # Step 1: Check if context is available
        has_context = cls._has_context(input_data)

        if has_context:
            # Path A: Use existing evaluator
            return cls._eval_with_context(input_data)
        else:
            # Path B: Custom workflow with web search
            return cls._eval_with_web_search(input_data)

    @classmethod
    def _eval_with_web_search(cls, input_data: Data) -> EvalDetail:
        """Execute custom workflow: extract claims → search → evaluate."""

        # Step 2: Extract factual claims (manual LLM call)
        claims = cls._extract_claims(input_data)

        if not claims:
            return cls._create_result(
                status=False,
                reason="No factual claims found to verify"
            )

        # Step 3: Search web for each claim (manual tool calls)
        search_results = []
        for claim in claims:
            result = cls.execute_tool('tavily_search', query=claim)
            if result.get('success'):
                search_results.append(result['result'])

        # Step 4: Synthesize context from search results
        context = cls._synthesize_context(search_results)

        # Step 5: Evaluate with synthesized context (delegate to evaluator)
        data_with_context = Data(
            content=input_data.content,
            context=context
        )
        return cls._eval_with_context(data_with_context)

    @classmethod
    def _extract_claims(cls, input_data: Data) -> List[str]:
        """Extract factual claims using LLM."""
        prompt = f"""Extract all factual claims from this text:
{input_data.content}

Return a JSON list of claims."""

        messages = [{"role": "user", "content": prompt}]
        response = cls.send_messages(messages)

        # Parse claims from response
        import json
        try:
            claims = json.loads(response)
            return claims if isinstance(claims, list) else []
        except json.JSONDecodeError:
            return []

    @classmethod
    def _synthesize_context(cls, search_results: List[Dict]) -> str:
        """Synthesize context from search results using LLM."""
        results_text = "\\n".join([
            f"Source: {r.get('title', 'Unknown')}\\n{r.get('content', '')}"
            for r in search_results
        ])

        prompt = f"""Synthesize the following search results into a coherent context:

{results_text}

Provide a concise summary of the key facts."""

        messages = [{"role": "user", "content": prompt}]
        return cls.send_messages(messages)

    @classmethod
    def plan_execution(cls, input_data: Data) -> List[Dict]:
        """Not used with custom eval() method."""
        return []
```

#### Pros and Cons

**Pros:**
- ✅ Full control over execution flow
- ✅ Can compose with existing Dingo evaluators
- ✅ Explicit error handling at each step
- ✅ Easy to debug (no framework magic)
- ✅ Can implement complex conditional logic

**Cons:**
- ❌ More code to write and maintain
- ❌ Manual tool orchestration required
- ❌ Need to handle retries and errors manually
- ❌ More imperative, less declarative

---

### Decision Tree: Which Pattern Should I Use?

```
Start
  │
  ├─ Do you need to compose with existing Dingo evaluators?
  │    ├─ Yes → Use Custom Pattern (AgentHallucination style)
  │    └─ No → Continue
  │
  ├─ Is your workflow highly domain-specific?
  │    ├─ Yes → Use Custom Pattern
  │    └─ No → Continue
  │
  ├─ Do you prefer explicit control over every step?
  │    ├─ Yes → Use Custom Pattern
  │    └─ No → Continue
  │
  └─ Default → Use LangChain Pattern (AgentFactCheck style)
       ✅ Simpler, less code, battle-tested
```

### Can I Mix Both Patterns?

**Yes!** You can use both patterns in the same project:

```json
{
  "evaluator": [{
    "evals": [
      {"name": "AgentFactCheck"},      // LangChain-based
      {"name": "AgentHallucination"}   // Custom workflow
    ]
  }]
}
```

Users don't need to know which pattern you used - both share the same configuration interface and are transparent at the user level.

### Migration Path

#### From Custom to LangChain

1. Set `use_agent_executor = True`
2. Move workflow logic from `eval()` to `_get_system_prompt()`
3. Implement `aggregate_results()` to parse agent output
4. Remove custom `eval()` implementation

#### From LangChain to Custom

1. Remove `use_agent_executor` flag (or set to False)
2. Implement custom `eval()` method with workflow logic
3. Manually call `execute_tool()` and `send_messages()`
4. Keep `plan_execution()` returning empty list

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

### Customizing Agent Input: The `_format_agent_input` Extension Point

When using LangChain agents (`use_agent_executor = True`), you can customize how input data is formatted before being sent to the agent. This is essential for agents that need to work with structured data like prompt, content, and context together.

#### Default Behavior

By default, BaseAgent passes only `input_data.content` to LangChain agents:

```python
# Default implementation in BaseAgent
@classmethod
def _format_agent_input(cls, input_data: Data) -> str:
    """Format input data into text for LangChain agent."""
    return input_data.content
```

#### Overriding for Custom Formatting

To include additional fields (prompt, context, etc.), override `_format_agent_input` in your agent:

```python
from dingo.model.llm.agent.base_agent import BaseAgent
from dingo.io import Data

class MyCustomAgent(BaseAgent):
    use_agent_executor = True
    available_tools = ["tavily_search"]

    @classmethod
    def _format_agent_input(cls, input_data: Data) -> str:
        """Format prompt + content + context for agent."""
        parts = []

        # Include prompt if available
        if hasattr(input_data, 'prompt') and input_data.prompt:
            parts.append(f"**Question:**\n{input_data.prompt}")

        # Always include content
        parts.append(f"**Response to Evaluate:**\n{input_data.content}")

        # Include context if available
        if hasattr(input_data, 'context') and input_data.context:
            if isinstance(input_data.context, list):
                context_str = "\n".join(f"- {c}" for c in input_data.context)
            else:
                context_str = str(input_data.context)
            parts.append(f"**Context:**\n{context_str}")
        else:
            parts.append("**Context:** None provided")

        return "\n\n".join(parts)
```

#### Best Practices for Input Formatting

1. **Safe Attribute Access**: Use `hasattr()` and check for truthiness
   ```python
   if hasattr(input_data, 'prompt') and input_data.prompt:
       # Safe to use input_data.prompt
   ```

2. **Clear Structure**: Use markdown-style headers for readability
   ```python
   parts.append(f"**Section Name:**\n{content}")
   ```

3. **Handle Multiple Types**: Context might be string or list
   ```python
   if isinstance(input_data.context, list):
       context_str = "\n".join(f"- {c}" for c in input_data.context)
   else:
       context_str = str(input_data.context)
   ```

4. **Provide Guidance**: Tell the agent what to do when data is missing
   ```python
   parts.append("**Context:** None provided - use web search to verify")
   ```

### Reference Implementation: AgentFactCheck

AgentFactCheck demonstrates a production-ready implementation using `_format_agent_input` with structured output parsing following LangChain 2025 best practices.

#### Key Features

1. **Autonomous Search Control**: Agent decides when to use web search based on context availability
2. **Structured Output**: Uses explicit format instructions for reliable parsing
3. **Robust Error Handling**: Multi-layer fallback for parsing agent responses
4. **Context-Aware Prompts**: System prompt adapts based on input data
5. **Enhanced Evidence Citation**: Extracts and displays source URLs for verification (v1.1)

#### Implementation Example

```python
from typing import Any, Dict, List
import re
from dingo.io import Data
from dingo.io.input.required_field import RequiredField
from dingo.io.output.eval_detail import EvalDetail, QualityLabel
from dingo.model import Model
from dingo.model.llm.agent.base_agent import BaseAgent

@Model.llm_register("AgentFactCheck")
class AgentFactCheck(BaseAgent):
    """
    LangChain-based fact-checking agent with autonomous search control.

    - With context: Agent MAY use web search for additional verification
    - Without context: Agent MUST use web search to verify facts
    """

    use_agent_executor = True  # Enable LangChain agent
    available_tools = ["tavily_search"]
    max_iterations = 5

    _required_fields = [RequiredField.PROMPT, RequiredField.CONTENT]
    # Note: CONTEXT is optional - agent adapts

    @classmethod
    def _format_agent_input(cls, input_data: Data) -> str:
        """Format prompt + content + context for agent."""
        parts = []

        if hasattr(input_data, 'prompt') and input_data.prompt:
            parts.append(f"**Question:**\n{input_data.prompt}")

        parts.append(f"**Response to Evaluate:**\n{input_data.content}")

        if hasattr(input_data, 'context') and input_data.context:
            if isinstance(input_data.context, list):
                context_str = "\n".join(f"- {c}" for c in input_data.context)
            else:
                context_str = str(input_data.context)
            parts.append(f"**Context:**\n{context_str}")
        else:
            parts.append("**Context:** None provided - use web search to verify")

        return "\n\n".join(parts)

    @classmethod
    def _get_system_prompt(cls, input_data: Data) -> str:
        """System prompt adapts based on context availability."""
        has_context = hasattr(input_data, 'context') and input_data.context

        base_instructions = """You are a fact-checking agent with web search capabilities.

Your task:
1. Analyze the Question and Response provided"""

        if has_context:
            context_instruction = """
2. Context is provided - evaluate the Response against it
3. You MAY use web search for additional verification if needed
4. Make your own decision about whether web search is necessary"""
        else:
            context_instruction = """
2. NO Context is available - you MUST use web search to verify facts
3. Search for reliable sources to fact-check the response"""

        # Following LangChain best practices: explicit output format
        output_format = """

**IMPORTANT: You must return your analysis in exactly this format:**

HALLUCINATION_DETECTED: [YES or NO]
EXPLANATION: [Your detailed analysis]
EVIDENCE: [Supporting sources or facts]
SOURCES: [List of URLs consulted, one per line with - prefix]

Example:
HALLUCINATION_DETECTED: YES
EXPLANATION: The response claims incorrect information.
EVIDENCE: According to reliable sources, this is false.
SOURCES:
- https://example.com/source1
- https://example.com/source2

Be precise and clear. Start your response with "HALLUCINATION_DETECTED:" followed by YES or NO.
Always include SOURCES with specific URLs when you perform web searches."""

        return base_instructions + context_instruction + output_format

    @classmethod
    def aggregate_results(cls, input_data: Data, results: List[Any]) -> EvalDetail:
        """Parse agent output to determine hallucination status."""
        if not results:
            return cls._create_error_result("No results from agent")

        agent_result = results[0]

        if not agent_result.get('success', True):
            error_msg = agent_result.get('error', 'Unknown error')
            return cls._create_error_result(error_msg)

        output = agent_result.get('output', '')

        if not output or not output.strip():
            return cls._create_error_result("Agent returned empty output")

        # Parse structured output
        has_hallucination = cls._detect_hallucination_from_output(output)

        result = EvalDetail(metric=cls.__name__)
        result.status = has_hallucination
        result.label = [
            f"{QualityLabel.QUALITY_BAD_PREFIX}HALLUCINATION"
            if has_hallucination
            else QualityLabel.QUALITY_GOOD
        ]
        result.reason = [
            f"Agent Analysis:\n{output}",
            f"🔍 Web searches: {len(agent_result.get('tool_calls', []))}",
            f"🤖 Reasoning steps: {agent_result.get('reasoning_steps', 0)}"
        ]

        return result

    @classmethod
    def _detect_hallucination_from_output(cls, output: str) -> bool:
        """
        Parse agent output using structured format.

        Strategy:
        1. Regex match for "HALLUCINATION_DETECTED: YES/NO"
        2. Check response start for marker
        3. Fallback to keyword detection
        """
        if not output:
            return False

        # Primary: Regex match
        match = re.search(r'HALLUCINATION_DETECTED:\s*(YES|NO)', output, re.IGNORECASE)
        if match:
            return match.group(1).upper() == 'YES'

        # Fallback: Keyword detection (check negatives first!)
        output_lower = output.lower()

        if any(kw in output_lower for kw in ['no hallucination detected', 'factually accurate']):
            return False
        if any(kw in output_lower for kw in ['hallucination detected', 'factual error']):
            return True

        return False  # Default to no hallucination

    @classmethod
    def _create_error_result(cls, error_message: str) -> EvalDetail:
        """Create error result."""
        result = EvalDetail(metric=cls.__name__)
        result.status = True
        result.label = [f"{QualityLabel.QUALITY_BAD_PREFIX}AGENT_ERROR"]
        result.reason = [f"Agent evaluation failed: {error_message}"]
        return result

    @classmethod
    def plan_execution(cls, input_data: Data) -> List[Dict[str, Any]]:
        """Not used with LangChain agent (agent handles planning)."""
        return []
```

#### Why This Pattern Works

1. **Structured Output Format**: Explicitly defines expected format in system prompt
2. **Regex Parsing**: Reliable primary parsing method
3. **Fallback Layers**: Keyword detection as safety net
4. **Error Handling**: Returns error status rather than crashing
5. **Context Awareness**: Adapts behavior based on available data

#### Configuration Example

```json
{
  "name": "AgentFactCheck",
  "config": {
    "key": "your-openai-api-key",
    "api_url": "https://api.openai.com/v1",
    "model": "gpt-4-turbo",
    "parameters": {
      "temperature": 0.1,
      "max_tokens": 16384,
      "agent_config": {
        "max_iterations": 5,
        "tools": {
          "tavily_search": {
            "api_key": "your-tavily-api-key",
            "max_results": 5,
            "search_depth": "advanced"
          }
        }
      }
    }
  }
}
```

#### Testing AgentFactCheck

```python
from dingo.io import Data
from dingo.model.llm.agent.agent_fact_check import AgentFactCheck

# Test with context
data_with_context = Data(
    prompt="What is the capital of France?",
    content="The capital is Berlin",
    context="France's capital is Paris"
)

# Test without context
data_without_context = Data(
    prompt="What year was Python created?",
    content="Python was created in 1995"
)

# Agent will adapt behavior automatically
result1 = AgentFactCheck.eval(data_with_context)
result2 = AgentFactCheck.eval(data_without_context)
```

**Full implementation**: `dingo/model/llm/agent/agent_fact_check.py`
**Tests**: `test/scripts/model/llm/agent/test_agent_fact_check.py` (35 tests)

#### Enhanced Evidence Citation (v1.1)

AgentFactCheck includes a feature to extract and display source URLs from the agent's output, making fact-checking results more transparent and verifiable.

**How it works**:

1. **System Prompt**: Agent is instructed to include a SOURCES section with URLs
2. **Extraction**: `_extract_sources_from_output()` parses the SOURCES section
3. **Display**: Sources are appended to the result's reason field

**Implementation**:

```python
@classmethod
def _extract_sources_from_output(cls, output: str) -> List[str]:
    """Extract source URLs from agent output."""
    sources = []
    in_sources_section = False

    for line in output.split('\n'):
        line = line.strip()

        if line.upper().startswith('SOURCES:'):
            in_sources_section = True
            continue

        if in_sources_section:
            # Check if we've reached a new section
            if line and ':' in line:
                section_header = line.split(':')[0].upper()
                if section_header in ['EXPLANATION', 'EVIDENCE', 'HALLUCINATION_DETECTED']:
                    break

            # Extract URL (with - or • prefix, or direct URL)
            if line.startswith(('- ', '• ', 'http://', 'https://')):
                url = line.lstrip('- •').strip()
                if url:
                    sources.append(url)

    return sources
```

**Usage in aggregate_results**:

```python
# Extract sources from output
sources = cls._extract_sources_from_output(output)

# Add sources section to result
result.reason.append("")
if sources:
    result.reason.append("📚 Sources consulted:")
    for source in sources:
        result.reason.append(f"   • {source}")
else:
    result.reason.append("📚 Sources: None explicitly cited")
```

**Benefits**:
- ✅ Increases transparency of agent's fact-checking process
- ✅ Allows users to verify the agent's judgment independently
- ✅ Provides attribution for evidence used in evaluation
- ✅ Meets academic and professional citation standards

**Example Output**:

```
Agent Analysis:
HALLUCINATION_DETECTED: YES
EXPLANATION: The response claims the Eiffel Tower is 450 meters tall, but it is actually 330 meters.
EVIDENCE: According to the official Eiffel Tower website, the height is 330 meters including antennas.
SOURCES:
- https://www.toureiffel.paris/en/the-monument
- https://en.wikipedia.org/wiki/Eiffel_Tower

🔍 Web searches performed: 2
🤖 Reasoning steps: 4
⚙️  Agent autonomously decided: Use web search

📚 Sources consulted:
   • https://www.toureiffel.paris/en/the-monument
   • https://en.wikipedia.org/wiki/Eiffel_Tower
```

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
