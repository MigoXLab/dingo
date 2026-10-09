import inspect
import json

from dingo.model import Model
from dingo.model.llm.text_quality.llm_text_quality_v7 import LLMTextQualityV7


def test_v7_is_registered_with_a_self_contained_prompt():
    source = inspect.getsource(inspect.getmodule(LLMTextQualityV7))

    assert Model.get_llm_name_map()["LLMTextQualityV7"] is LLMTextQualityV7
    assert "LLMTextQualityV6" not in source
    assert "_build_multi_label_prompt" not in source
    assert "# Role" in LLMTextQualityV7.prompt
    assert "# Input content to evaluate:" in LLMTextQualityV7.prompt
    assert '"statistics"' in LLMTextQualityV7.prompt
    assert '"formula_count"' in LLMTextQualityV7.prompt
    assert '"table_count"' in LLMTextQualityV7.prompt
    assert '"code_count"' in LLMTextQualityV7.prompt
    assert '"error_formula_count"' in LLMTextQualityV7.prompt
    assert '"error_table_count"' in LLMTextQualityV7.prompt
    assert '"error_code_count"' in LLMTextQualityV7.prompt
    assert "Error counts measure defective structures, not labels" in LLMTextQualityV7.prompt
    assert "finding alone therefore does not increase an error count" in LLMTextQualityV7.prompt


def test_v7_prompt_uses_detailed_formula_labels():
    formula_labels = {
        "Formula_Missing",
        "Formula_Partial_Loss",
        "Formula_Token_Corruption",
        "Formula_Unparseable",
        "Formula_Structure_Corruption",
        "Formula_Layout_Corruption",
        "Formula_Extra_Content",
    }

    assert "Formula_Corruption" not in LLMTextQualityV7.prompt
    for label in formula_labels:
        assert f"**{label}**" in LLMTextQualityV7.prompt
        assert f"`0 / Completeness / {label}`" in LLMTextQualityV7.prompt


def test_v7_prompt_uses_detailed_table_labels_in_expected_order():
    table_labels = [
        "Table_Missing",
        "Table_Unparseable",
        "Table_Partial_Loss",
        "Table_Cell_Corruption",
        "Table_Header_Corruption",
        "Table_Structure_Corruption",
        "Table_Layout_Corruption",
        "Table_Extra_Content",
    ]

    assert "Table_Corruption" not in LLMTextQualityV7.prompt
    assert "Table_Data_Inconsistency" not in LLMTextQualityV7.prompt
    label_positions = []
    for label in table_labels:
        label_positions.append(LLMTextQualityV7.prompt.index(f"**{label}**"))
        assert f"`0 / Completeness / {label}`" in LLMTextQualityV7.prompt
    assert label_positions == sorted(label_positions)


def test_v7_prompt_uses_detailed_code_labels_in_expected_order():
    code_labels = [
        "Code_Missing",
        "Code_Unparseable",
        "Code_Partial_Loss",
        "Code_Token_Corruption",
        "Code_Layout_Corruption",
        "Code_Extra_Content",
    ]

    assert "**Code_Corruption**" not in LLMTextQualityV7.prompt
    assert "`0 / Completeness / Code_Corruption`" not in LLMTextQualityV7.prompt
    assert "`0 / Completeness / Code_Indentation_Corruption`" not in LLMTextQualityV7.prompt
    assert "`0 / Completeness / Code_Duplication`" not in LLMTextQualityV7.prompt
    label_positions = []
    for label in code_labels:
        label_positions.append(LLMTextQualityV7.prompt.index(f"**{label}**"))
        assert f"`0 / Completeness / {label}`" in LLMTextQualityV7.prompt
    assert label_positions == sorted(label_positions)


def test_v7_aggregates_multiple_defects():
    response = json.dumps([
        {"score": 0, "type": "Effectiveness", "name": "Words_Stuck", "reason": "Missing spaces"},
        {"score": 0, "type": "Similarity", "name": "Duplication", "reason": "Repeated text"},
    ])

    result = LLMTextQualityV7.process_response(response)

    assert result.metric == "LLMTextQualityV7"
    assert result.status is True
    assert result.score == 0
    assert result.label == ["Effectiveness.Words_Stuck", "Similarity.Duplication"]
