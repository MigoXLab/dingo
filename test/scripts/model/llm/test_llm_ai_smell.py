"""
Unit tests for LLMAISmell - AI Smell Detector for Requirement Documents
"""
import json

import pytest

from dingo.model.llm.llm_ai_smell import LLMAISmell


class TestLLMAISmell:
    """Tests for the AI smell detection checker."""

    def _make_response(
        self,
        total_score=3,
        correct_nonsense=2,
        infinite_mirror=3,
        rainbow_fart=2,
        detail_vacuum=4,
        adjective_violence=2,
        verdict="文档有一定 AI 味但仍可接受",
        evidence=None,
    ):
        if evidence is None:
            evidence = {
                "correct_nonsense": "",
                "infinite_mirror": "",
                "rainbow_fart": "",
                "detail_vacuum": "",
                "adjective_violence": "",
            }
        return json.dumps(
            {
                "total_score": total_score,
                "dimensions": {
                    "correct_nonsense": correct_nonsense,
                    "infinite_mirror": infinite_mirror,
                    "rainbow_fart": rainbow_fart,
                    "detail_vacuum": detail_vacuum,
                    "adjective_violence": adjective_violence,
                },
                "evidence": evidence,
                "verdict": verdict,
            },
            ensure_ascii=False,
        )

    # ──────────────────────────────────────────────
    # Basic pass / fail logic
    # ──────────────────────────────────────────────

    def test_clean_document_not_flagged(self):
        """Low-scoring document should NOT be flagged as AI smell."""
        response = self._make_response(total_score=3, verdict="文档整体朴实，无明显 AI 味")
        result = LLMAISmell.process_response(response)

        assert result.status is False
        assert result.label == ["AI_SMELL_CLEAN"]
        assert result.metric == "LLMAISmell"

    def test_ai_smell_document_flagged(self):
        """High-scoring document SHOULD be flagged as AI smell."""
        response = self._make_response(
            total_score=8,
            correct_nonsense=8,
            detail_vacuum=9,
            adjective_violence=8,
            verdict="典型 AI 代写，大量废话和 buzzword，缺乏可落地细节",
            evidence={
                "correct_nonsense": "在当今数字化转型的大背景下……",
                "infinite_mirror": "",
                "rainbow_fart": "彻底革新传统模式",
                "detail_vacuum": "系统性能应满足业务需求",
                "adjective_violence": "赋能、闭环、降本增效、颗粒度",
            },
        )
        result = LLMAISmell.process_response(response)

        assert result.status is True
        assert result.label == ["AI_SMELL_DETECTED"]

    def test_threshold_boundary_exactly_at_threshold(self):
        """Score exactly at threshold (6) should be flagged."""
        response = self._make_response(total_score=LLMAISmell.threshold)
        result = LLMAISmell.process_response(response)

        assert result.status is True
        assert result.label == ["AI_SMELL_DETECTED"]

    def test_threshold_boundary_just_below(self):
        """Score just below threshold (5) should NOT be flagged."""
        response = self._make_response(total_score=LLMAISmell.threshold - 1)
        result = LLMAISmell.process_response(response)

        assert result.status is False
        assert result.label == ["AI_SMELL_CLEAN"]

    # ──────────────────────────────────────────────
    # Score normalization
    # ──────────────────────────────────────────────

    def test_score_normalized_to_zero_one(self):
        """score field should be in [0, 1] range."""
        for raw in [0, 5, 10]:
            response = self._make_response(total_score=raw)
            result = LLMAISmell.process_response(response)
            assert 0.0 <= result.score <= 1.0, f"score out of range for raw={raw}"

    def test_score_value_correct(self):
        """score = total_score / 10, rounded to 2 decimals."""
        response = self._make_response(total_score=7)
        result = LLMAISmell.process_response(response)
        assert result.score == pytest.approx(0.70, abs=1e-9)

    # ──────────────────────────────────────────────
    # Reason string content
    # ──────────────────────────────────────────────

    def test_reason_contains_total_score(self):
        """Reason should display the total AI smell score."""
        response = self._make_response(total_score=7)
        result = LLMAISmell.process_response(response)
        assert "7/10" in result.reason[0]

    def test_reason_contains_all_dimension_labels(self):
        """Reason should list all 5 dimension labels."""
        response = self._make_response()
        result = LLMAISmell.process_response(response)
        reason = result.reason[0]

        assert "💊 正确的废话指数" in reason
        assert "🪞 无限镜像感" in reason
        assert "🌈 彩虹屁密度" in reason
        assert "🧩 细节真空度" in reason
        assert "✨ 形容词暴力指数" in reason

    def test_reason_contains_verdict(self):
        """Reason should contain the verdict string."""
        verdict = "这是一份高度 AI 味的文档，建议重写"
        response = self._make_response(total_score=8, verdict=verdict)
        result = LLMAISmell.process_response(response)
        assert verdict in result.reason[0]

    def test_evidence_shown_for_high_scores(self):
        """Evidence should appear in reason for dimensions scoring >= 5."""
        evidence_text = "在当今社会，随着技术不断发展……"
        response = self._make_response(
            total_score=7,
            correct_nonsense=6,
            evidence={
                "correct_nonsense": evidence_text,
                "infinite_mirror": "",
                "rainbow_fart": "",
                "detail_vacuum": "",
                "adjective_violence": "",
            },
        )
        result = LLMAISmell.process_response(response)
        assert evidence_text in result.reason[0]

    def test_evidence_hidden_for_low_scores(self):
        """Evidence should NOT appear in reason for dimensions scoring < 5."""
        evidence_text = "某个不应出现的例句"
        response = self._make_response(
            total_score=3,
            correct_nonsense=2,
            evidence={
                "correct_nonsense": evidence_text,
                "infinite_mirror": "",
                "rainbow_fart": "",
                "detail_vacuum": "",
                "adjective_violence": "",
            },
        )
        result = LLMAISmell.process_response(response)
        assert evidence_text not in result.reason[0]

    # ──────────────────────────────────────────────
    # Markdown cleanup
    # ──────────────────────────────────────────────

    def test_markdown_json_code_block_stripped(self):
        """LLM often wraps JSON in ```json ... ``` — should be handled."""
        inner = self._make_response(total_score=4)
        wrapped = f"```json\n{inner}\n```"
        result = LLMAISmell.process_response(wrapped)
        assert result.label == ["AI_SMELL_CLEAN"]

    def test_plain_code_block_stripped(self):
        """Plain ``` ... ``` wrapper should also be stripped."""
        inner = self._make_response(total_score=7)
        wrapped = f"```\n{inner}\n```"
        result = LLMAISmell.process_response(wrapped)
        assert result.label == ["AI_SMELL_DETECTED"]

    # ──────────────────────────────────────────────
    # Error handling
    # ──────────────────────────────────────────────

    def test_invalid_json_raises_convert_error(self):
        """Garbage response should raise ConvertJsonError."""
        from dingo.utils.exception import ConvertJsonError

        with pytest.raises(ConvertJsonError):
            LLMAISmell.process_response("This is not JSON at all")

    # ──────────────────────────────────────────────
    # Metadata
    # ──────────────────────────────────────────────

    def test_metric_name_matches_class(self):
        """EvalDetail.metric should be the class name."""
        response = self._make_response()
        result = LLMAISmell.process_response(response)
        assert result.metric == "LLMAISmell"

    def test_required_fields(self):
        """Checker should only require CONTENT (no prompt/context needed)."""
        from dingo.io.input import RequiredField

        assert RequiredField.CONTENT in LLMAISmell._required_fields
        assert len(LLMAISmell._required_fields) == 1

    # ──────────────────────────────────────────────
    # Score bar helper
    # ──────────────────────────────────────────────

    def test_score_bar_full(self):
        bar = LLMAISmell._score_bar(10)
        assert bar == "[██████████]"

    def test_score_bar_empty(self):
        bar = LLMAISmell._score_bar(0)
        assert bar == "[░░░░░░░░░░]"

    def test_score_bar_half(self):
        bar = LLMAISmell._score_bar(5)
        assert bar == "[█████░░░░░]"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
