from dingo.model.model import Model
from dingo.model.prompt.base import BasePrompt


@Model.prompt_register("IMAGE_RELEVANT", [], ['VLMImageRelevant'])
class PromptImageRelevant(BasePrompt):

    # Metadata for documentation generation
    _metric_info = {
        "category": "Multimodality Assessment Metrics",
        "metric_name": "PromptImageRelevant",
        "description": "Evaluates image consistency and relevance through comprehensive analysis of content, semantics, visual quality, and detail fidelity",
        "evaluation_results": ""
    }

    content = """你是一个专业的图像对比分析系统。请对比分析两张图片的一致性和相关性。

【分析步骤】
1. 第一张图片分析
   仔细观察并记录第一张图片的核心内容：
   - 主要对象（人物、物体、场景）
   - 视觉元素（颜色、构图、风格）
   - 关键细节（文字、标识、特征）
   - 语义信息（主题、意图、情境）

2. 第二张图片评估
   基于第一张图片，从以下维度评估第二张图片：
   - 内容一致性：主要对象和场景元素是否保持一致
   - 语义相关性：主题意图和信息传达是否相符
   - 视觉质量：图像清晰度、完整性、是否存在明显缺陷
   - 细节保真度：重要特征、比例、空间关系是否准确

3. 综合评分
   评分标准：
   - 分数1：图片整体一致且相关，无明显问题
   - 分数0：存在以下任一情况
     * 主要内容不一致或缺失
     * 语义偏离或不相关
     * 存在明显的质量缺陷
     * 关键细节错误或失真

【输出要求】
请进行逐步分析后，输出最终评分和简要原因。
输出格式必须为JSON：{"score": 评分, "reason": "原因说明"}
"""
