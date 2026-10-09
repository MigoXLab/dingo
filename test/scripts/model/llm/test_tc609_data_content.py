import json

from dingo.config.input_args import EvaluatorLLMArgs
from dingo.io.input import Data, RequiredField
from dingo.model.llm.guobiao.llm_tc609_0206_content_consistency import LLM_TC609_0206_ContentConsistency
from dingo.model.llm.guobiao.llm_tc609_0207_data_type_consistency import LLM_TC609_0207_DataTypeConsistency
from dingo.model.llm.guobiao.llm_tc609_base import MAX_DATA_CONTENT_CHARS, serialize_data_content


def _data():
    return Data(
        data_content=[
            {"media_type": "text", "content": "标题：健康生活建议"},
            {"media_type": "text", "content": "正文：保持规律作息。"},
            {"media_type": "image", "content": "ignored.png"},
        ]
    )


def test_tc609_data_llms_require_and_serialize_data_content():
    for evaluator in (
        LLM_TC609_0206_ContentConsistency,
        LLM_TC609_0207_DataTypeConsistency,
    ):
        assert evaluator._required_fields == [RequiredField.DATA_CONTENT]
        message = evaluator.build_messages(_data())[0]["content"]
        assert "健康生活建议" in message
        assert "保持规律作息" in message
        assert "ignored.png" in message


def test_serialize_data_content_returns_complete_json():
    serialized = serialize_data_content(_data().data_content)
    assert json.loads(serialized) == _data().data_content


def test_serialize_data_content_truncates_by_character_count():
    serialized = serialize_data_content([{"content": "x" * 40000}])
    assert len(serialized) == MAX_DATA_CONTENT_CHARS


def test_tc609_0207_includes_configured_type_and_definitions():
    evaluator = LLM_TC609_0207_DataTypeConsistency
    previous_config = evaluator.dynamic_config
    try:
        evaluator.dynamic_config = EvaluatorLLMArgs(
            dataset_type="通识数据集",
            temperature=0,
        )
        assert evaluator.dynamic_config.model_extra == {
            "dataset_type": "通识数据集",
            "temperature": 0,
        }
        assert evaluator.get_request_extra_params() == {"temperature": 0}
        message = evaluator.build_messages(_data())[0]["content"]
        assert "# 目标数据集类型\n通识数据集" in message
        assert "# 数据集类型定义" in message
    finally:
        evaluator.dynamic_config = previous_config


def test_tc609_data_llm_binary_response():
    passed = LLM_TC609_0206_ContentConsistency.process_response(
        '{"score": 1, "reason": "no material conflict"}'
    )
    failed = LLM_TC609_0207_DataTypeConsistency.process_response(
        '{"score": 0, "reason": "content does not match target type"}'
    )
    assert passed.status is False
    assert failed.status is True
