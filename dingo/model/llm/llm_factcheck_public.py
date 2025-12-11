from dataclasses import dataclass
from typing import Dict, List, Literal, Optional

from dingo.io import Data
from dingo.model import Model
from dingo.model.llm.base_openai import BaseOpenAI
from dingo.model.modelres import ModelRes
from dingo.model.prompt.prompt_factcheck import PromptFactCheck
from dingo.utils.exception import ExceedMaxTokens


@dataclass
class Evidence:
    """验证证据"""
    url: str
    snippet: str
    summary: str


@dataclass
class FactCheckResult:
    """单条声明的验证结果"""
    claim: str
    answer: Literal["true", "false", "unsure"]
    reasoning: str
    supporting_evidence: List[Evidence]


@Model.prompt_register(metric_type="QUALITY_BAD_FACTUALITY", group=["factuality"])
@Model.llm_register("LLMFactCheckPublic")
class LLMFactCheckPublic(BaseOpenAI):
    """公开事实性评估器 - 基于 GPT-5 System Card 的两阶段评估"""

    _metric_info = {
        "category": "SFT Data Assessment Metrics",
        "quality_dimension": "FACTUAL_CORRECTNESS",
        "metric_name": "LLMFactCheckPublic",
        "description": "Two-stage factuality evaluation pipeline from GPT-5",
        "paper_title": "GPT-5 System Card",
        "paper_url": "https://cdn.openai.com/pdf/8124a3ce-ab78-4f06-96eb-49ea29ffb52f/gpt5-system-card-aug7.pdf",
        "paper_authors": "OpenAI"
    }

    prompt = PromptFactCheck
    threshold = 0.8
    batch_size = 10  # 默认批处理大小
    web_enabled = True  # 默认启用网络搜索

    @classmethod
    def eval(cls, input_data: Data) -> ModelRes:
        """执行两阶段评估"""
        try:
            # 0. 初始化 client
            if cls.client is None:
                cls.create_client()

            # 1. 提取声明
            claims = cls._extract_claims(input_data.prompt, input_data.content)
            if not claims:
                return ModelRes(
                    score=0.0,
                    threshold=cls.threshold,
                    reason=["No factual claims found"],
                    raw_resp={"claims": [], "results": []}
                )

            # 2. 分批验证
            all_results = []
            for i in range(0, len(claims), cls.batch_size):
                batch = claims[i:i + cls.batch_size]
                results = cls._verify_claims(input_data.prompt, input_data.content, batch)
                all_results.extend(results)

            # 3. 计算指标
            metrics = cls._calculate_metrics(all_results)

            # 4. 设置评估结果
            result = ModelRes(
                score=metrics["factual_ratio"],
                threshold=cls.threshold,
                reason=[cls._format_reason(metrics)],
                raw_resp={
                    "claims": claims,
                    "results": all_results,
                    "metrics": metrics
                }
            )

            # 5. 根据分数设置状态
            if metrics["factual_ratio"] < cls.threshold:
                result.error_status = True
                result.type = "QUALITY_BAD_FACTUALITY"
                result.name = "FACTUALITY_CHECK_FAILED"
            else:
                result.type = "QUALITY_GOOD"
                result.name = "FACTUALITY_CHECK_PASSED"

            return result

        except Exception as e:
            return ModelRes(
                error_status=True,
                type="QUALITY_BAD_FACTUALITY",
                name="FACTUALITY_CHECK_ERROR",
                score=0.0,
                threshold=cls.threshold,
                reason=[f"Evaluation failed: {str(e)}"],
                raw_resp={"error": str(e)}
            )

    @classmethod
    def _extract_claims(cls, prompt: str, response: str) -> List[str]:
        """提取事实性声明"""
        messages = [
            {"role": "user", "content": (PromptFactCheck.CLAIM_LISTING +
                (PromptFactCheck.CLAIM_LISTING_NO_WEB if not cls.web_enabled else "")).format(
                prompt=prompt,
                response=response
            )}
        ]
        result = cls.send_messages(messages)
        try:
            claims = cls._parse_json_list(result)
            return [c for c in claims if c.strip()]  # 过滤空声明
        except Exception as e:
            raise ValueError(f"Failed to parse claims: {str(e)}")

    @classmethod
    def _verify_claims(cls,
                      prompt: str,
                      response: str,
                      claims: List[str]) -> List[FactCheckResult]:
        """验证一批声明"""
        messages = [
            {"role": "user", "content": (PromptFactCheck.FACT_CHECKING +
                (PromptFactCheck.FACT_CHECKING_NO_WEB if not cls.web_enabled else "")).format(
                prompt=prompt,
                response=response,
                claims=claims
            )}
        ]
        result = cls.send_messages(messages)
        try:
            return cls._parse_check_results(result)
        except Exception as e:
            raise ValueError(f"Failed to parse check results: {str(e)}")

    @classmethod
    def _calculate_metrics(cls, results: List[FactCheckResult]) -> Dict:
        """计算评估指标"""
        total = len(results)
        if total == 0:
            return {
                "factual_ratio": 0.0,
                "true_count": 0,
                "false_count": 0,
                "unsure_count": 0,
                "total_claims": 0
            }

        counts = {
            "true": sum(1 for r in results if r.answer == "true"),
            "false": sum(1 for r in results if r.answer == "false"),
            "unsure": sum(1 for r in results if r.answer == "unsure")
        }

        return {
            "factual_ratio": counts["true"] / total,
            "true_count": counts["true"],
            "false_count": counts["false"],
            "unsure_count": counts["unsure"],
            "total_claims": total
        }

    @classmethod
    def _format_reason(cls, metrics: Dict) -> str:
        """格式化评估原因"""
        return (
            f"Found {metrics['total_claims']} claims: "
            f"{metrics['true_count']} true, "
            f"{metrics['false_count']} false, "
            f"{metrics['unsure_count']} unsure. "
            f"Factual ratio: {metrics['factual_ratio']:.2%}"
        )

    @classmethod
    def _parse_json_list(cls, text: str) -> List[str]:
        """解析 JSON 列表"""
        import json
        try:
            # 提取 JSON 部分
            start = text.find("[")
            end = text.rfind("]") + 1
            if start == -1 or end == 0:
                raise ValueError("No JSON list found")
            json_str = text[start:end]
            return json.loads(json_str)
        except Exception as e:
            raise ValueError(f"Invalid JSON format: {str(e)}")

    @classmethod
    def _parse_check_results(cls, text: str) -> List[FactCheckResult]:
        """解析验证结果"""
        import json
        try:
            # 提取 JSON 部分
            start = text.find("[")
            end = text.rfind("]") + 1
            if start == -1 or end == 0:
                raise ValueError("No JSON results found")
            json_str = text[start:end]
            data = json.loads(json_str)

            results = []
            for item in data:
                # 处理 evidence，确保所有必需字段都存在
                evidence_list = []
                for e in item.get("supporting_evidence", []):
                    # 确保所有必需字段都存在，提供默认值
                    evidence = Evidence(
                        url=e.get("url", ""),
                        snippet=e.get("snippet", ""),  # 提供默认值避免缺失
                        summary=e.get("summary", "")
                    )
                    evidence_list.append(evidence)

                results.append(FactCheckResult(
                    claim=item.get("claim", ""),
                    answer=item.get("answer", "unsure"),  # 默认为 unsure
                    reasoning=item.get("reasoning", ""),
                    supporting_evidence=evidence_list
                ))
            return results
        except Exception as e:
            raise ValueError(f"Invalid results format: {str(e)}")
