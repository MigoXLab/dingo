"""Evaluate data_content using the TC609 0202 safety-compliance LLM.

Set the OpenAI-compatible service configuration through environment variables.
"""

import os

from dingo.config.input_args import EvaluatorLLMArgs
from dingo.io import Data
from dingo.model.llm.guobiao.llm_tc609_0202_SafetyCompliance import LLM_TC609_0202_SafetyCompliance


def main():
    llm_config = {
        "model": os.getenv("OPENAI_MODEL", ""),
        "key": os.getenv("OPENAI_API_KEY", ""),
        "api_url": os.getenv("OPENAI_BASE_URL", ""),
    }

    data = Data(
        data_id="guobiao-safety-example",
        data_content=[
            {
                "media_type": "text",
                "content": "高血压患者应在医生指导下规律用药，并定期监测血压变化。",
            },
            {
                "media_type": "text",
                "content": "凶手残忍地杀害了被害人。",
            },
        ],
    )

    LLM_TC609_0202_SafetyCompliance.dynamic_config = EvaluatorLLMArgs(
        model=llm_config["model"],
        key=llm_config["key"],
        api_url=llm_config["api_url"],
        temperature=0,
    )
    result = LLM_TC609_0202_SafetyCompliance.eval(data)
    print(result)


if __name__ == "__main__":
    main()
