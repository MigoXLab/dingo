"""Evaluate one Chinese text using the national-standard perplexity rule.

Optional dependencies:
    conda run -n dingo pip install "dingo-python[hhem]"

The first run downloads the configured Hugging Face model unless it is already
available locally. Set ``MODEL_NAME`` to a local model directory to avoid a
download.
"""

from dingo.config.input_args import EvaluatorRuleArgs
from dingo.io import Data
from dingo.model.rule.guobiao.rule_tc609_quality import Rule_TC609_02080101_TextPerplexity


def main():
    data = Data(
        data_id="guobiao-ppl-example",
        content="人工智能正在推动科学研究和产业应用快速发展。高质量数据集能够为模型训练提供准确、完整且具有代表性的样本，从而提高模型在真实应用场景中的稳定性和可靠性。",
    )

    Rule_TC609_02080101_TextPerplexity.dynamic_config = EvaluatorRuleArgs(
        threshold=100.0,
        model="uer/gpt2-chinese-cluecorpussmall",
        stride=512,
    )
    result = Rule_TC609_02080101_TextPerplexity.eval(data)
    print(result)


if __name__ == "__main__":
    main()
