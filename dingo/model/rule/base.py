from typing import List

from dingo.config.input_args import EvaluatorRuleArgs
from dingo.io import Data
from dingo.model.modelres import ModelRes


class BaseRule:
    metric_type: str  # This will be set by the decorator
    group: List[str]  # This will be set by the decorator
    dynamic_config: EvaluatorRuleArgs

    # Quality label constants
    LABEL_QUALITY_GOOD = "QUALITY_GOOD"  # Indicates pass the quality check
    LABEL_QUALITY_BAD_PREFIX = "QUALITY_BAD_"  # Indicates not pass the quality check

    @classmethod
    def eval(cls, input_data: Data) -> ModelRes:
        """评估输入数据的质量

        子类应该覆盖此方法实现具体的评估逻辑。

        标准实现模式：
        ```python
        res = ModelRes()

        # 检查是否存在质量问题
        if 检测到问题:
            res.eval_status = True  # True 表示发现问题
            res.eval_details = {
                "label": ["问题标签"],
                "metric": ["规则名称"],
                "reason": ["问题描述"]
            }
        else:
            res.eval_details = {
                "label": [cls.LABEL_QUALITY_GOOD]
            }

        return res
        ```

        Args:
            input_data: 待评估的数据对象

        Returns:
            ModelRes: 评估结果对象
        """
        # 默认实现：返回质量合格
        res = ModelRes()
        res.eval_details = {
            "label": [cls.LABEL_QUALITY_GOOD]
        }
        return res
