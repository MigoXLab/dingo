import concurrent.futures
import copy
import itertools
import json
import os
import time
import uuid
from typing import Generator, List, Optional

from tqdm import tqdm

from dingo.config import InputArgs
from dingo.config.input_args import EvalPipline
from dingo.data import Dataset, DataSource, dataset_map, datasource_map
from dingo.exec.base import ExecProto, Executor
from dingo.io import Data, ResultInfo, SummaryModel
from dingo.io.output.result_info import ResTypeInfo
from dingo.model import Model
from dingo.model.llm.base import BaseLLM
from dingo.model.modelres import ModelRes
from dingo.model.rule.base import BaseRule
from dingo.utils import log


@Executor.register("local")
class LocalExecutor(ExecProto):
    def __init__(self, input_args: InputArgs):
        self.input_args: InputArgs = input_args
        self.llm: Optional[BaseLLM] = None
        self.summary: SummaryModel = SummaryModel()

    def load_data(self) -> Generator[Data, None, None]:
        """
        Reads data from given path.

        **Run in executor.**

        Returns:
            Generator[Data]
        """
        datasource_cls = datasource_map[self.input_args.dataset.source]
        dataset_cls = dataset_map[self.input_args.dataset.source]

        datasource: DataSource = datasource_cls(input_args=self.input_args)
        dataset: Dataset = dataset_cls(source=datasource)
        return dataset.get_data()

    def execute(self) -> SummaryModel:
        log.setLevel(self.input_args.log_level)
        create_time = time.strftime("%Y%m%d_%H%M%S", time.localtime())
        input_path = self.input_args.input_path
        output_path = os.path.join(
            self.input_args.output_path, create_time + "_" + str(uuid.uuid1())[:8]
        )
        if self.input_args.executor.result_save.bad:
            if not os.path.exists(output_path):
                os.makedirs(output_path)

        self.summary = SummaryModel(
            task_id=str(uuid.uuid1()),
            task_name=self.input_args.task_name,
            input_path=input_path,
            output_path=output_path if self.input_args.executor.result_save.bad else "",
            create_time=create_time,
        )

        # Evaluate data
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=self.input_args.executor.max_workers
        ) as thread_executor, concurrent.futures.ProcessPoolExecutor(
            max_workers=self.input_args.executor.max_workers
        ) as process_executor:
            data_iter = self.load_data()
            data_iter = itertools.islice(
                data_iter,
                self.input_args.executor.start_index,
                self.input_args.executor.end_index if self.input_args.executor.end_index >= 0 else None,
            )
            pbar = tqdm(total=None, unit="items")

            track_id = 0
            while True:
                batch = list(itertools.islice(data_iter, self.input_args.executor.batch_size))
                if not batch:
                    break

                futures = []
                futures_results = []
                for data in batch:
                    track_id += 1
                    r_i = ResultInfo(track_id = str(track_id), raw_data = data.to_dict())
                    futures_results.append(r_i)

                    for e_p in self.input_args.evaluator:
                        if e_p.fields:
                            map_data = {k: data.to_dict().get(v) for k, v in e_p.fields.items()}
                        else:
                            map_data = data.to_dict()
                        eval_list_rule = [eval for eval in e_p.evals if eval.name in Model.rule_name_map]
                        eval_list_llm = [eval for eval in e_p.evals if eval.name in Model.llm_name_map]
                        # rule
                        if os.environ.get("LOCAL_DEPLOYMENT_MODE") == "true":
                            futures += [thread_executor.submit(self.evaluate_single_data, str(track_id), e_p.fields, 'rule', map_data, eval_list_rule)]
                        else:
                            futures += [process_executor.submit(self.evaluate_single_data, str(track_id), e_p.fields, 'rule', map_data, eval_list_rule)]
                        # llm
                        futures += [thread_executor.submit(self.evaluate_single_data, str(track_id), e_p.fields, 'llm', map_data, eval_list_llm)]

                for future in concurrent.futures.as_completed(futures):
                    result_info = future.result()
                    futures_results = self.merge_result_info(futures_results, result_info)

                for result_info in futures_results:
                    # 统计eval_details，第一层key是字段名组合，第二层value是ResTypeInfo
                    # 错误类型从ResTypeInfo.label中获取
                    for field_key, res_type_info in result_info.eval_details.items():
                        if field_key not in self.summary.type_ratio:
                            self.summary.type_ratio[field_key] = {}
                        # 遍历 ResTypeInfo.label 中的每个错误类型
                        # 兼容 dict 和 ResTypeInfo 对象两种情况
                        if isinstance(res_type_info, dict):
                            label_list = res_type_info.get('label', [])
                        else:
                            label_list = res_type_info.label

                        for eval_details_name in label_list:
                            if eval_details_name not in self.summary.type_ratio[field_key]:
                                self.summary.type_ratio[field_key][eval_details_name] = 1
                            else:
                                self.summary.type_ratio[field_key][eval_details_name] += 1

                    if result_info.eval_status:
                        self.summary.num_bad += 1
                    else:
                        self.summary.num_good += 1
                    self.summary.total += 1

                    self.write_single_data(
                        self.summary.output_path, self.input_args, result_info
                    )
                    pbar.update()
                self.write_summary(
                    self.summary.output_path,
                    self.input_args,
                    self.summarize(self.summary),
                )

        log.debug("[Summary]: " + str(self.summary))

        # Finalize summary
        self.summary = self.summarize(self.summary)
        self.write_summary(self.summary.output_path, self.input_args, self.summary)

        return self.summary

    def evaluate_single_data(self, track_id: str, eval_fields: dict, eval_type: str, map_data: dict, eval_list: list) -> ResultInfo:
        """
        Unified evaluation function for both rule and llm evaluation types.

        Args:
            track_id: Tracking ID for the data item
            eval_type: Type of evaluation ('rule' or 'llm')
            map_data: Mapped data fields
            eval_list: List of evaluations to perform

        Returns:
            ResultInfo containing evaluation results
        """
        result_info = ResultInfo(track_id=track_id)
        bad_eval_details = None
        good_eval_details = None

        for e_c_i in eval_list:
            # Get model class and instantiate
            if eval_type == 'rule':
                model_cls = Model.rule_name_map.get(e_c_i.name)
                model = model_cls()  # 实例化类为对象，避免多线程配置覆盖
                Model.set_config_rule(model, e_c_i.config)
            elif eval_type == 'llm':
                model_cls = Model.llm_name_map.get(e_c_i.name)
                model = model_cls()  # 实例化类为对象，避免多线程配置覆盖
                Model.set_config_llm(model, e_c_i.config)
            else:
                raise ValueError(f"Error eval_type: {eval_type}")

            # Execute evaluation
            tmp: ModelRes = model.eval(Data(**map_data))
            if isinstance(tmp.eval_details, dict):
                tmp.eval_details = ResTypeInfo(**tmp.eval_details)

            # Collect eval_details from ModelRes
            if tmp.eval_status:
                result_info.eval_status = True
                # 合并 bad 的 eval_details (ModelRes.eval_details 现在直接是 ResTypeInfo)
                if isinstance(bad_eval_details, dict):
                    bad_eval_details = ResTypeInfo(**bad_eval_details)
                if bad_eval_details:
                    bad_eval_details.merge(tmp.eval_details)
                else:
                    bad_eval_details = tmp.eval_details.copy()
            else:
                # 合并 good 的 eval_details (ModelRes.eval_details 现在直接是 ResTypeInfo)
                if isinstance(good_eval_details, dict):
                    good_eval_details = ResTypeInfo(**good_eval_details)
                if good_eval_details:
                    good_eval_details.merge(tmp.eval_details)
                else:
                    good_eval_details = tmp.eval_details.copy()

        # Set result_info fields based on all_labels configuration and add field
        join_fields = ','.join(eval_fields.values())

        if self.input_args.executor.result_save.all_labels:
            # Always include both good and bad results when they exist
            # The final eval_status is True if ANY evaluation failed
            # 合并 good 和 bad 的 eval_details (现在是 ResTypeInfo 对象)
            all_eval_details = None
            if bad_eval_details:
                all_eval_details = bad_eval_details.copy()
            if good_eval_details:
                if all_eval_details:
                    all_eval_details.merge(good_eval_details)
                else:
                    all_eval_details = good_eval_details.copy()
            # add field (ResultInfo.eval_details 现在是 Dict[str, ResTypeInfo])
            if all_eval_details:
                result_info.eval_details = {join_fields: all_eval_details}
        else:
            # add field (ResultInfo.eval_details 现在是 Dict[str, ResTypeInfo])
            if result_info.eval_status:
                if bad_eval_details:
                    result_info.eval_details = {join_fields: bad_eval_details}
            else:
                if good_eval_details and self.input_args.executor.result_save.good:
                    result_info.eval_details = {join_fields: good_eval_details}

        return result_info

    def merge_result_info(self, existing_list: List[ResultInfo], new_item: ResultInfo) -> List[ResultInfo]:
        existing_item = next((item for item in existing_list if item.track_id == new_item.track_id), None)

        if existing_item:
            existing_item.eval_status = existing_item.eval_status or new_item.eval_status

            # 合并 eval_details 字典（第一层是字段名，第二层直接是 ResTypeInfo）
            for key, value in new_item.eval_details.items():
                # 第一层是字段名，如果存在，则合并 ResTypeInfo
                if key in existing_item.eval_details:
                    existing_item.eval_details[key].merge(value)
                # 第一层是字段名，如果不存在，则创建副本
                else:
                    existing_item.eval_details[key] = value.copy()
        else:
            existing_list.append(new_item)

        return existing_list

    def summarize(self, summary: SummaryModel) -> SummaryModel:
        new_summary = copy.deepcopy(summary)
        if new_summary.total == 0:
            return new_summary
        new_summary.score = round(new_summary.num_good / new_summary.total * 100, 2)

        # type_ratio是两层结构：第一层是字段名，第二层是具体错误类型
        for field_name in new_summary.type_ratio:
            for eval_details in new_summary.type_ratio[field_name]:
                new_summary.type_ratio[field_name][eval_details] = round(
                    new_summary.type_ratio[field_name][eval_details] / new_summary.total, 6
                )

        new_summary.finish_time = time.strftime("%Y%m%d_%H%M%S", time.localtime())
        return new_summary

    def write_single_data(
        self, path: str, input_args: InputArgs, result_info: ResultInfo
    ):
        if not input_args.executor.result_save.bad:
            return

        if not input_args.executor.result_save.good and not result_info.eval_status:
            return

        # 遍历 eval_details 的第一层（字段名组合），第二层直接是 ResTypeInfo
        for field_name, res_type_info in result_info.eval_details.items():
            # 第一层：根据字段名创建文件夹
            field_dir = os.path.join(path, field_name)
            if not os.path.exists(field_dir):
                os.makedirs(field_dir)

            # 从 ResTypeInfo.label 中获取错误类型列表
            if isinstance(res_type_info, dict):
                label_list = res_type_info.get('label', [])
            else:
                label_list = res_type_info.label
            for eval_details_name in label_list:
                # 按点分割错误类型名称，创建多层文件夹
                # 例如: "validity_errors.space_issues" -> ["validity_errors", "space_issues"]
                parts = eval_details_name.split(".")

                # 除了最后一部分，其他部分都是文件夹
                if len(parts) > 1:
                    # 创建多层文件夹
                    folder_path = os.path.join(field_dir, *parts[:-1])
                    if not os.path.exists(folder_path):
                        os.makedirs(folder_path)
                    # 最后一部分作为文件名
                    file_name = parts[-1] + ".jsonl"
                    f_n = os.path.join(folder_path, file_name)
                else:
                    # 没有点分割，直接在字段文件夹下创建文件
                    f_n = os.path.join(field_dir, parts[0] + ".jsonl")

                with open(f_n, "a", encoding="utf-8") as f:
                    if input_args.executor.result_save.raw:
                        str_json = json.dumps(result_info.to_raw_dict(), ensure_ascii=False)
                    else:
                        str_json = json.dumps(result_info.to_dict(), ensure_ascii=False)
                    f.write(str_json + "\n")

    def write_summary(self, path: str, input_args: InputArgs, summary: SummaryModel):
        if not input_args.executor.result_save.bad:
            return
        with open(path + "/summary.json", "w", encoding="utf-8") as f:
            json.dump(summary.to_dict(), f, indent=4, ensure_ascii=False)

    def get_summary(self):
        return self.summary

    def get_info_list(self, high_quality: bool) -> list:
        info_list = []

        save_raw = self.input_args.executor.result_save.raw
        output_path = self.summary.output_path
        if not os.path.isdir(output_path):
            raise ValueError(f"output_path not exists: {output_path}")

        for root, dirs, files in os.walk(output_path):
            for file in files:
                file_path = os.path.join(root, file)
                file_name = file
                if file_name == "summary.json":
                    continue
                with open(file_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        data = json.loads(line.strip())

                        if save_raw:
                            eval_status = data['dingo_result']['eval_status']
                        else:
                            eval_status = data['eval_status']
                        if high_quality and not eval_status:
                            info_list.append(data)
                        if not high_quality and eval_status:
                            info_list.append(data)

        return info_list

    def get_bad_info_list(self):
        return self.get_info_list(high_quality=False)

    def get_good_info_list(self):
        return self.get_info_list(high_quality=True)
