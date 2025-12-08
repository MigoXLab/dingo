import copy
import time
import uuid
from typing import Any, Dict, List, Optional

from pyspark import SparkConf
from pyspark.rdd import RDD
from pyspark.sql import SparkSession

from dingo.config import InputArgs
from dingo.exec.base import ExecProto, Executor
from dingo.io import Data, ResultInfo, SummaryModel
from dingo.model import Model
from dingo.model.llm.base import BaseLLM
from dingo.model.modelres import ModelRes
# from dingo.model.prompt.base import BasePrompt
from dingo.model.rule.base import BaseRule


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
        data: Data = data_rdd_item
        result_info = ResultInfo(raw_data = data.to_dict())

        for e_p in self.input_args.evaluator:
            if e_p.fields:
                map_data = {k: data.to_dict().get(v) for k, v in e_p.fields.items()}
            else:
                map_data = data.to_dict()
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
            for k,v in r_i.eval_details.items():
                if k not in result_info.eval_details:
                    result_info.eval_details[k] = v
                else:
                    result_info.eval_details[k].merge(v)

        return result_info.to_dict()

    def evaluate_item(self, eval_fields: dict, eval_type: str, map_data: dict, eval_list: list) -> ResultInfo:
        result_info = ResultInfo()
        bad_eval_details = None
        good_eval_details = None

        for e_c_i in eval_list:
            if eval_type == 'rule':
                model = Model.rule_name_map.get(e_c_i.name)
                Model.set_config_rule(model, e_c_i.config)
            elif eval_type == 'llm':
                model = Model.llm_name_map.get(e_c_i.name)
                Model.set_config_llm(model, e_c_i.config)
            else:
                raise ValueError(f"Error eval_type: {eval_type}")
            tmp: ModelRes = model.eval(Data(**map_data))
            # Collect eval_details from ModelRes
            if tmp.eval_status:
                result_info.eval_status = True
                if bad_eval_details:
                    bad_eval_details.merge(tmp.eval_details)
                else:
                    bad_eval_details = tmp.eval_details.copy()
            else:
                if good_eval_details:
                    good_eval_details.merge(tmp.eval_details)
                else:
                    good_eval_details = tmp.eval_details.copy()

        # Set result_info fields based on all_labels configuration and add field
        join_fields = ','.join(eval_fields.values())
        if self.input_args.executor.result_save.all_labels:
            all_eval_details = None
            if bad_eval_details:
                all_eval_details = bad_eval_details.copy()
            if good_eval_details:
                if all_eval_details:
                    all_eval_details.merge(good_eval_details)
                else:
                    all_eval_details = good_eval_details.copy()
            if all_eval_details:
                result_info.eval_details = {join_fields: all_eval_details}
        else:
            if result_info.eval_status:
                if bad_eval_details:
                    result_info.eval_details = {join_fields: bad_eval_details}
            else:
                if good_eval_details and self.input_args.executor.result_save.good:
                    result_info.eval_details = {join_fields: good_eval_details}
        return result_info

    def summarize(self, summary: SummaryModel) -> SummaryModel:
        """
        Summarize evaluation results and calculate type_ratio.

        统计所有评估结果中每个字段下每个 label 的出现次数，
        然后除以总数得到比例，填充到 summary.type_ratio 中。
        """
        new_summary = copy.deepcopy(summary)
        if new_summary.total == 0:
            return new_summary

        # 使用 Spark 聚合操作统计 eval_details
        # data_info_list 的每个元素是 Dict，包含 eval_details 字段
        def aggregate_eval_detailss(acc, item):
            """聚合单个 item 的 eval_details 到累加器中"""
            eval_details_dict = item.get('eval_details', {})

            # 遍历第一层：字段名
            for field_key, eval_detail_dict in eval_details_dict.items():
                if field_key not in acc:
                    acc[field_key] = {}

                # 从 EvalDetail 的 label 列表中获取错误类型
                label_list = eval_detail_dict.get('label', []) if isinstance(eval_detail_dict, dict) else eval_detail_dict.label

                # 统计每个 label 的出现次数
                for label in label_list:
                    if label not in acc[field_key]:
                        acc[field_key][label] = 1
                    else:
                        acc[field_key][label] += 1

            return acc

        def merge_eval_detailss(acc1, acc2):
            """合并两个累加器"""
            for field_key, label_dict in acc2.items():
                if field_key not in acc1:
                    acc1[field_key] = label_dict.copy()
                else:
                    for label, count in label_dict.items():
                        if label not in acc1[field_key]:
                            acc1[field_key][label] = count
                        else:
                            acc1[field_key][label] += count
            return acc1

        # 使用 aggregate 聚合所有 eval_details
        # data_info_list 在 execute 中已经被 persist() 并保存为实例变量
        if hasattr(self, 'data_info_list') and self.data_info_list:
            type_ratio_counts = self.data_info_list.aggregate(
                {},  # 初始累加器
                aggregate_eval_detailss,  # 聚合单个元素
                merge_eval_detailss  # 合并累加器
            )
        else:
            type_ratio_counts = {}

        # 将计数转换为比例
        new_summary.type_ratio = {}
        for field_name in type_ratio_counts:
            new_summary.type_ratio[field_name] = {}
            for eval_details in type_ratio_counts[field_name]:
                new_summary.type_ratio[field_name][eval_details] = round(
                    type_ratio_counts[field_name][eval_details] / new_summary.total, 6
                )

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
