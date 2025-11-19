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
    rule_groups = {}  # such as: {'default': [<class.RuleAlphaWords>]}

    # metric map
    rule_metric_type_map = {}   # such as: {'QUALITY_INEFFECTIVENESS': [<class.RuleAlphaWords>]}

    # other map
    rule_name_map = {}  # such as: {'RuleAlphaWords': <class.RuleAlphaWords>}
    llm_name_map = {}

    def __init__(self):
        return

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
    def get_rule_metric_type_map(cls) -> Dict[str, List[Callable]]:
        """
        Returns the rule metric type map.

        Returns:
            Rule metric type map ( { rule_metric_type: [rules] } )
        """
        return cls.rule_metric_type_map

    @classmethod
    def get_metric_type_by_rule_name(cls, rule_name: str) -> str:
        """
        Returns the metric_type by rule_name.
        Args:
            rule_name (str): The name of the rule.
        Returns:
            metric type.
        """
        rule = cls.rule_name_map[rule_name]
        for metric_type in cls.rule_metric_type_map:
            if rule in cls.rule_metric_type_map[metric_type]:
                return metric_type

    @classmethod
    def get_metric_type_list_by_rule_group(cls, rule_group: List[BaseRule]) -> List:
        metric_type_list = []
        for rule in rule_group:
            metric_type_list.append(cls.get_metric_type_by_rule_name(rule.__name__))
        return metric_type_list

    @classmethod
    def get_rule_group(cls, rule_group_name: str) -> List[Callable]:
        """
        Returns the rule groups by rule_group_name.

        Returns:
            Rule groups ( [rules] ).
        """
        return cls.rule_groups[rule_group_name]

    @classmethod
    def get_rule_groups(cls) -> Dict[str, List[Callable]]:
        """
        Returns the rule groups.

        Returns:
            Rule groups map ( { rule_group_id: [rules] } ).
        """
        return cls.rule_groups

    @classmethod
    def get_rules_by_group(cls, group_name: str) -> List[str]:
        """
        Returns rule by group name.

        Returns:
            Rule name list.
        """
        return [r.metric_type + '-' + r.__name__ for r in Model.get_rule_group(group_name)]

    @classmethod
    def get_rule_by_name(cls, name: str) -> Callable:
        """
        Returns rule by name.

        Returns:
            Rule function.
        """
        return cls.rule_name_map[name]

    @classmethod
    def get_llm_name_map(cls) -> Dict[str, BaseLLM]:
        """
        Returns the llm models.

        Returns:
            LLM models class List
        """
        return cls.llm_name_map

    @classmethod
    def get_llm(cls, llm_name: str) -> BaseLLM:
        """
        Returns the llm model by llm_model_name.
        Args:
            llm_name (str): The name of the llm model.

        Returns:
            LLM model class
        """
        return cls.llm_name_map[llm_name]

    @classmethod
    def print_rule_list(cls) -> None:
        """
        Print the rule list.

        Returns:
            List of rules.
        """
        rule_list = []
        for rule_name in cls.rule_name_map:
            rule_list.append(rule_name)
        print("\n".join(rule_list))

    @classmethod
    def get_all_info(cls):
        """
        Returns rules' map and llm models' map
        """
        raise NotImplementedError()

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
    def apply_config_rule(cls):
        if cls.input_args.evaluator.rule_config:
            for rule_name, rule_args in cls.input_args.evaluator.rule_config.items():
                log.debug(f"[Rule config]: config {rule_args} for {rule_name}")
                cls_rule: BaseRule = cls.rule_name_map[rule_name]
                config_default = getattr(cls_rule, 'dynamic_config')
                for k, v in rule_args:
                    if v is not None:
                        setattr(config_default, k, v)
                setattr(cls_rule, 'dynamic_config', config_default)

    @classmethod
    def apply_config_llm(cls):
        if cls.input_args.evaluator.llm_config:
            for llm_name, llm_args in cls.input_args.evaluator.llm_config.items():
                log.debug(f"[LLM config]: config {llm_args} for {llm_name}")
                cls_llm: BaseLLM = cls.llm_name_map[llm_name]
                config_default = getattr(cls_llm, 'dynamic_config')
                for k, v in llm_args:
                    if v is not None:
                        setattr(config_default, k, v)
                setattr(cls_llm, 'dynamic_config', config_default)

    @classmethod
    def apply_config_rule_list(cls):
        if cls.input_args.executor.rule_list:
            eg = cls.input_args.executor.eval_group
            Model.rule_groups[eg] = []
            for rule_name in cls.input_args.executor.rule_list:
                if rule_name not in Model.rule_name_map:
                    raise KeyError(f"{rule_name} not in Model.rule_name_map, there are {str(Model.rule_name_map.keys())}")
                Model.rule_groups[eg].append(Model.rule_name_map[rule_name])

    @classmethod
    def apply_config(cls, input_args: InputArgs):
        cls.input_args = input_args
        cls.apply_config_rule()
        cls.apply_config_llm()
        cls.apply_config_rule_list()

    @classmethod
    def apply_config_for_spark_driver(cls, input_args: InputArgs):
        cls.input_args = input_args
        cls.apply_config_rule()
        cls.apply_config_llm()
        cls.apply_config_rule_list()

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

        # llm auto register
        for file in os.listdir(os.path.join(this_module_directory, 'llm')):
            path = os.path.join(this_module_directory, 'llm', file)
            if os.path.isfile(path) and file.endswith('.py') and not file == '__init__.py':
                try:
                    importlib.import_module('dingo.model.llm.' + file.split('.')[0])
                except ModuleNotFoundError as e:
                    log.debug(e)
                except ImportError as e:
                    log.debug("=" * 30 + " ImportError " + "=" * 30)
                    log.debug(f'module {file.split(".")[0]} not imported because: \n{e}')
                    log.debug("=" * 73)
        cls.module_loaded = True

    @classmethod
    def set_config_rule(self, rule: BaseRule, rule_config: EvaluatorRuleArgs):
        if not rule_config:
            return
        config_default = getattr(rule, 'dynamic_config')
        for k, v in rule_config:
            if v is not None:
                setattr(config_default, k, v)
        setattr(rule, 'dynamic_config', config_default)

    @classmethod
    def set_config_llm(self, llm: BaseLLM, llm_config: EvaluatorLLMArgs):
        if not llm_config:
            return
        config_default = getattr(llm, 'dynamic_config')
        for k, v in llm_config:
            if v is not None:
                setattr(config_default, k, v)
        setattr(llm, 'dynamic_config', config_default)
