from dingo.config.input_args import EvaluatorLLMArgs
from dingo.io.input import RequiredField
from dingo.model import Model
from dingo.model.llm.base_openai import BaseOpenAI
from dingo.model.llm.guobiao.llm_tc609_base import serialize_data_content


@Model.llm_register("LLM_TC609_0202_SafetyCompliance")
class LLM_TC609_0202_SafetyCompliance(BaseOpenAI):
    """Evaluate dataset content for TC609 safety compliance."""

    _required_fields = [RequiredField.DATA_CONTENT]
    dynamic_config = EvaluatorLLMArgs()
    _metric_info = {
        "category": "National Standard LLM Assessment Metrics",
        "metric_name": "LLM_TC609_0202_SafetyCompliance",
        "description": "Uses an LLM to assess dataset content safety compliance.",
        "paper_title": "TC609 high-quality dataset quality evaluation specification",
        "paper_url": "",
        "paper_authors": "SAC/TC609",
        "evaluation_results": "",
        "examples": "examples/guobiao/llm_0202_SafetyCompliance.py",
    }
    prompt = """

"""

    @classmethod
    def build_messages(cls, input_data):
        if not cls.prompt or not cls.prompt.strip():
            raise ValueError("prompt cannot be empty.")
        content = serialize_data_content(input_data.data_content)
        return [{"role": "user", "content": cls.prompt + content}]
