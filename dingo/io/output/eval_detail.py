from typing import Optional

from pydantic import BaseModel


class QualityLabel:
    """质量标签常量类"""
    QUALITY_GOOD = "QUALITY_GOOD"  # Indicates pass the quality check
    QUALITY_BAD_PREFIX = "QUALITY_BAD_"  # Indicates not pass the quality check
    REVIEW_EXECUTION_ERROR_PREFIX = "REVIEW_EXECUTION_ERROR."  # 评审执行失败（基础设施错误），非质量问题


class TokenUsage(BaseModel):
    """Token usage returned by an LLM provider for one evaluator call."""

    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    reasoning_tokens: Optional[int] = None
    cached_tokens: Optional[int] = None
    model: Optional[str] = None
    # provider: Optional[str] = None
    calls: int = 1
    source: str = "provider"


class EvalDetail(BaseModel):
    metric: str
    status: bool = False

    score: Optional[float] = None
    label: Optional[list[str]] = None
    reason: Optional[list] = None
    usage: Optional[TokenUsage] = None

    # 评审引擎判定契约（spec §4.2/§7.3）。旧评估器不设时全部回退，行为不变。
    verdict: Optional[str] = None          # "pass" | "warning" | "issue"
    applicable: bool = True                # False = N/A，从聚合分母剔除（spec §15.2）
    # 为什么不适用。前两种在讲这次运行——判官读过证据仍判不了（declined），
    # 或这类运行上本就不适用（structural）；第三种只讲评测器自己挂了
    # （execution_error）。三者此前产生完全相同的 EvalDetail，下游只能靠一张
    # evaluator 名单去猜，而做出决定的地方才知道答案。
    not_applicable_kind: Optional[str] = None  # "declined" | "structural" | "execution_error"
    # 同一事实的机器可读形式：reason 是英文散文，界面要的是能翻译的代号。
    # 下游曾按 evaluator 名字维护 name→code 表反推，漏一条就是一句英文躺在
    # 整页中文里。未设时下游按原样显示 reason，行为不变。
    not_applicable_code: Optional[str] = None
    rule_id: Optional[str] = None          # decision-table 条款（Task 3）
    rubric_version: Optional[str] = None

    @property
    def effective_verdict(self) -> str:
        if self.verdict is not None:
            return self.verdict
        if not self.applicable:
            return "n/a"
        return "issue" if self.status else "pass"
