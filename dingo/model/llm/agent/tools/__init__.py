"""
Agent Tools Package

This package provides the tool system for agent-based evaluators.
Tools are reusable components that agents can invoke during evaluation.
"""

from dingo.model.llm.agent.tools.base_tool import BaseTool, ToolConfig
from dingo.model.llm.agent.tools.mineru_ocr_tool import MinerUOCRTool  # noqa: F401
from dingo.model.llm.agent.tools.render_tool import RenderTool  # noqa: F401
# Import tools to trigger registration
from dingo.model.llm.agent.tools.tavily_search import TavilySearch  # noqa: F401
from dingo.model.llm.agent.tools.tool_registry import ToolRegistry, tool_register

# Convenience function for getting tools
get_tool = ToolRegistry.get

__all__ = [
    'BaseTool',
    'ToolConfig',
    'ToolRegistry',
    'tool_register',
    'get_tool',
    'TavilySearch',
    'RenderTool',
    'MinerUOCRTool',
]
