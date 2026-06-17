"""Unit tests for RetrievalExecutor and CLI integration."""

import json
import os
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from dingo.config import InputArgs
from dingo.config.input_args import RetrievalArgs

PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)


class TestRetrievalArgs:
    def test_default_values(self):
        args = RetrievalArgs()
        assert args.backend == "agentic"
        assert args.limit == 100
        assert args.retrieval_mode == "hybrid"
        assert args.api_token is None
        assert args.max_queries is None

    def test_custom_values(self):
        args = RetrievalArgs(
            backend="agentic",
            api_url="https://api.example.com",
            api_token="token123",
            limit=50,
            retrieval_mode="milvus",
            max_queries=10,
        )
        assert args.api_url == "https://api.example.com"
        assert args.api_token == "token123"
        assert args.limit == 50
        assert args.max_queries == 10


class TestInputArgsWithRetrieval:
    def test_input_args_with_retrieval_config(self):
        input_data = {
            "input_path": "SciFact",
            "output_path": "outputs/test",
            "executor": {
                "retrieval": {
                    "backend": "agentic",
                    "api_url": "http://localhost:8080",
                    "limit": 100,
                }
            },
        }
        input_args = InputArgs(**input_data)
        assert input_args.executor.retrieval is not None
        assert input_args.executor.retrieval.backend == "agentic"
        assert input_args.executor.retrieval.limit == 100

    def test_input_args_without_retrieval(self):
        input_data = {
            "input_path": "test.json",
            "output_path": "outputs/",
            "evaluator": [{"evals": [{"name": "RuleSpecialCharacter"}]}],
        }
        input_args = InputArgs(**input_data)
        assert input_args.executor.retrieval is None

    def test_executor_map_has_retrieval(self):
        from dingo.exec import Executor

        assert "retrieval" in Executor.exec_map


class TestRetrievalExecutorInit:
    def test_missing_retrieval_config_raises(self):
        from dingo.exec import Executor

        input_data = {
            "input_path": "SciFact",
            "output_path": "outputs/test",
        }
        input_args = InputArgs(**input_data)
        with pytest.raises(ValueError, match="executor.retrieval config is required"):
            Executor.exec_map["retrieval"](input_args)

    def test_empty_input_path_raises(self):
        from dingo.exec import Executor

        input_data = {
            "input_path": "",
            "output_path": "outputs/test",
            "executor": {
                "retrieval": {
                    "backend": "agentic",
                    "api_url": "http://localhost:8080",
                }
            },
        }
        input_args = InputArgs(**input_data)
        executor = Executor.exec_map["retrieval"](input_args)
        with pytest.raises(ValueError, match="input_path must specify"):
            executor.execute()


class TestCLIEvalRetrieval:
    def _run_cli(self, *args, expect_exit=0):
        cmd = [sys.executable, "-W", "ignore", "-m", "dingo.run.cli"] + list(args)
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=PROJECT_ROOT)
        if expect_exit is not None:
            assert result.returncode == expect_exit, (
                f"Expected exit {expect_exit}, got {result.returncode}\n"
                f"stdout: {result.stdout}\nstderr: {result.stderr}"
            )
        return result.stdout, result.stderr, result.returncode

    def test_help(self):
        stdout, _, _ = self._run_cli("eval-retrieval", "--help")
        assert "--backend" in stdout
        assert "--tasks" in stdout
        assert "--api-url" in stdout
        assert "--limit" in stdout

    def test_api_url_is_optional(self):
        stdout, _, _ = self._run_cli("eval-retrieval", "--help")
        assert "default depends on backend" in stdout


class TestRetrievalExecutorEvaluatorAutoConfig:
    """Test evaluator auto-configuration logic."""

    def test_mteb_mode_configures_rule_evaluators(self):
        from dingo.exec.retrieval import RetrievalExecutor
        from dingo.model import Model
        Model.load_model()

        input_args = InputArgs(**{
            "input_path": "SciFact",
            "output_path": "/tmp/test",
            "executor": {
                "retrieval": {
                    "backend": "agentic",
                    "api_url": "http://test",
                }
            },
        })
        executor = RetrievalExecutor(input_args)
        configs = executor._build_evaluator_configs()
        names = [c.name for c in configs]
        assert "RuleNDCG" in names
        assert "RuleMRR" in names
        assert "RuleRecall" in names
        assert "LLMSearchResultRelevance" not in names

    def test_open_eval_adds_llm_evaluator(self):
        from dingo.config.input_args import OpenEvalArgs
        from dingo.exec.retrieval import RetrievalExecutor
        from dingo.model import Model
        Model.load_model()

        input_args = InputArgs(**{
            "input_path": "SciFact",
            "output_path": "/tmp/test",
            "executor": {
                "retrieval": {
                    "backend": "agentic",
                    "api_url": "http://test",
                    "open_eval": {
                        "enabled": True,
                        "model": "gpt-4o",
                        "key": "test-key",
                        "api_url": "http://llm/v1",
                    },
                }
            },
        })
        executor = RetrievalExecutor(input_args)
        configs = executor._build_evaluator_configs()
        names = [c.name for c in configs]
        assert "RuleNDCG" in names
        assert "LLMSearchResultRelevance" in names

        llm_config = next(c for c in configs if c.name == "LLMSearchResultRelevance")
        assert llm_config.config.model == "gpt-4o"
        assert llm_config.config.key == "test-key"
        assert llm_config.config.api_url == "http://llm/v1"

    def test_standalone_mode_only_llm(self):
        from dingo.exec.retrieval import RetrievalExecutor
        from dingo.model import Model
        Model.load_model()

        input_args = InputArgs(**{
            "input_path": "__open_eval__",
            "output_path": "/tmp/test",
            "executor": {
                "retrieval": {
                    "backend": "agentic",
                    "api_url": "http://test",
                    "input_queries": "queries.jsonl",
                    "open_eval": {
                        "enabled": True,
                        "model": "gpt-4o",
                        "key": "k",
                        "api_url": "http://llm/v1",
                    },
                }
            },
        })
        executor = RetrievalExecutor(input_args)
        configs = executor._build_evaluator_configs()
        names = [c.name for c in configs]
        assert "RuleNDCG" not in names
        assert "LLMSearchResultRelevance" in names
