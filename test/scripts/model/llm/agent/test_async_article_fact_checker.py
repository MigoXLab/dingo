"""
Tests for the two-phase async ArticleFactChecker.

Covers:
- Parallel execution path (mock agents)
- Semaphore concurrency limit
- asyncio.run() bridge in thread context
- Fallback when event loop is already running
- JSON parsing from mini-agent output
- Fallback when parsing fails
- _build_unverifiable_claim_record error handling
- _aggregate_parallel_results summary calculation
"""

import asyncio
import json
import threading
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ─── Fixtures ────────────────────────────────────────────────────────────────


def _make_claim(n: int) -> dict:
    return {
        "claim_id": f"claim_{n:03d}",
        "claim": f"Test claim number {n}",
        "claim_type": "factual",
        "confidence": 0.9,
        "verifiable": True,
    }


def _make_agent_result(verdict: str = "TRUE", tool: str = "tavily_search") -> dict:
    output_json = json.dumps({
        "verification_result": verdict,
        "evidence": f"Evidence for {verdict}",
        "sources": ["https://example.com"],
        "verification_method": tool,
        "search_queries_used": ["test query"],
        "reasoning": f"Found direct evidence: {verdict}",
    })
    return {
        "output": output_json,
        "messages": [],
        "tool_calls": [{"tool": tool, "args": {"query": "test query"}, "observation": "ok"}],
        "reasoning_steps": 2,
        "success": True,
    }


# ─── Tests for _parse_single_claim_result ────────────────────────────────────


class TestParseSingleClaimResult:
    """Unit tests for JSON parsing of mini-agent output."""

    def setup_method(self):
        from dingo.model.llm.agent.agent_article_fact_checker import ArticleFactChecker

        self.checker = ArticleFactChecker

    def test_parse_valid_json_returns_enriched_record(self):
        """Valid JSON output should be fully parsed into enriched record."""
        claim = _make_claim(1)
        agent_result = _make_agent_result("TRUE", "tavily_search")

        result = self.checker._parse_single_claim_result(claim, agent_result)

        assert result["claim_id"] == "claim_001"
        assert result["verification_result"] == "TRUE"
        assert result["evidence"] == "Evidence for TRUE"
        assert result["sources"] == ["https://example.com"]
        assert result["verification_method"] == "tavily_search"
        assert "Found direct evidence" in result["reasoning"]

    def test_parse_false_verdict(self):
        """FALSE verdict should be preserved correctly."""
        claim = _make_claim(2)
        agent_result = _make_agent_result("FALSE", "arxiv_search")

        result = self.checker._parse_single_claim_result(claim, agent_result)

        assert result["verification_result"] == "FALSE"

    def test_parse_invalid_json_falls_back_gracefully(self):
        """When LLM returns non-JSON, should fall back to UNVERIFIABLE with truncated output."""
        claim = _make_claim(3)
        agent_result = {
            "output": "Sorry, I could not find any evidence.",
            "tool_calls": [],
            "reasoning_steps": 1,
            "success": True,
        }

        result = self.checker._parse_single_claim_result(claim, agent_result)

        assert result["claim_id"] == "claim_003"
        assert result["verification_result"] == "UNVERIFIABLE"
        assert "Sorry" in result["reasoning"]

    def test_parse_extracts_search_queries_from_tool_calls(self):
        """When JSON lacks search_queries_used, should extract from tool_calls."""
        claim = _make_claim(4)
        output_json = json.dumps({
            "verification_result": "TRUE",
            "evidence": "Found",
            "sources": [],
            "verification_method": "tavily_search",
            "reasoning": "ok",
            # search_queries_used intentionally omitted
        })
        agent_result = {
            "output": output_json,
            "tool_calls": [
                {"tool": "tavily_search", "args": {"query": "my search"}, "observation": "data"}
            ],
            "reasoning_steps": 1,
            "success": True,
        }

        result = self.checker._parse_single_claim_result(claim, agent_result)

        assert result["search_queries_used"] == ["my search"]

    def test_parse_combined_method_when_multiple_tools_used(self):
        """When multiple tools are used, verification_method should be 'combined'."""
        claim = _make_claim(5)
        output_json = json.dumps({
            "verification_result": "TRUE",
            "evidence": "Multi-source",
            "sources": [],
            "reasoning": "both tools used",
            # verification_method intentionally omitted
        })
        agent_result = {
            "output": output_json,
            "tool_calls": [
                {"tool": "tavily_search", "args": {"query": "q1"}, "observation": ""},
                {"tool": "arxiv_search", "args": {"query": "q2"}, "observation": ""},
            ],
            "reasoning_steps": 2,
            "success": True,
        }

        result = self.checker._parse_single_claim_result(claim, agent_result)

        assert result["verification_method"] == "combined"


# ─── Tests for _parse_claim_json_robust ──────────────────────────────────────


class TestParseClaimJsonRobust:
    """Unit tests for the three-tier robust JSON parser."""

    def setup_method(self):
        from dingo.model.llm.agent.agent_article_fact_checker import ArticleFactChecker

        self.checker = ArticleFactChecker

    def test_complete_json_parsed_normally(self):
        """Tier 1: complete JSON with verification_result should parse directly."""
        output = json.dumps({
            "verification_result": "TRUE",
            "evidence": "Found direct evidence.",
            "sources": ["https://example.com"],
            "reasoning": "The claim is supported by evidence.",
        })
        result = self.checker._parse_claim_json_robust(output)

        assert result["verification_result"] == "TRUE"
        assert result["evidence"] == "Found direct evidence."
        assert result["sources"] == ["https://example.com"]
        assert "supported" in result["reasoning"]

    def test_truncated_json_missing_closing_brace(self):
        """Tier 2: JSON truncated mid-value, missing closing brace, should be repaired."""
        output = (
            '{"verification_result": "FALSE", "evidence": "Contradicted by source X", '
            '"sources": ["https://example.com"], "reasoning": "The claim is false'
        )
        result = self.checker._parse_claim_json_robust(output)

        assert result["verification_result"] == "FALSE"
        assert "Contradicted" in result.get("evidence", "")

    def test_markdown_wrapped_truncated_json(self):
        """Tier 2: markdown code-block wrapped truncated JSON should be unwrapped and repaired."""
        output = (
            '```json\n'
            '{"verification_result": "TRUE", "evidence": "Confirmed by multiple sources", '
            '"sources": ["https://a.com", "https://b.com"], "reasoning": "Strong evidence'
        )
        result = self.checker._parse_claim_json_robust(output)

        assert result.get("verification_result") == "TRUE"
        assert "Confirmed" in result.get("evidence", "")

    def test_truncated_json_with_corrupted_trailing_text_repaired_by_tier2(self):
        """Tier 2: truncated JSON with corrupted trailing text should be repaired by truncation repair."""
        output = (
            '{"verification_result": "FALSE", "evidence": "The data shows otherwise", '
            '"sources": ["https://example.com"], "reasoning": "Clear contradiction<ctrl46>'
        )
        result = self.checker._parse_claim_json_robust(output)

        assert result.get("verification_result") == "FALSE"
        assert "data shows" in result.get("evidence", "")
        assert result.get("sources") == ["https://example.com"]

    def test_completely_irrelevant_text_returns_empty(self):
        """When output is completely non-JSON, should return empty dict."""
        output = "I apologize, but I was unable to verify this claim due to technical issues."
        result = self.checker._parse_claim_json_robust(output)

        assert result == {}

    def test_empty_string_returns_empty(self):
        """Empty string input should return empty dict."""
        assert self.checker._parse_claim_json_robust("") == {}

    def test_none_input_returns_empty(self):
        """None input should return empty dict."""
        assert self.checker._parse_claim_json_robust(None) == {}

    def test_truncated_json_with_incomplete_sources_array(self):
        """Tier 2: JSON truncated inside sources array should recover what it can."""
        output = (
            '{"verification_result": "TRUE", "evidence": "Found evidence", '
            '"sources": ["https://a.com", "https://b.com'
        )
        result = self.checker._parse_claim_json_robust(output)

        # Should at least extract verification_result
        assert result.get("verification_result") == "TRUE"

    def test_json_embedded_in_surrounding_text(self):
        """Tier 1: JSON block embedded in prose should be extracted."""
        output = (
            'Based on my analysis, here is the result:\n'
            '{"verification_result": "UNVERIFIABLE", "evidence": "", "sources": [], '
            '"reasoning": "No relevant sources found"}\n'
            'Let me know if you need more details.'
        )
        result = self.checker._parse_claim_json_robust(output)

        assert result["verification_result"] == "UNVERIFIABLE"
        assert result["reasoning"] == "No relevant sources found"

    def test_tier1_match_but_invalid_json_falls_to_tier2(self):
        """Tier 1 regex match with trailing comma should fall through to Tier 2."""
        output = (
            '{"verification_result": "TRUE", "evidence": "found",}'
        )
        result = self.checker._parse_claim_json_robust(output)

        # Tier 1 json.loads fails on trailing comma; Tier 2 or Tier 3 should recover
        assert result.get("verification_result") == "TRUE"

    def test_case_insensitive_verdict_in_tier3(self):
        """Tier 3 should match lowercase/mixed-case verdicts and normalize to uppercase."""
        # No opening brace → Tier 1 and 2 skip, only Tier 3 regex fires
        output = 'Result: "verification_result": "true", "evidence": "confirmed"'
        result = self.checker._parse_claim_json_robust(output)

        assert result.get("verification_result") == "TRUE"
        assert result.get("evidence") == "confirmed"

    def test_escaped_quotes_in_string_values(self):
        """Strings with escaped quotes should be parsed correctly."""
        output = json.dumps({
            "verification_result": "TRUE",
            "evidence": 'The study states "significant results"',
            "sources": [],
            "reasoning": "ok",
        })
        result = self.checker._parse_claim_json_robust(output)

        assert result["verification_result"] == "TRUE"
        assert '"significant results"' in result["evidence"]

    def test_truncated_json_missing_reasoning_repaired_by_tier2(self):
        """Tier 2: truncated JSON with missing closing quote/brace should recover reasoning field."""
        output = (
            '{"verification_result": "FALSE", '
            '"reasoning": "The claim contradicts multiple peer-reviewed'
        )
        result = self.checker._parse_claim_json_robust(output)

        assert result.get("verification_result") == "FALSE"
        assert "contradicts" in result.get("reasoning", "")

    def test_integration_with_parse_single_claim_result(self):
        """Robust parser should integrate correctly with _parse_single_claim_result."""
        claim = _make_claim(99)
        # Simulate truncated output that old regex couldn't handle
        truncated_output = (
            '{"verification_result": "FALSE", "evidence": "Source contradicts claim", '
            '"sources": ["https://example.com"], "reasoning": "Clear evidence of'
        )
        agent_result = {
            "output": truncated_output,
            "tool_calls": [{"tool": "tavily_search", "args": {"query": "test"}, "observation": "ok"}],
            "reasoning_steps": 2,
            "success": True,
        }

        result = self.checker._parse_single_claim_result(claim, agent_result)

        # Should recover FALSE instead of falling back to UNVERIFIABLE
        assert result["verification_result"] == "FALSE"
        assert "contradicts" in result.get("evidence", "").lower()


# ─── Tests for _build_unverifiable_claim_record ──────────────────────────────


class TestBuildUnverifiableClaimRecord:
    def setup_method(self):
        from dingo.model.llm.agent.agent_article_fact_checker import ArticleFactChecker

        self.checker = ArticleFactChecker

    def test_builds_correct_structure(self):
        claim = _make_claim(1)
        record = self.checker._build_unverifiable_claim_record(claim, "API timeout")

        assert record["claim_id"] == "claim_001"
        assert record["verification_result"] == "UNVERIFIABLE"
        assert record["verification_method"] == "error"
        assert "API timeout" in record["reasoning"]
        assert record["sources"] == []
        assert "error_type" not in record


# ─── Tests for _aggregate_parallel_results ───────────────────────────────────


class TestAggregateParallelResults:
    def setup_method(self):
        from dingo.io.input.data import Data
        from dingo.model.llm.agent.agent_article_fact_checker import ArticleFactChecker

        self.checker = ArticleFactChecker
        self.data = Data(dingo_id="test_001", content="Test article content")

    def _make_vr_success(self, verdict: str) -> dict:
        """Create a success verification result dict."""
        agent_result = _make_agent_result(verdict)
        # Replace reasoning with non-hedging text for TRUE to pass consistency check
        if verdict == "TRUE":
            out = json.loads(agent_result["output"])
            out["reasoning"] = "Confirmed by direct evidence at https://example.com"
            agent_result["output"] = json.dumps(out)
        return {"claim": _make_claim(1), "agent_result": agent_result, "success": True}

    def test_summary_counts_are_correct(self):
        """_recalculate_summary should match actual verdict distribution."""
        claims = [_make_claim(i) for i in range(1, 4)]
        vr_true = self._make_vr_success("TRUE")
        vr_false = self._make_vr_success("FALSE")
        vr_unver = self._make_vr_success("UNVERIFIABLE")

        # Give each result the right claim
        vr_true["claim"] = claims[0]
        vr_false["claim"] = claims[1]
        vr_unver["claim"] = claims[2]

        result = self.checker._aggregate_parallel_results(
            self.data, claims, [vr_true, vr_false, vr_unver], time.time() - 1.0, None
        )

        # Check the EvalDetail score
        assert result.score == pytest.approx(1 / 3, abs=0.01)
        # Has false claim → status True (issue detected)
        assert result.status is True

    def test_exception_in_verification_result_becomes_unverifiable(self):
        """Exception objects from asyncio.gather should be handled gracefully."""
        claims = [_make_claim(1)]
        exc_result = RuntimeError("API rate limit exceeded")

        result = self.checker._aggregate_parallel_results(
            self.data, claims, [exc_result], time.time() - 1.0, None
        )

        # UNVERIFIABLE claim → has_issues is True
        assert result.status is True
        assert result.score == pytest.approx(0.0)

    def test_failed_success_flag_becomes_unverifiable(self):
        """success=False in vr should produce UNVERIFIABLE record."""
        claims = [_make_claim(1)]
        failed_vr = {"claim": claims[0], "agent_result": {"error": "timeout"}, "success": False}

        result = self.checker._aggregate_parallel_results(
            self.data, claims, [failed_vr], time.time() - 1.0, None
        )

        assert result.status is True  # UNVERIFIABLE → has_issues


# ─── Tests for asyncio.run() bridge ──────────────────────────────────────────


class TestAsyncioRunBridge:
    """Verify asyncio.run() works correctly inside a non-async (thread) context."""

    def test_asyncio_run_in_thread_context(self):
        """asyncio.run() should work in a fresh thread with no existing event loop."""
        result_holder = []

        async def dummy_coroutine():
            return 42

        def run_in_thread():
            value = asyncio.run(dummy_coroutine())
            result_holder.append(value)

        t = threading.Thread(target=run_in_thread)
        t.start()
        t.join(timeout=5.0)

        assert not t.is_alive(), "Thread should have completed"
        assert result_holder == [42]

    def test_asyncio_gather_with_semaphore(self):
        """asyncio.gather with Semaphore should respect max_concurrent limit."""
        max_concurrent = 3
        concurrent_tracker = {"current": 0, "max_seen": 0}

        async def task_with_semaphore(sem):
            async with sem:
                concurrent_tracker["current"] += 1
                concurrent_tracker["max_seen"] = max(
                    concurrent_tracker["max_seen"], concurrent_tracker["current"]
                )
                await asyncio.sleep(0.01)
                concurrent_tracker["current"] -= 1

        async def run():
            sem = asyncio.Semaphore(max_concurrent)
            await asyncio.gather(*[task_with_semaphore(sem) for _ in range(10)])

        asyncio.run(run())

        assert concurrent_tracker["max_seen"] <= max_concurrent

    def test_fallback_when_event_loop_running(self):
        """ThreadPoolExecutor fallback should produce the same result as asyncio.run()."""
        import concurrent.futures

        async def dummy():
            return "from_thread"

        result_holder = []

        def run_with_fallback():
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(lambda: asyncio.run(dummy()))
                result_holder.append(future.result())

        t = threading.Thread(target=run_with_fallback)
        t.start()
        t.join(timeout=5.0)

        assert result_holder == ["from_thread"]


# ─── Tests for _async_eval with mocked agents ────────────────────────────────


class TestAsyncEvalWithMocks:
    """Integration-level tests using mocked LLM/tools (run via asyncio.run)."""

    def setup_method(self):
        from dingo.io.input.data import Data
        from dingo.model.llm.agent.agent_article_fact_checker import ArticleFactChecker

        self.checker = ArticleFactChecker
        self.data = Data(dingo_id="art_001", content="Short test article with one fact.")

    def test_async_eval_with_mocked_components(self):
        """Full async_eval flow should complete and return EvalDetail when mocked."""
        from dingo.io.output.eval_detail import EvalDetail

        mock_claims = [_make_claim(1), _make_claim(2)]
        mock_agent_result = _make_agent_result("TRUE")
        # Use non-hedging reasoning to avoid consistency downgrade
        out = json.loads(mock_agent_result["output"])
        out["reasoning"] = "Confirmed by https://example.com directly."
        mock_agent_result["output"] = json.dumps(out)

        async def run():
            with (
                patch.object(
                    self.checker, '_async_extract_claims',
                    new=AsyncMock(return_value=mock_claims)
                ),
                patch.object(self.checker, '_save_claims'),
                patch.object(self.checker, 'get_langchain_llm', return_value=MagicMock()),
                patch.object(self.checker, 'get_langchain_tools', return_value=[]),
                patch.object(
                    self.checker,
                    '_async_verify_single_claim',
                    new=AsyncMock(
                        return_value={
                            "claim": mock_claims[0],
                            "agent_result": mock_agent_result,
                            "success": True,
                        }
                    ),
                ),
            ):
                return await self.checker._async_eval(self.data, time.time(), None)

        result = asyncio.run(run())
        assert isinstance(result, EvalDetail)
        assert result.metric == "ArticleFactChecker"

    def test_async_eval_returns_error_when_no_claims(self):
        """Empty claim extraction should return an error EvalDetail."""
        async def run():
            with patch.object(
                self.checker, '_async_extract_claims', new=AsyncMock(return_value=[])
            ):
                return await self.checker._async_eval(self.data, time.time(), None)

        result = asyncio.run(run())

        assert result.status is True
        assert any("No claims" in str(r) for r in result.reason)


# ─── Tests for _get_max_concurrent_claims ────────────────────────────────────


class TestGetMaxConcurrentClaims:
    def setup_method(self):
        from dingo.model.llm.agent.agent_article_fact_checker import ArticleFactChecker

        self.checker = ArticleFactChecker

    def test_returns_class_default_when_no_config(self):
        """Should return max_concurrent_claims class default when not configured."""
        with patch.object(self.checker, 'dynamic_config') as mock_cfg:
            mock_cfg.model_extra = {}
            result = self.checker._get_max_concurrent_claims()
        assert result == self.checker.max_concurrent_claims

    def test_returns_config_value_when_set(self):
        """Should return value from agent_config.max_concurrent_claims."""
        with patch.object(self.checker, 'dynamic_config') as mock_cfg:
            mock_cfg.model_extra = {"agent_config": {"max_concurrent_claims": 10}}
            result = self.checker._get_max_concurrent_claims()
        assert result == 10
