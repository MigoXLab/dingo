from dingo.io.input import RequiredField
from dingo.model import Model
from dingo.model.llm.base_openai import BaseOpenAI


@Model.llm_register("LLM_TC609_0102_DocContentFeatureCompleteness")
class LLM_TC609_0102_DocContentFeatureCompleteness(BaseOpenAI):
    """Evaluate completeness of dataset content features."""

    _required_fields = [RequiredField.CONTENT]
    _metric_info = {
        "category": "National Standard LLM Assessment Metrics",
        "metric_name": "LLM_TC609_0102_DocContentFeatureCompleteness",
        "description": (
            "Uses an LLM to assess modality, distribution, label statistics, "
            "sample examples, and limitations in dataset documentation."
        ),
        "paper_title": "TC609 high-quality dataset quality evaluation specification",
        "paper_url": "",
        "paper_authors": "SAC/TC609",
        "evaluation_results": "",
        "examples": "",
    }
    prompt = """
# 角色
你是高质量数据集说明文档审核专家。请评估文档的内容特征完整性（0102）。

# 检查事项
1. 模态类型：说明数据包含文本、图像、音频、视频或其他模态。
2. 数据分布：说明领域、类别、语言、时间或其他维度的数据分布。
3. 标签统计：说明标签类别及各类别的数量、占比或分布情况。
4. 样本示例：给出能够代表实际记录结构和内容的数据样例。
5. 局限性：说明覆盖范围、规模、偏差、适用边界或已知不足。

# 判定规则
逐项寻找明确证据。同义词、近义表达、表格和示例均可作为证据，不要求出现固定标题或关键词。
只能依据输入文档判断，不得根据常识补全。仅出现字段名称但没有说明实际数据集情况，不算完整。
共5项；明确覆盖至少4项时score为1，否则为0。
reason必须简洁列出已覆盖事项及证据，以及缺失或说明不足的事项。

# 输出格式
只输出合法JSON，不要输出Markdown或其他文字：
{"score": 0, "reason": "covered: ...; missing: ..."}

# 待评估文档
"""
