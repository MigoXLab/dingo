import pytest

from dingo.config import InputArgs
from dingo.exec import Executor, LocalExecutor
from dingo.io import ResultInfo
from dingo.io.output.eval_detail import EvalDetail, TokenUsage
from dingo.model import Model


class TestLocal:
    def test_rule_runtime_config_key_list_applies_in_local_executor(self):
        input_data = {
            "evaluator": [],
        }
        input_args = InputArgs(**input_data)
        executor = LocalExecutor(input_args)

        eval_list = [
            InputArgs(
                evaluator=[
                    {
                        "fields": {},
                        "evals": [
                            {
                                "name": "RuleQuanliangFieldValidation",
                                "config": {
                                    "key_list": ["doi", "references", "related_works", "citations"]
                                },
                            }
                        ],
                    }
                ]
            ).evaluator[0].evals[0]
        ]

        result = executor.evaluate_single_data(
            dingo_id="1",
            eval_fields={},
            eval_type="rule",
            map_data={},
            eval_list=eval_list,
        )

        details = result.eval_details["default"][0]
        assert details.metric == "RuleQuanliangFieldValidation"
        assert details.label == [
            "doi.missing_field",
            "references.missing_field",
            "related_works.missing_field",
            "citations.missing_field",
        ]

    def test_write_single_data_limit_per_file(self, tmp_path):
        input_data = {
            "executor": {
                "result_save": {
                    "bad": True,
                    "limit": 1,
                }
            },
            "evaluator": [],
        }
        input_args = InputArgs(**input_data)
        executor = LocalExecutor(input_args)

        result_info = ResultInfo(
            dingo_id="1",
            raw_data={"content": "test"},
            eval_status=True,
            eval_details={
                "content": [
                    EvalDetail(
                        metric="RuleColonEnd",
                        status=True,
                        label=["QUALITY_BAD_EFFECTIVENESS.RuleColonEnd"],
                        reason=["bad sample"],
                    )
                ]
            },
        )
        output_path = str(tmp_path)

        executor.write_single_data(output_path, input_args, result_info)
        executor.write_single_data(output_path, input_args, result_info)

        target_file = tmp_path / "content" / "QUALITY_BAD_EFFECTIVENESS" / "RuleColonEnd.jsonl"
        assert target_file.exists()
        lines = target_file.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1

    def test_write_single_data_limit_per_file_merge_mode(self, tmp_path):
        input_data = {
            "executor": {
                "result_save": {
                    "bad": True,
                    "merge": True,
                    "limit": 1,
                }
            },
            "evaluator": [],
        }
        input_args = InputArgs(**input_data)
        executor = LocalExecutor(input_args)

        result_info = ResultInfo(
            dingo_id="1",
            raw_data={"content": "test"},
            eval_status=True,
            eval_details={
                "content": [
                    EvalDetail(
                        metric="RuleColonEnd",
                        status=True,
                        label=["QUALITY_BAD_EFFECTIVENESS.RuleColonEnd"],
                        reason=["bad sample"],
                    )
                ]
            },
        )
        output_path = str(tmp_path)

        executor.write_single_data(output_path, input_args, result_info)
        executor.write_single_data(output_path, input_args, result_info)

        target_file = tmp_path / "all_results.jsonl"
        assert target_file.exists()
        lines = target_file.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1

    def test_merge_result_info(self):
        existing_list = []
        new_item1 = ResultInfo(
            dingo_id = "1",
            raw_data = {
                "content": "�I am 8 years old. ^I love apple because:",
            },
            eval_status = True,
            eval_details = {
                "content": [
                    EvalDetail(
                        metric="RuleColonEnd",
                        status=True,
                        label=["QUALITY_BAD_EFFECTIVENESS-RuleColonEnd"],
                        reason=["�I am 8 years old. ^I love apple because:"]
                    )
                ]
            }
        )
        new_item2 = ResultInfo(
            dingo_id = "1",
            raw_data = {
                "content": "�I am 8 years old. ^I love apple because:",
            },
            eval_status = True,
            eval_details = {
                "content": [
                    EvalDetail(
                        metric="PromptContentChaos",
                        status=True,
                        label=["QUALITY_BAD_EFFECTIVENESS-PromptContentChaos"],
                        reason=["文本中包含不可见字符或乱码（如�和^），可能影响阅读理解。"]
                    )
                ]
            }
        )

        localexecutor = LocalExecutor({})

        new_existing_list = localexecutor.merge_result_info(existing_list, new_item1)
        assert new_existing_list[0] == new_item1

        existing_list = []
        new_existing_list = localexecutor.merge_result_info(existing_list, new_item1)
        new_existing_list = localexecutor.merge_result_info(new_existing_list, new_item2)
        assert len(new_existing_list) == 1

        # 获取合并后的 content 字段的 EvalDetail 列表
        content_details = new_existing_list[0].eval_details.get('content')
        assert len(content_details) == 2

        # 收集所有的 label, metric, reason
        all_labels = []
        all_metrics = []
        all_reasons = []
        for detail in content_details:
            if detail.label:
                all_labels.extend(detail.label)
            if detail.metric:
                all_metrics.append(detail.metric)
            if detail.reason:
                all_reasons.extend(detail.reason)

        assert len(all_labels) == 2
        assert len(all_metrics) == 2
        assert len(all_reasons) == 2
        assert "QUALITY_BAD_EFFECTIVENESS-RuleColonEnd" in all_labels
        assert "QUALITY_BAD_EFFECTIVENESS-PromptContentChaos" in all_labels
        assert "�I am 8 years old. ^I love apple because:" in all_reasons
        assert "文本中包含不可见字符或乱码（如�和^），可能影响阅读理解。" in all_reasons

    def test_merge_result_info_preserves_token_usage_details(self):
        localexecutor = LocalExecutor({})
        item1 = ResultInfo(
            dingo_id="1",
            token_usage_details={
                "content": [
                    EvalDetail(
                        metric="LLMMetricA",
                        usage=TokenUsage(total_tokens=3),
                    )
                ]
            },
        )
        item2 = ResultInfo(
            dingo_id="1",
            token_usage_details={
                "content": [
                    EvalDetail(
                        metric="LLMMetricB",
                        usage=TokenUsage(total_tokens=5),
                    )
                ]
            },
        )

        merged = localexecutor.merge_result_info([], item1)
        merged = localexecutor.merge_result_info(merged, item2)

        assert len(merged[0].token_usage_details["content"]) == 2

    def test_token_usage_summary_can_include_unsaved_good_eval_details(self):
        class TokenUsageGoodLLM:
            def eval(self, input_data):
                return EvalDetail(
                    metric="TokenUsageGoodLLM",
                    status=False,
                    label=["QUALITY_GOOD"],
                    usage=TokenUsage(
                        prompt_tokens=10,
                        completion_tokens=5,
                        total_tokens=15,
                    ),
                )

        old_model = Model.llm_name_map.get("TokenUsageGoodLLM")
        Model.llm_name_map["TokenUsageGoodLLM"] = TokenUsageGoodLLM
        try:
            input_args = InputArgs(
                executor={
                    "result_save": {
                        "bad": True,
                        "good": False,
                        "all_labels": False,
                    }
                },
                evaluator=[
                    {
                        "fields": {"content": "content"},
                        "evals": [{"name": "TokenUsageGoodLLM"}],
                    }
                ],
            )
            executor = LocalExecutor(input_args)

            result = executor.evaluate_single_data(
                dingo_id="1",
                eval_fields={"content": "content"},
                eval_type="llm",
                map_data={"content": "ok"},
                eval_list=input_args.evaluator[0].evals,
            )

            assert result.eval_details == {}
            assert result.token_usage_details["content"][0].usage.total_tokens == 15
        finally:
            if old_model is None:
                Model.llm_name_map.pop("TokenUsageGoodLLM", None)
            else:
                Model.llm_name_map["TokenUsageGoodLLM"] = old_model

    def test_statistics_can_include_unsaved_good_eval_details(self):
        class StatisticsGoodLLM:
            def eval(self, input_data):
                return EvalDetail(
                    metric="StatisticsGoodLLM",
                    status=False,
                    label=["QUALITY_GOOD"],
                    statistics={"items": 2},
                )

        old_model = Model.llm_name_map.get("StatisticsGoodLLM")
        Model.llm_name_map["StatisticsGoodLLM"] = StatisticsGoodLLM
        try:
            input_args = InputArgs(
                executor={
                    "result_save": {
                        "bad": True,
                        "good": False,
                        "all_labels": False,
                    }
                },
                evaluator=[
                    {
                        "fields": {"content": "content"},
                        "evals": [{"name": "StatisticsGoodLLM"}],
                    }
                ],
            )
            executor = LocalExecutor(input_args)

            result = executor.evaluate_single_data(
                dingo_id="1",
                eval_fields={"content": "content"},
                eval_type="llm",
                map_data={"content": "ok"},
                eval_list=input_args.evaluator[0].evals,
            )

            assert result.eval_details == {}
            assert result.statistics_details["content"][0].statistics == {"items": 2}
        finally:
            if old_model is None:
                Model.llm_name_map.pop("StatisticsGoodLLM", None)
            else:
                Model.llm_name_map["StatisticsGoodLLM"] = old_model

    def test_statistics_are_aggregated_during_execution(self, tmp_path):
        class StatisticsLLM:
            def eval(self, input_data):
                return EvalDetail(
                    metric="StatisticsLLM",
                    status=False,
                    label=["QUALITY_GOOD"],
                    statistics={"items": 2},
                )

        input_path = tmp_path / "statistics.jsonl"
        input_path.write_text(
            '{"content": "first"}\n{"content": "second"}\n',
            encoding="utf-8",
        )
        old_model = Model.llm_name_map.get("StatisticsLLM")
        Model.llm_name_map["StatisticsLLM"] = StatisticsLLM
        try:
            input_args = InputArgs(
                input_path=str(input_path),
                output_path=str(tmp_path / "outputs"),
                dataset={"source": "local", "format": "jsonl"},
                executor={
                    "result_save": {
                        "bad": False,
                        "good": False,
                        "all_labels": False,
                    }
                },
                evaluator=[
                    {
                        "fields": {"content": "content"},
                        "evals": [{"name": "StatisticsLLM"}],
                    }
                ],
            )

            summary = LocalExecutor(input_args).execute()

            assert summary.to_dict()["statistics"] == {
                "content": {"StatisticsLLM": {"items": 4}}
            }
        finally:
            if old_model is None:
                Model.llm_name_map.pop("StatisticsLLM", None)
            else:
                Model.llm_name_map["StatisticsLLM"] = old_model

    def test_all_labels_config(self):
        input_data = {
            "input_path": "test/data/test_local_jsonl.jsonl",
            "dataset": {
                "source": "local",
                "format": "jsonl"
            },
            "executor": {
                "result_save": {
                    "all_labels": True,
                },
                "end_index": 1
            },
            "evaluator": [
                {
                    "fields": {"content": "content"},
                    "evals": [
                        {"name": "RuleColonEnd"},
                        {"name": "RuleSpecialCharacter"},
                        {"name": "RuleDocRepeat"}
                    ]
                }
            ]
        }
        input_args = InputArgs(**input_data)
        executor = Executor.exec_map["local"](input_args)
        result = executor.execute()
        print(result)
        assert all([item in result.type_ratio.get('content') for item in ["QUALITY_BAD_EFFECTIVENESS.RuleColonEnd",
                                                      "QUALITY_BAD_EFFECTIVENESS.RuleSpecialCharacter",
                                                      "QUALITY_GOOD"]])

        input_data["executor"]["result_save"]["all_labels"] = False
        input_args = InputArgs(**input_data)
        executor = Executor.exec_map["local"](input_args)
        result = executor.execute()
        assert all([item in result.type_ratio.get('content') for item in ["QUALITY_BAD_EFFECTIVENESS.RuleColonEnd",
                                                           "QUALITY_BAD_EFFECTIVENESS.RuleSpecialCharacter"]])

    def test_metrics_score_collection_with_scores(self):
        """测试带有分数的指标评估时，summary 正确收集和计算分数"""

        # 不依赖真实的数据文件和 API，直接测试 score 收集逻辑
        from dingo.io.output.summary_model import SummaryModel

        # 创建一个 summary 并添加分数
        summary = SummaryModel(
            task_name="test_rag",
            total=3,
            num_good=3,
            num_bad=0
        )

        # 手动模拟评估结果（因为实际 API 调用需要真实的 key）
        summary.add_metric_score("field1", "LLMRAGFaithfulness", 8.5)
        summary.add_metric_score("field1", "LLMRAGFaithfulness", 9.0)
        summary.add_metric_score("field1", "LLMRAGFaithfulness", 7.5)

        # 创建 executor 并调用 summarize
        executor = LocalExecutor({})
        result = executor.summarize(summary)

        # 验证 metrics_score 存在（层级结构）
        result_dict = result.to_dict()
        assert "metrics_score" in result_dict
        assert "field1" in result_dict["metrics_score"]
        assert "stats" in result_dict["metrics_score"]["field1"]
        assert "summary" in result_dict["metrics_score"]["field1"]
        assert "overall_average" in result_dict["metrics_score"]["field1"]

        # 验证统计信息正确
        stats = result.metrics_score_stats["field1"]["LLMRAGFaithfulness"]
        assert stats["score_average"] == 8.33
        assert stats["score_min"] == 7.5
        assert stats["score_max"] == 9.0
        assert stats["score_count"] == 3

        # 验证 summary 方法
        score_summary = result.get_metrics_score_summary("field1")
        assert "LLMRAGFaithfulness" in score_summary
        assert score_summary["LLMRAGFaithfulness"] == 8.33

        # 验证总平均分
        overall_avg = result.get_metrics_score_overall_average("field1")
        assert overall_avg == 8.33

    def test_metrics_score_collection_without_scores(self):
        """测试没有分数的指标评估时，summary 中没有分数统计"""
        # 使用 Rule 评估（这些指标不返回 score）
        input_data = {
            "input_path": "test/data/test_local_jsonl.jsonl",
            "dataset": {
                "source": "local",
                "format": "jsonl"
            },
            "executor": {
                "result_save": {
                    "good": True,
                    "bad": True,
                    "all_labels": True
                },
                "end_index": 2
            },
            "evaluator": [
                {
                    "fields": {"content": "content"},
                    "evals": [
                        {"name": "RuleColonEnd"},
                        {"name": "RuleSpecialCharacter"}
                    ]
                }
            ]
        }

        input_args = InputArgs(**input_data)
        executor = Executor.exec_map["local"](input_args)
        result = executor.execute()

        # 验证没有 metrics_score（因为 Rule 评估器不返回 score）
        result_dict = result.to_dict()
        assert "metrics_score" not in result_dict

    def test_metrics_score_collection_mixed(self):
        """测试混合场景：部分指标有分数，部分没有"""
        from dingo.io.output.summary_model import SummaryModel

        # 创建一个 summary
        summary = SummaryModel(
            task_name="test_mixed",
            total=10,
            num_good=8,
            num_bad=2
        )

        # 只添加一个指标的分数（模拟混合场景）
        summary.add_metric_score("field1", "MetricWithScore", 8.0)
        summary.add_metric_score("field1", "MetricWithScore", 9.0)
        # 注意：没有为其他指标添加分数

        # 创建 executor 并调用 summarize
        executor = LocalExecutor({})
        result = executor.summarize(summary)

        # 验证有 metrics_score
        result_dict = result.to_dict()
        assert "metrics_score" in result_dict
        assert "field1" in result.metrics_score_stats
        assert "MetricWithScore" in result.metrics_score_stats["field1"]

        # 验证统计信息
        stats = result.metrics_score_stats["field1"]["MetricWithScore"]
        assert stats["score_average"] == 8.5
        assert stats["score_count"] == 2

        # 验证只有一个指标
        assert len(result.metrics_score_stats) == 1

    def test_summarize_calculates_score_averages(self):
        """测试 summarize 方法会自动调用 calculate_metrics_score_averages"""
        from dingo.io.output.summary_model import SummaryModel

        # 创建一个 summary
        summary = SummaryModel(
            task_name="test_task",
            total=10,
            num_good=8,
            num_bad=2
        )

        # 添加一些分数
        summary.add_metric_score("field1", "TestMetric1", 8.0)
        summary.add_metric_score("field1", "TestMetric1", 9.0)
        summary.add_metric_score("field1", "TestMetric2", 7.0)
        summary.add_metric_score("field1", "TestMetric2", 6.0)

        # 创建 executor 并调用 summarize
        executor = LocalExecutor({})
        result = executor.summarize(summary)

        # 验证统计已计算
        assert "field1" in result.metrics_score_stats
        assert "TestMetric1" in result.metrics_score_stats["field1"]
        assert "TestMetric2" in result.metrics_score_stats["field1"]

        # 验证 scores 列表已被删除（calculate_metrics_score_averages 会删除它）
        assert "scores" not in result.metrics_score_stats["field1"]["TestMetric1"]
        assert "scores" not in result.metrics_score_stats["field1"]["TestMetric2"]

        # 验证统计值正确
        assert result.metrics_score_stats["field1"]["TestMetric1"]["score_average"] == 8.5
        assert result.metrics_score_stats["field1"]["TestMetric2"]["score_average"] == 6.5
        assert result.get_metrics_score_overall_average("field1") == 7.5
