from dingo.io.input import RequiredField
from dingo.model import Model
from dingo.model.llm.base_openai import BaseOpenAI


@Model.llm_register("LLM_TC609_0103_DocConstructionProcessCompleteness")
class LLM_TC609_0103_DocConstructionProcessCompleteness(BaseOpenAI):
    """Evaluate completeness of the dataset construction process."""

    _required_fields = [RequiredField.CONTENT]
    _metric_info = {
        "category": "National Standard LLM Assessment Metrics",
        "metric_name": "LLM_TC609_0103_DocConstructionProcessCompleteness",
        "description": (
            "Uses an LLM to assess source, collection, processing, annotation, "
            "and version control in dataset documentation."
        ),
        "paper_title": "TC609 high-quality dataset quality evaluation specification",
        "paper_url": "",
        "paper_authors": "SAC/TC609",
        "evaluation_results": "",
        "examples": "",
    }
    prompt = """
# 角色
你是高质量数据集说明文档审核专家。请评估文档的数据集构建过程完整性（0103）。

# 检查事项
1. 数据来源：说明数据来自何处，包括人工编写、公开数据、业务系统等来源。
2. 采集方法：说明数据如何采集、收集、生成或选取。
3. 加工处理流程：说明清洗、转换、去重、审核、质量控制等处理步骤。
4. 标注规范：说明标签定义、标注方式、标注人员或一致性要求。
5. 版本控制：说明版本号、发布日期、变更记录或版本管理方式。

# 判定规则
逐项寻找明确证据。同义词、近义表达、流程列表和表格均可作为证据，不要求出现固定标题或关键词。
只能依据输入文档判断，不得根据常识补全。仅出现字段名称但没有说明实际数据集情况，不算完整。
共5项；明确覆盖至少4项时score为1，否则为0。
reason必须简洁列出已覆盖事项及证据，以及缺失或说明不足的事项。

# 输出格式
只输出合法JSON，不要输出Markdown或其他文字：
{"score": 0, "reason": "covered: ...; missing: ..."}

# 待评估文档
"""
