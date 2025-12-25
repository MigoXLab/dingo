import copy
import time
import uuid
from typing import Any, Dict, Optional

from pyspark import SparkConf
from pyspark.rdd import RDD
from pyspark.sql import SparkSession

from dingo.config import InputArgs
from dingo.exec.base import ExecProto, Executor
from dingo.io import Data, ResultInfo, SummaryModel
from dingo.io.output.eval_detail import EvalDetail
from dingo.model import Model

# from dingo.model.prompt.base import BasePrompt


@Executor.register("spark")
class SparkExecutor(ExecProto):
    """
    Spark executor
    """

    def __init__(
        self,
        input_args: InputArgs,
        spark_rdd: RDD = None,
        spark_session: SparkSession = None,
        spark_conf: SparkConf = None,
    ):
        # Evaluation parameters
        self.summary: Optional[SummaryModel] = None
        self.data_info_list: Optional[RDD] = None
        self.bad_info_list: Optional[RDD] = None
        self.good_info_list: Optional[RDD] = None

        # Initialization parameters
        self.input_args = input_args
        self.spark_rdd = spark_rdd
        self.spark_session = spark_session
        self.spark_conf = spark_conf
        self._sc = None  # SparkContext placeholder

    def __getstate__(self):
        """Custom serialization to exclude non-serializable Spark objects."""
        state = self.__dict__.copy()
        del state["spark_session"]
        del state["spark_rdd"]
        del state["_sc"]
        return state

    def __setstate__(self, state):
        self.__dict__.update(state)

    def initialize_spark(self):
        """Initialize Spark session if not already provided."""
        if self.spark_session is not None:
            return self.spark_session, self.spark_session.sparkContext
        elif self.spark_conf is not None:
            spark = SparkSession.builder.config(conf=self.spark_conf).getOrCreate()
            return spark, spark.sparkContext
        else:
            raise ValueError(
                "Both spark_session and spark_conf are None. Please provide one."
            )

    def cleanup(self, spark):
        """Clean up Spark resources."""
        if spark:
            spark.stop()
            if spark.sparkContext:
                spark.sparkContext.stop()

    def load_data(self) -> RDD:
        """Load and return the RDD data."""
        return self.spark_rdd

    @staticmethod
    def _aggregate_eval_details(acc, item):
        """聚合单个 item 的 eval_details 到累加器中，同时收集 scores"""
        eval_details_dict = item.get('eval_details', {})

        # 遍历第一层：字段名，第二层是 List[EvalDetail] (序列化为 list of dicts)
        for field_key, eval_detail_list in eval_details_dict.items():
            # 初始化字段的统计数据
            if field_key not in acc['label_counts']:
                acc['label_counts'][field_key] = {}
            if field_key not in acc['metric_scores']:
                acc['metric_scores'][field_key] = {}

            # 遍历 List[EvalDetail]，同时收集指标分数和标签
            label_set = set()
            for eval_detail in eval_detail_list:
                # 收集指标分数（用于RAG等评估场景，按 field_key 分组）
                score = eval_detail.get('score') if isinstance(eval_detail, dict) else getattr(eval_detail, 'score', None)
                metric = eval_detail.get('metric') if isinstance(eval_detail, dict) else getattr(eval_detail, 'metric', None)

                if score is not None and metric:
                    if metric not in acc['metric_scores'][field_key]:
                        acc['metric_scores'][field_key][metric] = []
                    acc['metric_scores'][field_key][metric].append(score)

                # 收集标签统计（使用 set 去重，避免同一 item 中重复 label 多次计数）
                label_list = eval_detail.get('label', []) if isinstance(eval_detail, dict) else getattr(eval_detail, 'label', [])
                if label_list:
                    for label in label_list:
                        label_set.add(label)

            # 对该 item 的每个唯一 label 计数 +1
            for label in label_set:
                if label not in acc['label_counts'][field_key]:
                    acc['label_counts'][field_key][label] = 1
                else:
                    acc['label_counts'][field_key][label] += 1

        return acc

    @staticmethod
    def _merge_eval_details(acc1, acc2):
        """合并两个累加器"""
        # 合并 label 统计
        for field_key, label_dict in acc2['label_counts'].items():
            if field_key not in acc1['label_counts']:
                acc1['label_counts'][field_key] = label_dict.copy()
            else:
                for label, count in label_dict.items():
                    if label not in acc1['label_counts'][field_key]:
                        acc1['label_counts'][field_key][label] = count
                    else:
                        acc1['label_counts'][field_key][label] += count

        # 合并 metric scores（按 field_key 分组）
        for field_key, metrics_dict in acc2['metric_scores'].items():
            if field_key not in acc1['metric_scores']:
                acc1['metric_scores'][field_key] = {}
            for metric, scores in metrics_dict.items():
                if metric not in acc1['metric_scores'][field_key]:
                    acc1['metric_scores'][field_key][metric] = scores.copy()
                else:
                    acc1['metric_scores'][field_key][metric].extend(scores)

        return acc1

    def execute(self) -> SummaryModel:
        """Main execution method for Spark evaluation."""
        create_time = time.strftime("%Y%m%d_%H%M%S", time.localtime())

        print("============= Init PySpark =============")
        spark, sc = self.initialize_spark()
        self._sc = sc
        print("============== Init Done ===============")

        try:
            # Load and process data
            data_rdd = self.load_data()
            total = data_rdd.count()

            # Evaluate data
            data_info_list = data_rdd.map(
                lambda x: self.evaluate(x)
            ).persist()  # Cache the evaluated data for multiple uses

            # Save data_info_list as instance variable for summarize method
            self.data_info_list = data_info_list

            # Filter and count bad/good items
            self.bad_info_list = data_info_list.filter(lambda x: x["eval_status"])

            if self.input_args.executor.result_save.good:
                self.good_info_list = data_info_list.filter(
                    lambda x: not x["eval_status"]
                )

            num_bad = self.bad_info_list.count()
            num_good = total - num_bad
            # Create summary
            self.summary = SummaryModel(
                task_id=str(uuid.uuid1()),
                task_name=self.input_args.task_name,
                # eval_group=self.input_args.executor.eval_group,
                input_path=self.input_args.input_path if not self.spark_rdd else "",
                output_path="",
                create_time=create_time,
                score=round((total - num_bad) / total * 100, 2) if total > 0 else 0,
                num_good=num_good,
                num_bad=num_bad,
                total=total,
            )
            # Generate detailed summary
            self.summary = self.summarize(self.summary)
            return self.summary

        except Exception as e:
            raise e
        finally:
            if not self.input_args.executor.result_save.bad:
                self.cleanup(spark)
            else:
                self.spark_session = spark

    def evaluate(self, data_rdd_item) -> Dict[str, Any]:
        """Evaluate a single data item using broadcast variables."""
        data: Data = data_rdd_item.asDict()
        result_info = ResultInfo(raw_data = data)

        for e_p in self.input_args.evaluator:
            if e_p.fields:
                map_data = {k: data.get(v) for k, v in e_p.fields.items()}
            else:
                map_data = data
            eval_list_rule = [eval for eval in e_p.evals if eval.name in Model.rule_name_map]
            eval_list_llm = [eval for eval in e_p.evals if eval.name in Model.llm_name_map]
            for eval_type in ["rule", "llm"]:
                if eval_type == 'rule':
                    r_i: ResultInfo = self.evaluate_item(e_p.fields, eval_type, map_data, eval_list_rule)
                elif eval_type == 'llm':
                    r_i: ResultInfo = self.evaluate_item(e_p.fields, eval_type, map_data, eval_list_llm)
                else:
                    raise ValueError(f"Error eval_type: {eval_type}")

                if r_i.eval_status:
                    result_info.eval_status = True
                # Merge eval_details: Dict[str, List[EvalDetail]]
                for k, v in r_i.eval_details.items():
                    if k not in result_info.eval_details:
                        result_info.eval_details[k] = v
                    else:
                        result_info.eval_details[k].extend(v)

        return result_info.to_dict()

    def evaluate_item(self, eval_fields: dict, eval_type: str, map_data: dict, eval_list: list) -> ResultInfo:
        result_info = ResultInfo()
        eval_detail_list = []

        for e_c_i in eval_list:
            if eval_type == 'rule':
                model = Model.rule_name_map.get(e_c_i.name)
                Model.set_config_rule(model, e_c_i.config)
            elif eval_type == 'llm':
                model = Model.llm_name_map.get(e_c_i.name)
                Model.set_config_llm(model, e_c_i.config)
            else:
                raise ValueError(f"Error eval_type: {eval_type}")

            tmp: EvalDetail = model.eval(Data(**map_data))
            eval_detail_list.append(tmp)

            # If any EvalDetail's status is True, result_info.eval_status is True
            if tmp.status:
                result_info.eval_status = True

        # Set result_info fields
        join_fields = ','.join(eval_fields.values()) if eval_fields else 'default'

        # Decide which results to save based on configuration
        if self.input_args.executor.result_save.all_labels:
            # Save all results
            if eval_detail_list:
                result_info.eval_details = {join_fields: eval_detail_list}
        else:
            # Only save bad or good results
            if result_info.eval_status:
                # Has bad results, only keep EvalDetail with status=True
                result_info.eval_details = {join_fields: [ed for ed in eval_detail_list if ed.status]}
            else:
                # All good results, decide whether to save based on configuration
                if self.input_args.executor.result_save.good:
                    result_info.eval_details = {join_fields: [ed for ed in eval_detail_list if not ed.status]}

        return result_info

    def summarize(self, summary: SummaryModel) -> SummaryModel:
        """
        Summarize evaluation results and calculate type_ratio.

        统计所有评估结果中每个字段下每个 label 的出现次数，
        然后除以总数得到比例，填充到 summary.type_ratio 中。
        同时收集指标分数用于统计。
        """
        new_summary = copy.deepcopy(summary)
        if new_summary.total == 0:
            return new_summary

        # 使用 Spark 聚合操作统计 eval_details 和收集 scores
        # data_info_list 的每个元素是 Dict，包含 eval_details 字段
        if hasattr(self, 'data_info_list') and self.data_info_list:
            aggregated_results = self.data_info_list.aggregate(
                {'label_counts': {}, 'metric_scores': {}},  # 初始累加器
                SparkExecutor._aggregate_eval_details,  # 聚合单个元素
                SparkExecutor._merge_eval_details  # 合并累加器
            )
            type_ratio_counts = aggregated_results['label_counts']
            metric_scores = aggregated_results['metric_scores']
        else:
            type_ratio_counts = {}
            metric_scores = {}

        # 将计数转换为比例
        new_summary.type_ratio = {}
        for field_name in type_ratio_counts:
            new_summary.type_ratio[field_name] = {}
            for eval_details in type_ratio_counts[field_name]:
                new_summary.type_ratio[field_name][eval_details] = round(
                    type_ratio_counts[field_name][eval_details] / new_summary.total, 6
                )

        # 添加收集到的 metric scores 到 summary（按 field_key 分组）
        for field_key, metrics in metric_scores.items():
            for metric_name, scores in metrics.items():
                for score in scores:
                    new_summary.add_metric_score(field_key, metric_name, score)

        # 计算 metrics 的平均分等统计信息
        new_summary.calculate_metrics_score_averages()

        new_summary.finish_time = time.strftime("%Y%m%d_%H%M%S", time.localtime())
        return new_summary

    def get_summary(self):
        return self.summary

    def get_bad_info_list(self):
        """
        获取所有 eval_status 为 True 的数据列表
        Returns:
            RDD: 包含所有 bad 数据的 RDD，每条数据是 ResultInfo 的字典形式
        """
        return self.bad_info_list

    def get_good_info_list(self):
        """
        获取所有 eval_status 为 False 的数据列表
        Returns:
            RDD: 包含所有 good 数据的 RDD，每条数据是 ResultInfo 的字典形式
        """
        return self.good_info_list
