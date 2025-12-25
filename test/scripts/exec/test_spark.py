"""
Spark 执行器的单元测试
测试 Spark 引擎的指标分数收集和统计功能
"""
from unittest.mock import MagicMock

from dingo.config import InputArgs
from dingo.exec.spark import SparkExecutor
from dingo.io.output.summary_model import SummaryModel


class TestSparkExecutor:
    """Spark 执行器测试类"""

    def test_aggregate_eval_details_with_scores(self):
        """测试聚合函数正确收集指标分数"""
        # 模拟数据
        mock_items = [
            {
                'eval_details': {
                    'field1': [
                        {
                            'score': 9.5,
                            'metric': 'LLMRAGFaithfulness',
                            'label': ['good'],
                            'status': False
                        }
                    ]
                }
            },
            {
                'eval_details': {
                    'field1': [
                        {
                            'score': 8.3,
                            'metric': 'LLMRAGFaithfulness',
                            'label': ['good'],
                            'status': False
                        }
                    ]
                }
            }
        ]

        # 执行聚合（使用 SparkExecutor 的静态方法）
        acc = {'label_counts': {}, 'metric_scores': {}}
        for item in mock_items:
            acc = SparkExecutor._aggregate_eval_details(acc, item)

        # 验证结果
        assert 'field1' in acc['metric_scores']
        assert 'LLMRAGFaithfulness' in acc['metric_scores']['field1']
        assert len(acc['metric_scores']['field1']['LLMRAGFaithfulness']) == 2
        assert acc['metric_scores']['field1']['LLMRAGFaithfulness'] == [9.5, 8.3]
        assert 'field1' in acc['label_counts']
        assert acc['label_counts']['field1']['good'] == 2

    def test_merge_eval_details_with_scores(self):
        """测试合并函数正确合并多个累加器的分数"""
        # 模拟两个 partition 的累加器（按 field_key 分组）
        acc1 = {
            'label_counts': {'field1': {'good': 2}},
            'metric_scores': {'field1': {'LLMRAGFaithfulness': [9.5, 8.3]}}
        }
        acc2 = {
            'label_counts': {'field1': {'good': 1, 'bad': 1}},
            'metric_scores': {'field1': {'LLMRAGFaithfulness': [7.8], 'LLMRAGAnswerRelevancy': [6.5]}}
        }

        # 执行合并（使用 SparkExecutor 的静态方法）
        result = SparkExecutor._merge_eval_details(acc1, acc2)

        # 验证 metric scores 合并正确
        assert len(result['metric_scores']['field1']['LLMRAGFaithfulness']) == 3
        assert result['metric_scores']['field1']['LLMRAGFaithfulness'] == [9.5, 8.3, 7.8]
        assert 'LLMRAGAnswerRelevancy' in result['metric_scores']['field1']
        assert result['metric_scores']['field1']['LLMRAGAnswerRelevancy'] == [6.5]

        # 验证 label counts 合并正确
        assert result['label_counts']['field1']['good'] == 3
        assert result['label_counts']['field1']['bad'] == 1

    def test_full_aggregation_workflow(self):
        """测试完整的聚合工作流程（模拟实际的 Spark 聚合）"""
        # 模拟 3 个 partition 的数据
        partitions = [
            [
                {'eval_details': {'field1': [{'score': 9.5, 'metric': 'M1', 'label': ['good']}]}},
                {'eval_details': {'field1': [{'score': 8.3, 'metric': 'M1', 'label': ['good']}]}}
            ],
            [
                {'eval_details': {'field1': [{'score': 9.0, 'metric': 'M1', 'label': ['good']}]}},
                {'eval_details': {'field1': [{'score': 7.2, 'metric': 'M2', 'label': ['good']}]}}
            ],
            [
                {'eval_details': {'field1': [{'score': 6.8, 'metric': 'M2', 'label': ['bad']}]}},
                {'eval_details': {'field1': [{'score': 8.1, 'metric': 'M2', 'label': ['good']}]}}
            ]
        ]

        # 模拟 Spark 的 aggregate 操作
        # Step 1: 在每个 partition 内聚合（使用 SparkExecutor 的静态方法）
        partition_results = []
        for partition_data in partitions:
            acc = {'label_counts': {}, 'metric_scores': {}}
            for item in partition_data:
                acc = SparkExecutor._aggregate_eval_details(acc, item)
            partition_results.append(acc)

        # Step 2: 合并所有 partition 的结果（使用 SparkExecutor 的静态方法）
        final_result = {'label_counts': {}, 'metric_scores': {}}
        for partition_result in partition_results:
            final_result = SparkExecutor._merge_eval_details(final_result, partition_result)

        # 验证聚合结果
        assert 'field1' in final_result['metric_scores']
        assert 'M1' in final_result['metric_scores']['field1']
        assert 'M2' in final_result['metric_scores']['field1']
        assert len(final_result['metric_scores']['field1']['M1']) == 3
        assert len(final_result['metric_scores']['field1']['M2']) == 3

        # Step 3: 将结果添加到 summary
        summary = SummaryModel(task_name="test_full", total=6)
        for field_key, metrics in final_result['metric_scores'].items():
            for metric_name, scores in metrics.items():
                for score in scores:
                    summary.add_metric_score(field_key, metric_name, score)
        summary.calculate_metrics_score_averages()

        # 验证最终结果
        result = summary.to_dict()
        assert 'metrics_score' in result
        assert result['metrics_score']['field1']['stats']['M1']['score_count'] == 3
        assert result['metrics_score']['field1']['stats']['M2']['score_count'] == 3
        assert result['metrics_score']['field1']['stats']['M1']['score_average'] == 8.93
        assert result['metrics_score']['field1']['stats']['M2']['score_average'] == 7.37

    def test_spark_executor_summarize_with_mock_data(self):
        """测试 SparkExecutor.summarize 方法（使用 mock 数据）"""
        # 创建 InputArgs（最小配置）
        input_args = InputArgs(**{
            "task_name": "test_spark_executor",
            "evaluator": []
        })

        # 创建 SparkExecutor
        executor = SparkExecutor(input_args=input_args)

        # 模拟 data_info_list（RDD 的内容）
        mock_data_info_list = [
            {
                'eval_status': False,
                'eval_details': {
                    'field1': [
                        {
                            'score': 9.5,
                            'metric': 'LLMRAGFaithfulness',
                            'label': ['good'],
                            'status': False
                        }
                    ]
                }
            },
            {
                'eval_status': False,
                'eval_details': {
                    'field1': [
                        {
                            'score': 8.3,
                            'metric': 'LLMRAGFaithfulness',
                            'label': ['good'],
                            'status': False
                        }
                    ]
                }
            }
        ]

        # 创建 mock RDD
        mock_rdd = MagicMock()

        # 模拟 aggregate 方法的行为
        def mock_aggregate(init_acc, seq_func, comb_func):
            # 在每个元素上应用 seq_func
            result = init_acc
            for item in mock_data_info_list:
                result = seq_func(result, item)
            return result

        mock_rdd.aggregate = mock_aggregate
        executor.data_info_list = mock_rdd

        # 创建初始 summary
        summary = SummaryModel(
            task_name="test_spark_executor",
            total=2,
            num_good=2,
            num_bad=0
        )

        # 调用 summarize
        result = executor.summarize(summary)

        # 验证 metrics_score 存在
        result_dict = result.to_dict()
        assert 'metrics_score' in result_dict

        # 验证 LLMRAGFaithfulness 的统计
        stats = result_dict['metrics_score']['field1']['stats']['LLMRAGFaithfulness']
        assert stats['score_count'] == 2
        assert stats['score_average'] == 8.9  # (9.5 + 8.3) / 2
        assert stats['score_min'] == 8.3
        assert stats['score_max'] == 9.5

    def test_spark_executor_summarize_multiple_metrics(self):
        """测试 SparkExecutor.summarize 处理多个指标"""
        # 创建 InputArgs
        input_args = InputArgs(**{
            "task_name": "test_multiple_metrics",
            "evaluator": []
        })

        # 创建 SparkExecutor
        executor = SparkExecutor(input_args=input_args)

        # 模拟包含多个指标的数据
        mock_data_info_list = [
            {
                'eval_status': False,
                'eval_details': {
                    'field1': [
                        {'score': 9.5, 'metric': 'LLMRAGFaithfulness', 'label': ['good'], 'status': False},
                        {'score': 7.8, 'metric': 'LLMRAGAnswerRelevancy', 'label': ['good'], 'status': False}
                    ]
                }
            },
            {
                'eval_status': False,
                'eval_details': {
                    'field1': [
                        {'score': 8.3, 'metric': 'LLMRAGFaithfulness', 'label': ['good'], 'status': False},
                        {'score': 6.2, 'metric': 'LLMRAGAnswerRelevancy', 'label': ['bad'], 'status': True}
                    ]
                }
            }
        ]

        # 创建 mock RDD
        mock_rdd = MagicMock()

        def mock_aggregate(init_acc, seq_func, comb_func):
            result = init_acc
            for item in mock_data_info_list:
                result = seq_func(result, item)
            return result

        mock_rdd.aggregate = mock_aggregate
        executor.data_info_list = mock_rdd

        # 创建初始 summary
        summary = SummaryModel(
            task_name="test_multiple_metrics",
            total=2,
            num_good=1,
            num_bad=1
        )

        # 调用 summarize
        result = executor.summarize(summary)

        # 验证结果
        result_dict = result.to_dict()
        assert 'metrics_score' in result_dict
        assert 'LLMRAGFaithfulness' in result_dict['metrics_score']['field1']['stats']
        assert 'LLMRAGAnswerRelevancy' in result_dict['metrics_score']['field1']['stats']

        # 验证各指标的统计
        faith_stats = result_dict['metrics_score']['field1']['stats']['LLMRAGFaithfulness']
        assert faith_stats['score_count'] == 2
        assert faith_stats['score_average'] == 8.9

        relevancy_stats = result_dict['metrics_score']['field1']['stats']['LLMRAGAnswerRelevancy']
        assert relevancy_stats['score_count'] == 2
        assert relevancy_stats['score_average'] == 7.0  # (7.8 + 6.2) / 2

        # 验证 overall_average
        assert result_dict['metrics_score']['field1']['overall_average'] == 7.95  # (8.9 + 7.0) / 2

    def test_spark_executor_summarize_empty_data(self):
        """测试 SparkExecutor.summarize 处理空数据"""
        # 创建 InputArgs
        input_args = InputArgs(**{
            "task_name": "test_empty",
            "evaluator": []
        })

        # 创建 SparkExecutor
        executor = SparkExecutor(input_args=input_args)

        # 模拟空的 data_info_list
        mock_rdd = MagicMock()
        mock_rdd.aggregate = lambda init_acc, seq_func, comb_func: init_acc
        executor.data_info_list = mock_rdd

        # 创建初始 summary（total=0）
        summary = SummaryModel(
            task_name="test_empty",
            total=0,
            num_good=0,
            num_bad=0
        )

        # 调用 summarize
        result = executor.summarize(summary)

        # 验证结果（total=0 时直接返回）
        assert result.total == 0
        result_dict = result.to_dict()
        assert 'metrics_score' not in result_dict
