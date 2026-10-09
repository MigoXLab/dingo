"""Evaluate text content using the national-standard type-consistency rule.

Optional dependencies:
    conda run -n dingo pip install "dingo-python[hhem]"

The first run downloads the configured Hugging Face model unless it is already
available locally.
"""

from dingo.config.input_args import EvaluatorRuleArgs
from dingo.io import Data
from dingo.model.rule.guobiao.rule_tc609_quality import Rule_TC609_0207_DataTypeConsistency


def main():
    data = Data(
        data_id="guobiao-type-example",
        data_content=[
            {
                "media_type": "text",
                "content": "高血压患者应在医生指导下规律用药，并定期监测血压变化。",
            }
        ],
    )

    Rule_TC609_0207_DataTypeConsistency.dynamic_config = EvaluatorRuleArgs(
        dataset_type="行业通识数据集",
        threshold=0.5,
        model="MoritzLaurer/mDeBERTa-v3-base-mnli-xnli",
        device=-1,
    )
    result = Rule_TC609_0207_DataTypeConsistency.eval(data)
    print(result)


if __name__ == "__main__":
    main()
