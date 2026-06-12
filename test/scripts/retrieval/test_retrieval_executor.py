"""Unit tests for RetrievalExecutor and CLI integration."""

import json
import os
import subprocess
import sys
from types import SimpleNamespace

import pytest

from dingo.config import InputArgs
from dingo.config.input_args import RetrievalArgs

PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

mteb = pytest.importorskip("mteb", reason="mteb not installed (extras 'retrieval')")


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


class TestRetrievalExecutorFallbackMetrics:
    def test_execute_uses_trace_metrics_when_mteb_metrics_empty(self, tmp_path, monkeypatch):
        import dingo.exec.retrieval as retrieval_module
        from dingo.exec.retrieval import RetrievalExecutor

        class FakeClient:
            name = "fake-openalex"

        input_args = InputArgs(**{
            "input_path": "SciFact",
            "output_path": str(tmp_path),
            "executor": {
                "retrieval": {
                    "backend": "openalex",
                    "api_url": "https://api.openalex.org",
                    "limit": 10,
                }
            },
        })
        executor = RetrievalExecutor(input_args)

        monkeypatch.setattr(retrieval_module, "create_client", lambda *a, **k: FakeClient())
        monkeypatch.setattr(retrieval_module.mteb, "get_tasks", lambda tasks: [object()])
        monkeypatch.setattr(RetrievalExecutor, "_attach_relevant_docs", lambda self, model, tasks: None)

        def fake_evaluate(model, tasks, overwrite_strategy):
            model._search_traces.append({
                "task": "SciFact",
                "total_queries": 2,
                "queries": [
                    {
                        "qid": "q1",
                        "retrieved_doc_ids": ["d1", "d2"],
                        "gold_doc_ids": ["d1"],
                    },
                    {
                        "qid": "q2",
                        "retrieved_doc_ids": ["d3"],
                        "gold_doc_ids": ["d4"],
                    },
                ],
            })
            return SimpleNamespace(
                task_results=[SimpleNamespace(scores={})],
            )

        monkeypatch.setattr(retrieval_module.mteb, "evaluate", fake_evaluate)

        summary = executor.execute()

        assert summary.score == 0.5
        assert summary.metrics_score_stats["SciFact"]["main_score"] == 0.5
        assert summary.metrics_score_stats["SciFact"]["ndcg_at_10"] == 0.5
        assert summary.metrics_score_stats["SciFact"]["recall_at_10"] == 0.5
