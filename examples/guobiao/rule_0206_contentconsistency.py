"""Evaluate text items using the national-standard content-consistency rule.

Optional dependencies:
    conda run -n dingo pip install "dingo-python[hhem]"

The first run downloads the configured Hugging Face model unless it is already
available locally.
"""

from dingo.config.input_args import EvaluatorRuleArgs
from dingo.io import Data
from dingo.model.rule.guobiao.rule_tc609_quality import Rule_TC609_0206_ContentConsistency


def main():
    data = Data(
        data_id="guobiao-content-consistency-example",
        data_content=[
            {
                "media_type": "text",
                "content": "高血压患者的日常健康管理",
            },
            {
                "media_type": "text",
                "content": (
                    "高血压患者应遵医嘱规律用药，并定期监测血压。"
                    "日常生活中还应注意低盐饮食和适量运动。"
                ),
            },
            {
                "media_type": "image",
                "content": "../data/images/blood-pressure.jpg",
            },
        ],
    )

    Rule_TC609_0206_ContentConsistency.dynamic_config = EvaluatorRuleArgs(
        threshold=0.5,
        model=(
            "sentence-transformers/"
            "paraphrase-multilingual-MiniLM-L12-v2"
        ),
        device=-1,
    )
    result = Rule_TC609_0206_ContentConsistency.eval(data)
    print(result)


if __name__ == "__main__":
    main()
