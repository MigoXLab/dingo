"""
LLM Scout - Strategic Job Hunting Module

Analyzes industry reports and user profiles to generate targeted job hunting recommendations.

Features:
1. Natural language user profile parsing
2. Industry report analysis (company extraction, financial signals)
3. Person-job fit scoring algorithm with sub-scores
4. Search strategy generation
5. Interview style prediction
6. Grounding: All conclusions require source quotes
"""

import json
import re
from typing import Any, Dict, List, Tuple

from dingo.io.input import Data, RequiredField
from dingo.io.output.eval_detail import EvalDetail, QualityLabel
from dingo.model import Model
from dingo.model.llm.base_openai import BaseOpenAI
from dingo.utils import log
from dingo.utils.exception import ConvertJsonError

# Scoring weights for match calculation
SCORE_WEIGHTS = {
    "skill_match": 0.40,
    "risk_alignment": 0.20,
    "career_stage_fit": 0.15,
    "location_match": 0.10,
    "financial_health": 0.15
}

# Tier thresholds
TIER_THRESHOLDS = {
    "tier1": 0.75,
    "tier2": 0.50
}


@Model.llm_register("LLMScout")
class LLMScout(BaseOpenAI):
    """
    Strategic job hunting analysis using LLM.

    输入要求:
    - input_data.content: 行业报告文本
    - input_data.prompt: 用户画像 (自然语言或 JSON)
    - input_data.context: 个人简历文本 (可选, 用于技能提取提升匹配精度)

    Features:
    - Industry report analysis with company extraction
    - Financial signal classification (expansion/stable/contraction)
    - Person-job fit scoring with sub-scores
    - Evidence-based grounding (source quotes required)
    - Search strategy and interview prep generation
    """

    _metric_info = {
        "category": "Job Hunting Strategy Metrics",
        "metric_name": "LLMScout",
        "description": "Strategic job hunting analysis with industry report parsing and person-job matching",
        "paper_title": "N/A",
        "paper_url": "",
        "source_frameworks": "Dingo Scout Tools"
    }

    _required_fields = [RequiredField.CONTENT, RequiredField.PROMPT]
    threshold = 0.50  # Default threshold for recommended companies

    @classmethod
    def build_messages(cls, input_data: Data) -> List:
        """
        Build messages for scout analysis.
        """
        industry_report = input_data.content or ""
        user_profile = input_data.prompt or ""
        # Handle both branches: dev branch has context, main branch doesn't
        resume_text = getattr(input_data, 'context', None) or ""

        prompt_content = cls._build_prompt(industry_report, user_profile, resume_text)

        messages = [{"role": "user", "content": prompt_content}]
        return messages

    @classmethod
    def _build_prompt(cls, industry_report: str, user_profile: str, resume_text: str = "") -> str:
        """Build the scout analysis prompt."""
        system_prompt = cls._get_system_prompt()

        if resume_text:
            user_content = f"""{system_prompt}

### 行业报告:
{industry_report}

### 用户画像:
{user_profile}

### 个人简历 (用于技能提取，提升匹配精度):
{resume_text}

请分析并输出战略上下文卡片 (JSON 格式)。
注意：已提供简历，请从中提取技能列表用于 skill_match 评分计算。"""
        else:
            user_content = f"""{system_prompt}

### 行业报告:
{industry_report}

### 用户画像:
{user_profile}

请分析并输出战略上下文卡片 (JSON 格式)。"""

        return user_content

    @staticmethod
    def _get_system_prompt() -> str:
        """Get the system prompt for scout analysis."""
        return """你是 Dingo Scout，一位专业的求职战略分析师。
你的任务是从复杂的行业报告中提取对求职者有价值的信息，并生成精准的求职战略。

## 重要规则

1. **禁止使用任何 Emoji 符号**。输出必须是纯文本。
2. **只分析报告中明确提及的公司**，不要推测未提及的公司。
3. **所有财务判断必须附带原文引用 (Grounding)**。
4. 如果报告中只有"片汤话"而无具体数据，输出 confidence < 0.5。

---

## 1. 用户画像解析

| 维度 | 提取方法 | 默认值 |
|------|----------|--------|
| 学历 | "硕士/Master" -> Master | Bachelor |
| 专业 | "CS/计算机/软件" -> CS | CS |
| 经验年限 | "实习" -> 0-1年, "3年经验" -> 3年 | 0 |
| 技术栈 | 提取所有技术关键词 | [] |
| 风险偏好 | "大厂/稳定" -> conservative | moderate |
| 职业阶段 | "应届/23届" -> new_grad | new_grad |
| 地点偏好 | 提取城市名 | [] |

---

## 2. 财务信号分类

**Expansion**: ROE 上升、资金净流入、扩招信号
**Stable**: ROE 平稳、资金流平衡
**Contraction**: ROE 下降、资金流出、裁员
**Uncertain**: 存在矛盾信号
**Unknown**: 无具体财务数据

---

## 3. 人岗匹配逻辑

**Tier 1**: 技能匹配 >= 70%, 财务 expansion/stable, 置信度 >= 0.7
**Tier 2**: 技能匹配 50-70%, 或存在矛盾信号
**Not Recommended**: contraction, 技能匹配 < 50%, 置信度 < 0.5

---

## 4. 输出格式 (JSON)

```json
{
  "strategy_context": {
    "target_companies": [
      {
        "name": "公司名称",
        "financial_status": "expansion|stable|contraction|uncertain|unknown",
        "financial_evidence": {
          "source_quotes": ["原文引用1", "原文引用2"],
          "confidence": 0.0-1.0,
          "conflicting_signals": "矛盾说明或null"
        },
        "scoring_breakdown": {
          "skill_match": {"score": 0.0-1.0, "matched_skills": [], "missing_skills": [], "reasoning": ""},
          "risk_alignment": {"score": 0.0-1.0, "user_preference": "", "company_risk_level": "", "reasoning": ""},
          "career_stage_fit": {"score": 0.0-1.0, "user_stage": "", "company_fit": "", "reasoning": ""},
          "location_match": {"score": 0.0-1.0, "user_preference": [], "company_locations": [], "reasoning": ""},
          "financial_health": {"score": 0.0-1.0, "status": "", "reasoning": ""}
        },
        "match_reasoning": "为什么匹配",
        "hiring_trigger": "扩招原因",
        "search_keywords": ["关键词1", "关键词2"],
        "recommended_platforms": ["Boss直聘", "拉勾"],
        "interview_style": "面试风格",
        "interview_prep_tips": ["算法建议", "系统设计建议"],
        "salary_leverage": "薪资谈判筹码",
        "culture_fit": "文化匹配度",
        "timing_advice": "最佳投递时机"
      }
    ],
    "insufficient_data": [
      {"name": "公司名", "reason": "缺乏数据原因", "suggestion": "建议"}
    ],
    "not_recommended": [
      {"name": "公司名", "reason": "不推荐原因"}
    ],
    "meta": {
      "report_date": "日期",
      "analysis_confidence": 0.0-1.0,
      "user_profile_summary": "用户画像摘要"
    }
  }
}
```

---"""

    @classmethod
    def process_response(cls, response: str):
        """Process LLM response. Returns EvalDetail (dev) or ModelRes (main)."""
        log.info(f"Raw LLM response length: {len(response)} chars")

        # Extract think content and clean response
        response_think = cls._extract_think_content(response)
        response = cls._clean_response(response)

        try:
            response_json = json.loads(response)
        except json.JSONDecodeError:
            raise ConvertJsonError(f"Convert to JSON format failed: {response[:500]}")

        # Process and validate the result
        result_data = cls._process_scout_result(response_json)

        # Generate reason text
        reason = cls._generate_reason(result_data)

        # Add think content to reason if exists
        if response_think:
            reason += "\n\n[LLM Thinking]\n" + response_think

        # Calculate overall score based on top companies
        score = cls._calculate_overall_score(result_data)

        log.info(f"Scout analysis complete. Score: {score:.2f}, threshold: {cls.threshold:.2f}")

        # Build result
        result = EvalDetail(metric=cls.__name__)
        result.score = score
        result.reason = [reason]
        if score >= cls.threshold:
            result.status = False
            result.label = [QualityLabel.QUALITY_GOOD]
        else:
            result.status = True
            result.label = [f"QUALITY_BAD.{cls.__name__}"]
        # Store full response for downstream use
        result.strategy_context = result_data

        return result

    @staticmethod
    def _extract_think_content(response: str) -> str:
        """Extract <think> content from response (for reasoning models)."""
        if response.startswith("<think>"):
            think_content = re.search(r"<think>(.*?)</think>", response, flags=re.DOTALL)
            return think_content.group(1).strip() if think_content else ""
        return ""

    @staticmethod
    def _clean_response(response: str) -> str:
        """Clean response format, remove think tags and markdown code blocks."""
        response = re.sub(r"<think>.*?</think>", "", response, flags=re.DOTALL).strip()

        if response.startswith("```json"):
            response = response[7:]
        elif response.startswith("```"):
            response = response[3:]

        if response.endswith("```"):
            response = response[:-3]

        # Find JSON boundaries
        start = response.find('{')
        end = response.rfind('}')
        if start != -1 and end != -1:
            response = response[start:end + 1]

        return response.strip()

    @classmethod
    def _process_scout_result(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process and validate scout result, calculate scores."""
        context = data.get("strategy_context", data)

        # Ensure required fields exist
        if "target_companies" not in context:
            context["target_companies"] = []
        if "insufficient_data" not in context:
            context["insufficient_data"] = []
        if "not_recommended" not in context:
            context["not_recommended"] = []
        if "meta" not in context:
            context["meta"] = {}

        # Calculate scores for each company
        for company in context.get("target_companies", []):
            scoring = company.get("scoring_breakdown", {})
            if scoring:
                match_score, tier = cls._calculate_match_score(scoring)
                company["match_score"] = match_score
                company["tier"] = tier
            else:
                if company.get("match_score") is None:
                    company["match_score"] = 0.5
                if company.get("tier") is None:
                    company["tier"] = "Tier 2"

            # Apply defaults for optional fields
            company.setdefault("search_keywords", [])
            company.setdefault("recommended_platforms", ["Boss直聘"])
            company.setdefault("interview_style", "待确认")
            company.setdefault("interview_prep_tips", [])
            company.setdefault("financial_evidence", {
                "source_quotes": [],
                "confidence": 0.5,
                "conflicting_signals": None
            })

        # Filter by confidence
        qualified, insufficient, not_recommended = cls._filter_by_confidence(
            context.get("target_companies", [])
        )

        # Merge with existing not_recommended
        all_not_recommended = not_recommended + context.get("not_recommended", [])

        # Sort by score
        qualified.sort(key=lambda x: x.get("match_score", 0), reverse=True)

        return {
            "target_companies": qualified,
            "insufficient_data": insufficient + context.get("insufficient_data", []),
            "not_recommended": all_not_recommended,
            "meta": context.get("meta", {})
        }

    @classmethod
    def _calculate_match_score(cls, scoring_breakdown: Dict) -> Tuple[float, str]:
        """Calculate weighted match score from sub-scores."""
        total_score = 0.0
        total_weight = 0.0

        for dimension, weight in SCORE_WEIGHTS.items():
            if dimension in scoring_breakdown:
                sub_score = scoring_breakdown[dimension].get("score", 0.0)
                if sub_score is not None:
                    total_score += sub_score * weight
                    total_weight += weight

        if total_weight > 0:
            match_score = round(total_score / total_weight, 2)
        else:
            match_score = 0.5

        # Determine tier
        if match_score >= TIER_THRESHOLDS["tier1"]:
            tier = "Tier 1"
        elif match_score >= TIER_THRESHOLDS["tier2"]:
            tier = "Tier 2"
        else:
            tier = "Not Recommended"

        return match_score, tier

    @classmethod
    def _filter_by_confidence(cls, companies: List[Dict]) -> Tuple[List, List, List]:
        """Filter companies by financial evidence confidence."""
        qualified = []
        insufficient = []
        not_recommended = []

        for company in companies:
            evidence = company.get("financial_evidence", {})
            confidence = evidence.get("confidence", 0.0)
            status = company.get("financial_status", "unknown")

            # Contraction: directly exclude
            if status == "contraction":
                quotes = evidence.get("source_quotes", ["无"])
                quote_preview = quotes[0][:50] if quotes else "无"
                not_recommended.append({
                    "name": company.get("name", "Unknown"),
                    "reason": f"财务收缩期 (证据: {quote_preview}...)"
                })
                continue

            # Low confidence: insufficient data
            if confidence < 0.5:
                insufficient.append({
                    "name": company.get("name", "Unknown"),
                    "reason": "报告中缺乏该公司的具体财务数据",
                    "available_info": evidence.get("source_quotes", []),
                    "suggestion": "建议自行搜索该公司最新财报或招聘动态"
                })
                continue

            # Conflicting signals: downgrade to Tier 2
            if evidence.get("conflicting_signals"):
                company["tier"] = "Tier 2"
                company["risk_warning"] = evidence["conflicting_signals"]

            qualified.append(company)

        return qualified, insufficient, not_recommended

    @classmethod
    def _calculate_overall_score(cls, result_data: Dict) -> float:
        """Calculate overall score based on analysis results."""
        companies = result_data.get("target_companies", [])
        if not companies:
            return 0.0

        # Use the highest match score as overall score
        scores = [c.get("match_score", 0) for c in companies]
        return max(scores) if scores else 0.0

    @classmethod
    def _generate_reason(cls, result_data: Dict) -> str:
        """Generate human-readable reason for the analysis."""
        lines = ["=== Dingo Scout 战略分析报告 ===", ""]

        target_companies = result_data.get("target_companies", [])
        insufficient_data = result_data.get("insufficient_data", [])
        not_recommended = result_data.get("not_recommended", [])
        meta = result_data.get("meta", {})

        # Tier 1 & Tier 2 companies
        tier1 = [c for c in target_companies if c.get("tier") == "Tier 1"]
        tier2 = [c for c in target_companies if c.get("tier") == "Tier 2"]

        if tier1:
            lines.append("[Tier 1] 核心目标公司:")
            for c in tier1:
                score_pct = int(c.get('match_score', 0) * 100)
                lines.append(f"  - {c.get('name', 'Unknown')} (匹配度: {score_pct}%)")
            lines.append("")

        if tier2:
            lines.append("[Tier 2] 潜在机会:")
            for c in tier2:
                score_pct = int(c.get('match_score', 0) * 100)
                lines.append(f"  - {c.get('name', 'Unknown')} (匹配度: {score_pct}%)")
            lines.append("")

        if insufficient_data:
            lines.append("[数据不足] 建议自行搜索:")
            for item in insufficient_data:
                lines.append(f"  - {item.get('name', 'Unknown')}: {item.get('reason', '')}")
            lines.append("")

        if not_recommended:
            lines.append("[不推荐]:")
            for item in not_recommended:
                lines.append(f"  - {item.get('name', 'Unknown')}: {item.get('reason', '')}")
            lines.append("")

        # Meta info
        if meta:
            confidence_pct = int(meta.get('analysis_confidence', 0) * 100)
            lines.append(f"分析置信度: {confidence_pct}%")
            if meta.get('user_profile_summary'):
                lines.append(f"用户画像: {meta.get('user_profile_summary')}")

        return "\n".join(lines)

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        """Override eval to validate inputs."""
        # Validate that content (industry report) is provided
        if not input_data.content:
            result = EvalDetail(metric=cls.__name__)
            result.status = True
            result.label = [f"QUALITY_BAD.{cls.__name__}"]
            result.reason = ["行业报告 (content) 是必需的但未提供"]
            return result

        # Validate that prompt (user profile) is provided
        if not input_data.prompt:
            result = EvalDetail(metric=cls.__name__)
            result.status = True
            result.label = [f"QUALITY_BAD.{cls.__name__}"]
            result.reason = ["用户画像 (prompt) 是必需的但未提供"]
            return result

        # Call parent eval method
        return super().eval(input_data)
