"""
Base Agent Class for Agent-Based Evaluators

This module provides the abstract base class for agent-based evaluators that can use
tools to enhance their evaluation capabilities. Agents extend BaseOpenAI to inherit
LLM functionality while adding tool execution and multi-step reasoning capabilities.

Supports dual execution paths:
1. Legacy: Manual plan_execution → loop → aggregate_results
2. LangChain Agent: LangChain 1.0 create_agent for ReAct-style agents (Nov 2025)
"""

from abc import abstractmethod
from typing import Any, Dict, List

from dingo.io import Data
from dingo.io.output.eval_detail import EvalDetail, QualityLabel
from dingo.model.llm.agent.tools import ToolRegistry
from dingo.model.llm.base_openai import BaseOpenAI
from dingo.utils import log


class BaseAgent(BaseOpenAI):
    """
    Base class for agent-based evaluators with tool support.

    Agents extend LLMs with the ability to:
    - Use external tools (web search, APIs, etc.)
    - Perform multi-step reasoning
    - Adaptively gather context
    - Provide transparent decision traces

    Execution Paths:
    - use_agent_executor=False (default): Legacy manual loop
    - use_agent_executor=True: LangChain 1.0 create_agent (ReAct pattern, built on LangGraph)

    Subclasses must implement:
    - plan_execution(): Define the agent's reasoning/execution strategy (legacy)
    - aggregate_results(): Combine tool outputs into final evaluation (both paths)

    Attributes:
        available_tools: List of tool names this agent can use
        max_iterations: Maximum reasoning loop iterations (safety limit)
        use_agent_executor: Enable LangChain agent path (default: False)
    """

    available_tools: List[str] = []
    max_iterations: int = 5
    use_agent_executor: bool = False  # Opt-in to LangChain agent path

    @classmethod
    @abstractmethod
    def plan_execution(cls, input_data: Data) -> List[Dict[str, Any]]:
        """
        Define the agent's execution strategy.

        This method should return a plan of steps the agent will execute.
        Each step can be a tool call or an LLM call.

        Args:
            input_data: Input data to evaluate

        Returns:
            List of execution steps, where each step is a dict:
            - For tool: {'type': 'tool', 'tool': 'tool_name', 'args': {...}}
            - For LLM: {'type': 'llm', 'purpose': 'description', 'prompt': '...'}

        Example:
            return [
                {'type': 'tool', 'tool': 'tavily_search', 'args': {'query': 'fact'}},
                {'type': 'llm', 'purpose': 'synthesize', 'prompt': 'Analyze results...'}
            ]
        """
        raise NotImplementedError()

    @classmethod
    @abstractmethod
    def aggregate_results(cls, input_data: Data, results: List[Any]) -> EvalDetail:
        """
        Combine tool outputs and LLM responses into final evaluation.

        Args:
            input_data: Original input data
            results: List of results from plan execution (tool outputs, LLM responses)

        Returns:
            EvalDetail with final evaluation result

        Example:
            result = EvalDetail(metric=cls.__name__)
            result.status = results[0]['score'] > 0.7
            result.label = ["QUALITY_BAD.ISSUE"] if result.status else ["QUALITY_GOOD"]
            result.reason = [f"Analysis: {results[1]}"]
            return result
        """
        raise NotImplementedError()

    @classmethod
    def execute_tool(cls, tool_name: str, **kwargs) -> Dict[str, Any]:
        """
        Execute a tool and return its results.

        Args:
            tool_name: Name of the tool to execute
            **kwargs: Arguments to pass to the tool

        Returns:
            Dict with tool results (includes 'success' key)

        Raises:
            ValueError: If tool not found or not in available_tools
            Exception: Tool-specific exceptions
        """
        # Check if tool is available to this agent
        if tool_name not in cls.available_tools:
            raise ValueError(
                f"Tool '{tool_name}' not available for {cls.__name__}. "
                f"Available tools: {cls.available_tools}"
            )

        # Get tool class from registry
        tool_class = ToolRegistry.get(tool_name)

        # Configure tool from agent's config
        cls.configure_tool(tool_name, tool_class)

        # Execute tool
        log.info(f"{cls.__name__} executing tool: {tool_name}")
        try:
            result = tool_class.execute(**kwargs)
            log.info(f"Tool {tool_name} executed successfully")
            return result
        except Exception as e:
            log.error(f"Tool {tool_name} failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'tool': tool_name
            }

    @classmethod
    def get_tool_config(cls, tool_name: str) -> Dict[str, Any]:
        """
        Extract tool configuration from agent's dynamic_config.

        Configuration is expected in:
        dynamic_config.parameters.agent_config.tools.{tool_name}

        Args:
            tool_name: Name of the tool

        Returns:
            Dict of configuration values for the tool
        """
        params = cls.dynamic_config.parameters or {}
        agent_config = params.get('agent_config', {})
        tools_config = agent_config.get('tools', {})
        return tools_config.get(tool_name, {})

    @classmethod
    def configure_tool(cls, tool_name: str, tool_class):
        """
        Apply runtime configuration to a tool before execution.

        Args:
            tool_name: Name of the tool
            tool_class: Tool class to configure
        """
        config_dict = cls.get_tool_config(tool_name)

        if config_dict:
            log.debug(f"Configuring tool {tool_name} with: {config_dict}")
            tool_class.update_config(config_dict)
        else:
            log.debug(f"No configuration found for tool {tool_name}")

    @classmethod
    def get_max_iterations(cls) -> int:
        """
        Get maximum iterations from config or class default.

        Returns:
            Maximum number of iterations allowed
        """
        params = cls.dynamic_config.parameters or {}
        agent_config = params.get('agent_config', {})
        return agent_config.get('max_iterations', cls.max_iterations)

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        """
        Main evaluation method with dual-path support.

        Routes to LangChain agent or legacy path based on use_agent_executor flag.

        Execution Paths:
        - use_agent_executor=True: LangChain 1.0 create_agent (ReAct pattern, built on LangGraph)
        - use_agent_executor=False: Legacy manual loop (default)

        Both paths call aggregate_results() to generate final EvalDetail.

        Args:
            input_data: Data to evaluate

        Returns:
            EvalDetail with evaluation results

        Note:
            Subclasses can override this for fully custom workflows (like AgentHallucination).
        """
        # Dispatch to appropriate path
        if cls.use_agent_executor:
            log.debug(f"{cls.__name__}: Using LangChain agent path")
            return cls._eval_with_langchain_agent(input_data)
        else:
            log.debug(f"{cls.__name__}: Using legacy evaluation path")
            # Legacy path below

        # Get execution plan
        try:
            plan = cls.plan_execution(input_data)
        except Exception as e:
            log.error(f"{cls.__name__} plan_execution failed: {e}")
            result = EvalDetail(metric=cls.__name__)
            result.status = True
            result.label = ["AGENT_ERROR.PLAN_FAILED"]
            result.reason = [f"Failed to create execution plan: {str(e)}"]
            return result

        # Execute plan
        results = []
        max_iter = cls.get_max_iterations()

        for i, step in enumerate(plan):
            if i >= max_iter:
                log.warning(f"{cls.__name__} exceeded max iterations: {max_iter}")
                break

            try:
                if step.get('type') == 'tool':
                    # Execute tool
                    tool_name = step['tool']
                    tool_args = step.get('args', {})
                    result = cls.execute_tool(tool_name, **tool_args)
                    results.append(result)

                elif step.get('type') == 'llm':
                    # Call LLM
                    prompt = step.get('prompt', '')
                    # Use parent's send_messages method
                    messages = [{"role": "user", "content": prompt}]
                    response = cls.send_messages(messages)
                    results.append(response)

                else:
                    log.warning(f"Unknown step type: {step.get('type')}")
                    results.append(None)

            except Exception as e:
                log.error(f"{cls.__name__} step {i} failed: {e}")
                results.append({'success': False, 'error': str(e)})

        # Aggregate results
        try:
            return cls.aggregate_results(input_data, results)
        except Exception as e:
            log.error(f"{cls.__name__} aggregate_results failed: {e}")
            result = EvalDetail(metric=cls.__name__)
            result.status = True
            result.label = ["AGENT_ERROR.AGGREGATION_FAILED"]
            result.reason = [f"Failed to aggregate results: {str(e)}"]
            return result

    # ============================================================
    # LangChain Agent Path (LangChain 1.0 create_agent)
    # ============================================================

    @classmethod
    def _check_langchain_available(cls) -> bool:
        """
        Check if LangChain dependencies are installed.

        Returns:
            True if langchain and langchain-openai are available
        """
        try:
            import langchain  # noqa: F401
            import langchain_openai  # noqa: F401
            return True
        except ImportError:
            return False

    @classmethod
    def get_langchain_tools(cls):
        """
        Convert available_tools to LangChain StructuredTool format.

        Returns:
            List of LangChain StructuredTool objects

        Note:
            Uses DingoToolWrapper to preserve Dingo's configuration injection.
        """
        if not cls.available_tools:
            return []

        try:
            from dingo.model.llm.agent.langchain_adapter import convert_dingo_tools

            lc_tools = convert_dingo_tools(cls.available_tools, cls)
            log.debug(f"{cls.__name__}: Converted {len(lc_tools)} tools to LangChain format")
            return lc_tools

        except ImportError:
            log.error(
                "LangChain adapter not available. "
                "Install langchain dependencies or use legacy eval path."
            )
            return []

    @classmethod
    def get_langchain_llm(cls):
        """
        Create LangChain ChatOpenAI from agent's dynamic_config.

        Returns:
            LangChain ChatOpenAI instance
        """
        try:
            from dingo.model.llm.agent.agent_wrapper import AgentWrapper

            return AgentWrapper.get_openai_llm_from_dingo_config(
                cls.dynamic_config
            )

        except ImportError:
            log.error(
                "Agent wrapper not available. "
                "Install langchain dependencies or use legacy eval path."
            )
            raise

    @classmethod
    def _get_system_prompt(cls, input_data: Data) -> str:
        """
        Get system prompt for LangChain agent.

        Can be overridden by subclasses to customize agent behavior.

        Args:
            input_data: Input data (for context-aware prompts)

        Returns:
            System prompt string
        """
        return f"You are a {cls.__name__} agent with access to tools."

    @classmethod
    def _eval_with_langchain_agent(cls, input_data: Data) -> EvalDetail:
        """
        Evaluation using LangChain 1.0 create_agent (LangChain Agent PATH).

        Workflow:
        1. Get LangChain tools from available_tools
        2. Create agent using langchain.agents.create_agent
        3. Invoke agent with input_data
        4. Parse results
        5. Call aggregate_results() to generate EvalDetail

        Args:
            input_data: Data to evaluate

        Returns:
            EvalDetail with evaluation results

        Note:
            All errors are caught and returned as EvalDetail with
            status=True (indicating an error/issue) and appropriate labels.
        """
        # Check if LangChain is available
        if not cls._check_langchain_available():
            result = EvalDetail(metric=cls.__name__)
            result.status = True
            result.label = [f"{QualityLabel.QUALITY_BAD_PREFIX}DEPENDENCY_MISSING"]
            result.reason = [
                "LangChain is not installed but required for agent-based evaluation.",
                "",
                "Install with:",
                "  pip install -r requirements/agent.txt",
                "Or:",
                "  pip install 'dingo-python[agent]'",
                "",
                "Alternatively, use the legacy agent path by setting use_agent_executor=False"
            ]
            return result

        try:
            from dingo.model.llm.agent.agent_wrapper import AgentWrapper

            # Ensure OpenAI client exists
            cls.create_client()

            # Step 1: Get LangChain tools
            lc_tools = cls.get_langchain_tools()

            if not lc_tools and cls.available_tools:
                log.warning(
                    f"{cls.__name__}: Available tools {cls.available_tools} "
                    "but no LangChain tools created"
                )

            # Step 2: Get LLM in LangChain format
            llm = cls.get_langchain_llm()

            # Step 3: Create agent
            system_prompt = cls._get_system_prompt(input_data)
            agent = AgentWrapper.create_agent(
                llm=llm,
                tools=lc_tools,
                system_prompt=system_prompt
            )

            # Step 4: Invoke agent with max_iterations
            max_iter = cls.get_max_iterations()
            log.info(f"{cls.__name__}: Invoking LangChain agent (max_iterations={max_iter})")
            agent_result = AgentWrapper.invoke_and_format(
                agent,
                input_text=input_data.content,
                input_data=input_data,
                max_iterations=max_iter
            )

            # Step 5: Aggregate to EvalDetail
            log.info(f"{cls.__name__}: Aggregating agent results")
            return cls.aggregate_results(input_data, [agent_result])

        except ImportError as e:
            log.error(f"{cls.__name__}: LangChain not installed: {e}")
            result = EvalDetail(metric=cls.__name__)
            result.status = True
            result.label = [f"{QualityLabel.QUALITY_BAD_PREFIX}LANGCHAIN_NOT_INSTALLED"]
            result.reason = [
                f"LangChain dependencies not installed: {str(e)}",
                "Install with: pip install langchain>=1.0.0 langchain-openai"
            ]
            return result

        except Exception as e:
            log.error(f"{cls.__name__} LangChain agent evaluation failed: {e}")
            result = EvalDetail(metric=cls.__name__)
            result.status = True
            result.label = [f"{QualityLabel.QUALITY_BAD_PREFIX}AGENT_ERROR"]
            result.reason = [f"LangChain agent failed: {str(e)}"]
            return result
