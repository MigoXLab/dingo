import json
from pathlib import Path

import pytest

from dingo.io.input import Data
from dingo.model.model import Model
from dingo.model.rule.scibase import base_check_paper, rule_paper, rule_quanliang
from dingo.model.rule.scibase.base_field_validation import BaseFieldValidation


def test_paper_reuses_checks_with_independent_mapping_and_config():
    paper = rule_paper.RulePaperFieldValidation
    quanliang = rule_quanliang.RuleQuanliangFieldValidation
    assert Model.get_rule_by_name(paper.__name__) is paper
    assert paper.__bases__ == (BaseFieldValidation,)
    assert quanliang.__bases__ == (BaseFieldValidation,)
    assert paper.eval is quanliang.eval
    assert paper.eval is BaseFieldValidation.eval
    assert paper.normalize_record.__func__ is BaseFieldValidation.normalize_record.__func__
    assert quanliang.normalize_record.__func__ is BaseFieldValidation.normalize_record.__func__
    assert paper.field_validators is not quanliang.field_validators
    assert paper.dynamic_config is not quanliang.dynamic_config
    assert paper.dynamic_config.key_list is not quanliang.dynamic_config.key_list
    assert paper.dynamic_config.key_list == list(paper.field_validators)
    assert quanliang.dynamic_config.key_list == list(quanliang.field_validators)
    for module in (rule_paper, rule_quanliang):
        for name, check in vars(module).items():
            if name.startswith("check_"):
                if module is rule_paper and name in {
                    "check_access_is_oa", "check_access_oa_status", "check_locations",
                }:
                    assert check is not getattr(base_check_paper, name)
                    assert check.__module__ == rule_paper.__name__
                    continue
                assert check is getattr(base_check_paper, name)
                assert check.__module__ == base_check_paper.__name__

    data_path = Path(__file__).parents[3] / "data/scibase/rule_quanliang_cases.jsonl"
    for line in data_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        model = paper()
        model.dynamic_config = model.dynamic_config.model_copy(deep=True)
        model.dynamic_config.key_list = row["key_list"]
        result = model.eval(Data(**row["input"]))
        assert result.metric == "RulePaperFieldValidation"
        assert result.status is row["expected_status"], row["case"]
        assert result.label == row["expected_labels"], row["case"]
        assert (result.reason or []) == row["expected_reasons"], row["case"]


@pytest.mark.parametrize(
    "record, expected_label",
    [
        ({}, "missing_field"),
        ({"access_is_oa": None}, "null"),
        ({"access_is_oa": True}, "wrong_type"),
        ({"access_is_oa": False}, "wrong_type"),
        ({"access_is_oa": 1}, "wrong_type"),
        ({"access_is_oa": []}, "wrong_type"),
        ({"access_is_oa": {}}, "wrong_type"),
        ({"access_is_oa": ""}, "empty"),
        ({"access_is_oa": "True"}, "unsupported_value"),
        ({"access_is_oa": " true "}, "unsupported_value"),
        ({"access_is_oa": " "}, "unsupported_value"),
        ({"access_is_oa": "invalid"}, "unsupported_value"),
        ({"access_is_oa": "true"}, None),
        ({"access_is_oa": "false"}, None),
        ({"access_is_oa": "unknown"}, None),
    ],
)
@pytest.mark.parametrize(
    "metadata",
    [{}, {"metadata_type": "paper"}, {"metadata_type": "ebook"}, {"metadata_type": []}],
)
def test_paper_access_is_oa_basic_validation(record, expected_label, metadata):
    model = rule_paper.RulePaperFieldValidation()
    model.dynamic_config = model.dynamic_config.model_copy(deep=True)
    model.dynamic_config.key_list = ["access_is_oa"]
    result = model.eval(Data(**metadata, **record))
    assert result.status is (expected_label is not None)
    assert result.label == (
        [f"access_is_oa.{expected_label}"] if expected_label else ["QUALITY_GOOD"]
    )
    if expected_label:
        assert len(result.reason) == 1


@pytest.mark.parametrize("oa_flag", ["true", "false", "unknown"])
def test_paper_access_is_oa_is_independent_of_related_fields(oa_flag):
    record = {
        "metadata_type": "paper",
        "access_is_oa": oa_flag,
        "access_oa_status": "closed" if oa_flag == "true" else "gold",
        "access_oa_url": [] if oa_flag == "true" else ["https://example.com/paper.pdf"],
        "access_license": "cc-by",
    }
    assert rule_paper.RulePaperFieldValidation.field_validators["access_is_oa"](record) == (False, [], [])
    assert rule_quanliang.RuleQuanliangFieldValidation.field_validators["access_is_oa"](record)[0] is True


@pytest.mark.parametrize(
    "record, expected_label",
    [
        ({}, "missing_field"),
        ({"access_oa_status": None}, "null"),
        ({"access_oa_status": True}, "wrong_type"),
        ({"access_oa_status": 1}, "wrong_type"),
        ({"access_oa_status": []}, "wrong_type"),
        ({"access_oa_status": {}}, "wrong_type"),
        ({"access_oa_status": "Gold"}, "unsupported_value"),
        ({"access_oa_status": " gold "}, "unsupported_value"),
        ({"access_oa_status": " "}, "unsupported_value"),
        ({"access_oa_status": "unknown"}, "unsupported_value"),
    ],
)
def test_paper_access_oa_status_basic_validation(record, expected_label):
    model = rule_paper.RulePaperFieldValidation()
    model.dynamic_config = model.dynamic_config.model_copy(deep=True)
    model.dynamic_config.key_list = ["access_oa_status"]
    result = model.eval(Data(access_is_oa="false", **record))
    assert result.status is True
    assert result.label == [f"access_oa_status.{expected_label}"]
    assert len(result.reason) == 1


@pytest.mark.parametrize("status", ["diamond", "gold", "green", "hybrid", "bronze", "closed", ""])
@pytest.mark.parametrize("oa_flag", ["true", "false", "unknown", None, True, False, "invalid", []])
def test_paper_access_oa_status_consistency(status, oa_flag):
    model = rule_paper.RulePaperFieldValidation()
    model.dynamic_config = model.dynamic_config.model_copy(deep=True)
    model.dynamic_config.key_list = ["access_oa_status"]
    result = model.eval(Data(access_oa_status=status, access_is_oa=oa_flag))
    mismatch = (oa_flag == "false" and status != "closed") or (oa_flag == "true" and status == "closed")
    assert result.status is mismatch
    assert result.label == (
        ["access_oa_status.oa_status_mismatch"] if mismatch else ["QUALITY_GOOD"]
    )
    # Quanliang retains its independent basic status validator.
    assert rule_quanliang.RuleQuanliangFieldValidation.field_validators["access_oa_status"](
        {"access_oa_status": status, "access_is_oa": oa_flag}
    ) == (False, [], [])


PAPER_LOCATION_KEYS = (
    "license", "is_oa", "pdf_url", "landing_page_url", "is_published",
    "is_accepted", "source_url", "origin_url", "source", "version", "meta_db_name",
)


PAPER_SOURCE_KEYS = (
    "id", "display_name", "issn_l", "issn", "is_oa", "is_in_doaj", "is_core",
    "listed_in", "type", "host_organization", "host_organization_name",
    "host_organization_lineage", "host_organization_lineage_names",
)


def _paper_location():
    return {**dict.fromkeys(PAPER_LOCATION_KEYS), "license": "", "is_oa": "unknown",
        "source": dict.fromkeys(PAPER_SOURCE_KEYS), "version": "publishedVersion",
        "is_published": True, "is_accepted": True}


@pytest.mark.parametrize(
    "record, expected_label",
    [
        ({}, "missing_field"),
        ({"locations": None}, "null"),
        ({"locations": ""}, "wrong_type"),
        ({"locations": {}}, "wrong_type"),
        ({"locations": ()}, "wrong_type"),
        ({"locations": False}, "wrong_type"),
        ({"locations": [None]}, "wrong_type"),
        ({"locations": [""]}, "wrong_type"),
        ({"locations": [[]]}, "wrong_type"),
        ({"locations": [{}]}, "empty"),
    ],
)
def test_paper_locations_basic_validation(record, expected_label):
    model = rule_paper.RulePaperFieldValidation()
    model.dynamic_config = model.dynamic_config.model_copy(deep=True)
    model.dynamic_config.key_list = ["locations"]
    result = model.eval(Data(**record))
    assert result.status is True
    assert result.label == [f"locations.{expected_label}"]
    assert len(result.reason) == 1


@pytest.mark.parametrize("missing_key", PAPER_LOCATION_KEYS)
def test_paper_locations_requires_each_key(missing_key):
    location = {**_paper_location(), "license": "", "is_oa": "unknown"}
    incomplete = dict(location)
    del incomplete[missing_key]
    if missing_key == "version":
        incomplete.update(is_published=False, is_accepted=False)
    assert rule_paper.check_locations([location, incomplete]) == (
        True, ["missing_key"], [f"item[1] missing key '{missing_key}'"],
    )


@pytest.mark.parametrize("bad_item, expected_label", [(None, "wrong_type"), ({}, "empty")])
def test_paper_locations_checks_later_items(bad_item, expected_label):
    location = {**_paper_location(), "license": "", "is_oa": "unknown"}
    result = rule_paper.check_locations([location, bad_item])
    assert result[0] is True
    assert result[1] == [expected_label]
    assert "item[1]" in result[2][0]


@pytest.mark.parametrize("locations", [[],
    [{**_paper_location(), "license": "", "is_oa": "true"}],
    [{**_paper_location(), "is_oa": "false"}],
    [{**_paper_location(), "license": "", "is_oa": "unknown", "extra": "allowed"}],
])
def test_paper_locations_valid_structure(locations):
    model = rule_paper.RulePaperFieldValidation()
    model.dynamic_config = model.dynamic_config.model_copy(deep=True)
    model.dynamic_config.key_list = ["locations"]
    for value in (locations, json.dumps(locations)):
        result = model.eval(Data(locations=value))
        assert result.status is False
        assert result.label == ["QUALITY_GOOD"]


def test_paper_locations_and_quanliang_locations_are_independent():
    quanliang_location = {"type": "download", "url": "https://example.com/a.pdf",
        "license": "cc-by", "is_oa": "true"}
    assert rule_quanliang.check_locations([quanliang_location]) == (False, [], [])
    assert rule_paper.check_locations([quanliang_location])[1] == ["missing_key"] * 9
    assert rule_paper.check_locations(
        [{**_paper_location(), "license": "", "is_oa": "true"}]
    ) == (False, [], [])
    assert rule_quanliang.check_locations([dict.fromkeys(PAPER_LOCATION_KEYS)])[1] == ["missing_key"]


@pytest.mark.parametrize("is_oa", [None, "", "True", " true ", "invalid", True, False, 1, [], {}])
def test_paper_locations_is_oa_rejects_invalid_values(is_oa):
    valid = {**_paper_location(), "license": "", "is_oa": "true"}
    invalid = {**valid, "is_oa": is_oa}
    model = rule_paper.RulePaperFieldValidation()
    model.dynamic_config = model.dynamic_config.model_copy(deep=True)
    model.dynamic_config.key_list = ["locations"]
    result = model.eval(Data(locations=[valid, invalid]))
    assert result.status is True
    error = "unsupported_value" if isinstance(is_oa, str) else "wrong_type"
    reason = ("is_oa must be one of 'true', 'false' or 'unknown'"
        if isinstance(is_oa, str) else "is_oa must be a string")
    assert result.label == [f"locations.is_oa.{error}"]
    assert result.reason == [
        f"locations: item[1].{reason}",
    ]


def test_paper_locations_collects_errors_across_items_and_keys():
    valid = {**_paper_location(), "license": "", "is_oa": "true"}
    incomplete = {**valid, "is_oa": "invalid"}
    del incomplete["license"]
    del incomplete["pdf_url"]
    missing_is_oa = dict(valid)
    del missing_is_oa["is_oa"]
    model = rule_paper.RulePaperFieldValidation()
    model.dynamic_config = model.dynamic_config.model_copy(deep=True)
    model.dynamic_config.key_list = ["locations"]
    result = model.eval(Data(locations=[{}, incomplete, None, missing_is_oa, valid]))
    assert result.status is True
    assert result.label == [
        "locations.empty", "locations.missing_key", "locations.is_oa.unsupported_value",
        "locations.missing_key", "locations.wrong_type", "locations.missing_key",
    ]
    assert result.reason == [
        "locations: item[0] cannot be an empty object",
        "locations: item[1] missing key 'license'",
        "locations: item[1].is_oa must be one of 'true', 'false' or 'unknown'",
        "locations: item[1] missing key 'pdf_url'",
        "locations: item[2] must be an object",
        "locations: item[3] missing key 'is_oa'",
    ]


def test_paper_locations_reports_all_missing_keys_without_checking_absent_values():
    result = rule_paper.check_locations([{"locations.license": ""}])
    assert result == (
        True, ["missing_key"] * len(PAPER_LOCATION_KEYS),
        [f"item[0] missing key '{key}'" for key in PAPER_LOCATION_KEYS],
    )


@pytest.mark.parametrize("license_value", [
    "cc-by", "cc-by-nc", "cc-by-sa", "cc-by-nd", "cc-by-nc-sa", "cc-by-nc-nd",
    "other-oa", "cc0", "", "public-domain", "publisher-specific-oa", "publisher-specific",
    "wiley-specific", "elsevier-specific", "oup-specific", "acs-specific", "rsc-specific",
    "iop-specific", "unspecified-oa", "implied-oa", "nonexclusive-distrib", "gpl-v1",
    "gpl-v2", "gpl-v3", "mit", "apache-2-0", "isc", "ogl-c", "pd",
])
def test_paper_locations_license_accepts_supported_values(license_value):
    location = {**_paper_location(), "license": license_value, "is_oa": "unknown"}
    assert rule_paper.check_locations([location]) == (False, [], [])


@pytest.mark.parametrize("license_value", [None, True, 1, [], {}, "CC-BY", "cc-by ", "apache-2-0 ", "invalid"])
def test_paper_locations_license_errors_accumulate_with_other_errors(license_value):
    location = {**_paper_location(), "license": license_value, "is_oa": "invalid"}
    del location["pdf_url"]
    result = rule_paper.check_locations([location, location])
    error = "unsupported_value" if isinstance(license_value, str) else "wrong_type"
    reason = ("license must be a supported license string"
        if isinstance(license_value, str) else "license must be a string")
    assert result == (
        True, [f"license.{error}", "is_oa.unsupported_value", "missing_key"] * 2,
        [detail for idx in (0, 1) for detail in (
            f"item[{idx}].{reason}",
            f"item[{idx}].is_oa must be one of 'true', 'false' or 'unknown'",
            f"item[{idx}] missing key 'pdf_url'",
        )],
    )


@pytest.mark.parametrize("source", [None, "", [], True, 1, "{}"])
def test_paper_locations_source_requires_object(source):
    model = rule_paper.RulePaperFieldValidation()
    model.dynamic_config = model.dynamic_config.model_copy(deep=True)
    model.dynamic_config.key_list = ["locations"]
    result = model.eval(Data(locations=[{**_paper_location(), "source": source}]))
    assert result.label == ["locations.source.wrong_type"]
    assert result.reason == ["locations: item[0].source must be an object"]


@pytest.mark.parametrize("missing_key", PAPER_SOURCE_KEYS)
def test_paper_locations_source_requires_each_key(missing_key):
    location = _paper_location()
    del location["source"][missing_key]
    assert rule_paper.check_locations([location]) == (
        True, ["source.missing_key"], [f"item[0].source missing key '{missing_key}'"],
    )


def test_paper_locations_source_empty_and_type_errors_accumulate():
    location = {**_paper_location(), "source": {}, "license": "invalid"}
    labels = ["license.unsupported_value", "source.empty"]
    reasons = [
        "item[0].license must be a supported license string",
        "item[0].source cannot be an empty object",
    ]
    assert rule_paper.check_locations([location, {**_paper_location(), "source": None}]) == (
        True, labels + ["source.wrong_type"], reasons + ["item[1].source must be an object"],
    )


def test_paper_locations_source_collects_missing_keys_in_nonempty_object():
    location = {**_paper_location(), "source": {"extra": "allowed"}}
    assert rule_paper.check_locations([location]) == (
        True, ["source.missing_key"] * len(PAPER_SOURCE_KEYS),
        [f"item[0].source missing key '{key}'" for key in PAPER_SOURCE_KEYS],
    )


def test_paper_locations_source_allows_extra_keys_without_value_constraints():
    location = _paper_location()
    location["source"]["extra"] = "allowed"
    assert rule_paper.check_locations([location]) == (False, [], [])


@pytest.mark.parametrize("version", ["publishedVersion", "acceptedVersion", "submittedVersion"])
def test_paper_locations_version_accepts_supported_values(version):
    location = {**_paper_location(), "version": version,
        "is_published": version == "publishedVersion", "is_accepted": version != "submittedVersion"}
    assert rule_paper.check_locations([location]) == (False, [], [])


@pytest.mark.parametrize("version", [
    None, "", True, 1, [], {}, "publishedversion", "PublishedVersion", "publishedVersion ", "invalid",
])
def test_paper_locations_version_errors_accumulate(version):
    location = {**_paper_location(), "source": {}, "version": version, "is_published": False, "is_accepted": False}
    model = rule_paper.RulePaperFieldValidation()
    model.dynamic_config = model.dynamic_config.model_copy(deep=True)
    model.dynamic_config.key_list = ["locations"]
    result = model.eval(Data(locations=[location, location]))
    assert result.status is True
    error = "unsupported_value" if isinstance(version, str) else "wrong_type"
    reason = ("version must be one of 'publishedVersion', 'acceptedVersion' or 'submittedVersion'"
        if isinstance(version, str) else "version must be a string")
    assert result.label == ["locations.source.empty", f"locations.version.{error}"] * 2
    assert result.reason == [detail for idx in (0, 1) for detail in (
        f"locations: item[{idx}].source cannot be an empty object",
        f"locations: item[{idx}].{reason}",
    )]


@pytest.mark.parametrize("version", ["publishedVersion", "acceptedVersion", "submittedVersion"])
@pytest.mark.parametrize("is_published", [True, False])
def test_paper_locations_is_published_version_consistency(version, is_published):
    result = rule_paper.check_locations([
        {**_paper_location(), "version": version, "is_published": is_published,
            "is_accepted": version != "submittedVersion"},
    ])
    if version == "publishedVersion" and not is_published:
        assert result == (
            True, ["is_published.version_mismatch"],
            ["item[0].is_published must be true when version='publishedVersion'"],
        )
    elif version != "publishedVersion" and is_published:
        assert result == (
            True, ["is_published.version_mismatch"],
            ["item[0].is_published must be false when version != 'publishedVersion'"],
        )
    else:
        assert result == (False, [], [])


@pytest.mark.parametrize("is_published", [None, 0, 1, "true", "false", "", [], {}])
def test_paper_locations_is_published_requires_boolean(is_published):
    result = rule_paper.check_locations([{**_paper_location(), "is_published": is_published}])
    assert result == (
        True, ["is_published.wrong_type"], ["item[0].is_published must be a boolean"],
    )


def test_paper_locations_is_published_errors_accumulate_and_missing_version_is_safe():
    missing_version = {**_paper_location(), "is_published": False, "is_accepted": False}
    del missing_version["version"]
    model = rule_paper.RulePaperFieldValidation()
    model.dynamic_config = model.dynamic_config.model_copy(deep=True)
    model.dynamic_config.key_list = ["locations"]
    result = model.eval(Data(locations=[
        {**_paper_location(), "is_published": False, "source": {}},
        {**_paper_location(), "is_published": "true"},
        missing_version,
    ]))
    assert result.label == [
        "locations.is_published.version_mismatch", "locations.source.empty",
        "locations.is_published.wrong_type", "locations.missing_key",
    ]
    assert result.reason == [
        "locations: item[0].is_published must be true when version='publishedVersion'",
        "locations: item[0].source cannot be an empty object",
        "locations: item[1].is_published must be a boolean",
        "locations: item[2] missing key 'version'",
    ]


@pytest.mark.parametrize("version", ["publishedVersion", "acceptedVersion", "submittedVersion"])
@pytest.mark.parametrize("is_accepted", [True, False])
def test_paper_locations_is_accepted_version_consistency(version, is_accepted):
    result = rule_paper.check_locations([
        {**_paper_location(), "version": version, "is_accepted": is_accepted,
            "is_published": version == "publishedVersion"},
    ])
    if version in ("publishedVersion", "acceptedVersion") and not is_accepted:
        assert result == (
            True, ["is_accepted.version_mismatch"],
            ["item[0].is_accepted must be true when version is 'publishedVersion' or 'acceptedVersion'"],
        )
    elif version == "submittedVersion" and is_accepted:
        assert result == (
            True, ["is_accepted.version_mismatch"],
            ["item[0].is_accepted must be false when version is neither 'publishedVersion' nor 'acceptedVersion'"],
        )
    else:
        assert result == (False, [], [])


@pytest.mark.parametrize("is_accepted", [None, 0, 1, "true", "false", "", [], {}])
def test_paper_locations_is_accepted_requires_boolean(is_accepted):
    assert rule_paper.check_locations([{**_paper_location(), "is_accepted": is_accepted}]) == (
        True, ["is_accepted.wrong_type"], ["item[0].is_accepted must be a boolean"],
    )


def test_paper_locations_is_accepted_errors_accumulate_and_missing_version_is_safe():
    missing_version = {**_paper_location(), "is_published": False, "is_accepted": False}
    del missing_version["version"]
    model = rule_paper.RulePaperFieldValidation()
    model.dynamic_config = model.dynamic_config.model_copy(deep=True)
    model.dynamic_config.key_list = ["locations"]
    result = model.eval(Data(locations=[
        {**_paper_location(), "is_published": False, "is_accepted": False},
        {**_paper_location(), "is_accepted": "true"},
        missing_version,
    ]))
    assert result.label == [
        "locations.is_published.version_mismatch", "locations.is_accepted.version_mismatch",
        "locations.is_accepted.wrong_type", "locations.missing_key",
    ]
    assert result.reason == [
        "locations: item[0].is_published must be true when version='publishedVersion'",
        "locations: item[0].is_accepted must be true when version is 'publishedVersion' or 'acceptedVersion'",
        "locations: item[1].is_accepted must be a boolean",
        "locations: item[2] missing key 'version'",
    ]


def test_paper_locations_reports_independent_type_labels_for_all_value_checks():
    location = {**_paper_location(), "license": [], "is_oa": True, "source": None,
        "version": {}, "is_published": 1, "is_accepted": "true"}
    model = rule_paper.RulePaperFieldValidation()
    model.dynamic_config = model.dynamic_config.model_copy(deep=True)
    model.dynamic_config.key_list = ["locations"]
    result = model.eval(Data(locations=[location]))
    assert result.status is True
    assert result.label == [
        "locations.license.wrong_type", "locations.is_oa.wrong_type",
        "locations.is_published.wrong_type", "locations.is_accepted.wrong_type",
        "locations.source.wrong_type", "locations.version.wrong_type",
    ]
    assert len(result.reason) == len(result.label)


@pytest.mark.parametrize("version_data", [{}, {"version": None}, {"version": []}, {"version": "futureVersion"}])
@pytest.mark.parametrize("flag", [True, False])
def test_paper_locations_flags_use_else_branch_for_missing_or_invalid_version(version_data, flag):
    location = {**_paper_location(), "is_published": flag, "is_accepted": flag}
    del location["version"]
    location.update(version_data)
    result = rule_paper.check_locations([location])
    expected = ["is_published.version_mismatch", "is_accepted.version_mismatch"] if flag else []
    if "version" not in version_data:
        expected.append("missing_key")
    elif not isinstance(version_data["version"], str):
        expected.append("version.wrong_type")
    else:
        expected.append("version.unsupported_value")
    assert result[0] is True
    assert result[1] == expected
    assert len(result[2]) == len(expected)


def test_paper_check_can_be_replaced_independently(monkeypatch):
    assert rule_paper.check_title is rule_quanliang.check_title
    monkeypatch.setattr(
        rule_paper, "check_title",
        lambda value: (True, ["paper_specific"], ["paper title rejected"]),
    )
    model = rule_paper.RulePaperFieldValidation()
    model.dynamic_config = model.dynamic_config.model_copy(deep=True)
    model.dynamic_config.key_list = ["title"]
    result = model.eval(Data(title="A clean title"))
    assert result.label == ["title.paper_specific"]
    assert result.reason == ["title: paper title rejected"]
    assert rule_quanliang.RuleQuanliangFieldValidation.field_validators["title"](
        {"title": "A clean title"}
    )[0] is False


def test_paper_class_mapping_can_be_replaced_independently(monkeypatch):
    paper = rule_paper.RulePaperFieldValidation
    quanliang = rule_quanliang.RuleQuanliangFieldValidation
    monkeypatch.setitem(
        paper.field_validators, "paper_field",
        lambda record: (True, ["invalid"], ["paper field rejected"]),
    )
    model = paper()
    model.dynamic_config = model.dynamic_config.model_copy(deep=True)
    model.dynamic_config.key_list = ["paper_field"]
    result = model.eval(Data(paper_field="value"))
    assert result.label == ["paper_field.invalid"]
    assert result.reason == ["paper_field: paper field rejected"]
    assert "paper_field" not in quanliang.field_validators
