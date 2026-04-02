"""Tests for dingo-verify skill's fact_check.py helper functions."""

import json
import os
import sys
import tempfile

import pytest

# Add the script directory to path so we can import helpers
SCRIPT_DIR = os.path.join(
    os.path.dirname(__file__), '..', '..', '..', '.claude', 'skills', 'dingo-verify', 'scripts'
)
sys.path.insert(0, os.path.abspath(SCRIPT_DIR))

from fact_check import MAX_ARTICLE_BYTES, build_config, build_report, detect_format, validate_article_path, wrap_plaintext  # noqa: E402


class TestDetectFormat:
    def test_markdown_needs_wrapping(self):
        fmt, needs_wrap = detect_format("article.md")
        assert fmt == "plaintext"
        assert needs_wrap is True

    def test_txt_needs_wrapping(self):
        fmt, needs_wrap = detect_format("article.txt")
        assert fmt == "plaintext"
        assert needs_wrap is True

    def test_jsonl_no_wrapping(self):
        fmt, needs_wrap = detect_format("data.jsonl")
        assert fmt == "jsonl"
        assert needs_wrap is False

    def test_json_no_wrapping(self):
        fmt, needs_wrap = detect_format("data.json")
        assert fmt == "json"
        assert needs_wrap is False

    def test_csv_defaults_to_plaintext_wrapping(self):
        fmt, needs_wrap = detect_format("data.csv")
        assert fmt == "plaintext"
        assert needs_wrap is True

    def test_unknown_extension_defaults_to_plaintext(self):
        fmt, needs_wrap = detect_format("data.xyz")
        assert fmt == "plaintext"
        assert needs_wrap is True


class TestWrapPlaintext:
    def test_creates_temp_jsonl_with_content(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write("This is a test article.\nWith multiple lines.")
            src_path = f.name

        temp_path = None
        try:
            temp_path = wrap_plaintext(src_path)
            assert temp_path.endswith('.jsonl')
            assert os.path.exists(temp_path)

            with open(temp_path, 'r', encoding='utf-8') as f:
                data = json.loads(f.readline())
            assert "content" in data
            assert "This is a test article." in data["content"]
            assert "With multiple lines." in data["content"]
        finally:
            os.unlink(src_path)
            if temp_path and os.path.exists(temp_path):
                os.unlink(temp_path)

    def test_preserves_unicode(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as f:
            f.write("清华大学发布了 OmniDocBench")
            src_path = f.name

        temp_path = None
        try:
            temp_path = wrap_plaintext(src_path)
            with open(temp_path, 'r', encoding='utf-8') as f:
                data = json.loads(f.readline())
            assert "清华大学" in data["content"]
        finally:
            os.unlink(src_path)
            if temp_path and os.path.exists(temp_path):
                os.unlink(temp_path)


class TestWrapPlaintextEmpty:
    def test_empty_file_raises_value_error(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write("")
            src_path = f.name

        try:
            with pytest.raises(ValueError, match="empty"):
                wrap_plaintext(src_path)
        finally:
            os.unlink(src_path)

    def test_file_too_large_raises_value_error(self):
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.md', delete=False) as f:
            # Write just over the limit
            f.write(b'x' * (MAX_ARTICLE_BYTES + 1))
            src_path = f.name

        try:
            with pytest.raises(ValueError, match="too large"):
                wrap_plaintext(src_path)
        finally:
            os.unlink(src_path)


class TestValidateArticlePath:
    def test_valid_md_file_passes(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            src_path = f.name

        try:
            result = validate_article_path(src_path)
            assert os.path.isabs(result)
        finally:
            os.unlink(src_path)

    def test_valid_jsonl_file_passes(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            src_path = f.name

        try:
            validate_article_path(src_path)  # Should not raise
        finally:
            os.unlink(src_path)

    def test_unsupported_extension_raises(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            src_path = f.name

        try:
            with pytest.raises(ValueError, match="Unsupported file type"):
                validate_article_path(src_path)
        finally:
            os.unlink(src_path)

    def test_special_proc_path_raises(self):
        with pytest.raises(ValueError, match="special filesystem"):
            validate_article_path("/proc/self/environ")

    def test_symlink_raises(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            target_path = f.name
        link_path = target_path + "_link.md"
        os.symlink(target_path, link_path)

        try:
            with pytest.raises(ValueError, match="symlink"):
                validate_article_path(link_path)
        finally:
            os.unlink(link_path)
            os.unlink(target_path)


class TestBuildConfig:
    def test_basic_config_structure(self):
        config = build_config(
            input_path="test.jsonl",
            data_format="jsonl",
            model="gpt-4o-mini",
            api_key="sk-test",
            api_url="https://api.openai.com/v1",
            tavily_key=None,
            max_claims=50,
            max_concurrent=5,
        )
        assert config["input_path"] == "test.jsonl"
        assert config["dataset"]["format"] == "jsonl"
        evaluator = config["evaluator"][0]["evals"][0]
        assert evaluator["name"] == "ArticleFactChecker"
        assert evaluator["config"]["model"] == "gpt-4o-mini"

    def test_tavily_omitted_when_no_key(self):
        config = build_config(
            input_path="test.jsonl",
            data_format="jsonl",
            model="gpt-4o-mini",
            api_key="sk-test",
            api_url="https://api.openai.com/v1",
            tavily_key=None,
            max_claims=50,
            max_concurrent=5,
        )
        tools = config["evaluator"][0]["evals"][0]["config"]["agent_config"]["tools"]
        assert "tavily_search" not in tools
        assert "claims_extractor" in tools
        assert "arxiv_search" in tools

    def test_tavily_included_when_key_present(self):
        config = build_config(
            input_path="test.jsonl",
            data_format="jsonl",
            model="gpt-4o-mini",
            api_key="sk-test",
            api_url="https://api.openai.com/v1",
            tavily_key="tvly-xxx",
            max_claims=50,
            max_concurrent=5,
        )
        tools = config["evaluator"][0]["evals"][0]["config"]["agent_config"]["tools"]
        assert "tavily_search" in tools
        assert tools["tavily_search"]["api_key"] == "tvly-xxx"

    def test_temperature_is_zero(self):
        config = build_config(
            input_path="test.jsonl",
            data_format="jsonl",
            model="gpt-4o-mini",
            api_key="sk-test",
            api_url="https://api.openai.com/v1",
            tavily_key=None,
            max_claims=50,
            max_concurrent=5,
        )
        cfg = config["evaluator"][0]["evals"][0]["config"]
        assert cfg["temperature"] == 0


class TestErrorOutput:
    def test_missing_api_key_outputs_error_json(self):
        """Run script without OPENAI_API_KEY, verify stderr JSON."""
        import subprocess

        script_path = os.path.join(os.path.abspath(SCRIPT_DIR), 'fact_check.py')
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write("Test article content.")
            dummy_path = f.name

        try:
            env = os.environ.copy()
            env.pop("OPENAI_API_KEY", None)
            result = subprocess.run(
                [sys.executable, script_path, dummy_path],
                capture_output=True, text=True, env=env
            )
            assert result.returncode == 1
            error_data = json.loads(result.stderr.strip().split('\n')[-1])
            assert error_data["success"] is False
            assert "OPENAI_API_KEY" in error_data["error"]
        finally:
            os.unlink(dummy_path)


class TestBuildReport:
    def test_builds_report_from_summary_and_detail(self):
        summary = {
            "output_path": "/tmp/test_output",
            "total": 1,
            "num_good": 0,
            "num_bad": 1,
            "score": 0.0,
        }

        detail_report = {
            "verification_summary": {
                "total_verified": 5,
                "verified_true": 3,
                "verified_false": 1,
                "unverifiable": 1,
                "accuracy_score": 0.6,
            },
            "detailed_findings": [
                {
                    "claim_id": "claim_001",
                    "original_claim": "Test claim",
                    "claim_type": "factual",
                    "verification_result": "FALSE",
                    "evidence": "Contradicted by source",
                    "sources": ["https://example.com"],
                }
            ],
            "false_claims_comparison": [
                {
                    "article_claimed": "X is true",
                    "evidence": "X is false",
                }
            ],
        }

        report = build_report(summary, detail_report, duration=10.5)
        assert report["success"] is True
        assert report["summary"]["total_items"] == 1
        assert report["summary"]["dingo_score"] == 0.0
        assert report["verification"]["accuracy_score"] == 0.6
        assert len(report["false_claims"]) == 1
        assert len(report["all_claims"]) == 1
        assert report["duration_seconds"] == 10.5
