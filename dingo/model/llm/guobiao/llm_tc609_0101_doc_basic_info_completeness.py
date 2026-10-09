from dingo.io.input import RequiredField
from dingo.model import Model
from dingo.model.llm.base_openai import BaseOpenAI


@Model.llm_register("LLM_TC609_0101_DocBasicInfoCompleteness")
class LLM_TC609_0101_DocBasicInfoCompleteness(BaseOpenAI):
    """Evaluate completeness of basic dataset information."""

    _required_fields = [RequiredField.CONTENT]
    _metric_info = {
        "category": "National Standard LLM Assessment Metrics",
        "metric_name": "LLM_TC609_0101_DocBasicInfoCompleteness",
        "description": (
            "Uses an LLM to assess dataset scale, format, file structure, "
            "access channel, and technical support in dataset documentation."
        ),
        "paper_title": "TC609 high-quality dataset quality evaluation specification",
        "paper_url": "",
        "paper_authors": "SAC/TC609",
        "evaluation_results": "",
        "examples": "",
    }
    prompt = """
# 角色
你是高质量数据集说明文档审核专家。请评估文档的基本信息完整性（0101）。

# 检查事项
1. 数据集规模：说明样本数量、记录数量、文件数量、存储规模等可核实的规模信息。
2. 格式规范：说明文件格式、编码、字段结构或解析方式。
3. 文件结构：说明目录、文件组成及其组织关系。
4. 访问渠道：说明数据集的获取、下载或访问方式。
5. 技术支持：说明问题反馈、维护渠道或技术支持方式。

# 判定规则
逐项寻找明确证据。同义词、近义表达、表格、目录树和代码示例均可作为证据，不要求出现固定标题或关键词。
只能依据输入文档判断，不得根据常识补全。仅出现字段名称但没有说明实际数据集情况，不算完整。
共5项；明确覆盖至少4项时score为1，否则为0。
reason必须简洁列出已覆盖事项及证据，以及缺失或说明不足的事项。

# 输出格式
只输出合法JSON，不要输出Markdown或其他文字：
{"score": 0, "reason": "covered: ...; missing: ..."}

# 待评估文档
"""
