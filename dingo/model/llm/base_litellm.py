from typing import List

from dingo.config.input_args import EvaluatorLLMArgs
from dingo.model.llm.base import LLMCallResult
from dingo.model.llm.base_openai import LOCAL_ONLY_CONFIG_KEYS, BaseOpenAI
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

        # If embedding_config is configured, initialize the embedding client
        if cls.dynamic_config.embedding_config:
            from openai import OpenAI

            from dingo.config.input_args import EmbeddingConfigArgs

            embedding_cfg = cls.dynamic_config.embedding_config

            # Handle embedding_config being a dict or object
            if isinstance(embedding_cfg, dict):
                embedding_cfg = EmbeddingConfigArgs(**embedding_cfg)

            if not embedding_cfg.api_url:
                raise ValueError("embedding_config must provide api_url")

            if not embedding_cfg.model:
                raise ValueError("embedding_config must provide model")

            # Create independent Embedding client
            cls.embedding_client = OpenAI(
                api_key=embedding_cfg.key or 'dummy-key',
                base_url=embedding_cfg.api_url
            )

            cls.embedding_model = {
                'model_name': embedding_cfg.model,
                'client': cls.embedding_client
            }

    @classmethod
    def send_messages(cls, messages: List) -> str:
        import litellm

        model_name = cls.dynamic_config.model or ""
        # 这里刻意不走 ``get_request_extra_params``：那个方法按 OpenAI SDK 的
        # 签名放行，而 litellm 的入参集合更大（api_base、num_retries 等），拿
        # OpenAI 的签名当判据会把 litellm 自己的参数一并丢掉。
        #
        # 换成排除表的代价也小得多：litellm 收 ``**kwargs`` 且开了 drop_params，
        # 漏登记一个本地键最多是被它悄悄丢弃，不像 OpenAI SDK 那样直接抛
        # TypeError。要摘掉本地键，仍然是因为「悄悄丢弃」意味着这个键从未
        # 按配置的意图生效过。
        extra_params = {
            k: v
            for k, v in (cls.dynamic_config.model_extra or {}).items()
            if k not in LOCAL_ONLY_CONFIG_KEYS
        }
        cls.validate_config(extra_params)

        call_kwargs: dict = {
            "drop_params": True,
            **extra_params,
        }
        # 摘掉还不够——调用方配了它们是要它们生效的。只在配了的时候传：这个
        # 路径原先没有超时与重试上限，凭空给默认值会改掉既有行为。
        request_timeout = cls.get_local_config_value("request_timeout")
        if request_timeout is not None:
            call_kwargs["timeout"] = request_timeout
        max_retries = cls.get_local_config_value("max_retries")
        if max_retries is not None:
            call_kwargs["num_retries"] = max_retries
        if cls.dynamic_config.api_url:
            call_kwargs["api_base"] = cls.dynamic_config.api_url
        if cls.dynamic_config.key:
            call_kwargs["api_key"] = cls.dynamic_config.key

        response = litellm.completion(
            model=model_name,
            messages=messages,
            **call_kwargs,
        )

        if not response.choices:
            raise ValueError("LiteLLM returned an empty response choices list.")

        choice = response.choices[0]
        finish_reason = choice.finish_reason  # type: ignore[union-attr]
        if finish_reason == "length":
            raise ExceedMaxTokens(
                f"Exceed max tokens: {extra_params.get('max_tokens', 4000)}"
            )

        content = choice.message.content  # type: ignore[union-attr]
        return LLMCallResult(
            content=str(content) if content is not None else "",
            usage=cls._extract_token_usage(
                response,
                model_name=model_name,
                provider="litellm",
            ),
        )
