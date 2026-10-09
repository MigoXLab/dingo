"""Evaluate one dataset document using a guobiao completeness rule.

Optional dependencies:
    conda run -n dingo pip install "dingo-python[hhem]"

The first run downloads the configured Hugging Face model unless it is already
available locally.
"""

from dingo.config.input_args import EvaluatorRuleArgs
from dingo.io import Data
from dingo.model.rule.guobiao.rule_tc609_quality import Rule_TC609_0101_DocBasicInfoCompleteness


def main():
    data = Data(
        data_id="guobiao-doc-basic-info-example",
        content="本数据集说明文档包含数据集规模与样本数量说明，提供格式规范、文件结构、访问渠道和技术支持方式。"
    )

    Rule_TC609_0101_DocBasicInfoCompleteness.dynamic_config = EvaluatorRuleArgs(
        threshold=0.8,
    )
    result = Rule_TC609_0101_DocBasicInfoCompleteness.eval(data)
    print(result)


if __name__ == "__main__":
    main()
