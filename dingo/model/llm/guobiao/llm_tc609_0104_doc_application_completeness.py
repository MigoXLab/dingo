from dingo.io.input import RequiredField
from dingo.model import Model
from dingo.model.llm.base_openai import BaseOpenAI


@Model.llm_register("LLM_TC609_0104_DocApplicationCompleteness")
class LLM_TC609_0104_DocApplicationCompleteness(BaseOpenAI):
    """Evaluate completeness of dataset application information."""

    _required_fields = [RequiredField.CONTENT]
    _metric_info = {
        "category": "National Standard LLM Assessment Metrics",
        "metric_name": "LLM_TC609_0104_DocApplicationCompleteness",
        "description": (
            "Uses an LLM to assess license, target scenarios, evaluation "
            "method, benchmark results, and typical cases."
        ),
        "paper_title": "TC609 high-quality dataset quality evaluation specification",
        "paper_url": "",
        "paper_authors": "SAC/TC609",
        "evaluation_results": "",
        "examples": "",
    }
    prompt = """
# 角色
你是高质量数据集说明文档审核专家。请评估文档的应用说明完整性（0104）。

# 检查事项
1. 使用许可：说明许可证、授权协议或使用限制。
2. 目标应用场景：说明适用和不适用的任务、用户或业务场景。
3. 评估方法：说明如何评测该数据集或如何验证其质量。
4. 基准结果：给出评测结果、基线结果，或明确说明不提供基准及其原因。
5. 典型应用案例：说明一个具体使用流程、示例任务或实际应用案例。

# 判定规则
逐项寻找明确证据。同义词、近义表达、操作步骤和示例均可作为证据，不要求出现固定标题或关键词。
只能依据输入文档判断，不得根据常识补全。仅出现字段名称但没有说明实际数据集情况，不算完整。
共5项；明确覆盖至少4项时score为1，否则为0。
reason必须简洁列出已覆盖事项及证据，以及缺失或说明不足的事项。

# 输出格式
只输出合法JSON，不要输出Markdown或其他文字：
{"score": 0, "reason": "covered: ...; missing: ..."}

# 待评估文档
"""
