"""
Agent Wrapper for Dingo Agents (LangChain 1.0)

Wraps LangChain's create_agent to work with Dingo's agent patterns.
Uses the modern LangChain 1.0 API (released November 2025).

Key Changes from AgentExecutor:
- Uses langchain.agents.create_agent (built on LangGraph)
- Returns CompiledStateGraph instead of AgentExecutor
- Message-based invocation interface
- Built-in persistence and checkpointing support
"""

from typing import Any, Dict, List, Optional

from dingo.utils import log


class AgentWrapper:
    """
    Wrapper that integrates LangChain 1.0 create_agent with Dingo agents.

    Handles:
    - Tool conversion from Dingo to LangChain format
    - Agent creation using create_agent
    - Result parsing from message-based output to Dingo structures
    - Configuration and logging
    """

    @staticmethod
    def create_agent(
        llm,
        tools: List,
        system_prompt: Optional[str] = None,
        **config
    ):
        """
        Create a LangChain agent using langchain.agents.create_agent.

        Args:
            llm: LangChain LLM instance (ChatOpenAI)
            tools: List of LangChain StructuredTools
            system_prompt: Optional system message
            **config: Additional configuration (debug, middleware, etc.)

        Returns:
            CompiledStateGraph (LangGraph agent)

        Example:
            llm = AgentWrapper.get_openai_llm_from_dingo_config(config)
            tools = convert_dingo_tools(["tavily_search"], agent)
            agent = AgentWrapper.create_agent(
                llm=llm,
                tools=tools,
                system_prompt="You are a fact-checking agent..."
            )
        """
        try:
            from langchain.agents import create_agent
        except ImportError as e:
            error_msg = (
                "LangChain is not installed but required for agent creation.\n\n"
                "Install with:\n"
                "  pip install -r requirements/agent.txt\n"
                "Or:\n"
                "  pip install 'dingo-python[agent]'"
            )
            log.error(error_msg)
            raise ImportError(error_msg) from e

        try:
            # Create agent using LangChain 1.0 API
            agent = create_agent(
                model=llm,
                tools=tools,
                system_prompt=system_prompt or "You are a helpful assistant with access to tools.",
                debug=config.get("debug", False)
            )

            log.debug(
                f"Created agent with {len(tools)} tools using langchain.agents.create_agent"
            )
            return agent

        except Exception as e:
            log.error(f"Failed to create agent: {e}")
            raise

    @staticmethod
    def invoke_and_format(
        agent,
        input_text: str,
        input_data: Optional[Any] = None,
        max_iterations: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Invoke agent and format output for Dingo.

        Args:
            agent: Compiled agent (from create_agent)
            input_text: Text to pass to agent
            input_data: Optional Data object for context
            max_iterations: Maximum reasoning iterations (default: 25)
                In LangChain 1.0, this is passed as 'recursion_limit' to the agent

        Returns:
            Dict with:
            - output: str (agent's final response)
            - messages: List[Message] (full conversation)
            - tool_calls: List[Dict] (parsed tool invocations)
            - success: bool

        Example:
            result = AgentWrapper.invoke_and_format(
                agent,
                input_text="Is Paris the capital of France?",
                input_data=data_obj,
                max_iterations=10
            )

        Note:
            In LangChain 1.0, iteration limits are controlled by recursion_limit,
            which is passed at invocation time rather than during agent creation.
        """
        try:
            # Build config dict for agent invocation
            config = {}
            if max_iterations is not None:
                # LangChain 1.0 uses 'recursion_limit' instead of 'max_iterations'
                config["recursion_limit"] = max_iterations
                log.debug(f"Setting recursion_limit={max_iterations}")

            # Invoke agent with message-based input and config
            if config:
                result = agent.invoke(
                    {"messages": [("user", input_text)]},
                    config
                )
            else:
                # No config needed, use default recursion_limit (25)
                result = agent.invoke({
                    "messages": [("user", input_text)]
                })

            formatted_result = AgentWrapper._format_agent_result(result)
            log.debug(
                f"Agent execution completed: {len(formatted_result['tool_calls'])} tool calls, "
                f"{formatted_result['reasoning_steps']} reasoning steps"
            )
            return formatted_result

        except Exception as e:
            log.error(f"Agent invocation failed: {e}")
            return AgentWrapper._make_error_result(str(e))

    @staticmethod
    async def async_invoke_and_format(
        agent,
        input_text: str,
        input_data: Optional[Any] = None,
        max_iterations: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Async version of invoke_and_format using agent.ainvoke().

        Used for concurrent claim verification in ArticleFactChecker's
        two-phase parallel architecture.

        Args:
            agent: Compiled agent (from create_agent)
            input_text: Text to pass to agent
            input_data: Optional Data object for context (unused, kept for API parity)
            max_iterations: Maximum reasoning iterations (recursion_limit)

        Returns:
            Dict with output, messages, tool_calls, reasoning_steps, success
        """
        try:
            config = {}
            if max_iterations is not None:
                config["recursion_limit"] = max_iterations

            if config:
                result = await agent.ainvoke(
                    {"messages": [("user", input_text)]},
                    config
                )
            else:
                result = await agent.ainvoke({"messages": [("user", input_text)]})

            formatted_result = AgentWrapper._format_agent_result(result)
            log.debug(
                f"Async agent execution completed: {len(formatted_result['tool_calls'])} tool calls, "
                f"{formatted_result['reasoning_steps']} reasoning steps"
            )
            return formatted_result

        except Exception as e:
            log.error(f"Async agent invocation failed: {e}")
            return AgentWrapper._make_error_result(str(e))

    @staticmethod
    def _format_agent_result(result: Dict) -> Dict[str, Any]:
        """
        Convert raw agent invocation result into Dingo's standard output format.

        Shared by both invoke_and_format (sync) and async_invoke_and_format (async)
        to avoid duplication of message-parsing logic.

        Args:
            result: Raw dict returned by agent.invoke() / agent.ainvoke()

        Returns:
            Dict with output, messages, tool_calls, reasoning_steps, success=True
        """
        messages = result.get('messages', [])
        output = ""
        if messages:
            last_message = messages[-1]
            output = getattr(last_message, 'content', str(last_message))
        tool_calls = AgentWrapper._extract_tool_calls(messages)
        reasoning_steps = len([m for m in messages if hasattr(m, 'type') and m.type == 'ai'])
        return {
            'output': output,
            'messages': messages,
            'tool_calls': tool_calls,
            'reasoning_steps': reasoning_steps,
            'success': True,
        }

    @staticmethod
    def _make_error_result(error: str) -> Dict[str, Any]:
        """Build a standard error result dict for failed agent invocations."""
        return {
            'output': '',
            'messages': [],
            'tool_calls': [],
            'reasoning_steps': 0,
            'success': False,
            'error': error,
        }

    @staticmethod
    def _extract_tool_calls(messages: List) -> List[Dict[str, Any]]:
        """
        Extract tool calls from message sequence.

        Parses AIMessage objects with tool_calls and their corresponding
        ToolMessage responses.

        Args:
            messages: List of message objects

        Returns:
            List of dicts with tool, args, observation
        """
        tool_calls = []

        try:
            from langchain_core.messages import AIMessage, ToolMessage

            for i, message in enumerate(messages):
                # Check if AI message has tool calls
                if isinstance(message, AIMessage) and hasattr(message, 'tool_calls'):
                    for tool_call in message.tool_calls:
                        # Find corresponding tool response
                        observation = ""
                        if i + 1 < len(messages) and isinstance(messages[i + 1], ToolMessage):
                            observation = messages[i + 1].content

                        tool_calls.append({
                            'tool': tool_call.get('name', 'unknown'),
                            'args': tool_call.get('args', {}),
                            'observation': observation
                        })

        except ImportError:
            # Fallback if langchain_core not available
            log.warning("Could not import langchain_core for tool call extraction")

        except Exception as e:
            log.warning(f"Error extracting tool calls: {e}")

        return tool_calls

    @staticmethod
    def get_openai_llm_from_dingo_config(dynamic_config):
        """
        Create LangChain ChatOpenAI LLM from Dingo's dynamic_config.

        Args:
            dynamic_config: BaseOpenAI.dynamic_config (EvaluatorLLMArgs)

        Returns:
            LangChain ChatOpenAI instance

        Note:
            This wraps Dingo's existing client creation pattern
            for use with LangChain's agent framework.

        Example:
            llm = AgentWrapper.get_openai_llm_from_dingo_config(
                agent.dynamic_config
            )
        """
        try:
            from langchain_openai import ChatOpenAI
        except ImportError as e:
            error_msg = (
                "langchain-openai is not installed but required for LLM integration.\n\n"
                "Install with:\n"
                "  pip install -r requirements/agent.txt\n"
                "Or:\n"
                "  pip install 'dingo-python[agent]'"
            )
            log.error(error_msg)
            raise ImportError(error_msg) from e

        if not hasattr(dynamic_config, 'key') or not dynamic_config.key:
            raise ValueError(
                "dynamic_config must have 'key' (API key) for LLM"
            )

        if not hasattr(dynamic_config, 'api_url') or not dynamic_config.api_url:
            raise ValueError(
                "dynamic_config must have 'api_url' (base URL) for LLM"
            )

        # Extract parameters
        extra_params = dynamic_config.model_extra

        # Create ChatOpenAI instance
        llm = ChatOpenAI(
            api_key=dynamic_config.key,
            base_url=dynamic_config.api_url,
            model=dynamic_config.model or "gpt-4.1-mini",
            temperature=extra_params.get("temperature", 0.3),
            max_tokens=extra_params.get("max_tokens", 4096),
            top_p=extra_params.get("top_p", 1.0),
            timeout=extra_params.get("timeout", 30)
        )

        log.debug(
            f"Created ChatOpenAI: model={dynamic_config.model}, "
            f"temp={extra_params.get('temperature', 0.3)}"
        )

        return llm
