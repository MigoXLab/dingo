import concurrent.futures
import copy
import itertools
import json
import os
import subprocess
import sys
import time
import uuid
from typing import Generator, List, Optional

from tqdm import tqdm

from dingo.config import InputArgs
from dingo.data import Dataset, DataSource, dataset_map, datasource_map
from dingo.exec.base import ExecProto, Executor
from dingo.io import Data, ResultInfo, SummaryModel
from dingo.io.output.eval_detail import EvalDetail
from dingo.model import Model
from dingo.model.llm.base import BaseLLM
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

            dingo_id = 0
            while True:
                batch = list(itertools.islice(data_iter, self.input_args.executor.batch_size))
                if not batch:
                    break

                futures = []
                futures_results = []
                for data in batch:
                    dingo_id += 1
                    r_i = ResultInfo(dingo_id = str(dingo_id), raw_data = data.to_dict())
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
                            futures += [thread_executor.submit(self.evaluate_single_data, str(dingo_id), e_p.fields, 'rule', map_data, eval_list_rule)]
                        else:
                            futures += [process_executor.submit(self.evaluate_single_data, str(dingo_id), e_p.fields, 'rule', map_data, eval_list_rule)]
                        # llm
                        futures += [thread_executor.submit(self.evaluate_single_data, str(dingo_id), e_p.fields, 'llm', map_data, eval_list_llm)]

                for future in concurrent.futures.as_completed(futures):
                    result_info = future.result()
                    futures_results = self.merge_result_info(futures_results, result_info)

                for result_info in futures_results:
                    # 统计eval_details，第一层key是字段名组合，第二层value是List[EvalDetail]
                    # 错误类型从EvalDetail.label中获取
                    for field_key, eval_detail_list in result_info.eval_details.items():
                        if field_key not in self.summary.type_ratio:
                            self.summary.type_ratio[field_key] = {}

                        # 遍历 List[EvalDetail]，同时收集指标分数和标签
                        label_set = set()
                        for eval_detail in eval_detail_list:
                            # 收集指标分数（按 field_key 分组）
                            if eval_detail.score is not None and eval_detail.metric:
                                self.summary.add_metric_score(field_key, eval_detail.metric, eval_detail.score)

                            # 收集标签统计
                            label_list = eval_detail.label if eval_detail.label else []
                            for label in label_list:
                                label_set.add(label)

                        for label in label_set:
                            self.summary.type_ratio[field_key].setdefault(label, 0)
                            self.summary.type_ratio[field_key][label] += 1

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

        # Open browser if use_browser is True
        if self.input_args.use_browser:
            try:
                # 使用 sys.executable 获取当前 Python 解释器路径
                # 将命令作为列表传递，避免 shell 注入风险
                cmd = [sys.executable, "-m", "dingo.run.vsl", "--input", self.summary.output_path]
                log.warning(f"Opening browser with command: {' '.join(cmd)}")

                # 使用 subprocess.Popen 在后台启动服务器
                # start_new_session=True 让子进程独立运行，不受父进程退出影响
                # stdout/stderr=DEVNULL 避免管道缓冲区死锁问题
                subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True
                )

                # 给服务器一点时间启动
                time.sleep(1)
                log.warning("Browser server started in background")
            except Exception as e:
                log.warning(f"Failed to open browser: {e}")

        return self.summary

    def evaluate_single_data(self, dingo_id: str, eval_fields: dict, eval_type: str, map_data: dict, eval_list: list) -> ResultInfo:
        """
        Unified evaluation function for both rule and llm evaluation types.

        Args:
            dingo_id: Tracking ID for the data item
            eval_type: Type of evaluation ('rule' or 'llm')
            map_data: Mapped data fields
            eval_list: List of evaluations to perform

        Returns:
            ResultInfo containing evaluation results
        """
        result_info = ResultInfo(dingo_id=dingo_id)
        eval_detail_list = []

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
            tmp: EvalDetail = model.eval(Data(**map_data))

            # 直接添加EvalDetail到列表中，不再merge
            eval_detail_list.append(tmp)

            # 如果任意一个EvalDetail的status为True，则result_info.eval_status为True
            if tmp.status:
                result_info.eval_status = True

        # Set result_info fields
        join_fields = ','.join(eval_fields.values()) if eval_fields else 'default'

        # 根据配置决定保存哪些结果
        if self.input_args.executor.result_save.all_labels:
            # 保存所有结果
            if eval_detail_list:
                result_info.eval_details = {join_fields: eval_detail_list}
        else:
            # 只保存bad或good的结果
            if result_info.eval_status:
                # 有bad结果，只保留status=True的EvalDetail
                result_info.eval_details = {join_fields: [mr for mr in eval_detail_list if mr.status]}
            else:
                # 都是good结果，根据配置决定是否保存，只保留status=False的EvalDetail
                if self.input_args.executor.result_save.good:
                    result_info.eval_details = {join_fields: [mr for mr in eval_detail_list if not mr.status]}

        return result_info

    def merge_result_info(self, existing_list: List[ResultInfo], new_item: ResultInfo) -> List[ResultInfo]:
        existing_item = next((item for item in existing_list if item.dingo_id == new_item.dingo_id), None)

        if existing_item:
            existing_item.eval_status = existing_item.eval_status or new_item.eval_status

            # 合并 eval_details 字典（第一层是字段名，第二层是List[EvalDetail]）
            for key, value in new_item.eval_details.items():
                # 第一层是字段名，如果存在，则extend List[EvalDetail]
                if key in existing_item.eval_details:
                    existing_item.eval_details[key].extend(value)
                # 第一层是字段名，如果不存在，则直接赋值
                else:
                    existing_item.eval_details[key] = value
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

        # 计算指标分数的平均值、最小值、最大值、标准差等
        new_summary.calculate_metrics_score_averages()

        new_summary.finish_time = time.strftime("%Y%m%d_%H%M%S", time.localtime())
        return new_summary

    def write_single_data(
        self, path: str, input_args: InputArgs, result_info: ResultInfo
    ):
        if not input_args.executor.result_save.bad:
            return

        if not input_args.executor.result_save.good and not result_info.eval_status:
            return

        # 用集合记录已经写过的(字段名, label名)组合，避免重复写入
        written_labels = set()

        # 遍历 eval_details 的第一层（字段名组合），第二层是List[EvalDetail]
        for field_name, eval_detail_list in result_info.eval_details.items():
            # 第一层：根据字段名创建文件夹
            field_dir = os.path.join(path, field_name)
            if not os.path.exists(field_dir):
                os.makedirs(field_dir)

            # 遍历 List[EvalDetail]
            for eval_detail in eval_detail_list:
                # 从 EvalDetail.label 中获取错误类型列表
                label_list = eval_detail.label if eval_detail.label else []

                for eval_details_name in label_list:
                    # 检查是否已经写过这个(字段名, label名)组合
                    label_key = (field_name, eval_details_name)
                    if label_key in written_labels:
                        continue

                    # 标记为已写入
                    written_labels.add(label_key)

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
