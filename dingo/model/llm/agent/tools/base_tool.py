"""
Base Tool Interface for Agent Framework

This module provides the abstract base class and configuration for all agent tools.
Tools are reusable components that agents can invoke to perform specific tasks
like web search, API calls, or data processing.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from pydantic import BaseModel


class ToolConfig(BaseModel):
    """Base configuration for tools"""
    api_key: Optional[str] = None
    timeout: int = 30
    max_retries: int = 3

    class Config:
        extra = "allow"  # Allow additional tool-specific config fields


class BaseTool(ABC):
    """
    Base class for all agent tools.

    Tools provide specific capabilities that agents can use during evaluation,
    such as web search, document retrieval, or API calls.

    Attributes:
        name: Unique identifier for the tool
        description: Brief description for LLM to understand tool purpose
        config: Tool-specific configuration
    """

    name: str = None
    description: str = None
    config: ToolConfig = ToolConfig()

    @classmethod
    @abstractmethod
    def execute(cls, **kwargs) -> Dict[str, Any]:
        """
        Execute the tool with given arguments.

        Args:
            **kwargs: Tool-specific arguments

        Returns:
            Dict with 'success' key and tool-specific results

        Raises:
            Exception: Tool-specific exceptions
        """
        raise NotImplementedError()

    @classmethod
    def validate_config(cls):
        """
        Validate tool configuration before execution.

        Raises:
            ValueError: If configuration is invalid
        """
        if hasattr(cls.config, 'api_key') and not cls.config.api_key:
            raise ValueError(f"{cls.name}: API key is required")

    @classmethod
    def update_config(cls, config_dict: Dict[str, Any]):
        """
        Update tool configuration from dictionary.

        Args:
            config_dict: Configuration values to update
        """
        for key, value in config_dict.items():
            if hasattr(cls.config, key):
                setattr(cls.config, key, value)
