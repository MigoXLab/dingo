"""
Agent Tools Package

This package provides the tool system for agent-based evaluators.
Tools are reusable components that agents can invoke during evaluation.
"""

from dingo.model.llm.agent.tools.base_tool import BaseTool, ToolConfig
from dingo.model.llm.agent.tools.tool_registry import ToolRegistry, tool_register

# Convenience function for getting tools
get_tool = ToolRegistry.get

__all__ = [
    'BaseTool',
    'ToolConfig',
    'ToolRegistry',
    'tool_register',
    'get_tool',
]
