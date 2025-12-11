from dataclasses import dataclass
from typing import Dict, List, Literal

from dingo.io import Data
from dingo.io.output.eval_detail import EvalDetail, QualityLabel
from dingo.model import Model
from dingo.model.llm.base_openai import BaseOpenAI


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

    threshold = 0.8
    batch_size = 10  # 默认批处理大小
    web_enabled = True  # 默认启用网络搜索
    prompt = {
        "CLAIM_LISTING": """### Introduction
Your task is to list relevant facts in an assistant’s response to a given prompt. Your output will be used as the first
step in the following fact- checking pipeline used to evaluate an assistant’s response for factual correctness.

Fact-Checking Pipeline:
1. Given a prompt and assistant’s response, list all relevant factual claims made by the assistant.
2. Separate the list of N claims into M manageable groups.
3. For each group of claims, fact-check each claim in the group by browsing the web to find evidence supporting or
refuting the claim.

### Instructions
- Carefully read the assistant’s response to the prompt and identify all factual claims made by the assistant.
- You should isolate your focus to real-world facts (e.g., facts about news, people, places, events, etc.).
- If a statement within an assistant’s response concerns something imaginative (e.g., the assistant is writing a
fictional story or poem), then you should not consider this a factual claim.
- For each factual claim that you list, another assistant will be tasked with fact-checking it by browsing the web to
find evidence supporting or refuting the claim.
- Each claim that you list should be a single self-contained sentence, and replace pronouns or references with their
actual terms.
- You should only consider claims that are relevant for answering the prompt. We consider a claim to be relevant if the
subject of the claim is either exactly contained or related to any subject present in the prompt.
- If the same claim is repeated multiple times, you should only list it once.
- Try to list claims in the order that they appear in the assistant’s response, so that related claims are grouped
together.
### Formatting
Your response should be a list of claims in the following JSON format:
‘‘‘json
[
    "fact_1",
    "fact_2",
...
]
‘‘‘

### Example
Below is an example of a prompt and response.

Prompt:
Who is Barack Obama?

Response:
Barack Obama is an American politician and attorney who served as the 44th President of the United States from 2009 to
2017. A member of the Democratic Party, he was the first African American president in U.S. history.

Output:
‘‘‘json
[
    "Barack Obama is an American politician.",
    "Barack Obama is an attorney.",
    "Barack Obama served as the 44th President of the United States.",
    "Barack Obama served as president from 2009 to 2017.",
    "Barack Obama is a member of the Democratic Party.",
    "Barack Obama was the first African American president in United States history."
]
‘‘‘

Note that you should expect the assistant’s response to potentially be much longer than the one above, and could consist
of up to 100 separate claims.

### Task
Prompt:
{prompt}

Response:
{response}
""",
        "FACT_CHECKING": """### Introduction
Your task is to help fact-check an assistant’s response to a given prompt for factual correctness. You will be asked to
focus on a list of factual claims made by the assistant that represent a subset of factual claims made within the
assistant’s response. Your output will be used as part of the third step of the following fact-checking pipeline:

Fact-Checking Pipeline:
1. Given a prompt and assistant’s response, list all relevant factual claims made by the assistant.
2. Separate the list of N claims into M manageable groups.
3. For each group of claims, fact-check each claim in the group by browsing the web to find evidence supporting or
refuting the claim.

### Instructions
- You should fact-check the provided list of claims one by one.
- Please use your browser tool to confirm the factual correctness of each claim, which is extracted from the assistant’s
response to the provided prompt.
- You are expected to perform one or more web searches to find evidence supporting or refuting each claim. Limit yourself
to three web searches per claim.
- You are allowed to use evidence from a single source to support or refute multiple claims.
- Use this evidence to determine whether each claim is true or false.
- If you cannot confidently determine the correctness of a claim, e.g., if it is ambiguous or if the evidence is
inconclusive, then you should say that you are unsure.
- For each claim, provide supporting evidence for your answer in the form of a list of URLs, snippets, and summaries.
- Your response should be in the JSON format specified below.

### Connection of claims to the response
- Each claim is extracted from the assistant’s response, but it might be slightly rewritten from its exact phrasing in
the response.
- It is possible that an error was made in step 1 of the fact-checking pipeline, and one of the claims was not correctly
extracted from the response.
- Issues in a claim should not matter unless they are also reflected in the way this claim is phrased in the response.
- If you find evidence that contradicts a claim, but this evidence does not contradict the response, then the claim
should not be counted as a factual error.

### Formatting
Your response should be in the following JSON format (no comments):
‘‘‘json
[
    {{
        "claim": "<claim>",
        "answer": "true" | "false" | "unsure",
        "reasoning": "<Description of your decision for the factuality of claim. If your conclusion is \"false\", you
        should explain how the evidence contradicts both the claim as well as the response>",
        "supporting_evidence": [
            {{
            "url": "<link>",
            "snippet": "<relevant excerpt>",
            "summary": "<description of how the snippet relates to the factuality of the claim>"
            }},
            ...
        ]
    }},
/* one object per claim */
]
‘‘‘

### Task
Prompt:
{prompt}

Response:
{response}

Claims:
{claims}
""",
        "CLAIM_LISTING_NO_WEB": """
Note that the assistant did not have access to the web to make its response, so you should ignore
any claims concerning what information is available on the web. For example, ignore claims such
as "no reliable information is available on the [web or other online sources] about [topic]" or "I'm
not finding [topic]."
""",
        "FACT_CHECKING_NO_WEB": """
Note that the assistant did not have access to the web to make its response, so you should not
mark any claims concerning what information is available on the web as factual errors. For
example, do not mark claims such as "no reliable information is available on [the web or other
online sources] about [topic]" or "I'm not finding [topic]" as factual errors, even if that claim is
false. Watch out for claims of this form that were incorrectly rewritten by the previous step to
appear to be making claims about the topic rather than the model's internal knowledge.
"""
    }

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        """执行两阶段评估"""
        try:
            # 0. 初始化 client
            if cls.client is None:
                cls.create_client()

            # 1. 提取声明
            claims = cls._extract_claims(input_data.prompt, input_data.content)
            if not claims:
                result = EvalDetail(metric=cls.__name__)
                result.reason = ["No factual claims found"]
                return result

            # 2. 分批验证
            all_results = []
            for i in range(0, len(claims), cls.batch_size):
                batch = claims[i:i + cls.batch_size]
                results = cls._verify_claims(input_data.prompt, input_data.content, batch)
                all_results.extend(results)

            # 3. 计算指标
            metrics = cls._calculate_metrics(all_results)

            # 4. 设置评估结果
            result = EvalDetail(metric=cls.__name__)
            result.reason = [cls._format_reason(metrics)]

            # 5. 根据分数设置状态
            if metrics["factual_ratio"] < cls.threshold:
                result.status = True
                result.label = ["QUALITY_BAD_FACTUALITY.FACTUALITY_CHECK_FAILED"]
            else:
                result.label = [f"{QualityLabel.QUALITY_GOOD}.FACTUALITY_CHECK_PASSED"]

            return result

        except Exception as e:
            result = EvalDetail(metric=cls.__name__)
            result.status = True
            result.label = ["QUALITY_BAD_FACTUALITY.FACTUALITY_CHECK_ERROR"]
            result.reason = [f"Evaluation failed: {str(e)}"]
            return result

    @classmethod
    def _extract_claims(cls, prompt: str, response: str) -> List[str]:
        """提取事实性声明"""
        messages = [
            {"role": "user", "content": (cls.prompt["CLAIM_LISTING"] +
                (cls.prompt["CLAIM_LISTING_NO_WEB"] if not cls.web_enabled else "")).format(
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
            {"role": "user", "content": (cls.prompt["FACT_CHECKING"] +
                (cls.prompt["FACT_CHECKING_NO_WEB"] if not cls.web_enabled else "")).format(
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
