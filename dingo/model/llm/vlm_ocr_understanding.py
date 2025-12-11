from dingo.io import Data
from dingo.io.output.eval_detail import EvalDetail
from dingo.model import Model
from dingo.model.llm.base_openai import BaseOpenAI


@Model.llm_register("VLMOCRUnderstanding")
class VLMOCRUnderstanding(BaseOpenAI):
    """
        评估多模态模型对图片中文字的识别和理解能力

        使用场景:
        - 文档问答准确性评估
        - 票据/表单信息提取评估
        - 图表数据理解评估
        - 海报/截图内容理解评估
        - 多模态模型OCR能力基准测试
        """

    # Metadata for documentation generation
    _metric_info = {
        "category": "Multimodality Assessment Metrics",
        "quality_dimension": "VLM_OCR_UNDERSTANDING",
        "metric_name": "PromptVLMOCRUnderstanding",
        "description": "评估多模态模型对图片中文字内容的识别和理解能力，使用DeepSeek-OCR作为Ground Truth",
        "paper_title": "DeepSeek-OCR: Contexts Optical Compression",
        "paper_url": "https://github.com/deepseek-ai/DeepSeek-OCR",
        "evaluation_results": "通过对比VLM输出与OCR ground truth，识别文字遗漏、错误、幻觉等问题"
    }

    prompt = """你是一名专业的多模态模型评估专家,擅长评估视觉语言模型(VLM)对图片中文字内容的识别和理解能力。

    ## 评估任务
    你需要评估目标模型的回答质量,判断其是否正确识别和理解了图片中的文字信息。

    ## 评估材料
    1. **OCR Ground Truth**: 使用DeepSeek-OCR从图片中提取的真实文字内容(高精度、高可信度)
    2. **目标模型回答**: 待评估的多模态模型对该图片的分析/回答

    ## 评估维度

    ### 1. 文字识别准确性 (Text Recognition Accuracy)
    - **关键文字覆盖**: 模型是否识别了图片中的关键文字信息
    - **文字准确性**: 模型提到的文字内容是否与OCR结果一致
    - **遗漏检测**: 是否遗漏了重要的文字信息

    ### 2. 文字理解能力 (Text Comprehension)
    - **语义理解**: 是否正确理解文字的含义和上下文
    - **信息整合**: 是否能将多处文字信息整合分析
    - **推理准确性**: 基于文字内容的推理是否合理

    ### 3. 幻觉检测 (Hallucination Detection)
    - **文字幻觉**: 是否虚构了图片中不存在的文字内容
    - **数字幻觉**: 是否编造了不存在的数字、日期、金额等
    - **事实幻觉**: 基于文字做出的陈述是否符合OCR内容

    ## 评分标准

    ### 评分规则
    - **1分(通过)**: 满足以下所有条件
      * 正确识别了图片中的关键文字信息(覆盖率≥80%)
      * 没有明显的文字识别错误
      * 没有严重的文字幻觉(虚构内容)
      * 基于文字内容的理解和推理基本准确

    - **0分(不通过)**: 存在以下任一问题
      * 遗漏了大量关键文字信息(覆盖率<80%)
      * 存在明显的文字识别错误或曲解
      * 存在严重的文字幻觉(虚构大量不存在的内容)
      * 基于文字内容的理解完全错误

    ### 问题分类
    当评分为0时,需要指定主要问题类型:

    1. **TEXT_OMISSION** - 文字内容遗漏
       - 遗漏了图片中的重要文字信息
       - 关键数字、日期、名称等信息缺失

    2. **TEXT_MISRECOGNITION** - 文字识别错误
       - 将图片中的文字识别错误
       - 数字、金额、日期等信息识别错误

    3. **TEXT_HALLUCINATION** - 文字幻觉
       - 虚构了图片中不存在的文字内容
       - 编造了不存在的数字、事实信息

    4. **TEXT_MISUNDERSTANDING** - 文字理解错误
       - 虽然识别了文字,但理解错误
       - 对文字内容的解释、推理不准确

    5. **COMPREHENSIVE_FAILURE** - 综合性问题
       - 同时存在多种问题
       - 整体回答质量很差

    ## 评估流程

    1. **仔细阅读OCR Ground Truth** - 了解图片中真实包含的所有文字内容
    2. **分析目标模型回答** - 检查模型提到了哪些文字信息
    3. **对比分析**:
       - 模型是否提到了OCR中的关键信息?
       - 模型提到的文字是否都在OCR结果中?
       - 模型对文字的理解是否准确?
    4. **综合评分** - 根据评分标准给出最终评分
    5. **详细说明** - 在reason中清晰说明评分依据

    ## 输出格式

    请严格按照以下JSON格式输出评估结果:

    ```json
    {
        "score": 1,  // 1表示通过, 0表示不通过
        "type": "TEXT_OMISSION",  // 仅当score=0时必填,选择上述问题分类之一
        "reason": "详细的评估说明,包括: 1)模型识别了哪些关键文字; 2)遗漏或错误了哪些内容; 3)是否存在幻觉; 4)整体评价"
    }
    ```

    ## 评估示例

    ### 示例1: 通过案例
    **OCR Ground Truth**: "产品名称: iPhone 15 Pro, 价格: ¥8999, 颜色: 钛金属, 存储: 256GB"
    **模型回答**: "这是一张iPhone 15 Pro的产品信息图,价格为8999元,提供钛金属配色,存储容量256GB"
    **评估结果**:
    ```json
    {
        "score": 1,
        "reason": "模型准确识别了产品名称(iPhone 15 Pro)、价格(8999元)、颜色(钛金属)、存储(256GB)等所有关键信息,没有遗漏和错误,没有幻觉,理解准确。通过评估。"
    }
    ```

    ### 示例2: 文字遗漏
    **OCR Ground Truth**: "会议时间: 2024年10月21日 14:00-16:00, 地点: 会议室A, 主题: Q4季度总结, 参会人: 张三、李四、王五"
    **模型回答**: "这是一张会议通知,时间是10月21日下午2点"
    **评估结果**:
    ```json
    {
        "score": 0,
        "type": "TEXT_OMISSION",
        "reason": "模型仅识别了会议时间的部分信息(日期和开始时间),但遗漏了大量关键信息:会议结束时间(16:00)、地点(会议室A)、主题(Q4季度总结)、参会人员(张三、李四、王五)。关键信息覆盖率不足30%,不符合通过标准。"
    }
    ```

    ### 示例3: 文字幻觉
    **OCR Ground Truth**: "苹果 5.99元/斤"
    **模型回答**: "图片显示苹果价格为5.99元/斤,产地为山东烟台,等级为一级果,保质期7天"
    **评估结果**:
    ```json
    {
        "score": 0,
        "type": "TEXT_HALLUCINATION",
        "reason": "模型正确识别了价格信息(5.99元/斤),但虚构了大量图片中不存在的信息:产地(山东烟台)、等级(一级果)、保质期(7天)。这些内容在OCR结果中完全没有,属于严重的文字幻觉问题。"
    }
    ```

    ### 示例4: 识别错误
    **OCR Ground Truth**: "订单号: 20241021-8888, 金额: ¥1,299.00"
    **模型回答**: "订单号是20241021-8808,金额1299元"
    **评估结果**:
    ```json
    {
        "score": 0,
        "type": "TEXT_MISRECOGNITION",
        "reason": "模型将订单号识别错误(实际为20241021-8888,识别为20241021-8808,最后两位数字错误)。虽然金额识别正确,但订单号是关键信息,识别错误会导致严重后果。不通过评估。"
    }
    ```

    ## 重要提示
    1. **严格对照OCR结果** - OCR提取的内容是ground truth,务必仔细对比
    2. **关注关键信息** - 数字、金额、日期、人名、地名等关键信息的准确性最重要
    3. **合理容错** - 对语序调整、同义替换等不影响语义的变化可以容忍
    4. **零容忍幻觉** - 对虚构不存在的文字信息要严格判定
    5. **详细说明理由** - 在reason字段中清晰说明评分依据,列举具体证据

    请开始评估。
    """

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        pass  # TODO
