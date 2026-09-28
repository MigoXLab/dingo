import pytest

from dingo.io.input import Data
from dingo.model.rule.scibase.rule_patent import MAX_CLAIMS_LENGTH, RulePatentFieldValidation, check_ipc_unified


def _claims_with_string_length(length: int) -> list[dict]:
    empty_claims = [{"text": ""}]
    return [{"text": "x" * (length - len(str(empty_claims)))}]


class TestRulePatentFieldValidation:
    def test_claims_at_maximum_length_is_valid(self):
        claims = _claims_with_string_length(MAX_CLAIMS_LENGTH)
        assert len(str(claims)) == MAX_CLAIMS_LENGTH

        result = RulePatentFieldValidation().eval(Data(claims=claims, ipc_unified=[]))

        assert result.status is False
        assert result.label == ["QUALITY_GOOD"]

    def test_claims_over_maximum_length_is_invalid(self):
        claims = _claims_with_string_length(MAX_CLAIMS_LENGTH + 1)
        assert len(str(claims)) == MAX_CLAIMS_LENGTH + 1

        result = RulePatentFieldValidation().eval(Data(claims=claims, ipc_unified=[]))

        assert result.status is True
        assert result.label == ["claims.too_long"]
        assert result.reason == [
            "claims: string length 1000001 exceeds the maximum of 1000000"
        ]

    def test_missing_claims_is_invalid(self):
        result = RulePatentFieldValidation().eval(Data(ipc_unified=[]))

        assert result.status is True
        assert result.label == ["claims.missing_field"]

    @pytest.mark.parametrize(
        "ipc_unified",
        [
            [],
            ["A01A 1/00"],
            ["B60T 8/48", "H99Z 999/999999"],
            '["B60T 8/48", "B60T 8/58"]',
        ],
    )
    def test_valid_ipc_unified(self, ipc_unified):
        assert check_ipc_unified(ipc_unified) == (False, [], [])

    @pytest.mark.parametrize(
        "ipc_code",
        [
            "I01A 1/00",       # Section must be A-H.
            "A00A 1/00",       # Class must be 01-99.
            "A1A 1/00",        # Class must contain exactly two digits.
            "A01a 1/00",       # Subclass must be uppercase A-Z.
            "A01A\u00a01/00",  # Separator must be one ASCII space.
            "A01A  1/00",      # Only one separator space is allowed.
            "A01A 01/00",      # Main group must not be zero-padded.
            "A01A 1000/00",    # Main group must be at most 999.
            "A01A 1/0",        # Subgroup must contain at least two digits.
            "A01A 1/000",      # A zero subgroup must be written as 00.
            "A01A 1/1234567",  # Subgroup must contain at most six digits.
            "A01A 1-00",       # Groups must be separated by a slash.
            "A01A 1/00 A",     # Extra suffixes are not allowed.
        ],
    )
    def test_invalid_ipc_format(self, ipc_code):
        invalid, labels, reasons = check_ipc_unified([ipc_code])

        assert invalid is True
        assert labels == ["invalid_format"]
        assert reasons

    @pytest.mark.parametrize(
        ("ipc_unified", "expected_label"),
        [
            (None, "null"),
            ({"code": "A01A 1/00"}, "wrong_type"),
            ([1], "wrong_type"),
            ("not-json", "invalid_json"),
        ],
    )
    def test_invalid_ipc_unified_value(self, ipc_unified, expected_label):
        invalid, labels, reasons = check_ipc_unified(ipc_unified)

        assert invalid is True
        assert labels == [expected_label]
        assert reasons

    def test_rule_reports_invalid_ipc_unified(self):
        result = RulePatentFieldValidation().eval(
            Data(claims=[], ipc_unified=["A01A 01/00"])
        )

        assert result.status is True
        assert result.label == ["ipc_unified.invalid_format"]
        assert result.reason[0].startswith("ipc_unified: item[0]")
