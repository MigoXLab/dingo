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
    # 为什么不适用：evaluator 读过证据后判不了（"declined"），还是它在这类
    # 运行上根本不适用（"structural"）。两者产生的 EvalDetail 此前完全相同，
    # 下游只能靠一张 evaluator 名单去猜是哪一种——名单漏一个，一条本来干净
    # 的运行就会被当成"有维度判不了"而被压分。做出决定的地方才知道答案。
    # 第三种："execution_error" —— evaluator 自己挂了（重试耗尽后走到 eval() 的
    # 兜底分支）。它同样以 applicable=False 记录，于是下游把"评测器坏了"读成了
    # "这项检查不适用于你的运行"——恰好是本字段要区分的两件事里最不该混的一件：
    # 前两种说的是这次运行，这一种只说评测器自己。
    not_applicable_kind: Optional[str] = None  # "declined" | "structural" | "execution_error"
    # 同一个事实的机器可读形式。reason 是英文散文，界面要的是能翻译的代号，
    # 于是下游按 evaluator 名字维护了一张 name→code 表去反推——和上面那个字段
    # 出现前靠名单猜"哪种不适用"是同一个毛病：在离决定最远的地方，重新推导决定
    # 者已经知道的事。名单漏一条就是一句英文躺在整页中文里。
    # 未设时下游按原样显示 reason，行为不变。
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
