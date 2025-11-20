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
        # self.llm: Optional[BaseLLM] = None
        # self.group: Optional[Dict] = None
        self.summary: Optional[SummaryModel] = None
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

            # Filter and count bad/good items
            self.bad_info_list = data_info_list.filter(lambda x: x["error_status"])
            num_bad = self.bad_info_list.count()

            if self.input_args.executor.result_save.good:
                self.good_info_list = data_info_list.filter(
                    lambda x: not x["error_status"]
                )

            # Create summary
            self.summary = SummaryModel(
                task_id=str(uuid.uuid1()),
                task_name=self.input_args.task_name,
                # eval_group=self.input_args.executor.eval_group,
                input_path=self.input_args.input_path if not self.spark_rdd else "",
                output_path="",
                create_time=create_time,
                score=round((total - num_bad) / total * 100, 2) if total > 0 else 0,
                num_good=total - num_bad,
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

            if r_i.error_status:
                result_info.error_status = True
            for k,v in r_i.error_type.items():
                if k not in result_info.error_type:
                    result_info.error_type[k] = v
                else:
                    result_info.error_type[k].merge(v)

        return result_info.to_dict()

    def evaluate_item(self, eval_fields: dict, eval_type: str, map_data: dict, eval_list: list) -> ResultInfo:
        result_info = ResultInfo()
        bad_error_type = None
        good_error_type = None

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
            # Collect error_type from ModelRes
            if tmp.error_status:
                result_info.error_status = True
                if bad_error_type:
                    bad_error_type.merge(tmp.error_type)
                else:
                    bad_error_type = tmp.error_type.copy()
            else:
                if good_error_type:
                    good_error_type.merge(tmp.error_type)
                else:
                    good_error_type = tmp.error_type.copy()

        # Set result_info fields based on all_labels configuration and add field
        join_fields = ','.join(eval_fields.values())
        if self.input_args.executor.result_save.all_labels:
            all_error_type = None
            if bad_error_type:
                all_error_type = bad_error_type.copy()
            if good_error_type:
                if all_error_type:
                    all_error_type.merge(good_error_type)
                else:
                    all_error_type = good_error_type.copy()
            if all_error_type:
                result_info.error_type = {join_fields: all_error_type}
        else:
            if result_info.error_status:
                if bad_error_type:
                    result_info.error_type = {join_fields: bad_error_type}
            else:
                if good_error_type and self.input_args.executor.result_save.good:
                    result_info.error_type = {join_fields: good_error_type}
        return result_info

    def summarize(self, summary: SummaryModel) -> SummaryModel:
        """Generate summary statistics from bad info list."""

        def collect_ratio(data_info_list, key_name: str, total_count: int):
            data_info_counts = (
                data_info_list.flatMap(lambda x: [(t, 1) for t in x[key_name]])
                .reduceByKey(lambda a, b: a + b)
                .collectAsMap()
            )
            return {k: round(v / total_count, 6) for k, v in data_info_counts.items()}

        new_summary = copy.deepcopy(self.summary)
        if not self.bad_info_list and not self.good_info_list:
            return new_summary
        if not self.bad_info_list and self.good_info_list:
            if not self.input_args.executor.result_save.good:
                return new_summary

        new_summary.type_ratio = collect_ratio(
            self.bad_info_list, "type_list", new_summary.total
        )
        new_summary.name_ratio = collect_ratio(
            self.bad_info_list, "name_list", new_summary.total
        )

        if self.input_args.executor.result_save.good:
            type_ratio_correct = collect_ratio(
                self.good_info_list, "type_list", new_summary.total
            )
            name_ratio_correct = collect_ratio(
                self.good_info_list, "name_list", new_summary.total
            )
            new_summary.type_ratio.update(type_ratio_correct)
            new_summary.name_ratio.update(name_ratio_correct)

        new_summary.type_ratio = dict(sorted(new_summary.type_ratio.items()))
        new_summary.name_ratio = dict(sorted(new_summary.name_ratio.items()))

        new_summary.finish_time = time.strftime("%Y%m%d_%H%M%S", time.localtime())
        return new_summary

    def get_summary(self):
        return self.summary

    def get_bad_info_list(self):
        if self.input_args.executor.result_save.raw:
            return self.bad_info_list.map(
                lambda x: {
                    **x["raw_data"],
                    "dingo_result": {
                        "error_status": x["error_status"],
                        "type_list": x["type_list"],
                        "name_list": x["name_list"],
                        "reason_list": x["reason_list"],
                    },
                }
            )
        return self.bad_info_list

    def get_good_info_list(self):
        if self.input_args.executor.result_save.raw:
            return self.good_info_list.map(
                lambda x: {
                    **x["raw_data"],
                    "dingo_result": {
                        "error_status": x["error_status"],
                        "type_list": x["type_list"],
                        "name_list": x["name_list"],
                        "reason_list": x["reason_list"],
                    },
                }
            )
        return self.good_info_list
