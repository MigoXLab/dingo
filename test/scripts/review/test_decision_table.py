from dingo.review.rubric.decision_table import EXEMPTIONS, RUBRIC_VERSION, RULES, Arm, Mode, Verdict, rule_ids, valid_rule_id


def test_counts_match_spec():
    assert len(RULES) == 18          # spec §4.3
    assert len(EXEMPTIONS) == 9      # spec §4.4


def test_rule_ids_unique():
    ids = rule_ids()
    assert len(ids) == len(set(ids))
    assert all(valid_rule_id(i) for i in ids)
    assert not valid_rule_id("NOPE.NOT_A_RULE")


def test_seven_arms_present():
    assert {r.arm for r in RULES} == set(Arm)


def test_absence_and_blocked_rules_exist():
    modes = {r.mode for r in RULES}
    assert Mode.ABSENCE in modes and Mode.BLOCKED in modes and Mode.CONTRADICTION in modes


def test_known_anchors():
    by_id = {r.rule_id: r for r in RULES}
    assert by_id["EXEC.CLAIMED_ACTION_ABSENT"].mode is Mode.ABSENCE
    assert by_id["EXEC.CLAIMED_ACTION_ABSENT"].verdict is Verdict.ISSUE
    assert by_id["FILE.LABEL_MISMATCH"].verdict is Verdict.WARNING
    assert by_id["SRC.UNVERIFIABLE_AFTER_ATTEMPT"].mode is Mode.BLOCKED
    # 条件式 verdict（写文件 issue / 仅聊天 warning）用 verdict=None + verdict_note 表达
    assert by_id["SRC.FABRICATED_REFERENCE"].verdict is None
    assert by_id["SRC.FABRICATED_REFERENCE"].verdict_note


def test_exemption_priority_chain():
    by_id = {e.rule_id: e for e in EXEMPTIONS}
    # 铁律优先级链：forged/injected > 伪造引用 > domain recall > unsourced（spec §4.4）
    assert by_id["NOFLAG.FORGED_POINTER"].priority < by_id["NOFLAG.FABRICATED_REF_EXCEPTION"].priority
    assert by_id["NOFLAG.FABRICATED_REF_EXCEPTION"].priority < by_id["NOFLAG.DOMAIN_RECALL"].priority
    assert by_id["NOFLAG.DOMAIN_RECALL"].priority < by_id["NOFLAG.UNSOURCED_VALUE"].priority


def test_version_pinned():
    assert RUBRIC_VERSION == "2026-08-05.1"
