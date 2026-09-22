from dingo.io.input import Data
from dingo.model.rule.scibase.rule_patent import (
    MAX_CLAIMS_LENGTH,
    RulePatentFieldValidation,
)


def _claims_with_string_length(length: int) -> list[dict]:
    empty_claims = [{"text": ""}]
    return [{"text": "x" * (length - len(str(empty_claims)))}]


class TestRulePatentFieldValidation:
    def test_claims_at_maximum_length_is_valid(self):
        claims = _claims_with_string_length(MAX_CLAIMS_LENGTH)
        assert len(str(claims)) == MAX_CLAIMS_LENGTH

        result = RulePatentFieldValidation().eval(Data(claims=claims))

        assert result.status is False
        assert result.label == ["QUALITY_GOOD"]

    def test_claims_over_maximum_length_is_invalid(self):
        claims = _claims_with_string_length(MAX_CLAIMS_LENGTH + 1)
        assert len(str(claims)) == MAX_CLAIMS_LENGTH + 1

        result = RulePatentFieldValidation().eval(Data(claims=claims))

        assert result.status is True
        assert result.label == ["claims.too_long"]
        assert result.reason == [
            "claims: string length 1000001 exceeds the maximum of 1000000"
        ]

    def test_missing_claims_is_invalid(self):
        result = RulePatentFieldValidation().eval(Data())

        assert result.status is True
        assert result.label == ["claims.missing_field"]
