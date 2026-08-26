"""
Base class for all Agent evaluation metrics.

Provides standardized:
- 0~10 score → 0.0~1.0 normalization
- Configurable threshold via dynamic_config.model_extra
- Unified JSON response parsing with {"score": 0-10, "reason": "...", ...}
- Error fallback handling
- `eval_layer` and `input_data_type` declarations for orchestrator integration

Subclasses only need to define:
- `prompt`: the evaluation prompt template
- `build_messages()`: how to format input data into LLM messages
- Optionally override `process_response()` for custom parsing
"""

import json
from typing import Optional

from dingo.io.input import Data, RequiredField
from dingo.io.output.eval_detail import EvalDetail, QualityLabel
from dingo.model.llm.base_openai import BaseOpenAI
from dingo.utils import log
from dingo.utils.exception import ConvertJsonError


def evidence_discipline(specific_bullet: str) -> str:
    """The rules every judge shown a record must follow, said once.

    Pasted into three prompts by hand, it had already drifted within the commit
    that introduced it — and a judge holding a stale copy applies a different
    evidence standard from its neighbours while the two verdicts are shown side
    by side. Only the one bullet that is genuinely per-judge varies.
    """
    return f"""
Evidence discipline. The content may carry a section headed "What the tool calls
actually returned". That section is the record of the run; the agent's own
summary and final answer are its account of the run. Where the two disagree, the
record governs.

- Name the step or call each claim rests on ("call 3 returned nothing"), and do
  not restate the agent's summary as though it were verified.
- An agent's own statement is not evidence that the statement is true. A summary
  reporting a specific outcome, quoted back by the answer-delivery call, is one
  claim, not two.
- {specific_bullet}
- Unverified is not disproved. A claim the record neither confirms nor
  contradicts lowers your confidence, not the agent's grade: score what the
  record does show and say which part is unconfirmed.
- If the record cannot settle the question at all — nothing was recorded that
  bears on it — do not guess a number. Return `"not_applicable": true` with a
  reason saying what was missing, and omit "score".
"""


class BaseLLMAgentEval(BaseOpenAI):
    """Shared base class for all Agent evaluation metrics."""

    eval_layer: str = ""
    input_data_type: str = "trace_summary"
    default_threshold: float = 0.6

    @classmethod
    def _detect_language_hint(cls, text: str) -> str:
        """Which language to answer in, said explicitly either way.

        Returning nothing for a non-CJK sample was half the reason the language
        wandered: with no instruction at the end of the prompt, the only one
        left standing was a line in the template telling the judge to follow
        "the input content" — which is a different slice of the trace for every
        judge, and is exactly what deciding once per trace was meant to stop.
        Saying "answer in English" is not redundant; it is the half of the
        instruction that was missing.
        """
        if not text:
            return ""
        import re
        cjk_count = len(re.findall(r'[一-鿿㐀-䶿]', text[:500]))
        if cjk_count > 5:
            return '\n\n注意：请用中文回答 "reason" 字段。'
        return '\n\nNote: write the "reason" field in English.'

    @classmethod
    def language_hint_for(cls, input_data: Data) -> str:
        """The language every judge of one trace should answer in.

        Derived from the task, not from whatever each judge happens to be
        looking at. Reading `prompt + content` made the answer depend on the
        view: the tool-call view of a Chinese run is full of Chinese arguments
        while its trace summary is mostly English step names, so one trace came
        back with task completion in English and tool correctness in Chinese,
        side by side on the same card. The task is what the reader asked, and it
        is the same for all of them.

        A caller that has already decided for the whole trace says so on
        ``language_sample``, and that wins. It has to: a task can be too short
        to carry a signal at all — one live trace asks "1+1=？", which holds no
        CJK to count — and then each judge is back to choosing for itself, which
        is the same inconsistency in a smaller window. Deciding per trace is the
        caller's job because only the caller sees the whole trace.
        """
        sample = getattr(input_data, "language_sample", None)
        if isinstance(sample, str) and sample:
            return cls._detect_language_hint(sample)
        return cls._detect_language_hint(str(input_data.prompt or ""))

    @classmethod
    def _get_threshold(cls) -> float:
        if cls.dynamic_config and cls.dynamic_config.model_extra:
            return float(cls.dynamic_config.model_extra.get(
                "threshold", cls.default_threshold
            ))
        return cls.default_threshold

    @classmethod
    def _strip_json_fences(cls, response: str) -> str:
        response = response.strip()
        # Remove a leading code fence (```json / ```JSON / ```) of any case by
        # dropping the fence line, then a trailing fence.
        if response.startswith("```"):
            newline = response.find("\n")
            response = response[newline + 1:] if newline != -1 else response[3:]
        if response.endswith("```"):
            response = response[:-3]
        return response.strip()

    @staticmethod
    def _extract_json_object(text: str) -> Optional[str]:
        """Return the first balanced top-level JSON object substring, or None.

        Tolerates prose before/after the object (a common LLM output pattern)
        and brace characters inside strings.
        """
        start = text.find("{")
        if start == -1:
            return None
        depth = 0
        in_str = False
        esc = False
        for i in range(start, len(text)):
            ch = text[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
            elif ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[start:i + 1]
        return None

    @classmethod
    def _parse_json_response(cls, response: str) -> dict:
        cleaned = cls._strip_json_fences(response)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass
        # Fall back to extracting the first balanced JSON object — handles
        # responses with prose around the JSON or a missed/uppercase fence —
        # so a recoverable response is not penalized as a parse failure.
        candidate = cls._extract_json_object(cleaned) or cls._extract_json_object(response)
        if candidate:
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass
        raise ConvertJsonError(f"Failed to parse agent eval JSON: {cleaned[:500]}")

    @classmethod
    def process_response(cls, response: str) -> EvalDetail:
        """Standardized response processing for agent evaluators.

        Expected LLM output: {"score": 0-10, "reason": "...", ...extra fields...}
        Score is normalized to 0.0~1.0 and compared against threshold.
        Extra fields are preserved in EvalDetail.reason as JSON.
        """
        log.info(response)
        data = cls._parse_json_response(response)

        # A judge that cannot answer must be able to say so. Without this it had
        # only the score, so "the record cannot confirm or contradict this" and
        # "the agent failed" came out as the same low number under the same
        # "critical" label: two live traces whose attached file was never
        # returned by any call scored 0.2/critical on reasoning that said, in
        # its own words, that it could not verify either way — beside two
        # traces in the identical evidentiary position that scored 0.6-0.7.
        # Unverified is not disproved, and the platform already carries
        # `applicable` end to end for exactly this.
        if data.get("not_applicable") is True:
            result = EvalDetail(metric=cls.__name__)
            result.applicable = False
            # It read the evidence and could not decide. That is a gap in what
            # this run recorded, and a caller weighing the run needs to know it
            # — unlike a check that never applied here at all.
            result.not_applicable_kind = "declined"
            reason_text = data.get("reason", "")
            result.reason = [reason_text] if reason_text else None
            return result

        raw_score = data.get("score", data.get("overall_score", 0))
        try:
            raw_score = float(raw_score)
        except (TypeError, ValueError):
            raw_score = 0.0

        normalized_score = max(0.0, min(1.0, raw_score / 10.0))
        threshold = cls._get_threshold()

        reason_text = data.get("reason", "")
        details = {k: v for k, v in data.items() if k not in ("score", "reason")}

        result = EvalDetail(metric=cls.__name__)
        result.score = normalized_score

        if normalized_score >= threshold:
            result.status = False
            result.label = [QualityLabel.QUALITY_GOOD]
            result.verdict = "pass"
        else:
            result.status = True
            result.label = [f"AGENT_QUALITY.{cls.__name__}"]
            result.verdict = "issue"

        reason_parts = [reason_text] if reason_text else []
        if details:
            reason_parts.append(json.dumps(details, ensure_ascii=False, default=str))
        result.reason = reason_parts if reason_parts else None

        return result
