from dingo.config.input_args import EvaluatorLLMArgs, EvaluatorRuleArgs
from dingo.model.llm.llm_custom_metric import LLMCustomMetric
from dingo.model.llm.text_quality.llm_text_quality_v5 import LLMTextQualityV5
from dingo.model.model import Model
from dingo.model.rule.rule_common import RulePatternSearch


def test_set_config_rule_copies_dynamic_config_per_rule_object():
    rule_a = RulePatternSearch()
    rule_b = RulePatternSearch()

    Model.set_config_rule(rule_a, EvaluatorRuleArgs(pattern="apple"))
    Model.set_config_rule(rule_b, EvaluatorRuleArgs(pattern="banana"))

    assert rule_a.dynamic_config is not rule_b.dynamic_config
    assert rule_a.dynamic_config.pattern == "apple"
    assert rule_b.dynamic_config.pattern == "banana"
    assert RulePatternSearch.dynamic_config.pattern == "your pattern"


def test_set_config_llm_copies_dynamic_config_per_llm_object():
    # This verifies config object isolation only. Existing classmethod LLM evaluators
    # still read cls.dynamic_config at runtime unless separately refactored.
    llm_a = LLMTextQualityV5()
    llm_b = LLMTextQualityV5()

    Model.set_config_llm(
        llm_a,
        EvaluatorLLMArgs(model="model-a", parameters={"temperature": 0.1}),
    )
    Model.set_config_llm(
        llm_b,
        EvaluatorLLMArgs(model="model-b", parameters={"temperature": 0.9}),
    )

    assert llm_a.dynamic_config is not llm_b.dynamic_config
    assert llm_a.dynamic_config.model == "model-a"
    assert llm_b.dynamic_config.model == "model-b"
    assert llm_a.dynamic_config.parameters == {"temperature": 0.1}
    assert llm_b.dynamic_config.parameters == {"temperature": 0.9}
    assert LLMTextQualityV5.dynamic_config.model is None
    assert LLMTextQualityV5.dynamic_config.model_dump().get("parameters") is None


def test_set_config_llm_deep_copies_custom_metric_per_llm_object():
    llm_a = LLMCustomMetric()
    llm_b = LLMCustomMetric()

    Model.set_config_llm(
        llm_a,
        EvaluatorLLMArgs(
            custom_metric={
                "metric": "MetricA",
                "description": "Rule A",
                "criteria": ["criterion a"],
                "input_fields": ["prompt"],
            }
        ),
    )
    Model.set_config_llm(
        llm_b,
        EvaluatorLLMArgs(
            custom_metric={
                "metric": "MetricB",
                "description": "Rule B",
                "criteria": ["criterion b"],
                "input_fields": ["content"],
            }
        ),
    )

    llm_a.dynamic_config.custom_metric.criteria.append("criterion a2")

    assert llm_a.dynamic_config is not llm_b.dynamic_config
    assert llm_a.dynamic_config.custom_metric is not llm_b.dynamic_config.custom_metric
    assert llm_a.dynamic_config.custom_metric.metric == "MetricA"
    assert llm_b.dynamic_config.custom_metric.metric == "MetricB"
    assert llm_a.dynamic_config.custom_metric.criteria == ["criterion a", "criterion a2"]
    assert llm_b.dynamic_config.custom_metric.criteria == ["criterion b"]
    assert LLMCustomMetric.dynamic_config.custom_metric is None
