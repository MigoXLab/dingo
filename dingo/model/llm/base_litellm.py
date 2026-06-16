from typing import List

from dingo.config.input_args import EvaluatorLLMArgs
from dingo.model.llm.base_openai import BaseOpenAI
from dingo.utils.exception import ExceedMaxTokens


class BaseLiteLLM(BaseOpenAI):
    """Base class for LLM evaluators that route through LiteLLM.

    Provides access to 100+ providers (Anthropic, Gemini, Bedrock, Cohere,
    Mistral, Groq, etc.) via a single unified interface. Inherit from this
    class instead of BaseOpenAI when you want provider flexibility.

    Model string examples:
      - "anthropic/claude-3-5-sonnet-20241022"
      - "gemini/gemini-1.5-pro"
      - "bedrock/anthropic.claude-3-sonnet-20240229-v1:0"
      - "groq/llama3-8b-8192"
      - "gpt-4o"  (defaults to OpenAI, same as BaseOpenAI)

    Configuration (via EvaluatorLLMArgs):
      - model: required, provider-prefixed model string
      - key: optional, API key (overrides provider env var)
      - api_url: optional, custom base URL (e.g. LiteLLM proxy URL)
      - Any extra field is forwarded to litellm.completion() as a kwarg.

    Requires: pip install "dingo-python[litellm]"
    """

    dynamic_config: EvaluatorLLMArgs = EvaluatorLLMArgs()

    @classmethod
    def create_client(cls):
        if not cls.dynamic_config.model:
            raise ValueError("model cannot be empty in llm config.")
        try:
            import litellm  # noqa: F401
        except ImportError as exc:
            raise ImportError(
                "litellm is not installed. Run: pip install 'dingo-python[litellm]'"
            ) from exc
        # Use cls.client as an initialisation sentinel (no real client object needed).
        cls.client = True

    @classmethod
    def send_messages(cls, messages: List) -> str:
        import litellm

        model_name = cls.dynamic_config.model or ""
        extra_params = cls.dynamic_config.model_extra or {}
        cls.validate_config(extra_params)

        call_kwargs: dict = {
            "drop_params": True,
            **extra_params,
        }
        if cls.dynamic_config.api_url:
            call_kwargs["api_base"] = cls.dynamic_config.api_url
        if cls.dynamic_config.key:
            call_kwargs["api_key"] = cls.dynamic_config.key

        response = litellm.completion(
            model=model_name,
            messages=messages,
            **call_kwargs,
        )

        finish_reason = response.choices[0].finish_reason  # type: ignore[union-attr]
        if finish_reason == "length":
            raise ExceedMaxTokens(
                f"Exceed max tokens: {extra_params.get('max_tokens', 4000)}"
            )

        return str(response.choices[0].message.content)  # type: ignore[union-attr]
