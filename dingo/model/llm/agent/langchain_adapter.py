"""
LangChain Adapter for Dingo Agent Tools

Bridges Dingo's BaseTool system with LangChain's StructuredTool interface.
Preserves Dingo's configuration injection and tool registry patterns.
"""

import inspect
import json
from typing import Any, Callable, Dict, Optional, Type

from pydantic import BaseModel, Field, create_model

from dingo.model.llm.agent.tools import BaseTool, ToolRegistry
from dingo.utils import log


def create_tool_input_schema(tool_class: Type[BaseTool]) -> Type[BaseModel]:
    """
    Inspect tool's execute() signature and create Pydantic input schema.

    Example:
        For TavilySearch.execute(query: str, max_results: int = 5):
        Returns pydantic model with:
            query: str (required)
            max_results: int = 5 (optional)

    Args:
        tool_class: BaseTool subclass to analyze

    Returns:
        Pydantic BaseModel class representing tool input schema
    """
    try:
        sig = inspect.signature(tool_class.execute)
        fields = {}

        for param_name, param in sig.parameters.items():
            # Skip 'cls' and variadic parameters
            if param_name in ('cls', 'self', 'kwargs'):
                continue

            # Get type hint (default to str if not specified)
            param_type = param.annotation if param.annotation != inspect.Parameter.empty else str

            # Check if has default value
            if param.default != inspect.Parameter.empty:
                # Optional field with default
                fields[param_name] = (param_type, Field(default=param.default))
            else:
                # Required field
                fields[param_name] = (param_type, Field(...))

        # Create dynamic Pydantic model
        model_name = f'{tool_class.__name__}Input'
        return create_model(model_name, **fields)

    except Exception as e:
        log.error(f"Failed to create input schema for {tool_class.__name__}: {e}")
        # Return a minimal schema
        return create_model(f'{tool_class.__name__}Input', query=(str, Field(...)))


class DingoToolWrapper:
    """
    Wraps Dingo BaseTool to work with LangChain.
    Preserves Dingo's configuration and tool registry patterns.
    """

    @staticmethod
    def dingo_to_langchain(
        tool_name: str,
        agent_class: Optional[Any] = None
    ):
        """
        Convert a Dingo tool to LangChain StructuredTool.

        Args:
            tool_name: Name of tool in ToolRegistry
            agent_class: Agent class for config injection (optional)

        Returns:
            LangChain StructuredTool

        Preserves:
            - Dingo configuration via agent_class.get_tool_config()
            - Tool registry discovery
            - Error handling and logging
        """
        try:
            from langchain_core.tools import StructuredTool
        except ImportError:
            log.error(
                "LangChain not installed. Install with: pip install langchain langchain-openai"
            )
            raise

        try:
            # Get tool from Dingo registry
            tool_class = ToolRegistry.get(tool_name)

            # Configure tool (from agent config if provided)
            if agent_class and hasattr(agent_class, 'get_tool_config'):
                config_dict = agent_class.get_tool_config(tool_name)
                if config_dict:
                    tool_class.update_config(config_dict)
                    log.debug(f"Applied config to {tool_name}: {config_dict}")

            # Create input schema from tool's execute() signature
            input_schema = create_tool_input_schema(tool_class)

            # Create wrapper function
            def tool_func(**kwargs) -> str:
                """
                Wrapper that calls Dingo tool and formats output for LangChain.

                LangChain expects string return values.
                Dingo tools return Dict with 'success' key.
                """
                try:
                    result = tool_class.execute(**kwargs)

                    # Format for LangChain (return string)
                    if isinstance(result, dict):
                        if result.get('success', True):
                            # Success case - format as JSON
                            return json.dumps({
                                'success': True,
                                'data': {
                                    'answer': result.get('answer', ''),
                                    'results': result.get('results', []),
                                    'count': len(result.get('results', []))
                                }
                            }, ensure_ascii=False)
                        else:
                            # Error case
                            return json.dumps({
                                'success': False,
                                'error': result.get('error', 'Unknown error')
                            }, ensure_ascii=False)
                    else:
                        # Non-dict result, convert to string
                        return str(result)

                except Exception as e:
                    log.error(f"Tool {tool_name} error: {e}")
                    return json.dumps({
                        'success': False,
                        'error': str(e)
                    }, ensure_ascii=False)

            # Create LangChain StructuredTool
            lc_tool = StructuredTool(
                name=tool_class.name,
                description=tool_class.description,
                func=tool_func,
                args_schema=input_schema
            )

            log.debug(f"Converted Dingo tool '{tool_name}' to LangChain StructuredTool")
            return lc_tool

        except Exception as e:
            log.error(f"Failed to convert tool '{tool_name}' to LangChain: {e}")
            raise

    @staticmethod
    def langchain_to_dingo(tool_result: str) -> Dict[str, Any]:
        """
        Convert LangChain tool output back to Dingo format.

        AgentExecutor returns tool results as strings.
        This converts back to Dingo's Dict format for consistency.

        Args:
            tool_result: String result from LangChain tool

        Returns:
            Dict in Dingo format with 'success' key
        """
        try:
            # Try to parse as JSON
            return json.loads(tool_result)
        except (json.JSONDecodeError, TypeError):
            # Not JSON, wrap as success result
            return {
                'success': True,
                'result': tool_result
            }


# Convenience function
def convert_dingo_tools(tool_names: list, agent_class: Optional[Any] = None):
    """
    Convert multiple Dingo tools to LangChain format.

    Args:
        tool_names: List of tool names from ToolRegistry
        agent_class: Agent class for config injection (optional)

    Returns:
        List of LangChain StructuredTools

    Example:
        tools = convert_dingo_tools(["tavily_search", "calculator"], MyAgent)
    """
    lc_tools = []
    for tool_name in tool_names:
        try:
            tool = DingoToolWrapper.dingo_to_langchain(tool_name, agent_class)
            lc_tools.append(tool)
        except Exception as e:
            log.error(f"Failed to convert tool '{tool_name}': {e}")
            # Continue with other tools

    return lc_tools
