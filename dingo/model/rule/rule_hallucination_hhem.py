"""
HHEM-2.1-Open Hallucination Detection Rule

This module provides integration with Vectara's HHEM-2.1-Open model as a rule-based
hallucination detection tool for efficient local inference without API costs.

Key advantages of HHEM-2.1-Open:
- Superior performance compared to GPT-3.5/GPT-4 on benchmarks
- Local inference with <600MB RAM usage
- Fast processing (~1.5s for 2k tokens on modern CPU)
- No API costs or rate limits
"""

import json
from typing import List

from dingo.config.input_args import EvaluatorRuleArgs
from dingo.io.input import Data, RequiredField
from dingo.io.output.eval_detail import EvalDetail
from dingo.model import Model
from dingo.model.rule.base import BaseRule
from dingo.utils import log


@Model.rule_register("QUALITY_BAD_HALLUCINATION", ["hallucination", "rag"])
class RuleHallucinationHHEM(BaseRule):
    """
    HHEM-2.1-Open hallucination detection rule.

    Provides efficient local hallucination detection with:
    - Superior performance than GPT models on benchmarks
    - Low resource usage (<600MB RAM)
    - Fast inference (~1.5s for 2k tokens on modern CPU)
    - No API costs or rate limits
    """

    # Metadata for documentation generation
    _metric_info = {
        "category": "SFT Data Assessment Metrics",
        "quality_dimension": "HALLUCINATION",
        "metric_name": "RuleHallucinationHHEM",
        "description": "Uses Vectara's HHEM-2.1-Open model for local hallucination detection by evaluating consistency between response and context",
        "paper_title": "HHEM-2.1-Open",
        "paper_url": "https://huggingface.co/vectara/hallucination_evaluation_model",
        "paper_authors": "Forrest Bao, Miaoran Li, Rogger Luo, Ofer Mendelevitch"
    }

    _required_fields = [RequiredField.CONTENT, RequiredField.CONTEXT]
    dynamic_config = EvaluatorRuleArgs(threshold=0.5)
    model = None

    @classmethod
    def load_model(cls):
        """Load HHEM-2.1-Open model"""
        if cls.model is None:
            try:
                from transformers import AutoModelForSequenceClassification

                log.info("Loading HHEM-2.1-Open model...")
                cls.model = AutoModelForSequenceClassification.from_pretrained(
                    'vectara/hallucination_evaluation_model',
                    trust_remote_code=True
                )
                log.info("✅ HHEM-2.1-Open model loaded successfully")

            except ImportError:
                raise ImportError(
                    "transformers library is required for HHEM model. "
                    "Install with: pip install transformers"
                )
            except Exception as e:
                raise RuntimeError(f"Failed to load HHEM model: {e}")

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        """
        Evaluate hallucination using HHEM-2.1-Open model.

        Args:
            input_data: Data object containing content and context

        Returns:
            EvalDetail with hallucination detection results
        """
        # Check if context is available
        if not hasattr(input_data, 'context') or not input_data.context:
            # Try to get context from raw_data as fallback
            if hasattr(input_data, 'raw_data') and input_data.raw_data and 'context' in input_data.raw_data:
                contexts = input_data.raw_data['context']
            else:
                # No context available - cannot evaluate
                result = EvalDetail(metric=cls.__name__)
                result.status = True
                # result.type = cls.metric_type
                # result.name = "MISSING_CONTEXT"
                # result.reason = ["Context is required for HHEM hallucination detection but was not provided"]
                result.label = [f"{cls.metric_type}.MISSING_CONTEXT"]
                result.reason = ["Context is required for HHEM hallucination detection but was not provided"]
                return result
        else:
            contexts = input_data.context

        # Load model if not already loaded
        cls.load_model()

        # Prepare context(s)
        if isinstance(contexts, list):
            context_list = contexts
        else:
            # Try to parse as JSON list, fallback to single context
            try:
                context_list = json.loads(contexts)
                if not isinstance(context_list, list):
                    context_list = [str(contexts)]
            except (json.JSONDecodeError, ValueError):
                context_list = [str(contexts)]

        response = input_data.content

        # Create premise-hypothesis pairs for HHEM evaluation
        # Format: (premise, hypothesis) where premise=context, hypothesis=response
        pairs = [(context, response) for context in context_list]

        try:
            # Use HHEM model's official predict() method
            # This returns consistency scores (0=hallucinated, 1=consistent)
            scores = cls.model.predict(pairs)

            # Convert to list if tensor
            consistency_scores = scores.tolist() if hasattr(scores, 'tolist') else list(scores)

            # HHEM returns consistency scores (0=hallucinated, 1=consistent)
            # We convert to hallucination scores (1=hallucinated, 0=consistent)
            hallucination_scores = [1.0 - score for score in consistency_scores]

            # Average hallucination score across all contexts
            avg_hallucination_score = sum(hallucination_scores) / len(hallucination_scores)

            # Create result
            result = EvalDetail(metric=cls.__name__)
            # result.score = avg_hallucination_score

            # Determine if hallucination detected based on threshold
            if avg_hallucination_score > cls.dynamic_config.threshold:
                result.status = True
                # result.type = cls.metric_type
                # result.name = "HALLUCINATION_DETECTED"
                result.label = [f"{cls.metric_type}.HALLUCINATION_DETECTED"]

                # Generate detailed analysis
                analysis_parts = [
                    f"🔍 HHEM-2.1-Open 幻觉检测分析",
                    f"📊 平均幻觉分数: {avg_hallucination_score:.3f} (阈值: {cls.dynamic_config.threshold})",
                    f"📝 评估上下文数量: {len(context_list)}"
                ]

                # Add per-context analysis
                contradictions = []
                consistent_contexts = []

                for i, (context, consistency_score, hallucination_score) in enumerate(
                    zip(context_list, consistency_scores, hallucination_scores), 1
                ):
                    if hallucination_score > cls.dynamic_config.threshold:
                        contradictions.append(
                            f"  {i}. 上下文: \"{context[:100]}{'...' if len(context) > 100 else ''}\"\n"
                            f"     一致性分数: {consistency_score:.3f}, 幻觉分数: {hallucination_score:.3f}"
                        )
                    else:
                        consistent_contexts.append(
                            f"  {i}. 上下文: \"{context[:100]}{'...' if len(context) > 100 else ''}\"\n"
                            f"     一致性分数: {consistency_score:.3f}, 幻觉分数: {hallucination_score:.3f}"
                        )

                if contradictions:
                    analysis_parts.append(f"❌ 发现 {len(contradictions)} 个潜在矛盾:")
                    analysis_parts.extend(contradictions)

                if consistent_contexts:
                    analysis_parts.append(f"✅ {len(consistent_contexts)} 个上下文与回答一致:")
                    analysis_parts.extend(consistent_contexts)

                analysis_parts.extend([
                    f"🚨 结论: 检测到幻觉 (分数 {avg_hallucination_score:.3f} > 阈值 {cls.dynamic_config.threshold})",
                    "   回答与提供的上下文存在显著矛盾",
                    "",
                    "💡 模型信息: 使用 Vectara HHEM-2.1-Open (本地推理)"
                ])

                # result.reason = ["\n".join(analysis_parts)]
                result.reason = ["\n".join(analysis_parts)]
            else:
                result.status = False
                # result.type = "QUALITY_GOOD"
                # result.name = "NO_HALLUCINATION"
                result.label = ['QUALITY_GOOD.NO_HALLUCINATION']

                # Generate analysis for non-hallucination case
                analysis = (
                    f"✅ HHEM-2.1-Open 幻觉检测分析\n"
                    f"📊 平均幻觉分数: {avg_hallucination_score:.3f} (阈值: {cls.dynamic_config.threshold})\n"
                    f"📝 评估上下文数量: {len(context_list)}\n"
                    f"🎉 结论: 未检测到幻觉，回答与上下文基本一致\n"
                    f"💡 模型信息: 使用 Vectara HHEM-2.1-Open (本地推理)"
                )
                # result.reason = [analysis]
                result.reason = [analysis]

            return result

        except Exception as e:
            # Handle model inference errors
            result = EvalDetail(metric=cls.__name__)
            result.status = True
            # result.type = cls.metric_type
            # result.name = "HHEM_ERROR"
            # result.reason = [f"HHEM model inference failed: {str(e)}"]
            result.label = [f"{cls.metric_type}.HHEM_ERROR"]
            result.reason = [f"HHEM model inference failed: {str(e)}"]
            return result

    @classmethod
    def evaluate_with_detailed_output(cls, input_data: Data) -> dict:
        """
        Evaluate with detailed output for analysis.

        Returns:
            Dictionary with detailed evaluation metrics
        """
        result = cls.eval(input_data)

        return {
            # "overall_score": getattr(result, 'score', 0.0),
            "is_hallucinated": result.eval_status,
            "threshold": cls.dynamic_config.threshold,
            # "assessment_type": result.type,
            # "assessment_name": result.name,
            "analysis": result.reason[0] if result.reason else "",
            "model_info": "HHEM-2.1-Open (Vectara)"
        }

    @classmethod
    def batch_evaluate(cls, data_list: List[Data]) -> List[EvalDetail]:
        """
        Batch evaluation for efficiency.

        Args:
            data_list: List of Data objects to evaluate

        Returns:
            List of EvalDetail objects
        """
        # Load model once for batch processing
        cls.load_model()

        results = []
        for data in data_list:
            result = cls.eval(data)
            results.append(result)

        return results
