"""Shared response processing for multi-label text quality evaluators."""

import json

from dingo.io.input import RequiredField
from dingo.io.output.eval_detail import EvalDetail
from dingo.model.llm.base_openai import BaseOpenAI
from dingo.model.response.response_class import ResponseScoreTypeNameReason


class BaseTextQualityV2(BaseOpenAI):
    """Parse a JSON list of quality findings into one ``EvalDetail``."""

    _required_fields = [RequiredField.CONTENT]

    @classmethod
    def process_response(cls, response: str) -> EvalDetail:
        response = response.strip()
        if response.startswith("```json"):
            response = response[7:]
        elif response.startswith("```"):
            response = response[3:]
        if response.rstrip().endswith("```"):
            response = response.rstrip()[:-3]

        response_json = json.loads(response.strip())
        if not isinstance(response_json, list) or not response_json:
            raise ValueError("Text quality response must be a non-empty JSON list")

        findings = [ResponseScoreTypeNameReason(**item) for item in response_json]
        good_findings = [item for item in findings if item.score == 1]
        bad_findings = [item for item in findings if item.score == 0]

        if len(good_findings) == 1 and len(findings) == 1:
            good = good_findings[0]
            if good.type != "Good" or good.name != "None":
                raise ValueError("A passing finding must use type 'Good' and name 'None'")
            return EvalDetail(
                metric=cls.__name__,
                status=False,
                score=1,
                label=["QUALITY_GOOD"],
                reason=[good.reason],
            )

        if good_findings:
            raise ValueError("A Good finding cannot be mixed with defect findings")
        if len(bad_findings) != len(findings):
            raise ValueError("Each defect finding must have score 0")
        label_keys = [(item.type, item.name) for item in bad_findings]
        if len(set(label_keys)) != len(label_keys):
            raise ValueError("Duplicate defect labels are not allowed")

        return EvalDetail(
            metric=cls.__name__,
            status=True,
            score=0,
            label=[f"{item.type}.{item.name}" for item in bad_findings],
            reason=[item.reason for item in bad_findings],
        )
