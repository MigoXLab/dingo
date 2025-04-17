import os
import time
import uuid
from typing import Any, Callable, Dict, Generator, List, Optional, Union

from dingo.config import GlobalConfig
from dingo.data import Dataset, DataSource, dataset_map, datasource_map
from dingo.exec.base import ExecProto, Executor
from dingo.io import InputArgs, MetaData, ResultInfo, SummaryModel
from dingo.model import Model
from dingo.model.llm.base import BaseLLM
from dingo.model.modelres import ModelRes
from dingo.model.prompt.base import BasePrompt
from dingo.model.rule.base import BaseRule
from dingo.utils import log
from pyspark import SparkConf, SparkContext
from pyspark.rdd import RDD
from pyspark.sql import DataFrame, Row, SparkSession


@Executor.register('spark')
class SparkExecutor(ExecProto):
    """
    Spark executor
    """

    def __init__(self, input_args: InputArgs,
                 spark_rdd: RDD = None,
                 spark_session: SparkSession = None,
                 spark_conf: SparkConf = None):
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
        del state['spark_session']
        del state['spark_rdd']
        del state['_sc']
        return state

    def __setstate__(self, state):
        self.__dict__.update(state)

    def _initialize_spark(self):
        """Initialize Spark session if not already provided."""
        if self.spark_session is not None:
            return self.spark_session, self.spark_session.sparkContext
        elif self.spark_conf is not None:
            spark = SparkSession.builder.config(conf=self.spark_conf).getOrCreate()
            return spark, spark.sparkContext
        else:
            raise ValueError('Both spark_session and spark_conf are None. Please provide one.')

    def load_data(self) -> RDD:
        """Load and return the RDD data."""
        return self.spark_rdd

    def execute(self) -> List[SummaryModel]:
        """Main execution method for Spark evaluation."""
        create_time = time.strftime('%Y%m%d_%H%M%S', time.localtime())

        # Initialize models and configuration
        Model.apply_config(self.input_args.custom_config, self.input_args.eval_group)
        self.group = Model.get_group(self.input_args.eval_group)

        if GlobalConfig.config and GlobalConfig.config.llm_config:
            for llm_name in GlobalConfig.config.llm_config:
                self.llm = Model.get_llm(llm_name)

        print("============= Init PySpark =============")
        spark, sc = self._initialize_spark()
        self._sc = sc
        print("============== Init Done ===============")

        try:
            # Load and process data
            data_rdd = self.load_data()
            total = data_rdd.count()

            # Apply configuration for Spark driver
            Model.apply_config_for_spark_driver(self.input_args.custom_config, self.input_args.eval_group)

            # Broadcast necessary objects to workers
            broadcast_group = sc.broadcast(self.group)
            broadcast_llm = sc.broadcast(self.llm) if self.llm else None

            # Evaluate data
            data_info_list = data_rdd.map(
                lambda x: self._evaluate_item(x, broadcast_group, broadcast_llm)
            ).persist()  # Cache the evaluated data for multiple uses

            # Filter and count bad/good items
            self.bad_info_list = data_info_list.filter(lambda x: x['error_status'])
            num_bad = self.bad_info_list.count()

            if self.input_args.save_correct:
                self.good_info_list = data_info_list.filter(lambda x: not x['error_status'])

            # Create summary
            self.summary = SummaryModel(
                task_id=str(uuid.uuid1()),
                task_name=self.input_args.task_name,
                eval_group=self.input_args.eval_group,
                input_path=self.input_args.input_path if not self.spark_rdd else '',
                output_path='',
                create_time=create_time,
                score=round((total - num_bad) / total * 100, 2) if total > 0 else 0,
                num_good=total - num_bad,
                num_bad=num_bad,
                total=total,
                type_ratio={},
                name_ratio={}
            )
            # Generate detailed summary
            self._summarize_results()

            self.summary.finish_time = time.strftime('%Y%m%d_%H%M%S', time.localtime())

            return [self.summary]

        except Exception as e:
            raise e
        finally:
            if not self.input_args.save_data:
                self._cleanup(spark)
            else:
                self.spark_session = spark

    def _evaluate_item(self, data_rdd_item, broadcast_group, broadcast_llm) -> Dict[str, Any]:
        """Evaluate a single data item using broadcast variables."""
        data: MetaData = data_rdd_item
        result_info = ResultInfo(data_id=data.data_id, prompt=data.prompt, content=data.content)

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
            if group_type == 'rule':
                r_i = self._evaluate_rule(group_items, data)
            elif group_type == 'prompt':
                r_i = self._evaluate_prompt(group_items, data, llm)
            else:
                raise RuntimeError(f'Unsupported group type: {group_type}')

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
        result_info.name_list = list(dict.fromkeys(target_names))  # Preserve order while removing duplicates

        target_reasons = bad_reason_list if result_info.error_status else good_reason_list
        result_info.reason_list = [r for r in target_reasons if r]  # Filter out None/empty reasons

        return result_info.to_dict()

    def _evaluate_rule(self, group: List[BaseRule], data: MetaData) -> ResultInfo:
        """Evaluate data against a group of rules."""
        result_info = ResultInfo(data_id=data.data_id, prompt=data.prompt, content=data.content)

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
        result_info.name_list = bad_name_list if result_info.error_status else good_name_list
        result_info.reason_list = bad_reason_list if result_info.error_status else good_reason_list

        return result_info

    def _evaluate_prompt(self, group: List[BasePrompt], data: MetaData, llm: BaseLLM) -> ResultInfo:
        """Evaluate data against a group of prompts using LLM."""
        if llm is None:
            raise ValueError("LLM is required for prompt evaluation")

        result_info = ResultInfo(data_id=data.data_id, prompt=data.prompt, content=data.content)

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
        result_info.name_list = bad_name_list if result_info.error_status else good_name_list
        result_info.reason_list = bad_reason_list if result_info.error_status else good_reason_list

        return result_info

    def _summarize_results(self):
        """Generate summary statistics from bad info list."""
        if not self.bad_info_list:
            return

        # Calculate type ratios
        type_counts = (
            self.bad_info_list
            .flatMap(lambda x: [(t, 1) for t in x['type_list']])
            .reduceByKey(lambda a, b: a + b)
            .collectAsMap()
        )
        self.summary.type_ratio = {
            k: round(v / self.summary.total, 6)
            for k, v in type_counts.items()
        }

        # Calculate name ratios
        name_counts = (
            self.bad_info_list
            .flatMap(lambda x: [(n, 1) for n in x['name_list']])
            .reduceByKey(lambda a, b: a + b)
            .collectAsMap()
        )
        self.summary.name_ratio = {
            k: round(v / self.summary.total, 6)
            for k, v in name_counts.items()
        }

        self.summary.type_ratio = dict(sorted(self.summary.type_ratio.items()))
        self.summary.name_ratio = dict(sorted(self.summary.name_ratio.items()))

    def get_summary(self):
        return self.summary

    def get_bad_info_list(self):
        if self.input_args.save_raw:
            return self.bad_info_list.map(lambda x: {
                **x['raw_data'],
                'dingo_result': {
                    'error_status': x['error_status'],
                    'type_list': x['type_list'],
                    'name_list': x['name_list'],
                    'reason_list': x['reason_list']
                }
            })
        return self.bad_info_list

    def get_good_info_list(self):
        if self.input_args.save_raw:
            return self.good_info_list.map(lambda x: {
                **x['raw_data'],
                'dingo_result': {
                    'error_status': x['error_status'],
                    'type_list': x['type_list'],
                    'name_list': x['name_list'],
                    'reason_list': x['reason_list']
                }
            })
        return self.good_info_list

    def save_data(self, start_time):
        """Save output data to specified path."""
        output_path = os.path.join(self.input_args.output_path, start_time)
        model_path = os.path.join(output_path, self.input_args.eval_group)
        os.makedirs(model_path, exist_ok=True)

    def _cleanup(self, spark):
        """Clean up Spark resources."""
        if spark:
            spark.stop()
            if spark.sparkContext:
                spark.sparkContext.stop()
