from dingo.model import Model
from dingo.model.llm.text_quality.base_text_quality_v2 import BaseTextQualityV2
from dingo.model.llm.text_quality.llm_text_quality_v6 import LLMTextQualityV6


def _build_multi_label_prompt() -> str:
    """Derive V7 from the V6 rubric while replacing its output contract."""
    prompt = LLMTextQualityV6.prompt
    replacements = {
        "5. Return only one label: the single defect with the greatest training impact. If no label is clearly supported, return Good.":
            "5. Return every clearly supported label. Each label must describe a distinct material defect; do not emit duplicates or speculative secondary labels. If no label is clearly supported, return only Good.",
        "4. **Identify Primary Cause**: If problematic, which single label best explains the dominant training harm?":
            "4. **Identify Defects**: Collect every distinct label whose threshold is independently met.",
        "6. **Assign Label**:\n   - Score: 1 (suitable for training) or 0 (unsuitable)":
            "6. **Assign Labels**:\n   - Return one object per supported defect, each with score 0\n   - If no defect is supported, return exactly one Good object with score 1",
        'Return JSON only: {"score": 0/1, "type": "", "name": "", "reason": ""}':
            'Return a non-empty JSON array only: [{"score": 0/1, "type": "", "name": "", "reason": ""}]\n\nFor defective text, include all independently supported labels. Do not include a Good object together with defect objects. Emit each label at most once.',
    }
    for old, new in replacements.items():
        if old not in prompt:
            raise RuntimeError(f"V6 prompt fragment not found: {old}")
        prompt = prompt.replace(old, new)

    # All V6 examples contain one object. V7 keeps them as one-item arrays.
    prompt = prompt.replace("Output: {", "Output: [{").replace("}\n\n**Example", "}]\n\n**Example")
    prompt = prompt.replace("}\n\n---\n\n# Input content", "}]\n\n**Example 5 (Bad - Multiple Labels)**:\nInput: \"Thequickbrownfox. Thequickbrownfox. Thequickbrownfox. Thequickbrownfox. Thequickbrownfox. Thequickbrownfox.\"\nOutput: [{\"score\": 0, \"type\": \"Effectiveness\", \"name\": \"Words_Stuck\", \"reason\": \"Word boundaries are missing in every repeated sentence\"}, {\"score\": 0, \"type\": \"Similarity\", \"name\": \"Duplication\", \"reason\": \"The same sentence repeats 6 times\"}]\n\n---\n\n# Input content")
    return prompt


@Model.llm_register("LLMTextQualityV7")
class LLMTextQualityV7(BaseTextQualityV2):
    """Multi-label variant of the V6 text quality evaluator."""

    _metric_info = {
        **LLMTextQualityV6._metric_info,
        "metric_name": "LLMTextQualityV7",
        "description": "Multi-label impact-driven text quality evaluation for LLM pretraining",
    }
    prompt = _build_multi_label_prompt()
