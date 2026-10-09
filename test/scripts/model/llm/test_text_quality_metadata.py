import importlib.util

from dingo.model import Model
from dingo.model.llm.text_quality.llm_text_quality_v2 import LLMTextQualityV2
from dingo.model.llm.text_quality.llm_text_quality_v3 import LLMTextQualityV3
from dingo.model.llm.text_quality.llm_text_quality_v4 import LLMTextQualityV4
from dingo.model.llm.text_quality.llm_text_quality_v5 import LLMTextQualityV5
from dingo.model.llm.text_quality.llm_text_quality_v6 import LLMTextQualityV6
from dingo.model.llm.text_quality.llm_text_quality_v7 import LLMTextQualityV7


def test_every_retained_text_quality_version_has_concise_metric_info():
    versions = [
        LLMTextQualityV2,
        LLMTextQualityV3,
        LLMTextQualityV4,
        LLMTextQualityV5,
        LLMTextQualityV6,
        LLMTextQualityV7,
    ]

    for version in versions:
        info = version._metric_info
        assert info["metric_name"] == version.__name__
        assert info["description"].count(".") == 2


def test_v8_is_no_longer_available():
    Model.load_model()

    assert "LLMTextQualityV8" not in Model.get_llm_name_map()
    assert importlib.util.find_spec(
        "dingo.model.llm.text_quality.llm_text_quality_v8"
    ) is None
