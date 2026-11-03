import hashlib

from dingo.io.input import Data
from dingo.io.output.eval_detail import EvalDetail
from dingo.model.llm.repository_code_quality import LLMRepositoryCodeQualityPipeline, truncation_rules
from dingo.model.llm.repository_code_quality.input_content_rules import input_content_findings
from dingo.model.llm.repository_code_quality.llm_repository_security_review import LLMRepositorySecurityPolitics, LLMRepositorySecurityProhibition
from dingo.model.llm.repository_code_quality.llm_repository_sensitive_review import LLMRepositorySensitiveReview
from dingo.model.llm.repository_code_quality.schema_rules import schema_findings
from dingo.model.llm.repository_code_quality.sensitive_rules import confirmed_security_findings, security_candidates
from dingo.model.llm.repository_code_quality.similarity_rules import RepositoryDuplicateIndex, intra_document_repetition


def repository_data(content, **kwargs):
    values = {
        "track_id": "test-record",
        "source": "unit-test",
        "content": content,
        "language": "python",
    }
    values.update(kwargs)
    return Data(**values)


def test_security_candidate_values_are_available_for_local_review():
    content = 'password = "actual-production-password"\nserver = "10.2.3.4"\nemail = "person@corp.cn"'
    candidates = security_candidates(content)
    assert {item["category"] for item in candidates} == {"secret", "internal_endpoint", "pii"}
    assert "actual-production-password" in repr(candidates)


def test_placeholders_and_examples_are_excluded():
    assert security_candidates('api_key = "YOUR_API_KEY"\nmail = "user@example.com"') == []


def test_input_content_hard_rules_cover_empty_and_placeholders():
    assert {item["label"] for item in input_content_findings(Data(content="   \n"))} == {
        "Effectiveness.Empty_Content", "Effectiveness.Extreme_Length",
    }
    assert {item["label"] for item in input_content_findings(Data(content="undefined"))} == {
        "Effectiveness.Placeholder_Content", "Effectiveness.Extreme_Length",
    }
    assert {item["label"] for item in input_content_findings(Data(content="HTTP 503 fetch failed"))} == {
        "Effectiveness.Error_Placeholder_Content",
    }


def test_input_content_hard_rules_cover_unicode_and_controls():
    invalid = input_content_findings(Data(content="valid prefix " + "â€™" + " valid suffix"))
    assert [item["label"] for item in invalid] == ["Effectiveness.Invalid_Unicode"]

    control = input_content_findings(Data(content="print('valid code')\x00\n", language="python", file_name="main.py"))
    assert "Effectiveness.Illegal_Control_Characters" in {item["label"] for item in control}

    literal = input_content_findings(Data(content='value = "embedded\x00control"\n', language="python", file_name="main.py"))
    assert "Effectiveness.Illegal_Control_Characters" not in {item["label"] for item in literal}


def test_input_content_hard_rules_cover_length_and_sha256_aliases():
    content = "print('hash checked')\n"
    digest = hashlib.sha256(content.encode()).hexdigest()
    assert input_content_findings(Data(content=content, dedup_content_sha256=digest)) == []
    mismatch = input_content_findings(Data(content=content, dedup_content_sha256="0" * 64))
    assert [item["label"] for item in mismatch] == ["Effectiveness.Content_SHA256_Mismatch"]

    long_line = "x" * 20_001
    labels = {item["label"] for item in input_content_findings(Data(content=long_line))}
    assert "Effectiveness.Extreme_Length" in labels


def test_input_hard_gate_skips_every_llm_stage(monkeypatch):
    def unexpected_stage(cls, evaluator, input_data, config):
        raise AssertionError("hard-gated records must not call an LLM")

    monkeypatch.setattr(LLMRepositoryCodeQualityPipeline, "_run_stage", classmethod(unexpected_stage))
    result = LLMRepositoryCodeQualityPipeline.eval(repository_data("404 not found"))
    assert set(result.label) == {
        "Effectiveness.Error_Placeholder_Content", "Effectiveness.Extreme_Length",
    }
    assert result.applicable


def test_repository_sensitive_rules_cover_requested_pii_taxonomy():
    content = """email = "person@company.cn"
full_name = "Lynn Marshall"
ipv4 = "147.46.27.126"
phone = "0755-27357825"
ipv6 = "2001::F00F"
mac = "02:42:ac:16:00:03"
ssn = "899-46-2035"
ein = "64-6221541"
card = "4202297003827029"
cvv = "082"
tfn = "84 099 019 851"
imei = "867435050765767"
iban = "ES18 0182 4466 1702 0154 1449"
id_card = "371525199504125318"
bank_account = "339146391262"
tax_it = "CHPMRC80D12L219D"
routing = "211372378"
"""
    candidates = security_candidates(content)
    kinds = {candidate["kind"] for candidate in candidates}
    assert kinds >= {
        "EMAIL", "PERSON_NAME", "IP_V4", "PHONE", "IP_V6", "MAC", "SSN",
        "TAX_ID_US", "CREDIT_CARD", "CVV", "TAX_ID_AU", "IMEI", "IBAN", "ID_CARD_CN",
        "BANK_ACCOUNT", "TAX_ID_IT", "ABA_ROUTING",
    }
    assert all(set(candidate) == {
        "category", "kind", "line", "severity", "confidence", "validator", "context_hint", "matched_value",
    } for candidate in candidates)
    assert "person@company.cn" in repr(candidates)
    assert "4202297003827029" in repr(candidates)


def test_repository_sensitive_rules_cover_requested_credential_taxonomy():
    content = """password = "654321"
api_key = "9697a71c025df7188683c8cd5e91f27c"
cloud_token = "5112570737:AAFGYqD2UI5uSXF5ZjpmLFqP56Ttr8zAPrg"
db = "mongodb+srv://service:strong-password@cluster.example.net"
Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.abcdefghijklmnop
private_key = "-----BEGIN RSA PRIVATE KEY-----"
password_hash = "$2y$10$C0vas4IEYBi7RFvD3sL3OuweYYYcnLxb123456789012345678901"
url = "https://service-user:strong-password@private.example.net/api"
cookie = "cdc8c3819fc7865ffd688469a907230c"
"""
    candidates = security_candidates(content)
    kinds = {candidate["kind"] for candidate in candidates}
    assert kinds >= {
        "PASSWORD", "API_KEY", "CLOUD_TOKEN", "DB_CONNECTION", "AUTHORIZATION", "JWT",
        "PRIVATE_KEY", "PASSWORD_HASH", "AUTH_URL", "COOKIE",
    }
    assert "strong-password" in repr(candidates)


def test_complete_private_key_block_is_confirmed_without_exposing_body():
    body = "A" * 80
    content = f"-----BEGIN PRIVATE KEY-----\n{body}\n-----END PRIVATE KEY-----"
    candidates = security_candidates(content)
    private_key = next(candidate for candidate in candidates if candidate["kind"] == "PRIVATE_KEY")
    assert private_key["confidence"] == "high"
    assert body in repr(candidates)


def test_checksum_and_context_guards_reduce_common_false_positives():
    content = """id = "371525199504125319"
card = "4202297003827028"
imei = "867435050765768"
iban = "ES18 0182 4466 1702 0154 1448"
routing = "211372379"
version = "1.2.3.999"
number = "123456789"
mail = "user@example.com"
password = "${PASSWORD}"
"""
    assert security_candidates(content) == []


def test_public_ledger_addresses_and_version_strings_are_not_flagged():
    content = """wallet = "0xdcf8acaa9f47586ce15136f4b172c8eec93fe863"
donation = "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4"
release = "1.2.3.4"
"""
    kinds = {candidate["kind"] for candidate in security_candidates(content)}
    assert "CRYPTO_ADDRESS" not in kinds
    assert "IP_V4" not in kinds


def test_author_attribution_names_are_contextual_pii():
    candidates = security_candidates(
        "// Copyright 2008-2010 by Robert Fernie\n// Copyright 2020 PrestaShop SA\n"
    )
    assert [item["matched_value"] for item in candidates if item["kind"] == "PERSON_NAME"] == ["Robert Fernie"]
    assert all(item["confidence"] == "contextual" for item in candidates)


def test_routable_public_ip_is_contextual_pii_without_context_words():
    candidates = security_candidates('"185.53.88.104"\n"127.0.0.1"\n"192.0.2.1"\n"8.8.8.8"\n')
    assert [item["matched_value"] for item in candidates] == ["185.53.88.104"]
    assert candidates[0]["category"] == "pii"
    assert candidates[0]["confidence"] == "contextual"


def test_unquoted_credentials_are_split_by_literal_strength():
    strong = security_candidates("db_password:=foobar-bizz-buzz\n")
    assert [(item["kind"], item["confidence"], item["matched_value"]) for item in strong] == [
        ("PASSWORD", "high", "foobar-bizz-buzz")
    ]

    weak = security_candidates("keyStorePassword: passw0rd\n")
    assert [(item["kind"], item["confidence"]) for item in weak] == [("PASSWORD", "contextual")]

    references = security_candidates(
        "token = context.getCurrentToken();\npassword_file = ${PWD}/secrets/db.password\n"
    )
    assert references == []


def test_url_query_and_connection_string_credentials_are_contextual():
    query = security_candidates('url = "https://api.example.org/?t=x&apikey=6637725e"\n')
    assert [(item["kind"], item["matched_value"]) for item in query] == [("API_KEY", "6637725e")]

    template = security_candidates("url = `https://api.example.org/?api_key=${MOVIE_DB_API_KEY}`\n")
    assert template == []

    connection = security_candidates('<add ConnectionString="Server=DB01;User Id=ST;Password=Amdocs11;" />\n')
    assert any(item["matched_value"] == "Amdocs11" for item in connection)


def test_openvpn_static_key_marker_is_confirmed():
    candidates = security_candidates("-----BEGIN OpenVPN Static key V1-----\n")
    assert [item["kind"] for item in candidates] == ["PRIVATE_KEY"]
    assert candidates[0]["confidence"] == "high"


def test_role_based_contacts_are_excluded_but_personal_header_emails_are_kept():
    assert security_candidates('mail = "info@company.org"\nirc = "support@company.org"\n') == []

    header = security_candidates("# Copyright 2015 Roland Meier <roland@rptd.ch>\n")
    assert [item["matched_value"] for item in header if item["kind"] == "EMAIL"] == ["roland@rptd.ch"]


def test_context_guards_avoid_common_identifier_false_positives():
    content = """order_ref = "0755-27357825"
sessionId = crypto.randomUUID()
import com.host.internal.service
"""
    assert security_candidates(content) == []


def test_organizations_prose_and_version_quads_are_not_flagged():
    content = """// Copyright (C) 2003, International Business Machines
 * Copyright (C) 2018 - 2021 Hedera Hashgraph, LLC
 * Copyright Metaparadigm Pte. Ltd. 2004.
 * Copyright (C) 2016 Fraunhofer Institut IOSB, Fraunhoferstr. 1
//COPYRIGHT:    University of California, San Francisco, 2008
<link rel="copyright" href="ln-idm46082189555600.html" title="Legal Notice">
<p>When only 1 file is created by one API call it is stored by Google Drive</p>
LogSupport.debug(ctx, MODULE, "Tax Authority is null for trans " + trans.getResponsibleBAN());
[assembly: AssemblyVersion("1.0.0.0")]
 * $Id: DictionarySerializer.java,v 1.5.2.2 2006-03-06 12:39:21 mclark Exp $
"""
    assert security_candidates(content) == []


def test_real_attributions_and_contacts_are_still_flagged():
    content = """// Copyright 2016 Mitchell Kember. Subject to the MIT License.
 * Copyright (C) 1995 David S. Miller (davem@caip.rutgers.edu)
"""
    values = {candidate["matched_value"] for candidate in security_candidates(content)}
    assert {"Mitchell Kember", "davem@caip.rutgers.edu"} <= values


def test_prose_attributions_are_flagged_but_collective_names_are_not():
    content = """<p>The Java mascot was created by Joe Palrang. Palrang also worked on Hollywood.</p>
              Ivan Fratric is a security researcher at Google Project Zero, where he focuses on fuzzing.
"""
    values = {candidate["matched_value"] for candidate in security_candidates(content) if candidate["kind"] == "PERSON_NAME"}
    assert {"Joe Palrang", "Ivan Fratric"} <= values


def test_prose_without_attribution_context_is_not_flagged():
    content = """ * Author: UC San Diego Intermediate Software Development MOOC team
 *  (c) 2017 Semantic Access and Retrieval group, All rights reserved
               When Microsoft announced the change there was an audible sigh of relief.
<p>When only 1 file is created by one API call it is stored by Google Drive.</p>
"""
    assert security_candidates(content) == []


def test_code_identifiers_and_type_names_are_not_credentials():
    content = """var cancellationToken = _transaction?.CancellationToken ?? _cancellationToken;
static const String isPINAvailable = 'isPINAvailable';
c.PasswordSalt = "mobile"
"""
    assert security_candidates(content) == []


def test_quoted_literal_passwords_are_still_flagged():
    content = """final String password = "thanh112002";//change accordingly
PASSWORD = 'Todd.Test123'
"""
    values = {candidate["matched_value"] for candidate in security_candidates(content)}
    assert values == {"thanh112002", "Todd.Test123"}


def test_asset_paths_and_dummy_addresses_are_not_emails():
    content = """img = "/assets/s-site-assets-template-stylesheets/images/bc_logo_black_1@1x.png"
user = new LdoDUser(this.ldoD, "ars1", "ars", "Antonio", "Silva", "a@a.a");
tracker = "bug-Spreadsheet-WriteExcel@rt.cpan.org"
"""
    assert security_candidates(content) == []


def test_confirmed_matches_are_rule_first_and_contextual_matches_are_separate():
    candidates = security_candidates(
        'card = "4202297003827029"\nemail = "private.person@company.cn"\n'
    )
    findings = confirmed_security_findings(candidates)
    assert [finding["label"] for finding in findings] == ["Security.PII_Exposure"]
    assert "CREDIT_CARD" in findings[0]["reason"]
    assert "EMAIL" not in findings[0]["reason"]


def test_sensitive_llm_receives_only_redacted_candidate_context():
    raw_email = "private.person@company.cn"
    candidates = security_candidates(f'email = "{raw_email}"')
    messages = LLMRepositorySensitiveReview.build_messages(
        Data(content=f'email = "{raw_email}"', repository_security_candidates=candidates)
    )
    assert raw_email not in repr(messages)
    assert "REDACTED" in repr(messages)


def test_intra_document_repetition_uses_handoff_thresholds():
    finding = intra_document_repetition("same generated row\n" * 100)
    assert finding["label"] == "Similarity.Intra_Document_Repetition"
    assert intra_document_repetition("print('useful')\n") is None


def test_duplicate_index_covers_cross_record_rules():
    index = RepositoryDuplicateIndex(near_threshold=0.80)
    header = "# Copyright 2020 Example\n# Licensed under the Apache License, Version 2.0\n"
    body = "\n".join(
        f"value_{index} = calculate_total(source_{index}, adjustment_{index})"
        for index in range(24)
    ) + "\n"
    first = Data(content=header + body, language="python", file_name="a.py")
    exact = Data(content=header + body, language="python", file_name="b.py")
    near = Data(content=header + body + "print('done')\n", language="python", file_name="c.py")
    assert index.annotate(first, "first") == []
    exact_labels = {item["label"] for item in index.annotate(exact, "exact")}
    assert "Similarity.Normalized_Token_Duplicate" in exact_labels
    near_labels = {item["label"] for item in index.annotate(near, "near")}
    assert "Similarity.Token_Shingle_Near_Duplicate" in near_labels


def test_builtin_security_parsers_emit_public_labels():
    prohibited = LLMRepositorySecurityProhibition.process_response(
        '{"porn":"neg","gamble":"pos","drug":"neg"}'
    )
    assert prohibited.label == ["Security.Gamble"]
    politics = LLMRepositorySecurityPolitics.process_response(
        '{"hurt_socialist_regime_system":"none","hurt_china_interests_image":"none",'
        '"hurt_china_unity_stability":"none","terrorism_and_extremism":"neg",'
        '"ethnic_hate_and_discrimination":"none"}'
    )
    assert politics.label == ["Security.Politics"]


def test_politics_parser_accepts_common_outer_format_noise():
    payload = (
        '"hurt_socialist_regime_system":"none","hurt_china_interests_image":"none",'
        '"hurt_china_unity_stability":"none","terrorism_and_extremism":"none",'
        '"ethnic_hate_and_discrimination":"none"'
    )
    for response in (
        "{{" + payload + "}}",
        "Result:\n```json\n{" + payload + "}\n```",
    ):
        result = LLMRepositorySecurityPolitics.process_response(response)
        assert result.label == ["QUALITY_GOOD"]


def test_politics_retries_once_after_parse_failure(monkeypatch):
    valid = (
        '{"hurt_socialist_regime_system":"none","hurt_china_interests_image":"none",'
        '"hurt_china_unity_stability":"none","terrorism_and_extremism":"none",'
        '"ethnic_hate_and_discrimination":"none"}'
    )
    responses = iter(["not-json", valid])
    calls = []

    def fake_send(cls, messages):
        calls.append(messages)
        return next(responses)

    monkeypatch.setattr(LLMRepositorySecurityPolitics, "client", object())
    monkeypatch.setattr(LLMRepositorySecurityPolitics, "send_messages", classmethod(fake_send))
    result = LLMRepositorySecurityPolitics.eval(Data(content="ordinary source code"))
    assert result.applicable
    assert result.label == ["QUALITY_GOOD"]
    assert len(calls) == 2


def test_pipeline_merges_prepared_and_stage_findings(monkeypatch):
    def fake_stage(cls, evaluator, input_data, config):
        labels = {
            "LLMTextAdvertisement": ["Effectiveness.Advertisement"],
            "LLMRepositorySensitiveReview": ["Security.Secret_Credentials"],
        }.get(evaluator.__name__, ["QUALITY_GOOD"])
        return EvalDetail(
            metric=evaluator.__name__, status=labels != ["QUALITY_GOOD"], label=labels, reason=["reviewed"]
        )

    monkeypatch.setattr(LLMRepositoryCodeQualityPipeline, "_run_stage", classmethod(fake_stage))
    data = repository_data(
        'password = "actual-production-password"\n' + ("repeat line\n" * 100),
        repository_duplicate_findings=[{"label": "Similarity.Normalized_Token_Duplicate", "reason": "duplicate"}],
    )
    result = LLMRepositoryCodeQualityPipeline.eval(data)
    assert result.applicable
    assert set(result.label) >= {
        "Effectiveness.Advertisement", "Security.Secret_Credentials",
        "Similarity.Intra_Document_Repetition",
    }


def test_pipeline_reports_validated_pii_without_sensitive_llm_or_content_mutation(monkeypatch):
    stages = []

    def fake_stage(cls, evaluator, input_data, config):
        stages.append(evaluator.__name__)
        return EvalDetail(metric=evaluator.__name__, label=["QUALITY_GOOD"], reason=["reviewed"])

    monkeypatch.setattr(LLMRepositoryCodeQualityPipeline, "_run_stage", classmethod(fake_stage))
    original = 'card = "4202297003827029"'
    data = repository_data(original)
    result = LLMRepositoryCodeQualityPipeline.eval(data)

    assert "Security.PII_Exposure" in result.label
    assert "4202297003827029" in result.reason[result.label.index("Security.PII_Exposure")]
    assert "LLMRepositorySensitiveReview" not in stages
    assert data.content == original


def test_pipeline_adds_raw_evidence_after_contextual_review(monkeypatch):
    def fake_stage(cls, evaluator, input_data, config):
        if evaluator is LLMRepositorySensitiveReview:
            return EvalDetail(
                metric=evaluator.__name__, status=True,
                label=["Security.PII_Exposure"], reason=["Confirmed private contact data."],
            )
        return EvalDetail(metric=evaluator.__name__, label=["QUALITY_GOOD"], reason=["reviewed"])

    monkeypatch.setattr(LLMRepositoryCodeQualityPipeline, "_run_stage", classmethod(fake_stage))
    raw_email = "private.person@company.cn"
    result = LLMRepositoryCodeQualityPipeline.eval(repository_data(f'email = "{raw_email}"'))
    assert raw_email in result.reason[result.label.index("Security.PII_Exposure")]


def test_pipeline_preserves_stage_error_type(monkeypatch):
    def fake_stage(cls, evaluator, input_data, config):
        if evaluator is LLMRepositorySecurityPolitics:
            return EvalDetail(
                metric=evaluator.__name__, applicable=False,
                not_applicable_kind="execution_error",
                label=["REVIEW_EXECUTION_ERROR.ConvertJsonError"],
                reason=["Invalid political review JSON"],
            )
        return EvalDetail(metric=evaluator.__name__, label=["QUALITY_GOOD"], reason=["ok"])

    monkeypatch.setattr(LLMRepositoryCodeQualityPipeline, "_run_stage", classmethod(fake_stage))
    result = LLMRepositoryCodeQualityPipeline.eval(repository_data("print('ordinary source code')\n"))
    assert not result.applicable
    assert result.label == ["REVIEW_EXECUTION_ERROR.politics"]
    assert "ConvertJsonError" in result.reason[0]


def test_repository_schema_rules_cover_required_type_length_and_regex():
    labels = {
        finding["label"]
        for finding in schema_findings(Data(
            track_id=True,
            source="bad source",
            content="valid code",
            language="x" * 65,
            sha256="A" * 64,
        ))
    }
    assert labels == {
        "Effectiveness.Field_Type_Mismatch",
        "Effectiveness.Field_Length_Out_Of_Range",
        "Effectiveness.Field_Regex_Mismatch",
    }
    assert [item["label"] for item in schema_findings(Data(source="repo", content=None))] == [
        "Effectiveness.Missing_Required",
        "Effectiveness.Empty_Required",
    ]


def test_repository_schema_accepts_alias_and_supported_sources():
    for source in ("s3://bucket/key", "https://example.com/a", "file:///tmp/a", "/tmp/a", "github-v2"):
        data = repository_data("print('schema valid')\n", source=source, dedup_content_sha256="a" * 64)
        assert schema_findings(data) == []


def test_code_truncation_requires_parser_and_tail_signals(monkeypatch):
    content = (
        "def calculate(value):\n"
        "    result = (\n"
        + "        value + 1\n" * 5
    )
    monkeypatch.setattr(
        truncation_rules,
        "_error_evidence",
        lambda _content, _parser: {
            "error_nodes": 1, "missing_nodes": 0,
            "tail_error_nodes": 1, "tail_missing_nodes": 0,
        },
    )
    finding = truncation_rules.code_truncation_finding(repository_data(content, file_name="main.py"))
    assert finding["label"] == "Completeness.Code_Truncation"
    assert "unclosed_paren" in finding["reason"]

    complete = "def calculate(value):\n    return value + 1\n" + "# padding\n" * 6
    assert truncation_rules.code_truncation_finding(repository_data(complete, file_name="main.py")) is None


def test_code_truncation_skips_structured_and_parser_unavailable(monkeypatch):
    content = '{"items": [1, 2, 3,' + " " * 80
    called = []
    monkeypatch.setattr(truncation_rules, "_error_evidence", lambda *_args: called.append(True))
    assert truncation_rules.code_truncation_finding(
        repository_data(content, language="json", file_name="data.json")
    ) is None
    assert called == []

    code = "def f(value):\n    return (\n" + "        value + 1\n" * 5
    assert truncation_rules.code_truncation_finding(
        repository_data(code, language="unsupported", file_name="main.custom")
    ) is None
