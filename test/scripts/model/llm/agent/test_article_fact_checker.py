"""
Integration tests for ArticleFactChecker agent.

Tests the end-to-end article fact-checking workflow including:
- Agent initialization and configuration
- Tool registration and availability
- Result structure validation
- Claims extraction from tool calls
- Per-claim verification merging
- Structured report generation
- File saving methods
- Verdict normalization and summary recalculation
- Claims fallback extraction from detailed_findings
- Prompt enhancements (VERDICT_CRITERIA, SELF_VERIFICATION_STEP)
"""

import json
import os
import tempfile
from pathlib import Path

import pytest

from dingo.io.input import Data
from dingo.model import Model
from dingo.model.llm.agent import ArticleFactChecker
from dingo.model.llm.agent.agent_article_fact_checker import PromptTemplates


class TestArticleFactCheckerBasic:
    """Basic tests for ArticleFactChecker agent structure"""

    def test_agent_registered(self):
        """Test that ArticleFactChecker is registered in Model registry"""
        Model.load_model()
        assert "ArticleFactChecker" in Model.llm_name_map
        assert Model.llm_name_map["ArticleFactChecker"] == ArticleFactChecker

    def test_agent_configuration(self):
        """Test agent configuration attributes"""
        assert ArticleFactChecker.use_agent_executor is True
        assert 'claims_extractor' in ArticleFactChecker.available_tools
        assert 'arxiv_search' in ArticleFactChecker.available_tools
        assert 'tavily_search' in ArticleFactChecker.available_tools
        assert ArticleFactChecker.max_iterations == 10

    def test_format_agent_input(self):
        """Test _format_agent_input method"""
        article_text = "Test article content"
        data = Data(content=article_text)

        result = ArticleFactChecker._format_agent_input(data)

        assert "ARTICLE START" in result
        assert "ARTICLE END" in result
        assert article_text in result
        assert "analyze the article type" in result
        assert "Extract ALL verifiable claims" in result

    def test_get_system_prompt(self):
        """Test system prompt generation"""
        data = Data(content="test")
        prompt = ArticleFactChecker._get_system_prompt(data)

        # Check core prompt content
        assert "expert article fact-checker" in prompt
        assert "claims_extractor" in prompt
        assert "arxiv_search" in prompt
        assert "tavily_search" in prompt
        # Check for all 8 claim types
        assert "temporal" in prompt
        assert "comparative" in prompt
        assert "monetary" in prompt
        assert "technical" in prompt
        # Check for article type analysis step (modular prompts)
        assert "article type" in prompt.lower()
        assert "Analyze Article Type" in prompt

    def test_get_system_prompt_with_article_type(self):
        """Test system prompt generation with specific article type"""
        # Test default prompt
        default_prompt = PromptTemplates.build()
        assert "expert article fact-checker" in default_prompt
        assert len(default_prompt) > 3000  # Substantial prompt

        # Test academic article type prompt
        academic_prompt = PromptTemplates.build(article_type="academic")
        assert "arxiv_search" in academic_prompt
        assert len(academic_prompt) > len(default_prompt)  # Has additional guidance

        # Test news article type prompt
        news_prompt = PromptTemplates.build(article_type="news")
        assert "tavily_search" in news_prompt

        # Test all article types are available
        article_types = PromptTemplates.get_article_types()
        assert "academic" in article_types
        assert "news" in article_types
        assert "product" in article_types
        assert "blog" in article_types
        assert len(article_types) == 6

    def test_output_format_prompt_contains_new_fields(self):
        """Test that OUTPUT_FORMAT prompt requires verification_method, search_queries_used, reasoning"""
        output_fmt = PromptTemplates.OUTPUT_FORMAT
        assert "verification_method" in output_fmt
        assert "search_queries_used" in output_fmt
        assert "reasoning" in output_fmt


class TestArticleFactCheckerResultStructure:
    """Test result structure and parsing"""

    def test_parse_verification_output_json(self):
        """Test parsing valid JSON output"""
        json_output = """{
            "article_verification_summary": {
                "article_type": "academic",
                "total_claims": 5,
                "verified_claims": 4,
                "false_claims": 1,
                "unverifiable_claims": 0,
                "accuracy_score": 0.8
            }
        }"""

        result = ArticleFactChecker._parse_verification_output(json_output)

        assert result is not None
        assert "article_verification_summary" in result
        assert result["article_verification_summary"]["total_claims"] == 5
        assert result["article_verification_summary"]["false_claims"] == 1

    def test_parse_verification_output_with_code_block(self):
        """Test parsing JSON in code block"""
        output_with_block = """Here is the result:
```json
{
    "article_verification_summary": {
        "total_claims": 3,
        "verified_claims": 3,
        "false_claims": 0,
        "accuracy_score": 1.0
    }
}
```
"""

        result = ArticleFactChecker._parse_verification_output(output_with_block)

        assert result is not None
        assert result["article_verification_summary"]["total_claims"] == 3
        assert result["article_verification_summary"]["false_claims"] == 0

    def test_parse_verification_output_fallback(self):
        """Test fallback parsing for non-JSON output"""
        text_output = """
        Total claims: 5
        False claims: 2
        Verified claims: 3
        """

        result = ArticleFactChecker._parse_verification_output(text_output)

        assert result is not None
        assert "article_verification_summary" in result
        assert result["article_verification_summary"]["total_claims"] == 5
        assert result["article_verification_summary"]["false_claims"] == 2

    def test_build_eval_detail_from_verification_without_report(self):
        """Test building EvalDetail from verification data (no report)"""
        verification_data = {
            "article_verification_summary": {
                "total_claims": 10,
                "verified_claims": 8,
                "false_claims": 2,
                "unverifiable_claims": 0,
                "accuracy_score": 0.8
            },
            "detailed_findings": [
                {"claim_id": "claim_001", "verification_result": "TRUE"},
                {"claim_id": "claim_002", "verification_result": "FALSE"}
            ]
        }

        result = ArticleFactChecker._build_eval_detail_from_verification(
            verification_data, tool_calls=[], reasoning_steps=5
        )

        assert result is not None
        assert result.metric == "ArticleFactChecker"
        assert result.status is True  # Has false claims
        assert result.score == 0.8
        assert len(result.reason) >= 1
        # reason[0] should be a string summary
        assert isinstance(result.reason[0], str)
        assert "Total Claims" in result.reason[0]

    def test_build_eval_detail_from_verification_with_report(self):
        """Test building EvalDetail with dual-layer reason (text + report)"""
        verification_data = {
            "article_verification_summary": {
                "total_claims": 5,
                "verified_claims": 4,
                "false_claims": 1,
                "unverifiable_claims": 0,
                "accuracy_score": 0.8
            },
            "detailed_findings": []
        }
        report = {"report_version": "2.0", "verification_summary": {"accuracy_score": 0.8}}

        result = ArticleFactChecker._build_eval_detail_from_verification(
            verification_data, tool_calls=[], reasoning_steps=3, report=report
        )

        assert len(result.reason) == 2
        assert isinstance(result.reason[0], str)
        assert isinstance(result.reason[1], dict)
        assert result.reason[1]["report_version"] == "2.0"

    def test_create_error_result(self):
        """Test error result creation"""
        error_msg = "Test error message"

        result = ArticleFactChecker._create_error_result(error_msg)

        assert result is not None
        assert result.metric == "ArticleFactChecker"
        assert result.status is True  # Error = issue
        assert any("ERROR" in label for label in result.label)
        assert any(error_msg in str(line) for line in result.reason)


class TestClaimsExtractionFromToolCalls:
    """Test _extract_claims_from_tool_calls method"""

    def test_extract_claims_from_valid_tool_calls(self):
        """Test extracting claims from claims_extractor observation"""
        tool_calls = [
            {
                "tool": "claims_extractor",
                "args": {"text": "article text..."},
                "observation": json.dumps({
                    "success": True,
                    "data": {
                        "claims": [
                            {"claim_id": "claim_001", "claim": "Claim A", "claim_type": "factual", "confidence": 0.9},
                            {"claim_id": "claim_002", "claim": "Claim B", "claim_type": "institutional", "confidence": 0.85}
                        ]
                    }
                })
            },
            {
                "tool": "tavily_search",
                "args": {"query": "Claim A"},
                "observation": "{\"success\": true, \"data\": {\"results\": []}}"
            }
        ]

        claims = ArticleFactChecker._extract_claims_from_tool_calls(tool_calls)

        assert len(claims) == 2
        assert claims[0]["claim_id"] == "claim_001"
        assert claims[1]["claim_type"] == "institutional"

    def test_extract_claims_from_empty_tool_calls(self):
        """Test with no tool calls"""
        claims = ArticleFactChecker._extract_claims_from_tool_calls([])
        assert claims == []

    def test_extract_claims_when_no_claims_extractor_called(self):
        """Test when only search tools were called"""
        tool_calls = [
            {"tool": "tavily_search", "args": {"query": "test"}, "observation": "{}"}
        ]
        claims = ArticleFactChecker._extract_claims_from_tool_calls(tool_calls)
        assert claims == []

    def test_extract_claims_with_failed_observation(self):
        """Test when claims_extractor returned failure"""
        tool_calls = [
            {
                "tool": "claims_extractor",
                "args": {"text": "article"},
                "observation": json.dumps({"success": False, "error": "API error"})
            }
        ]
        claims = ArticleFactChecker._extract_claims_from_tool_calls(tool_calls)
        assert claims == []

    def test_extract_claims_with_malformed_observation(self):
        """Test when observation is not valid JSON"""
        tool_calls = [
            {"tool": "claims_extractor", "args": {}, "observation": "not json"}
        ]
        claims = ArticleFactChecker._extract_claims_from_tool_calls(tool_calls)
        assert claims == []


class TestPerClaimVerification:
    """Test _build_per_claim_verification method"""

    def test_merge_with_complete_data(self):
        """Test merging when all three data sources have matching data"""
        verification_data = {
            "detailed_findings": [
                {
                    "claim_id": "claim_001",
                    "original_claim": "Test claim",
                    "claim_type": "factual",
                    "verification_result": "TRUE",
                    "evidence": "Found evidence",
                    "sources": ["https://example.com"],
                    "verification_method": "tavily_search",
                    "search_queries_used": ["test query"],
                    "reasoning": "Step-by-step..."
                }
            ],
            "false_claims_comparison": []
        }
        extracted_claims = [
            {"claim_id": "claim_001", "claim": "Test claim", "claim_type": "factual", "confidence": 0.95}
        ]
        tool_calls = [
            {"tool": "tavily_search", "args": {"query": "test query"}, "observation": "{}"}
        ]

        enriched = ArticleFactChecker._build_per_claim_verification(
            verification_data, extracted_claims, tool_calls
        )

        assert len(enriched) == 1
        assert enriched[0]["claim_id"] == "claim_001"
        assert enriched[0]["confidence"] == 0.95
        assert enriched[0]["verification_result"] == "TRUE"
        assert enriched[0]["verification_method"] == "tavily_search"

    def test_merge_with_false_claims_preserves_evidence(self):
        """Test that FALSE claims preserve evidence from detailed_findings"""
        verification_data = {
            "detailed_findings": [
                {
                    "claim_id": "claim_001",
                    "original_claim": "OpenAI released o1 in November 2024",
                    "verification_result": "FALSE",
                    "evidence": "Released Dec 5"
                }
            ],
            "false_claims_comparison": [
                {
                    "article_claimed": "OpenAI released o1 in November 2024",
                    "actual_truth": "Released December 5",
                }
            ]
        }

        enriched = ArticleFactChecker._build_per_claim_verification(
            verification_data, [], []
        )

        assert len(enriched) == 1
        assert enriched[0]["verification_result"] == "FALSE"
        assert enriched[0]["evidence"] == "Released Dec 5"
        assert "error_type" not in enriched[0]
        assert "severity" not in enriched[0]

    def test_fallback_when_no_detailed_findings(self):
        """Test placeholder records when agent has no detailed_findings"""
        verification_data = {"detailed_findings": []}
        extracted_claims = [
            {"claim_id": "claim_001", "claim": "Some claim", "claim_type": "factual", "confidence": 0.9}
        ]

        enriched = ArticleFactChecker._build_per_claim_verification(
            verification_data, extracted_claims, []
        )

        assert len(enriched) == 1
        assert enriched[0]["verification_result"] == "UNVERIFIABLE"
        assert enriched[0]["original_claim"] == "Some claim"

    def test_empty_all_sources(self):
        """Test with no data at all"""
        enriched = ArticleFactChecker._build_per_claim_verification({}, [], [])
        assert enriched == []


class TestStructuredReport:
    """Test _build_structured_report method"""

    def setup_method(self):
        """Set up dynamic_config mock for model name access"""
        from dingo.config.input_args import EvaluatorLLMArgs
        self._original_dynamic_config = getattr(ArticleFactChecker, 'dynamic_config', None)
        ArticleFactChecker.dynamic_config = EvaluatorLLMArgs(
            key="test-key", api_url="https://api.example.com", model="test-model"
        )

    def teardown_method(self):
        """Restore original dynamic_config to avoid test pollution"""
        if self._original_dynamic_config is not None:
            ArticleFactChecker.dynamic_config = self._original_dynamic_config

    def test_report_structure(self):
        """Test that report has all required top-level keys"""
        verification_data = {
            "article_verification_summary": {
                "total_claims": 3,
                "verified_claims": 2,
                "false_claims": 1,
                "unverifiable_claims": 0,
                "accuracy_score": 0.67
            },
            "false_claims_comparison": []
        }
        extracted_claims = [
            {"claim_id": "claim_001", "claim_type": "factual", "verifiable": True},
            {"claim_id": "claim_002", "claim_type": "institutional", "verifiable": True},
            {"claim_id": "claim_003", "claim_type": "factual", "verifiable": False}
        ]

        report = ArticleFactChecker._build_structured_report(
            verification_data=verification_data,
            extracted_claims=extracted_claims,
            enriched_claims=[],
            tool_calls=[{"tool": "tavily_search"}],
            reasoning_steps=5,
            content_length=1000,
            execution_time=30.5
        )

        assert report["report_version"] == "2.0"
        assert "generated_at" in report
        assert report["article_info"]["content_length"] == 1000
        assert report["claims_extraction"]["total_extracted"] == 3
        assert report["claims_extraction"]["verifiable"] == 2
        assert report["claims_extraction"]["claim_types_distribution"]["factual"] == 2
        assert report["verification_summary"]["accuracy_score"] == 0.67
        assert report["agent_metadata"]["tool_calls_count"] == 1
        assert report["agent_metadata"]["execution_time_seconds"] == 30.5
        assert report["agent_metadata"]["model"] == "test-model"

    def test_report_verified_true_math_after_recalculation(self):
        """Test that verified_true equals true_count, not true_count - false_count.

        Regression test: _recalculate_summary sets verified_claims=true_count.
        _build_structured_report must use verified_claims directly for verified_true,
        and verified_claims + false_claims for total_verified.
        """
        # Simulate recalculated summary: 3 TRUE, 1 FALSE, 1 UNVERIFIABLE
        verification_data = {
            "article_verification_summary": {
                "total_claims": 5,
                "verified_claims": 3,
                "false_claims": 1,
                "unverifiable_claims": 1,
                "accuracy_score": 0.6
            },
            "false_claims_comparison": []
        }
        enriched = [
            {"claim_id": f"c{i}", "verification_result": v, "claim_type": "factual"}
            for i, v in enumerate(["TRUE", "TRUE", "TRUE", "FALSE", "UNVERIFIABLE"])
        ]

        report = ArticleFactChecker._build_structured_report(
            verification_data=verification_data,
            extracted_claims=enriched,
            enriched_claims=enriched,
            tool_calls=[],
            reasoning_steps=5,
            content_length=500,
            execution_time=10.0
        )

        summary = report["verification_summary"]
        assert summary["verified_true"] == 3, "verified_true should equal true_count"
        assert summary["verified_false"] == 1
        assert summary["unverifiable"] == 1
        assert summary["total_verified"] == 4, "total_verified should be true + false"


class TestFileSaving:
    """Test file saving methods"""

    def setup_method(self):
        """Save original dynamic_config before tests that modify it"""
        self._original_dynamic_config = getattr(ArticleFactChecker, 'dynamic_config', None)

    def teardown_method(self):
        """Restore original dynamic_config to avoid test pollution"""
        if self._original_dynamic_config is not None:
            ArticleFactChecker.dynamic_config = self._original_dynamic_config

    def test_save_article_content(self, tmp_path):
        """Test saving article content to markdown file"""
        content = "# Test Article\n\nThis is test content."

        result_path = ArticleFactChecker._save_article_content(str(tmp_path), content)

        assert os.path.exists(result_path)
        with open(result_path, 'r', encoding='utf-8') as f:
            assert f.read() == content

    def test_save_claims(self, tmp_path):
        """Test saving claims to JSONL file"""
        claims = [
            {"claim_id": "claim_001", "claim": "First claim"},
            {"claim_id": "claim_002", "claim": "Second claim"}
        ]

        result_path = ArticleFactChecker._save_claims(str(tmp_path), claims)

        assert os.path.exists(result_path)
        with open(result_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        assert len(lines) == 2
        assert json.loads(lines[0])["claim_id"] == "claim_001"

    def test_save_verification_details(self, tmp_path):
        """Test saving verification details to JSONL file"""
        enriched = [
            {"claim_id": "claim_001", "verification_result": "TRUE"},
            {"claim_id": "claim_002", "verification_result": "FALSE"}
        ]

        result_path = ArticleFactChecker._save_verification_details(str(tmp_path), enriched)

        assert os.path.exists(result_path)
        with open(result_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        assert len(lines) == 2
        assert json.loads(lines[1])["verification_result"] == "FALSE"

    def test_save_full_report(self, tmp_path):
        """Test saving full report to JSON file"""
        report = {
            "report_version": "2.0",
            "verification_summary": {"accuracy_score": 0.8}
        }

        result_path = ArticleFactChecker._save_full_report(str(tmp_path), report)

        assert os.path.exists(result_path)
        with open(result_path, 'r', encoding='utf-8') as f:
            loaded = json.load(f)
        assert loaded["report_version"] == "2.0"

    def test_get_output_dir_auto_generates_path_when_not_configured(self, tmp_path):
        """Test _get_output_dir auto-generates timestamped path when no output_path configured"""
        from dingo.config.input_args import EvaluatorLLMArgs
        ArticleFactChecker.dynamic_config = EvaluatorLLMArgs(
            key="test", api_url="https://api.example.com", model="test",
            agent_config={"base_output_path": str(tmp_path)}
        )
        result = ArticleFactChecker._get_output_dir()
        assert result is not None
        assert os.path.isdir(result)
        assert "article_factcheck_" in os.path.basename(result)
        assert result.startswith(str(tmp_path))

    def test_get_output_dir_returns_none_when_save_artifacts_disabled(self):
        """Test _get_output_dir returns None when save_artifacts=False"""
        from dingo.config.input_args import EvaluatorLLMArgs
        ArticleFactChecker.dynamic_config = EvaluatorLLMArgs(
            key="test", api_url="https://api.example.com", model="test",
            agent_config={"save_artifacts": False}
        )
        result = ArticleFactChecker._get_output_dir()
        assert result is None

    def test_get_output_dir_creates_directory(self, tmp_path):
        """Test _get_output_dir creates directory when configured"""
        from dingo.config.input_args import EvaluatorLLMArgs

        output_dir = str(tmp_path / "new_output_dir")
        ArticleFactChecker.dynamic_config = EvaluatorLLMArgs(
            key="test", api_url="https://api.example.com", model="test",
            agent_config={"output_path": output_dir}
        )

        result = ArticleFactChecker._get_output_dir()

        assert result == output_dir
        assert os.path.isdir(output_dir)


class TestAggregateResultsErrorPaths:
    """Test aggregate_results error handling paths"""

    def setup_method(self):
        """Set up dynamic_config"""
        from dingo.config.input_args import EvaluatorLLMArgs
        self._original_dynamic_config = getattr(ArticleFactChecker, 'dynamic_config', None)
        ArticleFactChecker.dynamic_config = EvaluatorLLMArgs(
            key="test-key", api_url="https://api.example.com", model="test-model"
        )

    def teardown_method(self):
        """Restore original dynamic_config"""
        if self._original_dynamic_config is not None:
            ArticleFactChecker.dynamic_config = self._original_dynamic_config

    def test_aggregate_results_with_empty_results(self):
        """Test aggregate_results when results list is empty"""
        data = Data(content="test")
        result = ArticleFactChecker.aggregate_results(data, [])

        assert result.status is True
        assert any("AGENT_ERROR" in label for label in result.label)

    def test_aggregate_results_with_recursion_limit_error(self):
        """Test aggregate_results handles recursion limit error"""
        data = Data(content="test")
        agent_result = {
            'success': False,
            'error': 'Recursion limit of 25 reached without finishing.'
        }

        result = ArticleFactChecker.aggregate_results(data, [agent_result])

        assert result.status is True
        assert any("RECURSION_LIMIT" in label for label in result.label)
        assert any("25" in str(line) for line in result.reason)

    def test_aggregate_results_with_timeout_error(self):
        """Test aggregate_results handles timeout error"""
        data = Data(content="test")
        agent_result = {
            'success': False,
            'error': 'Request timed out after 120 seconds'
        }

        result = ArticleFactChecker.aggregate_results(data, [agent_result])

        assert result.status is True
        assert any("TIMEOUT" in label for label in result.label)

    def test_aggregate_results_with_empty_output(self):
        """Test aggregate_results when agent returns empty output"""
        data = Data(content="test")
        agent_result = {
            'success': True,
            'output': '',
            'tool_calls': [],
            'reasoning_steps': 0
        }

        result = ArticleFactChecker.aggregate_results(data, [agent_result])

        assert result.status is True
        assert any("AGENT_ERROR" in label for label in result.label)

    def test_aggregate_results_with_valid_json_output(self):
        """Test aggregate_results with valid JSON agent output"""
        data = Data(content="test article")
        agent_output = json.dumps({
            "article_verification_summary": {
                "article_type": "blog",
                "total_claims": 3,
                "verified_claims": 3,
                "false_claims": 0,
                "unverifiable_claims": 0,
                "accuracy_score": 1.0
            },
            "detailed_findings": [],
            "false_claims_comparison": []
        })
        agent_result = {
            'success': True,
            'output': agent_output,
            'tool_calls': [],
            'reasoning_steps': 5
        }

        result = ArticleFactChecker.aggregate_results(data, [agent_result])

        assert result.status is False  # No false claims
        assert result.score == 1.0
        assert isinstance(result.reason[0], str)


class TestArticleFactCheckerIntegration:
    """Integration tests requiring API keys (marked as slow)"""

    # DeepSeek API configuration (uses OpenAI SDK)
    DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"
    DEEPSEEK_MODEL = "deepseek-chat"

    def setup_method(self):
        """Configure ArticleFactChecker to use DeepSeek API"""
        from dingo.config.input_args import EvaluatorLLMArgs

        api_key = os.getenv("OPENAI_API_KEY")
        if api_key:
            ArticleFactChecker.dynamic_config = EvaluatorLLMArgs(
                key=api_key,
                api_url=self.DEEPSEEK_BASE_URL,
                model=self.DEEPSEEK_MODEL
            )

    @pytest.fixture
    def api_keys(self):
        """Get API keys from environment"""
        openai_key = os.getenv("OPENAI_API_KEY")
        tavily_key = os.getenv("TAVILY_API_KEY")

        if not openai_key:
            pytest.skip("OPENAI_API_KEY not set")

        return {
            'openai': openai_key,
            'tavily': tavily_key
        }

    @pytest.fixture
    def blog_article_path(self):
        """Get path to blog article test data"""
        test_file = Path(__file__)
        article_path = test_file.parents[4] / "data" / "blog_article.md"

        if not article_path.exists():
            pytest.skip(f"Blog article not found: {article_path}")

        return article_path

    @pytest.mark.slow
    @pytest.mark.skipif(
        not os.getenv("OPENAI_API_KEY"),
        reason="Requires OPENAI_API_KEY for real API test"
    )
    def test_eval_with_real_article(self, api_keys, blog_article_path):
        """
        Integration test with real article and API calls.

        NOTE: This test uses real LLM and search APIs, so it:
        - Requires valid API keys
        - Consumes API quota
        - Results may vary based on external data
        """
        with open(blog_article_path, 'r', encoding='utf-8') as f:
            article_content = f.read()

        data = Data(content=article_content)

        result = ArticleFactChecker.eval(data)

        # Verify result structure
        assert result is not None
        assert result.metric == "ArticleFactChecker"
        assert isinstance(result.status, bool)
        assert result.reason is not None
        assert len(result.reason) >= 1
        # reason[0] should be human-readable text
        assert isinstance(result.reason[0], str)
        assert len(result.reason[0]) > 100

    @pytest.mark.slow
    @pytest.mark.skipif(
        not os.getenv("OPENAI_API_KEY"),
        reason="Requires OPENAI_API_KEY"
    )
    def test_eval_with_empty_article(self, api_keys):
        """Test handling of empty article"""
        data = Data(content="")

        result = ArticleFactChecker.eval(data)

        assert result is not None
        assert result.metric == "ArticleFactChecker"
        assert isinstance(result.status, bool)
        assert result.score == 0.0 or result.score is None

    @pytest.mark.slow
    @pytest.mark.skipif(
        not os.getenv("OPENAI_API_KEY"),
        reason="Requires OPENAI_API_KEY"
    )
    def test_eval_with_short_article(self, api_keys):
        """Test with very short article"""
        short_article = """
# Short Test Article

PaddleOCR-VL is an OCR model. It scored 92.6 on OmniDocBench.
"""

        data = Data(content=short_article)

        result = ArticleFactChecker.eval(data)

        assert result is not None
        assert result.metric == "ArticleFactChecker"
        assert isinstance(result.status, bool)
        assert result.reason is not None


class TestVerdictNormalization:
    """Test _normalize_verdict method"""

    def test_standard_values_unchanged(self):
        """Test that standard verdicts pass through unchanged"""
        assert ArticleFactChecker._normalize_verdict("TRUE") == "TRUE"
        assert ArticleFactChecker._normalize_verdict("FALSE") == "FALSE"
        assert ArticleFactChecker._normalize_verdict("UNVERIFIABLE") == "UNVERIFIABLE"

    def test_case_insensitive(self):
        """Test case insensitivity"""
        assert ArticleFactChecker._normalize_verdict("true") == "TRUE"
        assert ArticleFactChecker._normalize_verdict("False") == "FALSE"
        assert ArticleFactChecker._normalize_verdict("unverifiable") == "UNVERIFIABLE"

    def test_variant_mappings_true(self):
        """Test TRUE variant mappings"""
        assert ArticleFactChecker._normalize_verdict("CONFIRMED") == "TRUE"
        assert ArticleFactChecker._normalize_verdict("ACCURATE") == "TRUE"
        assert ArticleFactChecker._normalize_verdict("CORRECT") == "TRUE"
        assert ArticleFactChecker._normalize_verdict("VERIFIED") == "TRUE"

    def test_variant_mappings_false(self):
        """Test FALSE variant mappings"""
        assert ArticleFactChecker._normalize_verdict("INACCURATE") == "FALSE"
        assert ArticleFactChecker._normalize_verdict("INCORRECT") == "FALSE"
        assert ArticleFactChecker._normalize_verdict("WRONG") == "FALSE"
        assert ArticleFactChecker._normalize_verdict("DISPROVEN") == "FALSE"
        assert ArticleFactChecker._normalize_verdict("REFUTED") == "FALSE"

    def test_unknown_defaults_to_unverifiable(self):
        """Test that unknown values default to UNVERIFIABLE"""
        assert ArticleFactChecker._normalize_verdict("MAYBE") == "UNVERIFIABLE"
        assert ArticleFactChecker._normalize_verdict("PARTIAL") == "UNVERIFIABLE"
        assert ArticleFactChecker._normalize_verdict("UNKNOWN") == "UNVERIFIABLE"

    def test_empty_and_none_values(self):
        """Test empty and None values"""
        assert ArticleFactChecker._normalize_verdict("") == "UNVERIFIABLE"
        assert ArticleFactChecker._normalize_verdict(None) == "UNVERIFIABLE"

    def test_non_string_input_returns_unverifiable(self):
        """Test that non-string types (int, bool, list) return UNVERIFIABLE"""
        assert ArticleFactChecker._normalize_verdict(0) == "UNVERIFIABLE"
        assert ArticleFactChecker._normalize_verdict(42) == "UNVERIFIABLE"
        assert ArticleFactChecker._normalize_verdict(True) == "UNVERIFIABLE"
        assert ArticleFactChecker._normalize_verdict(False) == "UNVERIFIABLE"
        assert ArticleFactChecker._normalize_verdict(["TRUE"]) == "UNVERIFIABLE"

    def test_whitespace_handling(self):
        """Test that whitespace is stripped"""
        assert ArticleFactChecker._normalize_verdict("  TRUE  ") == "TRUE"
        assert ArticleFactChecker._normalize_verdict(" false ") == "FALSE"


class TestRecalculateSummary:
    """Test _recalculate_summary method"""

    def test_basic_counts(self):
        """Test basic counting of verdict types"""
        claims = [
            {"verification_result": "TRUE"},
            {"verification_result": "TRUE"},
            {"verification_result": "FALSE"},
            {"verification_result": "UNVERIFIABLE"},
        ]
        result = ArticleFactChecker._recalculate_summary(claims)

        assert result["total_claims"] == 4
        assert result["verified_claims"] == 2
        assert result["false_claims"] == 1
        assert result["unverifiable_claims"] == 1
        assert result["accuracy_score"] == 0.5

    def test_empty_list(self):
        """Test with empty claims list"""
        result = ArticleFactChecker._recalculate_summary([])

        assert result["total_claims"] == 0
        assert result["verified_claims"] == 0
        assert result["false_claims"] == 0
        assert result["unverifiable_claims"] == 0
        assert result["accuracy_score"] == 0.0

    def test_all_true(self):
        """Test when all claims are TRUE"""
        claims = [
            {"verification_result": "TRUE"},
            {"verification_result": "TRUE"},
            {"verification_result": "TRUE"},
        ]
        result = ArticleFactChecker._recalculate_summary(claims)

        assert result["total_claims"] == 3
        assert result["verified_claims"] == 3
        assert result["accuracy_score"] == 1.0

    def test_all_unverifiable(self):
        """Test when all claims are UNVERIFIABLE"""
        claims = [
            {"verification_result": "UNVERIFIABLE"},
            {"verification_result": "UNVERIFIABLE"},
        ]
        result = ArticleFactChecker._recalculate_summary(claims)

        assert result["total_claims"] == 2
        assert result["verified_claims"] == 0
        assert result["accuracy_score"] == 0.0

    def test_accuracy_rounding(self):
        """Test accuracy score rounding to 4 decimal places"""
        claims = [
            {"verification_result": "TRUE"},
            {"verification_result": "FALSE"},
            {"verification_result": "UNVERIFIABLE"},
        ]
        result = ArticleFactChecker._recalculate_summary(claims)
        assert result["accuracy_score"] == 0.3333


class TestClaimsFallbackExtraction:
    """Test _extract_claims_from_detailed_findings method"""

    def test_extract_from_detailed_findings(self):
        """Test extracting claims from agent's detailed_findings"""
        verification_data = {
            "detailed_findings": [
                {
                    "claim_id": "claim_001",
                    "original_claim": "The model achieved 95% accuracy",
                    "claim_type": "statistical",
                    "verification_result": "TRUE"
                },
                {
                    "claim_id": "claim_002",
                    "original_claim": "Released by Google in 2024",
                    "claim_type": "temporal",
                    "verification_result": "FALSE"
                }
            ]
        }

        claims = ArticleFactChecker._extract_claims_from_detailed_findings(verification_data)

        assert len(claims) == 2
        assert claims[0]["claim_id"] == "claim_001"
        assert claims[0]["claim"] == "The model achieved 95% accuracy"
        assert claims[0]["claim_type"] == "statistical"
        assert claims[0]["source"] == "agent_reasoning"
        assert claims[0]["confidence"] is None
        assert claims[0]["verifiable"] is True

    def test_empty_findings(self):
        """Test with empty detailed_findings"""
        claims = ArticleFactChecker._extract_claims_from_detailed_findings({"detailed_findings": []})
        assert claims == []

    def test_missing_findings_key(self):
        """Test with missing detailed_findings key"""
        claims = ArticleFactChecker._extract_claims_from_detailed_findings({})
        assert claims == []

    def test_source_marker(self):
        """Test that all extracted claims have source='agent_reasoning'"""
        verification_data = {
            "detailed_findings": [
                {"claim_id": "c1", "original_claim": "Test", "claim_type": "factual"},
                {"claim_id": "c2", "original_claim": "Test2"},
            ]
        }
        claims = ArticleFactChecker._extract_claims_from_detailed_findings(verification_data)
        for claim in claims:
            assert claim["source"] == "agent_reasoning"

    def test_missing_fields_use_defaults(self):
        """Test that missing fields use appropriate defaults"""
        verification_data = {
            "detailed_findings": [
                {"verification_result": "TRUE"}  # Minimal finding, missing most fields
            ]
        }
        claims = ArticleFactChecker._extract_claims_from_detailed_findings(verification_data)

        assert len(claims) == 1
        assert claims[0]["claim_id"] == ""
        assert claims[0]["claim"] == ""
        assert claims[0]["claim_type"] == "unknown"


class TestPromptEnhancements:
    """Test prompt template enhancements for verdict consistency"""

    def test_verdict_criteria_exists(self):
        """Test that VERDICT_CRITERIA is defined and substantive"""
        assert hasattr(PromptTemplates, 'VERDICT_CRITERIA')
        criteria = PromptTemplates.VERDICT_CRITERIA
        assert "TRUE" in criteria
        assert "FALSE" in criteria
        assert "UNVERIFIABLE" in criteria
        assert "CRITICAL RULE" in criteria
        assert "Absence of contradictory evidence" in criteria

    def test_self_verification_step_exists(self):
        """Test that SELF_VERIFICATION_STEP is defined and substantive"""
        assert hasattr(PromptTemplates, 'SELF_VERIFICATION_STEP')
        step = PromptTemplates.SELF_VERIFICATION_STEP
        assert "Self-Verify" in step
        assert "MANDATORY" in step
        assert "consistency" in step.lower()

    def test_build_includes_new_components(self):
        """Test that build() includes VERDICT_CRITERIA and SELF_VERIFICATION_STEP"""
        prompt = PromptTemplates.build()
        assert "Verdict Decision Criteria" in prompt
        assert "Self-Verify Verdict-Reasoning Consistency" in prompt

    def test_build_assembly_order(self):
        """Test that prompt components are in correct order"""
        prompt = PromptTemplates.build()
        # SELF_VERIFICATION_STEP should come after WORKFLOW_STEPS
        workflow_pos = prompt.index("Workflow (Autonomous Decision-Making)")
        self_verify_pos = prompt.index("Self-Verify Verdict-Reasoning Consistency")
        assert self_verify_pos > workflow_pos

        # VERDICT_CRITERIA should come before OUTPUT_FORMAT
        verdict_pos = prompt.index("Verdict Decision Criteria")
        output_pos = prompt.index("Output Format:")
        assert verdict_pos < output_pos

    def test_workflow_step1_mandatory_language(self):
        """Test that Step 1 uses mandatory language for claims_extractor"""
        prompt = PromptTemplates.build()
        assert "REQUIRED - Do NOT skip this step" in prompt
        assert "You MUST call the claims_extractor tool" in prompt

    def test_build_with_article_type_includes_all_components(self):
        """Test that article-type prompt still includes all new components"""
        prompt = PromptTemplates.build(article_type="academic")
        assert "Verdict Decision Criteria" in prompt
        assert "Self-Verify Verdict-Reasoning Consistency" in prompt
        assert "Article Type Guidance (Academic)" in prompt

    def test_institutional_claim_tool_guidance_in_workflow(self):
        """Test that WORKFLOW_STEPS includes institutional claim-specific tool guidance.

        Institutional claims must use arxiv_search + tavily_search combination
        regardless of article type. This guidance must be in WORKFLOW_STEPS (not
        just ARTICLE_TYPE_GUIDANCE) to apply to all article types.
        """
        prompt = PromptTemplates.build()
        assert "INSTITUTIONAL/ATTRIBUTION claims" in prompt
        assert "arxiv_search FIRST" in prompt
        assert "Do NOT rely on" in prompt


class TestAggregateResultsNormalization:
    """Test verdict normalization and summary recalculation in aggregate_results"""

    def setup_method(self):
        """Set up dynamic_config"""
        from dingo.config.input_args import EvaluatorLLMArgs
        self._original_dynamic_config = getattr(ArticleFactChecker, 'dynamic_config', None)
        ArticleFactChecker.dynamic_config = EvaluatorLLMArgs(
            key="test-key", api_url="https://api.example.com", model="test-model"
        )

    def teardown_method(self):
        """Restore original dynamic_config"""
        if self._original_dynamic_config is not None:
            ArticleFactChecker.dynamic_config = self._original_dynamic_config

    def test_nonstandard_verdicts_are_normalized(self):
        """Test that non-standard verdicts are normalized in aggregate_results output"""
        data = Data(content="test article")
        agent_output = json.dumps({
            "article_verification_summary": {
                "article_type": "blog",
                "total_claims": 3,
                "verified_claims": 2,
                "false_claims": 1,
                "unverifiable_claims": 0,
                "accuracy_score": 0.67
            },
            "detailed_findings": [
                {"claim_id": "c1", "original_claim": "Claim 1", "verification_result": "CONFIRMED"},
                {"claim_id": "c2", "original_claim": "Claim 2", "verification_result": "INCORRECT"},
                {"claim_id": "c3", "original_claim": "Claim 3", "verification_result": "MAYBE"},
            ],
            "false_claims_comparison": []
        })
        agent_result = {
            'success': True,
            'output': agent_output,
            'tool_calls': [],
            'reasoning_steps': 5
        }

        result = ArticleFactChecker.aggregate_results(data, [agent_result])

        # After normalization: CONFIRMED->TRUE, INCORRECT->FALSE, MAYBE->UNVERIFIABLE
        # Recalculated: 1 TRUE, 1 FALSE, 1 UNVERIFIABLE -> accuracy = 1/3 ≈ 0.3333
        assert result is not None
        assert result.score == pytest.approx(0.3333, abs=0.001)
        # Binary alignment: FALSE + UNVERIFIABLE → status=True (issue detected)
        assert result.status is True
        assert any("FACTUAL_ERROR" in label for label in result.label)

    def test_summary_recalculated_from_actual_data(self):
        """Test that agent's self-reported summary is overridden by recalculated data"""
        data = Data(content="test article")
        # Agent reports 3 verified, 0 false - but detailed_findings show 1 FALSE
        agent_output = json.dumps({
            "article_verification_summary": {
                "article_type": "news",
                "total_claims": 3,
                "verified_claims": 3,
                "false_claims": 0,
                "unverifiable_claims": 0,
                "accuracy_score": 1.0
            },
            "detailed_findings": [
                {"claim_id": "c1", "original_claim": "Claim 1", "verification_result": "TRUE"},
                {"claim_id": "c2", "original_claim": "Claim 2", "verification_result": "FALSE"},
                {"claim_id": "c3", "original_claim": "Claim 3", "verification_result": "TRUE"},
            ],
            "false_claims_comparison": []
        })
        agent_result = {
            'success': True,
            'output': agent_output,
            'tool_calls': [],
            'reasoning_steps': 3
        }

        result = ArticleFactChecker.aggregate_results(data, [agent_result])

        # Recalculated: 2 TRUE, 1 FALSE -> accuracy = 2/3 ≈ 0.6667
        assert result.status is True  # Has false claims
        assert result.score == pytest.approx(0.6667, abs=0.001)

    def test_claims_source_in_report(self):
        """Test that claims_source appears in structured report"""
        data = Data(content="test article")
        agent_output = json.dumps({
            "article_verification_summary": {
                "article_type": "blog",
                "total_claims": 1,
                "verified_claims": 1,
                "false_claims": 0,
                "unverifiable_claims": 0,
                "accuracy_score": 1.0
            },
            "detailed_findings": [
                {"claim_id": "c1", "original_claim": "Test claim", "verification_result": "TRUE"},
            ],
            "false_claims_comparison": []
        })
        agent_result = {
            'success': True,
            'output': agent_output,
            'tool_calls': [],  # No claims_extractor tool call
            'reasoning_steps': 3
        }

        result = ArticleFactChecker.aggregate_results(data, [agent_result])

        # Should have report in reason[1]
        assert len(result.reason) >= 2
        report = result.reason[1]
        assert isinstance(report, dict)
        assert report["claims_extraction"]["claims_source"] == "agent_reasoning"


class TestReasoningVerdictConsistency:
    """Test code-level reasoning-verdict consistency check.

    This tests the hedging language detector that downgrades TRUE verdicts
    to UNVERIFIABLE when the reasoning contains language indicating
    insufficient evidence. This is a systemic safety net, not claim-type specific.
    """

    def test_hedging_downgrades_true_to_unverifiable(self):
        """Test that hedging language in reasoning downgrades TRUE → UNVERIFIABLE"""
        claims = [
            {
                "claim_id": "c1",
                "verification_result": "TRUE",
                "reasoning": "The exact tripartite collaboration isn't explicitly stated in the README"
            }
        ]
        downgraded = ArticleFactChecker._check_reasoning_verdict_consistency(claims)
        assert downgraded == 1
        assert claims[0]["verification_result"] == "UNVERIFIABLE"

    def test_run3_exact_scenario(self):
        """Test Run 3's exact institutional claim failure case.

        Run 3 had: reasoning="While the exact tripartite collaboration isn't
        explicitly stated in the GitHub README, multiple sources reference..."
        verdict=TRUE → should be downgraded to UNVERIFIABLE.
        """
        claims = [
            {
                "claim_id": "claim_010",
                "claim_type": "institutional",
                "verification_result": "TRUE",
                "reasoning": (
                    "The OmniDocBench GitHub repository shows it's maintained by "
                    "OpenDataLab with institutional affiliations. While the exact "
                    "tripartite collaboration isn't explicitly stated in the GitHub "
                    "README, multiple sources reference Tsinghua and Alibaba DAMO's "
                    "involvement in OmniDocBench development."
                )
            }
        ]
        downgraded = ArticleFactChecker._check_reasoning_verdict_consistency(claims)
        assert downgraded == 1
        assert claims[0]["verification_result"] == "UNVERIFIABLE"

    def test_false_verdicts_never_changed(self):
        """Test that FALSE verdicts are never affected by hedging detection"""
        claims = [
            {
                "claim_id": "c1",
                "verification_result": "FALSE",
                "reasoning": "The paper does not explicitly list these institutions"
            }
        ]
        downgraded = ArticleFactChecker._check_reasoning_verdict_consistency(claims)
        assert downgraded == 0
        assert claims[0]["verification_result"] == "FALSE"

    def test_unverifiable_verdicts_not_affected(self):
        """Test that UNVERIFIABLE verdicts are not affected"""
        claims = [
            {
                "claim_id": "c1",
                "verification_result": "UNVERIFIABLE",
                "reasoning": "Could not find evidence"
            }
        ]
        downgraded = ArticleFactChecker._check_reasoning_verdict_consistency(claims)
        assert downgraded == 0
        assert claims[0]["verification_result"] == "UNVERIFIABLE"

    def test_clear_reasoning_passes_through(self):
        """Test that clear, definitive reasoning does not trigger downgrade"""
        claims = [
            {
                "claim_id": "c1",
                "verification_result": "TRUE",
                "reasoning": (
                    "The arXiv paper 2412.07626 confirms the model was released by "
                    "Baidu with 0.9B parameters. Multiple independent sources verify "
                    "this information."
                )
            }
        ]
        downgraded = ArticleFactChecker._check_reasoning_verdict_consistency(claims)
        assert downgraded == 0
        assert claims[0]["verification_result"] == "TRUE"

    def test_multiple_claims_selective_downgrade(self):
        """Test that only hedging TRUE claims are downgraded in a batch"""
        claims = [
            {
                "claim_id": "c1",
                "verification_result": "TRUE",
                "reasoning": "Confirmed by arXiv paper with specific evidence"
            },
            {
                "claim_id": "c2",
                "verification_result": "TRUE",
                "reasoning": "The specific numbers cannot be fully verified from available sources"
            },
            {
                "claim_id": "c3",
                "verification_result": "FALSE",
                "reasoning": "Contradicts the paper's author list"
            },
            {
                "claim_id": "c4",
                "verification_result": "TRUE",
                "reasoning": "Not directly confirmed by the search results found"
            },
        ]
        downgraded = ArticleFactChecker._check_reasoning_verdict_consistency(claims)
        assert downgraded == 2
        assert claims[0]["verification_result"] == "TRUE"
        assert claims[1]["verification_result"] == "UNVERIFIABLE"
        assert claims[2]["verification_result"] == "FALSE"
        assert claims[3]["verification_result"] == "UNVERIFIABLE"

    @pytest.mark.parametrize("hedging_phrase", [
        "not explicitly stated in the documentation",
        "cannot be verified from available sources",
        "could not find direct evidence",
        "isn't explicitly mentioned in the results",
        "is not explicitly listed in the paper",
        "no direct evidence found for this claim",
        "not directly confirmed by search results",
        "the exact details cannot be fully verified",
        "unable to verify the institutional affiliation",
        "unable to confirm the claimed partnership",
        "insufficient evidence to support this claim",
    ])
    def test_hedging_patterns_comprehensive(self, hedging_phrase):
        """Test various hedging patterns all trigger downgrade"""
        claims = [
            {
                "claim_id": "c1",
                "verification_result": "TRUE",
                "reasoning": f"Some context. {hedging_phrase}. More context."
            }
        ]
        downgraded = ArticleFactChecker._check_reasoning_verdict_consistency(claims)
        assert downgraded == 1, f"Pattern not detected: '{hedging_phrase}'"
        assert claims[0]["verification_result"] == "UNVERIFIABLE"

    def test_empty_reasoning_not_downgraded(self):
        """Test that empty reasoning does not trigger downgrade"""
        claims = [
            {
                "claim_id": "c1",
                "verification_result": "TRUE",
                "reasoning": ""
            }
        ]
        downgraded = ArticleFactChecker._check_reasoning_verdict_consistency(claims)
        assert downgraded == 0
        assert claims[0]["verification_result"] == "TRUE"

    def test_no_reasoning_key_not_downgraded(self):
        """Test that missing reasoning key does not trigger downgrade"""
        claims = [
            {
                "claim_id": "c1",
                "verification_result": "TRUE",
            }
        ]
        downgraded = ArticleFactChecker._check_reasoning_verdict_consistency(claims)
        assert downgraded == 0

    def test_integration_with_aggregate_results(self):
        """Test that consistency check is integrated into aggregate_results pipeline"""
        from dingo.config.input_args import EvaluatorLLMArgs
        original_config = getattr(ArticleFactChecker, 'dynamic_config', None)
        ArticleFactChecker.dynamic_config = EvaluatorLLMArgs(
            key="test-key", api_url="https://api.example.com", model="test-model"
        )
        try:
            data = Data(content="test article")
            agent_output = json.dumps({
                "article_verification_summary": {
                    "article_type": "academic",
                    "total_claims": 2,
                    "verified_claims": 2,
                    "false_claims": 0,
                    "unverifiable_claims": 0,
                    "accuracy_score": 1.0
                },
                "detailed_findings": [
                    {
                        "claim_id": "c1",
                        "original_claim": "Paper by University X",
                        "claim_type": "institutional",
                        "verification_result": "TRUE",
                        "reasoning": "The exact institutional affiliation is not explicitly stated in available sources"
                    },
                    {
                        "claim_id": "c2",
                        "original_claim": "Model has 0.9B params",
                        "claim_type": "technical",
                        "verification_result": "TRUE",
                        "reasoning": "Confirmed by arXiv paper title and Hugging Face model card"
                    },
                ],
                "false_claims_comparison": []
            })
            agent_result = {
                'success': True,
                'output': agent_output,
                'tool_calls': [],
                'reasoning_steps': 3
            }

            result = ArticleFactChecker.aggregate_results(data, [agent_result])

            # c1 should be downgraded: 1 TRUE + 1 UNVERIFIABLE → accuracy = 0.5
            assert result.score == pytest.approx(0.5, abs=0.01)
            # Binary alignment: UNVERIFIABLE → status=True (issue detected)
            assert result.status is True
        finally:
            if original_config is not None:
                ArticleFactChecker.dynamic_config = original_config


class TestBinaryAlignmentWithDingo:
    """Test binary alignment of verification results with Dingo's evaluation model.

    Dingo uses a binary evaluation system: status=True (issue) or status=False (pass).
    ArticleFactChecker maps:
      - TRUE claims → no issue (status=False)
      - FALSE claims → issue (status=True, label=ARTICLE_FACTUAL_ERROR)
      - UNVERIFIABLE claims → issue (status=True, label=ARTICLE_UNVERIFIED_CLAIMS)

    FALSE takes label priority over UNVERIFIABLE when both are present.
    """

    @staticmethod
    def _make_summary(total, verified, false_claims, unverifiable, accuracy):
        """Build verification_data dict for _build_eval_detail_from_verification."""
        return {
            "article_verification_summary": {
                "total_claims": total,
                "verified_claims": verified,
                "false_claims": false_claims,
                "unverifiable_claims": unverifiable,
                "accuracy_score": accuracy,
            },
            "detailed_findings": [],
        }

    def test_all_true_returns_no_issue(self):
        """Test: all TRUE claims → status=False, QUALITY_GOOD label"""
        verification_data = self._make_summary(total=3, verified=3, false_claims=0, unverifiable=0, accuracy=1.0)
        result = ArticleFactChecker._build_eval_detail_from_verification(
            verification_data, tool_calls=[], reasoning_steps=3
        )
        assert result.status is False
        assert result.score == 1.0
        assert any("QUALITY_GOOD" in label for label in result.label)

    def test_unverifiable_only_returns_issue(self):
        """Test: UNVERIFIABLE claims (no FALSE) → status=True, UNVERIFIED_CLAIMS label"""
        verification_data = self._make_summary(total=5, verified=3, false_claims=0, unverifiable=2, accuracy=0.6)
        result = ArticleFactChecker._build_eval_detail_from_verification(
            verification_data, tool_calls=[], reasoning_steps=5
        )
        assert result.status is True
        assert result.score == 0.6
        assert any("ARTICLE_UNVERIFIED_CLAIMS" in label for label in result.label)

    def test_false_only_returns_factual_error(self):
        """Test: FALSE claims (no UNVERIFIABLE) → status=True, FACTUAL_ERROR label"""
        verification_data = self._make_summary(total=4, verified=3, false_claims=1, unverifiable=0, accuracy=0.75)
        result = ArticleFactChecker._build_eval_detail_from_verification(
            verification_data, tool_calls=[], reasoning_steps=4
        )
        assert result.status is True
        assert result.score == 0.75
        assert any("ARTICLE_FACTUAL_ERROR" in label for label in result.label)

    def test_false_plus_unverifiable_prefers_factual_error_label(self):
        """Test: both FALSE and UNVERIFIABLE → FACTUAL_ERROR label takes priority"""
        verification_data = self._make_summary(total=5, verified=2, false_claims=1, unverifiable=2, accuracy=0.4)
        result = ArticleFactChecker._build_eval_detail_from_verification(
            verification_data, tool_calls=[], reasoning_steps=5
        )
        assert result.status is True
        assert result.score == 0.4
        assert any("ARTICLE_FACTUAL_ERROR" in label for label in result.label)

    def test_zero_claims_returns_no_issue(self):
        """Test: zero claims → status=False (no evidence of issues)"""
        verification_data = self._make_summary(total=0, verified=0, false_claims=0, unverifiable=0, accuracy=0.0)
        result = ArticleFactChecker._build_eval_detail_from_verification(
            verification_data, tool_calls=[], reasoning_steps=1
        )
        assert result.status is False
        assert any("QUALITY_GOOD" in label for label in result.label)
