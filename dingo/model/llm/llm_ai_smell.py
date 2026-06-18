"""
AI Smell Detector for Requirement Documents (需求文档 AI 味检测器)

Detects AI-generated writing patterns in requirement documents across 5 dimensions:
- 正确的废话指数 (Correct Nonsense Index)
- 无限镜像感 (Infinite Mirror Index)
- 彩虹屁密度 (Rainbow Fart Density)
- 细节真空度 (Detail Vacuum Index)
- 形容词暴力指数 (Adjective Violence Index)
"""

import json

from dingo.io.input import Data, RequiredField
from dingo.io.output.eval_detail import EvalDetail
from dingo.model import Model
from dingo.model.llm.base_openai import BaseOpenAI
from dingo.utils import log
from dingo.utils.exception import ConvertJsonError


@Model.llm_register("LLMAISmell")
class LLMAISmell(BaseOpenAI):
    """
    AI Smell Detector for requirement documents.

    Evaluates 5 dimensions of AI-generated writing patterns:
    1. 正确的废话指数 - Hollow truisms ("In today's society...", "With the rapid development of...")
    2. 无限镜像感     - Repetitive emphasis of the same point in different words
    3. 彩虹屁密度     - Excessive praise, inflated importance claims
    4. 细节真空度     - Sounds complete but lacks any actionable specifics
    5. 形容词暴力指数  - Buzzword overuse (高效/赋能/闭环/生态/颗粒度...)

    Each dimension is scored 0-10. Overall AI smell score is the weighted average.
    """

    _metric_info = {
        "category": "Document Quality Assessment Metrics",
        "metric_name": "LLMAISmell",
        "description": "Detects AI-generated writing patterns in requirement documents across 5 dimensions: hollow truisms, repetition, rainbow farts, detail vacuum, and adjective violence",
        "examples": "examples/llm_and_rule/llm_local.py",
        "evaluation_results": "",
    }

    _required_fields = [RequiredField.CONTENT]

    # Score threshold above which a document is flagged as AI-smelling
    threshold = 6

    prompt = """
# 角色
你是一位资深需求评审专家，专门识别需求文档中的 AI 代写痕迹。

# 任务
分析下面的文档，从 5 个维度评估其"AI 味"，每个维度打分 0-10：

## 评估维度

### 1. 💊 正确的废话指数（0-10）
**定义**：用正确但毫无信息量的话填充文档，听起来很有道理但什么都没说。
**典型表现**：
- "在当今社会……"、"随着技术的不断发展……"
- "这对用户体验至关重要"（但没有说为什么或怎么做）
- "我们需要确保系统的稳定性和可靠性"（没有具体指标）
- 每段开头都在重述背景

**打分标准**：
- 0-2：文档直接切入主题，陈述均有实质内容
- 3-5：有少量套话但不影响整体
- 6-8：大量空洞表述，信息密度低
- 9-10：几乎全是废话，读完不知道要做什么

### 2. 🪞 无限镜像感（0-10）
**定义**：同一个意思用不同的话反复说，制造"内容丰富"的假象。
**典型表现**：
- 同一个功能点在不同章节反复描述
- "提升用户体验" → "优化用户感受" → "改善用户满意度"（三句话说同一件事）
- 结论和摘要和正文高度重复

**打分标准**：
- 0-2：每句话都有新信息
- 3-5：有轻微重复但可接受
- 6-8：明显感觉在凑字数
- 9-10：镜中镜，绕来绕去

### 3. 🌈 彩虹屁密度（0-10）
**定义**：过度拔高重要性、夸大影响、给自己项目过度背书。
**典型表现**：
- "这将彻底改变……"、"革命性的……"、"行业领先的……"
- "大幅提升"但没有数据
- "用户迫切需要"但没有调研依据
- 每个功能都是"核心"、"关键"、"重要"

**打分标准**：
- 0-2：表述客观，有数据支撑
- 3-5：略有夸张但在合理范围
- 6-8：随处可见夸大词汇
- 9-10：每句话都在吹，读起来像广告

### 4. 🧩 细节真空度（0-10）
**定义**：文档结构完整、格式规范，但缺乏任何可落地的具体信息。
**典型表现**：
- "系统应支持多种支付方式"（哪些方式？）
- "性能要满足用户需求"（什么性能？什么需求？）
- "界面设计应符合用户习惯"（谁的习惯？什么标准？）
- 没有数字、没有边界条件、没有异常处理

**打分标准**：
- 0-2：有具体的数字、接口、用例、边界条件
- 3-5：部分模糊但核心功能有描述
- 6-8：大量"应该"、"需要"但没有"怎么做"
- 9-10：读完完全不知道要开发什么

### 5. ✨ 形容词暴力指数（0-10）
**定义**：大量堆叠科技/管理类buzzword，用词汇密度掩盖内容空洞。
**高危词汇**：高效、赋能、闭环、生态、颗粒度、抓手、落地、对齐、拉通、赛道、底层逻辑、顶层设计、数字化转型、智能化、一体化、全链路、沉淀、复用、标准化、降本增效、价值最大化
**打分标准**：
- 0-2：用词精准朴素，术语有明确定义
- 3-5：偶有流行词但不影响理解
- 6-8：buzzword 密集，读起来像PPT
- 9-10：去掉这些词文档就空了

---

## 综合 AI 味总分（0-10）
基于以上 5 个维度的加权综合评估。

**权重参考**：
- 细节真空度（0.3）：最能区分 AI 和人写的
- 正确的废话指数（0.25）
- 形容词暴力指数（0.2）
- 无限镜像感（0.15）
- 彩虹屁密度（0.1）

---

## 输出格式

请严格按照以下 JSON 格式输出，不要输出任何其他内容：

```json
{
  "total_score": <综合AI味总分 0-10>,
  "dimensions": {
    "correct_nonsense": <正确的废话指数 0-10>,
    "infinite_mirror": <无限镜像感 0-10>,
    "rainbow_fart": <彩虹屁密度 0-10>,
    "detail_vacuum": <细节真空度 0-10>,
    "adjective_violence": <形容词暴力指数 0-10>
  },
  "evidence": {
    "correct_nonsense": "<最典型的1-2个例子，直接引用原文>",
    "infinite_mirror": "<最典型的1-2个例子，直接引用原文>",
    "rainbow_fart": "<最典型的1-2个例子，直接引用原文>",
    "detail_vacuum": "<最典型的1-2个例子，直接引用原文>",
    "adjective_violence": "<最典型的1-2个例子，直接引用原文>"
  },
  "verdict": "<一句话总结，不超过50字>"
}
```

---

## 待评估文档：

"""

    @classmethod
    def process_response(cls, response: str) -> EvalDetail:
        """
        Process LLM response and convert to EvalDetail.
        """
        # Strip leading/trailing whitespace first, then remove markdown code blocks
        response = response.strip()
        if response.startswith("```json"):
            response = response[7:]
        elif response.startswith("```"):
            response = response[3:]
        if response.endswith("```"):
            response = response[:-3]
        response = response.strip()

        try:
            data = json.loads(response)
            if not isinstance(data, dict):
                raise ConvertJsonError(
                    f"Parsed JSON is not a dictionary: {type(data)}"
                )
        except json.JSONDecodeError:
            raise ConvertJsonError(f"Failed to parse AI smell response as JSON: {response[:200]}")

        try:
            total_score = float(data.get("total_score", 0))
        except (ValueError, TypeError):
            total_score = 0.0
        dimensions = data.get("dimensions") or {}
        evidence = data.get("evidence") or {}
        verdict = str(data.get("verdict") or "")

        # Build human-readable reason
        dim_labels = {
            "correct_nonsense": "💊 正确的废话指数",
            "infinite_mirror": "🪞 无限镜像感",
            "rainbow_fart": "🌈 彩虹屁密度",
            "detail_vacuum": "🧩 细节真空度",
            "adjective_violence": "✨ 形容词暴力指数",
        }

        reason_lines = [f"🤖 AI味总分：{int(total_score)}/10"]
        reason_lines.append("")
        for key, label in dim_labels.items():
            raw_score = dimensions.get(key, 0)
            try:
                score = float(raw_score)
            except (ValueError, TypeError):
                score = 0.0
            example = evidence.get(key, "")
            bar = cls._score_bar(round(score))
            reason_lines.append(f"{label}：{int(score)}/10 {bar}")
            if example and score >= 5:
                reason_lines.append(f"  └ 例：{example}")
        reason_lines.append("")
        reason_lines.append(f"📝 {verdict}")

        is_ai_smell = total_score >= cls.threshold

        result = EvalDetail(
            metric=cls.__name__,
            status=is_ai_smell,
            score=round(total_score / 10, 2),  # normalize to 0-1 for consistency
            label=["AI_SMELL_DETECTED"] if is_ai_smell else ["AI_SMELL_CLEAN"],
            reason=["\n".join(reason_lines)],
        )

        return result

    @classmethod
    def _score_bar(cls, score: int, width: int = 10) -> str:
        """Generate a simple ASCII progress bar for a 0-10 score."""
        filled = max(0, min(width, int(round(score))))
        empty = width - filled
        return f"[{'█' * filled}{'░' * empty}]"
