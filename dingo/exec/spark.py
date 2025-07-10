import copy
import time
import uuid
from typing import Any, Dict, List, Optional

from pyspark import SparkConf
from pyspark.rdd import RDD
from pyspark.sql import SparkSession

from dingo.config import GlobalConfig
from dingo.exec.base import ExecProto, Executor
from dingo.io import Data, InputArgs, ResultInfo, SummaryModel
from dingo.model import Model
from dingo.model.llm.base import BaseLLM
from dingo.model.modelres import ModelRes
from dingo.model.prompt.base import BasePrompt
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
        self.llm: Optional[BaseLLM] = None
        self.group: Optional[Dict] = None
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

        # Initialize models and configuration
        Model.apply_config(self.input_args.custom_config, self.input_args.eval_group)
        self.group = Model.get_group(self.input_args.eval_group)

        if GlobalConfig.config and GlobalConfig.config.llm_config:
            for llm_name in GlobalConfig.config.llm_config:
                self.llm = Model.get_llm(llm_name)

        print("============= Init PySpark =============")
        spark, sc = self.initialize_spark()
        self._sc = sc
        print("============== Init Done ===============")

        try:
            # Load and process data
            data_rdd = self.load_data()
            total = data_rdd.count()

            # Apply configuration for Spark driver
            Model.apply_config_for_spark_driver(
                self.input_args.custom_config, self.input_args.eval_group
            )

            # Broadcast necessary objects to workers
            broadcast_group = sc.broadcast(self.group)
            broadcast_llm = sc.broadcast(self.llm) if self.llm else None

            # Evaluate data
            data_info_list = data_rdd.map(
                lambda x: self.evaluate_item(x, broadcast_group, broadcast_llm)
            ).persist()  # Cache the evaluated data for multiple uses

            # Filter and count bad/good items
            self.bad_info_list = data_info_list.filter(lambda x: x["error_status"])
            num_bad = self.bad_info_list.count()

            if self.input_args.save_correct:
                self.good_info_list = data_info_list.filter(
                    lambda x: not x["error_status"]
                )

            # Create summary
            self.summary = SummaryModel(
                task_id=str(uuid.uuid1()),
                task_name=self.input_args.task_name,
                eval_group=self.input_args.eval_group,
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
            if not self.input_args.save_data:
                self.cleanup(spark)
            else:
                self.spark_session = spark

    def evaluate(self):
        pass

    def evaluate_item(
        self, data_rdd_item, broadcast_group, broadcast_llm
    ) -> Dict[str, Any]:
        """Evaluate a single data item using broadcast variables."""
        data: Data = data_rdd_item
        result_info = ResultInfo(
            data_id=data.data_id, prompt=data.prompt, content=data.content
        )

        if self.input_args.save_raw:
            result_info.raw_data = data.raw_data

        group = broadcast_group.value
        llm = broadcast_llm.value if broadcast_llm else None

        bad_type_list = []
        good_type_list = []
        bad_name_list = []
        good_name_list = []
        bad_reason_list = []
        good_reason_list = []

        for group_type, group_items in group.items():
            if group_type == "rule":
                r_i = self.evaluate_rule(group_items, data)
            elif group_type == "prompt":
                r_i = self.evaluate_prompt(group_items, data, llm)
            else:
                raise RuntimeError(f"Unsupported group type: {group_type}")

            if r_i.error_status:
                result_info.error_status = True
                bad_type_list.extend(r_i.type_list)
                bad_name_list.extend(r_i.name_list)
                bad_reason_list.extend(r_i.reason_list)
            else:
                good_type_list.extend(r_i.type_list)
                good_name_list.extend(r_i.name_list)
                good_reason_list.extend(r_i.reason_list)

        # Process results
        target_list = bad_type_list if result_info.error_status else good_type_list
        result_info.type_list = list(set(target_list))

        target_names = bad_name_list if result_info.error_status else good_name_list
        result_info.name_list = list(
            dict.fromkeys(target_names)
        )  # Preserve order while removing duplicates

        target_reasons = (
            bad_reason_list if result_info.error_status else good_reason_list
        )
        result_info.reason_list = [
            r for r in target_reasons if r
        ]  # Filter out None/empty reasons

        return result_info.to_dict()

    def evaluate_rule(self, group: List[BaseRule], data: Data) -> ResultInfo:
        """Evaluate data against a group of rules."""
        result_info = ResultInfo(
            data_id=data.data_id, prompt=data.prompt, content=data.content
        )

        bad_type_list = []
        good_type_list = []
        bad_name_list = []
        good_name_list = []
        bad_reason_list = []
        good_reason_list = []

        for rule in group:
            res: ModelRes = rule.eval(data)

            if res.error_status:
                result_info.error_status = True
                bad_type_list.append(res.type)
                bad_name_list.append(f"{res.type}-{res.name}")
                bad_reason_list.extend(res.reason)
            else:
                good_type_list.append(res.type)
                good_name_list.append(f"{res.type}-{res.name}")
                good_reason_list.extend(res.reason)

        # Set results
        target_list = bad_type_list if result_info.error_status else good_type_list
        result_info.type_list = list(set(target_list))
        result_info.name_list = (
            bad_name_list if result_info.error_status else good_name_list
        )
        result_info.reason_list = (
            bad_reason_list if result_info.error_status else good_reason_list
        )

        return result_info

    def evaluate_prompt(
        self, group: List[BasePrompt], data: Data, llm: BaseLLM
    ) -> ResultInfo:
        """Evaluate data against a group of prompts using LLM."""
        if llm is None:
            raise ValueError("LLM is required for prompt evaluation")

        result_info = ResultInfo(
            data_id=data.data_id, prompt=data.prompt, content=data.content
        )

        bad_type_list = []
        good_type_list = []
        bad_name_list = []
        good_name_list = []
        bad_reason_list = []
        good_reason_list = []

        for prompt in group:
            llm.set_prompt(prompt)
            res: ModelRes = llm.eval(data)

            if res.error_status:
                result_info.error_status = True
                bad_type_list.append(res.type)
                bad_name_list.append(f"{res.type}-{res.name}")
                bad_reason_list.extend(res.reason)
            else:
                good_type_list.append(res.type)
                good_name_list.append(f"{res.type}-{res.name}")
                good_reason_list.extend(res.reason)

        # Set results
        target_list = bad_type_list if result_info.error_status else good_type_list
        result_info.type_list = list(set(target_list))
        result_info.name_list = (
            bad_name_list if result_info.error_status else good_name_list
        )
        result_info.reason_list = (
            bad_reason_list if result_info.error_status else good_reason_list
        )

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
            if not self.input_args.save_correct:
                return new_summary

        new_summary.type_ratio = collect_ratio(
            self.bad_info_list, "type_list", new_summary.total
        )
        new_summary.name_ratio = collect_ratio(
            self.bad_info_list, "name_list", new_summary.total
        )

        if self.input_args.save_correct:
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
        if self.input_args.save_raw:
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
        if self.input_args.save_raw:
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
