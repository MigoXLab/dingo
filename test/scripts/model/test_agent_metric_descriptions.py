from dingo.model.llm.agent_eval.llm_agent_argument_correctness import LLMAgentArgumentCorrectness
from dingo.model.llm.agent_eval.llm_agent_error_recovery import LLMAgentErrorRecovery
from dingo.model.llm.agent_eval.llm_agent_plan_adherence import LLMAgentPlanAdherence
from dingo.model.llm.agent_eval.llm_agent_plan_quality import LLMAgentPlanQuality
from dingo.model.llm.agent_eval.llm_agent_step_efficiency import LLMAgentStepEfficiency
from dingo.model.llm.agent_eval.llm_agent_task_completion import LLMAgentTaskCompletion
from dingo.model.llm.agent_eval.llm_agent_tool_correctness import LLMAgentToolCorrectness
from dingo.model.rule.rule_agent import (
    RuleAgentTraceDestructiveAction,
    RuleAgentTraceGatewayBypass,
    RuleAgentTraceIntegrity,
    RuleAgentTraceLatencyAnomaly,
    RuleAgentTraceLoopDetection,
    RuleAgentTraceSandboxExplicitlyDisabled,
    RuleAgentTraceSecretExposure,
    RuleAgentTraceSensitiveAccess,
    RuleAgentTraceTokenBudget,
)


AGENT_METRICS = (
    RuleAgentTraceDestructiveAction,
    RuleAgentTraceGatewayBypass,
    RuleAgentTraceIntegrity,
    RuleAgentTraceLatencyAnomaly,
    RuleAgentTraceLoopDetection,
    RuleAgentTraceSandboxExplicitlyDisabled,
    RuleAgentTraceSecretExposure,
    RuleAgentTraceSensitiveAccess,
    RuleAgentTraceTokenBudget,
    LLMAgentArgumentCorrectness,
    LLMAgentErrorRecovery,
    LLMAgentPlanAdherence,
    LLMAgentPlanQuality,
    LLMAgentStepEfficiency,
    LLMAgentTaskCompletion,
    LLMAgentToolCorrectness,
)


def test_all_16_agent_metric_descriptions_explain_the_ms_swift_requirement():
    assert len(AGENT_METRICS) == 16

    for metric in AGENT_METRICS:
        info = getattr(metric, "_metric_info", None)
        assert isinstance(info, dict), metric.__name__
        assert info.get("metric_name") == metric.__name__

        description = info.get("description") or ""
        assert len(description) > 80, metric.__name__
        assert "ms-swift dataset format" in description, metric.__name__
        assert "dataset.format" in description, metric.__name__
        assert '"ms_swift"' in description, metric.__name__
