"""Evaluate TC609 0206 content consistency with an LLM.

Set the OpenAI-compatible service configuration through environment variables.
"""

import os

from dingo.config.input_args import EvaluatorLLMArgs
from dingo.io import Data
from dingo.model.llm.guobiao.llm_tc609_0206_content_consistency import LLM_TC609_0206_ContentConsistency


def main():
    llm_config = {
        "model": os.getenv("OPENAI_MODEL", ""),
        "key": os.getenv("OPENAI_API_KEY", ""),
        "api_url": os.getenv("OPENAI_BASE_URL", ""),
    }

    data = Data(
        data_id="guobiao-llm-content-consistency-example",
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

    LLM_TC609_0206_ContentConsistency.dynamic_config = EvaluatorLLMArgs(
        model=llm_config["model"],
        key=llm_config["key"],
        api_url=llm_config["api_url"],
        temperature=0,
    )
    result = LLM_TC609_0206_ContentConsistency.eval(data)
    print(result)


if __name__ == "__main__":
    main()
