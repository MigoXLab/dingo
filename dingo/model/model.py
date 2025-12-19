import importlib
import inspect
import os
from typing import Callable, Dict, List, Optional

from pydantic import BaseModel

from dingo.config import InputArgs
from dingo.config.input_args import EvaluatorLLMArgs, EvaluatorRuleArgs
from dingo.model.llm.base import BaseLLM
from dingo.model.rule.base import BaseRule
from dingo.utils import log


class BaseEvalModel(BaseModel):
    name: str
    type: str


class Model:
    input_args: InputArgs
    module_loaded = False

    # group
    rule_groups: Dict[str, List[Callable]] = {}  # such as: {'default': [<class.RuleAlphaWords>]}

    # metric map
    rule_metric_type_map: Dict[str, List[Callable]] = {}   # such as: {'QUALITY_INEFFECTIVENESS': [<class.RuleAlphaWords>]}

    # other map
    rule_name_map: Dict[str, BaseRule] = {}  # such as: {'RuleAlphaWords': <class.RuleAlphaWords>}
    llm_name_map: Dict[str, BaseLLM] = {}

    def __init__(self):
        return

    @classmethod
    def get_rule_groups(cls):
        return cls.rule_groups

    @classmethod
    def get_rule_metric_type_map(cls):
        return cls.rule_metric_type_map

    @classmethod
    def get_rule_name_map(cls):
        return cls.rule_name_map

    @classmethod
    def get_llm_name_map(cls):
        return cls.llm_name_map

    @classmethod
    def get_rule_by_name(cls, name: str) -> BaseRule:
        return cls.rule_name_map[name]

    def get_llm_by_name(cls, name: str) -> BaseLLM:
        return cls.llm_name_map[name]

    @classmethod
    def get_group(cls, group_name) -> Dict[str, List]:
        res = {}
        if group_name not in Model.rule_groups:
            raise KeyError('no such group: ' + group_name)
        if group_name in Model.rule_groups:
            log.debug(f"[Load rule group {group_name}]")
            res['rule'] = Model.rule_groups[group_name]
        return res

    @classmethod
    def rule_register(cls, metric_type: str, group: List[str]) -> Callable:
        """
        Register a model. (register)
        Args:
            metric_type (str): The metric type (quality map).
            group (List[str]): The group names.
        """
        def decorator(root_class):
            # group
            for group_name in group:
                if group_name not in cls.rule_groups:
                    cls.rule_groups[group_name] = []
                cls.rule_groups[group_name].append(root_class)
            cls.rule_name_map[root_class.__name__] = root_class
            root_class.group = group

            # metric_type
            if metric_type not in cls.rule_metric_type_map:
                cls.rule_metric_type_map[metric_type] = []
            cls.rule_metric_type_map[metric_type].append(root_class)
            root_class.metric_type = metric_type

            return root_class

        return decorator

    @classmethod
    def llm_register(cls, llm_id: str) -> Callable:
        """
        Register a model. (register)
        Args:
            llm_id (str): Name of llm model class.
        """
        def decorator(root_class):
            cls.llm_name_map[llm_id] = root_class

            if inspect.isclass(root_class):
                return root_class
            else:
                raise ValueError("root_class must be a class")

        return decorator

    @classmethod
    def load_model(cls):
        if cls.module_loaded:
            return
        this_module_directory = os.path.dirname(os.path.abspath(__file__))
        # rule auto register
        for file in os.listdir(os.path.join(this_module_directory, 'rule')):
            path = os.path.join(this_module_directory, 'rule', file)
            if os.path.isfile(path) and file.endswith('.py') and not file == '__init__.py':
                try:
                    importlib.import_module('dingo.model.rule.' + file.split('.')[0])
                except ModuleNotFoundError as e:
                    log.debug(e)

        # llm auto register - 递归扫描子目录
        llm_base_dir = os.path.join(this_module_directory, 'llm')
        for root, dirs, files in os.walk(llm_base_dir):
            # 跳过 __pycache__ 目录
            dirs[:] = [d for d in dirs if d != '__pycache__']

            for file in files:
                if file.endswith('.py') and file != '__init__.py':
                    # 计算相对于 llm 目录的模块路径
                    rel_path = os.path.relpath(root, llm_base_dir)
                    if rel_path == '.':
                        module_name = f'dingo.model.llm.{file[:-3]}'
                    else:
                        # 将路径分隔符转换为点
                        rel_module = rel_path.replace(os.sep, '.')
                        module_name = f'dingo.model.llm.{rel_module}.{file[:-3]}'

                    try:
                        importlib.import_module(module_name)
                    except ModuleNotFoundError as e:
                        log.debug(e)
                    except ImportError as e:
                        log.debug("=" * 30 + " ImportError " + "=" * 30)
                        log.debug(f'module {module_name} not imported because: \n{e}')
                        log.debug("=" * 73)

        cls.module_loaded = True

    @classmethod
    def set_config_rule(cls, rule: BaseRule, rule_config: EvaluatorRuleArgs):
        if not rule_config:
            return
        config_default = getattr(rule, 'dynamic_config')
        # Iterate over rule_config fields using Pydantic's model_dump()
        for k, v in rule_config.model_dump().items():
            if v is not None:
                setattr(config_default, k, v)
        setattr(rule, 'dynamic_config', config_default)

    @classmethod
    def set_config_llm(cls, llm: BaseLLM, llm_config: EvaluatorLLMArgs):
        if not llm_config:
            return
        config_default = getattr(llm, 'dynamic_config')
        # Iterate over llm_config fields using Pydantic's model_dump()
        for k, v in llm_config.model_dump().items():
            if v is not None:
                setattr(config_default, k, v)
        setattr(llm, 'dynamic_config', config_default)
