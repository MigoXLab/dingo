import concurrent.futures
import copy
import itertools
from more_itertools import batched
import json
import os
import time
import uuid
from tqdm import tqdm
from typing import Generator, Iterable, List, Optional, cast, Set

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
from tqdm import tqdm


@Executor.register('local')
class LocalExecutor(ExecProto):

    def __init__(self, input_args: InputArgs):
        self.input_args: InputArgs = input_args
        self.llm: Optional[BaseLLM] = None
        self.summary: SummaryModel = SummaryModel()
        self.bad_info_list: List[ResultInfo] = []
        self.good_info_list: List[ResultInfo] = []

        self.bad_info_index = 0
        self.good_info_index = 0
        self._dataset: Dataset | None = None

    def load_data(self) -> Generator[MetaData, None, None]:
        """
        Reads data from given path.

        **Run in executor.**

        Returns:
            Generator[MetaData]
        """
        datasource_cls = datasource_map[self.input_args.dataset]
        dataset_cls = dataset_map[self.input_args.dataset]

        datasource: DataSource = datasource_cls(input_args=self.input_args)
        dataset: Dataset = dataset_cls(source=datasource)
        self._dataset = dataset
        return dataset.get_data()

    def execute(self) -> List[SummaryModel]:
        log.setLevel(self.input_args.log_level)
        create_time = time.strftime('%Y%m%d_%H%M%S', time.localtime())
        Model.apply_config(self.input_args.custom_config, self.input_args.eval_group)
        input_path = self.input_args.input_path
        output_path = os.path.join(self.input_args.output_path, create_time + '_' + str(uuid.uuid1())[:8])

        log.debug(str(self.input_args.eval_group))
        for group_name in [self.input_args.eval_group]:
            if self.input_args.save_data:
                if not os.path.exists(output_path):
                    os.makedirs(output_path)
            if GlobalConfig.config and GlobalConfig.config.llm_config:
                for llm_name in GlobalConfig.config.llm_config:
                    self.llm = Model.get_llm(llm_name)

            self.summary = SummaryModel(
                task_id=str(uuid.uuid1()),
                task_name=self.input_args.task_name,
                eval_group=group_name,
                input_path=input_path,
                output_path=output_path if self.input_args.save_data else '',
                create_time=create_time,
                score=0,
                num_good=0,
                num_bad=0,
                total=0,
                type_ratio={},
                name_ratio={}
            )
            self.evaluate()
            self.summary = self.summarize(self.summary)
            self.summary.finish_time = time.strftime('%Y%m%d_%H%M%S', time.localtime())
            if self.input_args.save_data:
                self.save_data(output_path, self.input_args, self.bad_info_list[self.bad_info_index:], self.good_info_list[self.good_info_index:], self.summary)

        return [self.summary]

    def evaluate(self):
        """
        get score (main progres).
        Args:
            group (Any): _description_
            group_type (str): _description_
        """
        with concurrent.futures.ProcessPoolExecutor(max_workers=self.input_args.max_workers) as executor:
            data_iter = self.load_data()
            self._dataset = cast(Dataset, self._dataset)
            batched_iter = batched(itertools.islice(data_iter, self.input_args.start_index, None), self.input_args.batch_size)

            unfinished: Set[concurrent.futures.Future[List[ResultInfo]]] = set()
            stop = False
            bar = tqdm(unit="bytes", total=self._dataset.size, smoothing=0.05)

            while not stop or unfinished:
                while not stop and len(unfinished) < self.input_args.max_workers:
                    try:
                        batch = next(batched_iter)
                        unfinished.add(executor.submit(self._process_batch, batch, self.input_args.eval_group, self.llm, self.input_args.save_raw))
                    except StopIteration:
                        stop = True

                finished: Set[concurrent.futures.Future[List[ResultInfo]]]

                finished, unfinished = concurrent.futures.wait(unfinished, return_when=concurrent.futures.FIRST_COMPLETED)

                for future in finished:
                    results_info = future.result()
                    for result_info in results_info:
                        bar.update(result_info.size)
                        # calculate summary ratio
                        if result_info.error_status:
                            self.bad_info_list.append(result_info)
                            self.summary.num_bad += 1
                            for t in result_info.type_list:
                                if t not in self.summary.type_ratio:
                                    self.summary.type_ratio[t] = 1
                                else:
                                    self.summary.type_ratio[t] += 1
                            for n in result_info.name_list:
                                if n not in self.summary.name_ratio:
                                    self.summary.name_ratio[n] = 1
                                else:
                                    self.summary.name_ratio[n] += 1
                        else:
                            for result_info in results_info:
                                if self.input_args.save_correct:
                                    self.good_info_list.append(result_info)
                                    for t in result_info.type_list:
                                        if t not in self.summary.type_ratio:
                                            self.summary.type_ratio[t] = 1
                                        else:
                                            self.summary.type_ratio[t] += 1
                                    for n in result_info.name_list:
                                        if n not in self.summary.name_ratio:
                                            self.summary.name_ratio[n] = 1
                                        else:
                                            self.summary.name_ratio[n] += 1
                        self.summary.total += 1
        log.debug('[Summary]: ' + str(self.summary))

    @staticmethod
    def _process_batch(batch: Iterable[MetaData], eval_group: str, llm: BaseLLM | None, save_raw: bool) -> List[ResultInfo]:
        return [LocalExecutor.evaluate_single_data(eval_group, data, llm, save_raw) for data in batch]

    @staticmethod
    def evaluate_single_data(group_name, data: MetaData, llm: BaseLLM | None, save_raw: bool) -> ResultInfo:
        result_info = ResultInfo(data_id=data.data_id, prompt=data.prompt, content=data.content)
        if save_raw:
            result_info.raw_data = data.raw_data
        bad_type_list = []
        good_type_list = []
        bad_name_list = []
        good_name_list = []
        bad_reason_list = []
        good_reason_list = []
        for group_type, group in Model.get_group(group_name).items():
            if group_type == 'rule':
                r_i = LocalExecutor.evaluate_rule(group, data)
            elif group_type == 'prompt':
                r_i = LocalExecutor.evaluate_prompt(group, data, llm)
            else:
                raise RuntimeError(f'Unsupported group type: {group_type}')
            if r_i.error_status:
                result_info.error_status = True
                bad_type_list = bad_type_list + r_i.type_list
                bad_name_list = bad_name_list + r_i.name_list
                bad_reason_list = bad_reason_list + r_i.reason_list
            else:
                good_type_list = good_type_list + r_i.type_list
                good_name_list = good_name_list + r_i.name_list
                good_reason_list = good_reason_list + r_i.reason_list
        if result_info.error_status:
            result_info.type_list = list(set(bad_type_list))
            for name in bad_name_list:
                if name not in result_info.name_list:
                    result_info.name_list.append(name)
            for reason in bad_reason_list :
                if reason and reason not in result_info.reason_list:
                    result_info.reason_list.append(reason)
        else:
            result_info.type_list = list(set(good_type_list))
            for name in good_name_list:
                if name not in result_info.name_list:
                    result_info.name_list.append(name)
            for reason in good_reason_list:
                if reason and reason not in result_info.reason_list:
                    result_info.reason_list.append(reason)
        result_info.size = data.size
        return result_info

    @staticmethod
    def evaluate_rule(group: List[BaseRule], d: MetaData) -> ResultInfo:
        result_info = ResultInfo(data_id=d.data_id, prompt=d.prompt, content=d.content)
        log.debug("[RuleGroup]: " + str(group))
        bad_type_list = []
        good_type_list = []
        bad_name_list = []
        good_name_list = []
        bad_reason_list = []
        good_reason_list = []
        for r in group:
            # execute rule
            tmp: ModelRes = r.eval(d)
            # analyze result
            if tmp.error_status:
                result_info.error_status = True
                bad_type_list.append(tmp.type)
                bad_name_list.append(tmp.type + '-' + tmp.name)
                bad_reason_list.extend(tmp.reason)
            else:
                good_type_list.append(tmp.type)
                good_name_list.append(tmp.type + '-' + tmp.name)
                good_reason_list.extend(tmp.reason)
        if result_info.error_status:
            result_info.type_list = list(set(bad_type_list))
            result_info.name_list = bad_name_list
            result_info.reason_list = bad_reason_list
        else:
            result_info.type_list = list(set(good_type_list))
            result_info.name_list = good_name_list
            result_info.reason_list = good_reason_list
        return result_info

    @staticmethod
    def evaluate_prompt(group: List[BasePrompt], d: MetaData, llm: BaseLLM) -> ResultInfo:
        result_info = ResultInfo(data_id=d.data_id, prompt=d.prompt, content=d.content)
        log.debug("[PromptGroup]: " + str(group))
        bad_type_list = []
        good_type_list = []
        bad_name_list = []
        good_name_list = []
        bad_reason_list = []
        good_reason_list = []
        for p in group:
            llm.set_prompt(p)
            # execute prompt
            tmp: ModelRes = llm.call_api(d)
            # analyze result
            if tmp.error_status:
                result_info.error_status = True
                bad_type_list.append(tmp.type)
                bad_name_list.append(tmp.type + '-' + tmp.name)
                bad_reason_list.extend(tmp.reason)
            else:
                good_type_list.append(tmp.type)
                good_name_list.append(tmp.type + '-' + tmp.name)
                good_reason_list.extend(tmp.reason)
        if result_info.error_status:
            result_info.type_list = list(set(bad_type_list))
            result_info.name_list = bad_name_list
            result_info.reason_list = bad_reason_list
        else:
            result_info.type_list = list(set(good_type_list))
            result_info.name_list = good_name_list
            result_info.reason_list = good_reason_list
        return result_info

    def summarize(self, summary: SummaryModel) -> SummaryModel:
        new_summary = copy.deepcopy(summary)
        if new_summary.total == 0:
            return new_summary
        new_summary.num_good = new_summary.total - new_summary.num_bad
        new_summary.score = round(new_summary.num_good / new_summary.total * 100, 2)
        for t in new_summary.type_ratio:
            new_summary.type_ratio[t] = round(new_summary.type_ratio[t] / new_summary.total, 6)
        for n in new_summary.name_ratio:
            new_summary.name_ratio[n] = round(new_summary.name_ratio[n] / new_summary.total, 6)
        new_summary.type_ratio = dict(sorted(new_summary.type_ratio.items()))
        new_summary.name_ratio = dict(sorted(new_summary.name_ratio.items()))
        return new_summary

    def get_summary(self):
        return self.summary

    def get_bad_info_list(self):
        return self.bad_info_list

    def get_good_info_list(self):
        return self.good_info_list

    def save_data(
            self,
            path: str,
            input_args: InputArgs,
            bad_info_list: List[ResultInfo],
            good_info_list: List[ResultInfo],
            summary: SummaryModel,
    ):
        for result_info in bad_info_list:
            for new_name in result_info.name_list:
                t = str(new_name).split('-')[0]
                n = str(new_name).split('-')[1]
                p_t = os.path.join(path, t)
                if not os.path.exists(p_t):
                    os.makedirs(p_t)
                f_n = os.path.join(path, t, n) + ".jsonl"
                with open(f_n, 'a', encoding='utf-8') as f:
                    if input_args.save_raw:
                        str_json = json.dumps(result_info.to_raw_dict(), ensure_ascii=False)
                    else:
                        str_json = json.dumps(result_info.to_dict(), ensure_ascii=False)
                    f.write(str_json + '\n')
        if input_args.save_correct:
            for result_info in good_info_list:
                for new_name in result_info.name_list:
                    t = str(new_name).split('-')[0]
                    n = str(new_name).split('-')[1]
                    p_t = os.path.join(path, t)
                    if not os.path.exists(p_t):
                        os.makedirs(p_t)
                    f_n = os.path.join(path, t, n) + ".jsonl"
                    with open(f_n, 'a', encoding='utf-8') as f:
                        if input_args.save_raw:
                            str_json = json.dumps(result_info.to_raw_dict(), ensure_ascii=False)
                        else:
                            str_json = json.dumps(result_info.to_dict(), ensure_ascii=False)
                        f.write(str_json + '\n')

        with open(path + '/summary.json', 'w', encoding='utf-8') as f:
            json.dump(summary.to_dict(), f, indent=4, ensure_ascii=False)
