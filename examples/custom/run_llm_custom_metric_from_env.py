import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ENV_PATH = PROJECT_ROOT / ".env"
DEFAULT_INPUT_PATH = PROJECT_ROOT / "examples/custom/llm_custom_metric_data.jsonl"
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "outputs/custom_llm_metric_run/"

# Ensure local repository package is used instead of an installed site-packages version.
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dingo.config import InputArgs  # noqa: E402
from dingo.exec import Executor  # noqa: E402


def load_dotenv(env_path: Path) -> None:
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return value


def build_input_args() -> InputArgs:
    model = require_env("OPENAI_MODEL")
    key = require_env("OPENAI_API_KEY")
    api_url = require_env("OPENAI_API_URL")

    input_data = {
        "task_name": "llm_custom_metric_demo",
        "input_path": str(DEFAULT_INPUT_PATH),
        "output_path": str(DEFAULT_OUTPUT_PATH),
        "dataset": {
            "source": "local",
            "format": "jsonl",
        },
        "executor": {
            "max_workers": 1,
            "batch_size": 1,
            "result_save": {
                "bad": True,
                "good": True,
            },
        },
        "evaluator": [
            {
                "fields": {
                    "prompt": "question",
                    "content": "answer",
                },
                "evals": [
                    {
                        "name": "LLMCustomMetric",
                        "config": {
                            "model": model,
                            "key": key,
                            "api_url": api_url,
                            "temperature": 0,
                            "custom_metric": {
                                "metric": "AnswerRelevance",
                                "description": "Judge whether the answer directly addresses the user question.",
                                "criteria": [
                                    "Question: {{prompt}}",
                                    "Answer: {{content}}",
                                    "The answer must focus on the question above.",
                                    "The answer must not mainly discuss unrelated topics.",
                                    "Supplemental information is allowed only when it does not hide the core answer.",
                                ],
                                "input_fields": ["prompt", "content"],
                            },
                        },
                    }
                ],
            }
        ],
    }
    return InputArgs(**input_data)


def main() -> None:
    load_dotenv(DEFAULT_ENV_PATH)
    input_args = build_input_args()
    executor = Executor.exec_map["local"](input_args)
    result = executor.execute()
    print(result)
    print(f"Output written under: {input_args.output_path}")


if __name__ == "__main__":
    main()
