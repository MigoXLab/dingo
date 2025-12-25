"""
单元测试: SummaryModel 的指标分数统计功能

测试场景:
1. 添加分数并计算统计信息
2. 没有分数时的行为
3. 单个分数的统计
4. 多个指标的统计
5. to_dict() 输出格式
"""

import pytest

from dingo.io.output.summary_model import SummaryModel


class TestSummaryModel:
    """测试 SummaryModel 的指标分数统计功能"""

    def test_add_metric_score_single(self):
        """测试添加单个指标的多个分数"""
        summary = SummaryModel(
            task_name="test_task",
            task_id="test_001"
        )

        # 添加分数
        summary.add_metric_score("field1", "TestMetric1", 8.5)
        summary.add_metric_score("field1", "TestMetric1", 9.0)
        summary.add_metric_score("field1", "TestMetric1", 7.5)

        # 验证分数已添加
        assert "field1" in summary.metrics_score_stats
        assert "TestMetric1" in summary.metrics_score_stats["field1"]
        assert summary.metrics_score_stats["field1"]["TestMetric1"]["score_count"] == 3
        assert len(summary.metrics_score_stats["field1"]["TestMetric1"]["scores"]) == 3

    def test_add_metric_score_multiple_metrics(self):
        """测试添加多个指标的分数"""
        summary = SummaryModel(
            task_name="test_task",
            task_id="test_002"
        )

        # 添加不同指标的分数
        summary.add_metric_score("field1", "Metric1", 8.0)
        summary.add_metric_score("field1", "Metric2", 7.0)
        summary.add_metric_score("field1", "Metric1", 9.0)
        summary.add_metric_score("field1", "Metric2", 6.5)

        # 验证分数已正确分类
        assert "field1" in summary.metrics_score_stats
        assert len(summary.metrics_score_stats["field1"]) == 2
        assert summary.metrics_score_stats["field1"]["Metric1"]["score_count"] == 2
        assert summary.metrics_score_stats["field1"]["Metric2"]["score_count"] == 2

    def test_calculate_metrics_score_averages(self):
        """测试计算指标分数的平均值、最小值、最大值、标准差"""
        summary = SummaryModel(
            task_name="test_task",
            task_id="test_003"
        )

        # 添加分数
        summary.add_metric_score("field1", "TestMetric", 8.0)
        summary.add_metric_score("field1", "TestMetric", 9.0)
        summary.add_metric_score("field1", "TestMetric", 7.0)

        # 计算统计值
        summary.calculate_metrics_score_averages()

        # 验证统计结果
        stats = summary.metrics_score_stats["field1"]["TestMetric"]
        assert stats["score_average"] == 8.0
        assert stats["score_min"] == 7.0
        assert stats["score_max"] == 9.0
        assert stats["score_count"] == 3
        assert "score_std_dev" in stats
        assert stats["score_std_dev"] > 0
        # 验证 scores 列表已被删除
        assert "scores" not in stats

    def test_calculate_metrics_score_averages_single_score(self):
        """测试只有一个分数时的统计（不应该有 score_std_dev）"""
        summary = SummaryModel(
            task_name="test_task",
            task_id="test_004"
        )

        # 只添加一个分数
        summary.add_metric_score("field1", "TestMetric", 8.5)

        # 计算统计值
        summary.calculate_metrics_score_averages()

        # 验证统计结果
        stats = summary.metrics_score_stats["field1"]["TestMetric"]
        assert stats["score_average"] == 8.5
        assert stats["score_min"] == 8.5
        assert stats["score_max"] == 8.5
        assert stats["score_count"] == 1
        # 单个分数不应该计算标准差
        assert "score_std_dev" not in stats

    def test_get_metrics_score_summary(self):
        """测试获取指标分数汇总"""
        summary = SummaryModel(
            task_name="test_task",
            task_id="test_005"
        )

        # 添加多个指标的分数
        summary.add_metric_score("field1", "Metric1", 8.0)
        summary.add_metric_score("field1", "Metric1", 9.0)
        summary.add_metric_score("field1", "Metric2", 7.0)
        summary.add_metric_score("field1", "Metric2", 6.0)

        # 计算统计值
        summary.calculate_metrics_score_averages()

        # 获取汇总
        score_summary = summary.get_metrics_score_summary("field1")

        # 验证汇总结果
        assert len(score_summary) == 2
        assert score_summary["Metric1"] == 8.5
        assert score_summary["Metric2"] == 6.5

    def test_get_metrics_score_overall_average(self):
        """测试计算总平均分"""
        summary = SummaryModel(
            task_name="test_task",
            task_id="test_006"
        )

        # 添加多个指标的分数
        summary.add_metric_score("field1", "Metric1", 8.0)
        summary.add_metric_score("field1", "Metric1", 9.0)
        summary.add_metric_score("field1", "Metric2", 7.0)
        summary.add_metric_score("field1", "Metric2", 5.0)

        # 计算统计值
        summary.calculate_metrics_score_averages()

        # 获取总平均分
        overall_avg = summary.get_metrics_score_overall_average("field1")

        # 验证：(8.5 + 6.0) / 2 = 7.25
        assert overall_avg == 7.25

    def test_get_metrics_score_overall_average_empty(self):
        """测试没有分数时的总平均分"""
        summary = SummaryModel(
            task_name="test_task",
            task_id="test_007"
        )

        # 没有添加分数
        overall_avg = summary.get_metrics_score_overall_average("field1")

        # 验证：应该返回 0.0
        assert overall_avg == 0.0

    def test_to_dict_with_scores(self):
        """测试 to_dict() 在有分数时的输出"""
        summary = SummaryModel(
            task_name="test_task",
            task_id="test_008",
            total=10,
            num_good=8,
            num_bad=2
        )

        # 添加分数
        summary.add_metric_score("field1", "Metric1", 8.0)
        summary.add_metric_score("field1", "Metric1", 9.0)

        # 计算统计值
        summary.calculate_metrics_score_averages()

        # 转换为字典
        result = summary.to_dict()

        # 验证基本字段
        assert result["task_name"] == "test_task"
        assert result["task_id"] == "test_008"
        assert result["total"] == 10

        # 验证分数统计字段（层级结构）
        assert "metrics_score" in result
        assert "field1" in result["metrics_score"]
        assert "stats" in result["metrics_score"]["field1"]
        assert "summary" in result["metrics_score"]["field1"]
        assert "overall_average" in result["metrics_score"]["field1"]

        # 验证分数统计内容
        assert "Metric1" in result["metrics_score"]["field1"]["stats"]
        assert result["metrics_score"]["field1"]["stats"]["Metric1"]["score_average"] == 8.5
        assert result["metrics_score"]["field1"]["summary"]["Metric1"] == 8.5
        assert result["metrics_score"]["field1"]["overall_average"] == 8.5

    def test_to_dict_without_scores(self):
        """测试 to_dict() 在没有分数时的输出"""
        summary = SummaryModel(
            task_name="test_task",
            task_id="test_009",
            total=10,
            num_good=8,
            num_bad=2
        )

        # 不添加任何分数
        # 转换为字典
        result = summary.to_dict()

        # 验证基本字段
        assert result["task_name"] == "test_task"
        assert result["task_id"] == "test_009"
        assert result["total"] == 10

        # 验证没有分数统计字段
        assert "metrics_score" not in result

    def test_multiple_metrics_different_score_counts(self):
        """测试不同指标有不同数量的分数"""
        summary = SummaryModel(
            task_name="test_task",
            task_id="test_010"
        )

        # Metric1 有 3 个分数
        summary.add_metric_score("field1", "Metric1", 8.0)
        summary.add_metric_score("field1", "Metric1", 9.0)
        summary.add_metric_score("field1", "Metric1", 7.0)

        # Metric2 有 5 个分数
        for score in [6.0, 7.0, 8.0, 9.0, 10.0]:
            summary.add_metric_score("field1", "Metric2", score)

        # 计算统计值
        summary.calculate_metrics_score_averages()

        # 验证统计结果
        assert summary.metrics_score_stats["field1"]["Metric1"]["score_count"] == 3
        assert summary.metrics_score_stats["field1"]["Metric2"]["score_count"] == 5
        assert summary.metrics_score_stats["field1"]["Metric1"]["score_average"] == 8.0
        assert summary.metrics_score_stats["field1"]["Metric2"]["score_average"] == 8.0

    def test_score_rounding(self):
        """测试分数的四舍五入"""
        summary = SummaryModel(
            task_name="test_task",
            task_id="test_011"
        )

        # 添加会产生小数的分数
        summary.add_metric_score("field1", "TestMetric", 8.333)
        summary.add_metric_score("field1", "TestMetric", 9.666)
        summary.add_metric_score("field1", "TestMetric", 7.111)

        # 计算统计值
        summary.calculate_metrics_score_averages()

        # 验证四舍五入
        stats = summary.metrics_score_stats["field1"]["TestMetric"]
        # (8.333 + 9.666 + 7.111) / 3 = 8.37
        assert stats["score_average"] == 8.37
        assert stats["score_min"] == 7.11
        assert stats["score_max"] == 9.67

    def test_rag_evaluation_scenario(self):
        """测试 RAG 评估场景：5个指标的完整评估"""
        summary = SummaryModel(
            task_name="rag_evaluation",
            task_id="rag_001"
        )

        # 模拟 5 个 RAG 指标，每个指标有 10 个样本
        rag_metrics = [
            "LLMRAGFaithfulness",
            "LLMRAGAnswerRelevancy",
            "LLMRAGContextRelevancy",
            "LLMRAGContextRecall",
            "LLMRAGContextPrecision"
        ]

        # 为每个指标添加 10 个分数
        for metric in rag_metrics:
            for i in range(10):
                # 模拟不同的分数
                score = 7.0 + (i % 3)  # 7.0, 8.0, 9.0 循环
                summary.add_metric_score("field1", metric, score)

        # 计算统计值
        summary.calculate_metrics_score_averages()

        # 验证所有指标都有统计
        assert "field1" in summary.metrics_score_stats
        assert len(summary.metrics_score_stats["field1"]) == 5
        for metric in rag_metrics:
            assert metric in summary.metrics_score_stats["field1"]
            assert summary.metrics_score_stats["field1"][metric]["score_count"] == 10

        # 验证总平均分
        overall_avg = summary.get_metrics_score_overall_average("field1")
        # 7.0, 8.0, 9.0 循环10次：(7+8+9)*3 + 7 = 79, 79/10 = 7.9
        assert overall_avg == 7.9
