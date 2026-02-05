"""
Unit tests for Tool Registry system
"""

import pytest

from dingo.model.llm.agent.tools import BaseTool, ToolConfig, ToolRegistry, tool_register


class TestToolConfig:
    """Test ToolConfig base class"""

    def test_default_values(self):
        """Test default configuration values"""
        config = ToolConfig()
        assert config.api_key is None
        assert config.timeout == 30
        assert config.max_retries == 3

    def test_custom_values(self):
        """Test custom configuration values"""
        config = ToolConfig(api_key="test_key", timeout=60, max_retries=5)
        assert config.api_key == "test_key"
        assert config.timeout == 60
        assert config.max_retries == 5

    def test_extra_fields(self):
        """Test that extra fields are allowed"""
        config = ToolConfig(custom_field="custom_value")
        assert hasattr(config, 'custom_field')
        assert config.custom_field == "custom_value"


class TestToolRegistry:
    """Test ToolRegistry functionality"""

    def setup_method(self):
        """Reset registry before each test"""
        ToolRegistry._tools = {}

    def test_register_tool(self):
        """Test registering a tool"""
        class TestTool(BaseTool):
            name = "test_tool"
            description = "Test tool"

            @classmethod
            def execute(cls, **kwargs):
                return {"success": True}

        ToolRegistry.register(TestTool)
        assert "test_tool" in ToolRegistry._tools
        assert ToolRegistry._tools["test_tool"] == TestTool

    def test_register_tool_without_name(self):
        """Test that registering tool without name raises error"""
        class InvalidTool(BaseTool):
            # Missing 'name' attribute
            @classmethod
            def execute(cls, **kwargs):
                return {}

        with pytest.raises(ValueError, match="must have 'name' attribute"):
            ToolRegistry.register(InvalidTool)

    def test_get_tool(self):
        """Test retrieving a registered tool"""
        class TestTool(BaseTool):
            name = "test_tool"

            @classmethod
            def execute(cls, **kwargs):
                return {"success": True}

        ToolRegistry.register(TestTool)
        retrieved = ToolRegistry.get("test_tool")
        assert retrieved == TestTool

    def test_get_nonexistent_tool(self):
        """Test that getting nonexistent tool raises error"""
        with pytest.raises(ValueError, match="Tool 'nonexistent' not found"):
            ToolRegistry.get("nonexistent")

    def test_list_tools(self):
        """Test listing all registered tools"""
        class Tool1(BaseTool):
            name = "tool1"

            @classmethod
            def execute(cls, **kwargs):
                return {}

        class Tool2(BaseTool):
            name = "tool2"

            @classmethod
            def execute(cls, **kwargs):
                return {}

        ToolRegistry.register(Tool1)
        ToolRegistry.register(Tool2)

        tools = ToolRegistry.list_tools()
        assert len(tools) == 2
        assert "tool1" in tools
        assert "tool2" in tools

    def test_is_registered(self):
        """Test checking if tool is registered"""
        class TestTool(BaseTool):
            name = "test_tool"

            @classmethod
            def execute(cls, **kwargs):
                return {}

        assert not ToolRegistry.is_registered("test_tool")
        ToolRegistry.register(TestTool)
        assert ToolRegistry.is_registered("test_tool")

    def test_tool_register_decorator(self):
        """Test @tool_register decorator"""
        @tool_register
        class DecoratedTool(BaseTool):
            name = "decorated_tool"
            description = "Tool registered via decorator"

            @classmethod
            def execute(cls, **kwargs):
                return {"success": True}

        assert ToolRegistry.is_registered("decorated_tool")
        assert ToolRegistry.get("decorated_tool") == DecoratedTool


class TestBaseTool:
    """Test BaseTool base class"""

    def test_abstract_execute(self):
        """Test that execute method must be implemented"""
        class IncompleteTool(BaseTool):
            name = "incomplete"

        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            IncompleteTool()

    def test_validate_config_no_api_key(self):
        """Test config validation when API key is required but missing"""
        class TestTool(BaseTool):
            name = "test_tool"
            config = ToolConfig(api_key=None)

            @classmethod
            def execute(cls, **kwargs):
                return {}

        with pytest.raises(ValueError, match="API key is required"):
            TestTool.validate_config()

    def test_validate_config_with_api_key(self):
        """Test config validation when API key is provided"""
        class TestTool(BaseTool):
            name = "test_tool"
            config = ToolConfig(api_key="valid_key")

            @classmethod
            def execute(cls, **kwargs):
                return {}

        # Should not raise
        TestTool.validate_config()

    def test_update_config(self):
        """Test updating tool configuration"""
        class TestTool(BaseTool):
            name = "test_tool"
            config = ToolConfig(timeout=30, max_retries=3)

            @classmethod
            def execute(cls, **kwargs):
                return {}

        TestTool.update_config({"timeout": 60, "max_retries": 5})
        assert TestTool.config.timeout == 60
        assert TestTool.config.max_retries == 5

    def test_update_config_ignores_invalid_keys(self):
        """Test that update_config ignores keys not in config"""
        class TestTool(BaseTool):
            name = "test_tool"
            config = ToolConfig(timeout=30)

            @classmethod
            def execute(cls, **kwargs):
                return {}

        # Should not raise, just ignores invalid key
        TestTool.update_config({"invalid_key": "value", "timeout": 60})
        assert TestTool.config.timeout == 60
        assert not hasattr(TestTool.config, 'invalid_key')
