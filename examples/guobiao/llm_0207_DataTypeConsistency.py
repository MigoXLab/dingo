"""Evaluate TC609 0207 dataset-type consistency with an LLM.

Set the OpenAI-compatible service configuration through environment variables.
"""

import os

from dingo.config.input_args import EvaluatorLLMArgs
from dingo.io import Data
from dingo.model.llm.guobiao.llm_tc609_0207_data_type_consistency import LLM_TC609_0207_DataTypeConsistency


def main():
    llm_config = {
        "model": os.getenv("OPENAI_MODEL", ""),
        "key": os.getenv("OPENAI_API_KEY", ""),
        "api_url": os.getenv("OPENAI_BASE_URL", ""),
    }

    data = Data(
        data_id="guobiao-llm-data-type-consistency-example",
        data_content=[
            {
                "media_type": "text",
                "content": (
                    "高血压患者应在医生指导下规律用药，并定期监测血压变化。"
                    "本记录用于医疗健康领域的知识问答训练。"
                ),
            }
        ],
    )

    LLM_TC609_0207_DataTypeConsistency.dynamic_config = EvaluatorLLMArgs(
        model=llm_config["model"],
        key=llm_config["key"],
        api_url=llm_config["api_url"],
        dataset_type="行业通识数据集",
        temperature=0,
    )
    result = LLM_TC609_0207_DataTypeConsistency.eval(data)
    print(result)


if __name__ == "__main__":
    main()
