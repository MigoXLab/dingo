"""
Agent Framework for Dingo

This package provides agent-based evaluation capabilities that extend LLMs with
tool usage, multi-step reasoning, and adaptive context gathering.

Key Components:
- BaseAgent: Abstract base class for agent evaluators
- Tool system: Registry and base classes for agent tools
"""

from dingo.model.llm.agent.base_agent import BaseAgent
from dingo.model.llm.agent.tools import BaseTool, ToolConfig, ToolRegistry, get_tool, tool_register

__all__ = [
    'BaseAgent',
    'BaseTool',
    'ToolConfig',
    'ToolRegistry',
    'get_tool',
    'tool_register',
]
