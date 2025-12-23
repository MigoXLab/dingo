"""
Tool Registry for Agent Framework

This module provides tool registration and discovery similar to Dingo's Model registry.
Tools self-register using the @tool_register decorator and can be retrieved by name.
"""

from typing import Dict, Type

from dingo.model.llm.agent.tools.base_tool import BaseTool
from dingo.utils import log


class ToolRegistry:
    """
    Registry for agent tools.

    Follows the same pattern as Dingo's Model registry for consistency.
    Tools are registered via decorator and retrieved by name.
    """

    _tools: Dict[str, Type[BaseTool]] = {}

    @classmethod
    def register(cls, tool_class: Type[BaseTool]) -> Type[BaseTool]:
        """
        Register a tool class in the registry.

        Args:
            tool_class: Tool class to register

        Returns:
            The registered tool class (for decorator chaining)

        Raises:
            ValueError: If tool name is None or already registered
        """
        if tool_class.name is None:
            raise ValueError(
                f"Tool class {tool_class.__name__} must have 'name' attribute"
            )

        if tool_class.name in cls._tools:
            log.warning(
                f"Tool '{tool_class.name}' already registered. "
                f"Overwriting with {tool_class.__name__}"
            )

        cls._tools[tool_class.name] = tool_class
        log.info(f"Registered tool: {tool_class.name} ({tool_class.__name__})")

        return tool_class

    @classmethod
    def get(cls, tool_name: str) -> Type[BaseTool]:
        """
        Retrieve a tool class by name.

        Args:
            tool_name: Name of the tool to retrieve

        Returns:
            Tool class

        Raises:
            ValueError: If tool not found
        """
        if tool_name not in cls._tools:
            available_tools = ", ".join(cls._tools.keys())
            raise ValueError(
                f"Tool '{tool_name}' not found. "
                f"Available tools: {available_tools or 'none'}"
            )

        return cls._tools[tool_name]

    @classmethod
    def list_tools(cls) -> Dict[str, Type[BaseTool]]:
        """
        Get all registered tools.

        Returns:
            Dictionary mapping tool names to tool classes
        """
        return cls._tools.copy()

    @classmethod
    def is_registered(cls, tool_name: str) -> bool:
        """
        Check if a tool is registered.

        Args:
            tool_name: Name of the tool

        Returns:
            True if tool is registered, False otherwise
        """
        return tool_name in cls._tools


def tool_register(tool_class: Type[BaseTool]) -> Type[BaseTool]:
    """
    Decorator for registering tools in the ToolRegistry.

    Usage:
        @tool_register
        class MyTool(BaseTool):
            name = "my_tool"
            ...

    Args:
        tool_class: Tool class to register

    Returns:
        The registered tool class
    """
    return ToolRegistry.register(tool_class)
