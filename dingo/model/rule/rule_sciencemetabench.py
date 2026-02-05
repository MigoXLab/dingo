import json
import os
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path

import pandas as pd

from dingo.config.input_args import EvaluatorRuleArgs
from dingo.io.input import Data, RequiredField
from dingo.io.output.eval_detail import EvalDetail, QualityLabel
from dingo.model import Model
from dingo.model.rule.base import BaseRule


def calculate_similarity(str1, str2) -> float:
    """
    计算两个字符串的相似度

    规则:
    1. 一个为空另一个不为空，相似度为0
    2. 二者完全相同（包括全为空），相似度为1
    3. 忽略大小写进行比较
    4. 使用SequenceMatcher计算相似度
    """
    # 规则1: 一个为空另一个不为空，相似度为0
    if (str1 is None or str1 == "") and (str2 is not None and str2 != ""):
        return 0.0
    if (str2 is None or str2 == "") and (str1 is not None and str1 != ""):
        return 0.0

    # 规则2: 二者完全相同（包括全为空），相似度为1
    if (str1 or "") == (str2 or ""):
        return 1.0

    # 规则3: 忽略大小写进行比较
    s1_lower = str1.lower()
    s2_lower = str2.lower()

    # 如果忽略大小写后相同，直接返回1
    if s1_lower == s2_lower:
        return 1.0

    # 使用SequenceMatcher计算相似度
    matcher = SequenceMatcher(None, s1_lower, s2_lower)
    similarity = matcher.ratio()

    return similarity


@Model.rule_register("QUALITY_BAD_EFFECTIVENESS", ["sciencemetabench"])
class RuleMetadataSimilarity(BaseRule):
    """
    元数据字段相似度匹配的基类

    数据结构：每个字段包含 standard 和 produced 两个子字段
    例如: {"doi": {"standard": "...", "produced": "..."}}

    使用方式：通过 fields 映射单个字段到 metadata
    配置示例: "fields": {"metadata": "doi"}

    阈值默认为 0.6，相似度达到阈值才算通过

    子类需要定义:
    - _metric_info: 包含 metric_name 和 description
    - dynamic_config: 包含 threshold (阈值) 和 key_list (字段名称)
    """

    _metric_info = {
        "category": "Rule-Based Metadata Quality Metrics",
        "quality_dimension": "EFFECTIVENESS",
        "metric_name": "RuleMetadataSimilarity",
        "description": "检查元数据字段与基准数据的相似度匹配，阈值默认为0.6",
    }

    _required_fields = [RequiredField.METADATA]

    dynamic_config = EvaluatorRuleArgs(
        threshold=0.6,
        key_list=["standard", "produced"]
    )

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        # 验证 threshold 是否在 [0, 1] 闭区间内
        if not hasattr(cls.dynamic_config, 'threshold'):
            raise ValueError(f"dynamic_config.threshold 必须设置")
        if not (0 <= cls.dynamic_config.threshold <= 1):
            raise ValueError(f"dynamic_config.threshold 必须在 [0, 1] 区间内，当前值: {cls.dynamic_config.threshold}")

        # 验证 key_list 是否包含至少2个元素
        if not hasattr(cls.dynamic_config, 'key_list') or len(cls.dynamic_config.key_list) < 2:
            raise ValueError(f"dynamic_config.key_list 必须包含至少2个元素")

        res = EvalDetail(metric=cls.__name__)

        # 检查并获取 metadata 字段
        if not hasattr(input_data, RequiredField.METADATA.value):
            raise ValueError(f"input_data 中缺少必需字段: {RequiredField.METADATA.value}")

        metadata = getattr(input_data, RequiredField.METADATA.value)

        # 验证 metadata 格式
        if not isinstance(metadata, dict):
            raise ValueError(f"metadata 字段的数据格式错误，应为字典")

        key_standard = cls.dynamic_config.key_list[0]
        key_produced = cls.dynamic_config.key_list[1]

        if key_standard not in metadata or key_produced not in metadata:
            raise ValueError(f"metadata 字段缺少 '{key_standard}' 或 '{key_produced}' 子字段")

        # 获取字段值
        standard_value = metadata.get(key_standard, "")
        produced_value = metadata.get(key_produced, "")

        # 计算相似度
        similarity = calculate_similarity(
            str(standard_value) if standard_value is not None else "",
            str(produced_value) if produced_value is not None else ""
        )

        # 判断是否通过
        if similarity < cls.dynamic_config.threshold:
            res.status = True
            res.label = [f"{cls.metric_type}.{cls.__name__}"]
        else:
            res.label = [QualityLabel.QUALITY_GOOD]
        res.score = round(similarity, 3)

        return res
