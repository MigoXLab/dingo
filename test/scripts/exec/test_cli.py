import json
import os
import subprocess
import sys
import tempfile
from unittest import mock

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def run_cli(*args, expect_exit=0):
    """Run the dingo CLI as a subprocess and return (stdout, stderr, returncode)."""
    cmd = [sys.executable, "-W", "ignore", "-m", "dingo.run.cli"] + list(args)
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=PROJECT_ROOT)
    if expect_exit is not None:
        assert result.returncode == expect_exit, (
            f"Expected exit code {expect_exit}, got {result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
    return result.stdout, result.stderr, result.returncode


def parse_json_from_output(text):
    """Extract and parse JSON from output that may contain non-JSON content (e.g. warnings)."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1:
            return json.loads(text[start:end + 1])
        raise


class TestCLIHelp:
    def test_root_help(self):
        stdout, _, _ = run_cli("--help")
        assert "eval" in stdout
        assert "info" in stdout
        assert "Dingo" in stdout

    def test_eval_help(self):
        stdout, _, _ = run_cli("eval", "--help")
        assert "--input" in stdout
        assert "--json" in stdout

    def test_info_help(self):
        stdout, _, _ = run_cli("info", "--help")
        assert "--rules" in stdout
        assert "--llm" in stdout
        assert "--groups" in stdout
        assert "--json" in stdout

    def test_no_args_shows_help(self):
        stdout, _, _ = run_cli()
        assert "eval" in stdout
        assert "info" in stdout


class TestCLIInfo:
    def test_info_rules_json(self):
        stdout, _, _ = run_cli("info", "--rules", "--json")
        data = json.loads(stdout)
        assert "rules" in data
        assert len(data["rules"]) > 0
        first_rule = next(iter(data["rules"].values()))
        assert "metric_type" in first_rule
        assert "groups" in first_rule
        assert "required_fields" in first_rule

    def test_info_llm_json(self):
        stdout, _, _ = run_cli("info", "--llm", "--json")
        data = json.loads(stdout)
        assert "llm_evaluators" in data
        assert len(data["llm_evaluators"]) > 0

    def test_info_groups_json(self):
        stdout, _, _ = run_cli("info", "--groups", "--json")
        data = json.loads(stdout)
        assert "groups" in data
        assert "default" in data["groups"]

    def test_info_all_json(self):
        stdout, _, _ = run_cli("info", "--json")
        data = json.loads(stdout)
        assert "rules" in data
        assert "llm_evaluators" in data
        assert "groups" in data

    def test_info_table_output(self):
        stdout, _, _ = run_cli("info", "--rules")
        assert "Rule Evaluators" in stdout
        assert "RuleColonEnd" in stdout


class TestCLIEval:
    def test_eval_json_output(self):
        config_path = os.path.join(PROJECT_ROOT, ".github/env/local_plaintext.json")
        stdout, _, _ = run_cli("eval", "--input", config_path, "--json")
        data = json.loads(stdout)
        assert "task_id" in data
        assert "score" in data
        assert "total" in data
        assert "type_ratio" in data
        assert data["total"] > 0

    def test_eval_plain_output(self):
        config_path = os.path.join(PROJECT_ROOT, ".github/env/local_plaintext.json")
        stdout, _, _ = run_cli("eval", "--input", config_path)
        assert "task_id=" in stdout
        assert "score=" in stdout

    def test_backward_compat_no_subcommand(self):
        config_path = os.path.join(PROJECT_ROOT, ".github/env/local_plaintext.json")
        stdout, _, _ = run_cli("--input", config_path)
        assert "task_id=" in stdout
        assert "score=" in stdout


class TestCLIErrorHandling:
    def test_missing_config_file_json(self):
        """--json mode: missing file produces JSON error on stderr with exit code 3."""
        _, stderr, code = run_cli("eval", "--input", "/nonexistent/path.json", "--json", expect_exit=3)
        data = parse_json_from_output(stderr)
        assert data["status"] == "error"
        assert data["error_type"] == "ConfigError"
        assert "not found" in data["message"]

    def test_missing_config_file_plain(self):
        """Non-JSON mode: missing file produces traceback with non-zero exit."""
        _, stderr, code = run_cli("eval", "--input", "/nonexistent/path.json", expect_exit=None)
        assert code != 0
        assert "FileNotFoundError" in stderr

    def test_invalid_json_config(self):
        """--json mode: malformed JSON produces JSON error with exit code 1."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("{bad json")
            f.flush()
            try:
                _, stderr, code = run_cli("eval", "--input", f.name, "--json", expect_exit=1)
                data = parse_json_from_output(stderr)
                assert data["status"] == "error"
                assert data["error_type"] == "ConfigError"
                assert "Invalid JSON" in data["message"]
            finally:
                os.unlink(f.name)

    def test_invalid_config_schema(self):
        """--json mode: valid JSON but invalid InputArgs produces JSON error with exit code 1."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"invalid_field_only": True}, f)
            f.flush()
            try:
                _, stderr, code = run_cli("eval", "--input", f.name, "--json", expect_exit=1)
                data = parse_json_from_output(stderr)
                assert data["status"] == "error"
                assert data["error_type"] == "ConfigError"
            finally:
                os.unlink(f.name)

    def test_exit_code_zero_on_success(self):
        """Successful eval returns exit code 0."""
        config_path = os.path.join(PROJECT_ROOT, ".github/env/local_plaintext.json")
        _, _, code = run_cli("eval", "--input", config_path, "--json", expect_exit=0)


class TestCLIExitCodes:
    def test_exit_0_success(self):
        config_path = os.path.join(PROJECT_ROOT, ".github/env/local_plaintext.json")
        _, _, code = run_cli("eval", "--input", config_path, "--json")
        assert code == 0

    def test_exit_1_config_error(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("not json")
            f.flush()
            try:
                _, _, code = run_cli("eval", "--input", f.name, "--json", expect_exit=1)
            finally:
                os.unlink(f.name)

    def test_exit_3_io_error(self):
        _, _, code = run_cli("eval", "--input", "/no/such/file.json", "--json", expect_exit=3)


class TestCLIServe:
    def test_serve_help(self):
        stdout, _, _ = run_cli("serve", "--help")
        assert "--transport" in stdout
        assert "--host" in stdout
        assert "--port" in stdout
        assert "sse" in stdout
        assert "stdio" in stdout

    def test_serve_args_defaults(self):
        """Verify default argument values are parsed correctly."""
        from dingo.run.cli import parse_args

        with mock.patch("sys.argv", ["dingo", "serve"]):
            args, _ = parse_args()
        assert args.command == "serve"
        assert args.transport == "sse"
        assert args.host == "0.0.0.0"
        assert args.port == 8000

    def test_serve_args_custom(self):
        """Verify custom argument values are parsed correctly."""
        from dingo.run.cli import parse_args

        with mock.patch("sys.argv", ["dingo", "serve", "--transport", "stdio", "--host", "127.0.0.1", "--port", "9000"]):
            args, _ = parse_args()
        assert args.transport == "stdio"
        assert args.host == "127.0.0.1"
        assert args.port == 9000

    def test_serve_invalid_transport(self):
        """Invalid transport value should cause argparse error."""
        _, stderr, code = run_cli("serve", "--transport", "invalid", expect_exit=2)
        assert "invalid choice" in stderr

    def test_serve_mcp_server_not_found(self):
        """cmd_serve should exit with error when mcp_server.py is missing."""
        from dingo.run.cli import cmd_serve

        args = mock.MagicMock()
        args.transport = "sse"
        args.host = "0.0.0.0"
        args.port = 8000

        with mock.patch("os.path.exists", return_value=False):
            with pytest.raises(SystemExit) as exc_info:
                cmd_serve(args)
            assert exc_info.value.code == 1

    def test_serve_loads_and_runs_mcp_sse(self):
        """cmd_serve should load mcp_server.py, configure settings, and call mcp.run with SSE."""
        from dingo.run.cli import cmd_serve

        mock_mcp = mock.MagicMock()
        mock_mcp.settings = mock.MagicMock()
        mock_module = mock.MagicMock()
        mock_module.mcp = mock_mcp

        args = mock.MagicMock()
        args.transport = "sse"
        args.host = "127.0.0.1"
        args.port = 9999

        with mock.patch("os.path.exists", return_value=True), \
             mock.patch("importlib.util.spec_from_file_location") as mock_spec_fn, \
             mock.patch("importlib.util.module_from_spec", return_value=mock_module):
            mock_spec = mock.MagicMock()
            mock_spec_fn.return_value = mock_spec

            cmd_serve(args)

            mock_spec.loader.exec_module.assert_called_once_with(mock_module)
            assert mock_mcp.settings.host == "127.0.0.1"
            assert mock_mcp.settings.port == 9999
            mock_mcp.run.assert_called_once_with(transport="sse")

    def test_serve_loads_and_runs_mcp_stdio(self):
        """cmd_serve should load mcp_server.py and call mcp.run with stdio transport."""
        from dingo.run.cli import cmd_serve

        mock_mcp = mock.MagicMock()
        mock_module = mock.MagicMock()
        mock_module.mcp = mock_mcp

        args = mock.MagicMock()
        args.transport = "stdio"

        with mock.patch("os.path.exists", return_value=True), \
             mock.patch("importlib.util.spec_from_file_location") as mock_spec_fn, \
             mock.patch("importlib.util.module_from_spec", return_value=mock_module):
            mock_spec = mock.MagicMock()
            mock_spec_fn.return_value = mock_spec

            cmd_serve(args)

            mock_mcp.run.assert_called_once_with(transport="stdio")
