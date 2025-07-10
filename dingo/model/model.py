import importlib
import inspect
import os
from typing import Callable, Dict, List, Optional

from pydantic import BaseModel

from dingo.config import GlobalConfig
from dingo.model.llm.base import BaseLLM
from dingo.model.prompt.base import BasePrompt
from dingo.model.rule.base import BaseRule
from dingo.utils import log


class BaseEvalModel(BaseModel):
    name: str
    type: str


class Model:
    """
    Model configuration class.
    """
    module_loaded = False
    rule_groups = {}  # such as: {'default': [<class.RuleAlphaWords>]}
    prompt_groups = {}

    rule_metric_type_map = {}   # such as: {'QUALITY_INEFFECTIVENESS': [<class.RuleAlphaWords>]}
    prompt_metric_type_map = {}  # such as: {'QUALITY_INEFFECTIVENESS': [<class.QaRepeat>]}

    rule_name_map = {}  # such as: {'RuleAlphaWords': <class.RuleAlphaWords>}
    prompt_name_map = {}
    llm_name_map = {}

    def __init__(self):
        return

    @classmethod
    def get_group(cls, group_name) -> Dict[str, List]:
        res = {}
        if group_name not in Model.rule_groups and group_name not in Model.prompt_groups:
            raise KeyError('no such group: ' + group_name)
        if group_name in Model.rule_groups:
            log.debug(f"[Load rule group {group_name}]")
            res['rule'] = Model.rule_groups[group_name]
        if group_name in Model.prompt_groups:
            log.debug(f"[Load prompt group {group_name}]")
            res['prompt'] = Model.prompt_groups[group_name]
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
    def prompt_register(cls, metric_type: str, group: List[str]) -> Callable:
        def decorator(root_class):
            # group
            for group_name in group:
                if group_name not in cls.prompt_groups:
                    cls.prompt_groups[group_name] = []
                cls.prompt_groups[group_name].append(root_class)
            cls.prompt_name_map[root_class.__name__] = root_class
            root_class.group = group

            # metric_type
            if metric_type not in cls.prompt_metric_type_map:
                cls.prompt_metric_type_map[metric_type] = []
            cls.prompt_metric_type_map[metric_type].append(root_class)
            root_class.metric_type = metric_type

            return root_class

        return decorator

    @classmethod
    def apply_config_rule(cls):
        if GlobalConfig.config and GlobalConfig.config.rule_config:
            for rule, rule_config in GlobalConfig.config.rule_config.items():
                if rule not in cls.rule_name_map:
                    continue
                assert isinstance(rule, str)
                log.debug(f"[Rule config]: config {rule_config} for {rule}")
                cls_rule: BaseRule = cls.rule_name_map[rule]
                config_default = getattr(cls_rule, 'dynamic_config')
                for k, v in rule_config:
                    if v is not None:
                        setattr(config_default, k, v)
                setattr(cls_rule, 'dynamic_config', config_default)

    @classmethod
    def apply_config_llm(cls):
        if GlobalConfig.config and GlobalConfig.config.llm_config:
            for llm, llm_config in GlobalConfig.config.llm_config.items():
                if llm not in cls.llm_name_map.keys():
                    continue
                assert isinstance(llm, str)
                log.debug(f"[Rule config]: config {llm_config} for {llm}")
                cls_llm: BaseLLM = cls.llm_name_map[llm]
                config_default = getattr(cls_llm, 'dynamic_config')
                for k, v in llm_config:
                    if v is not None:
                        setattr(config_default, k, v)
                setattr(cls_llm, 'dynamic_config', config_default)

    @classmethod
    def apply_config_rule_list(cls, eval_group: str = ''):
        if GlobalConfig.config and GlobalConfig.config.rule_list:
            model: List[BaseRule] = []
            for rule in GlobalConfig.config.rule_list:
                assert isinstance(rule, str)
                if rule not in Model.rule_name_map:
                    raise KeyError(f"{rule} not in Model.rule_name_map, there are {str(Model.rule_name_map.keys())}")
                model.append(Model.rule_name_map[rule])
            Model.rule_groups[eval_group] = model

    @classmethod
    def apply_config_prompt_list(cls, eval_group: str = ''):
        if GlobalConfig.config and GlobalConfig.config.prompt_list:
            model: List[BasePrompt] = []
            for prompt in GlobalConfig.config.prompt_list:
                assert isinstance(prompt, str)
                if prompt not in Model.prompt_name_map:
                    raise KeyError(f"{prompt} not in Model.prompt_name_map, there are {str(Model.prompt_name_map.keys())}")
                model.append(Model.prompt_name_map[prompt])
            Model.prompt_groups[eval_group] = model

    @classmethod
    def apply_config(cls, custom_config: Optional[str | dict], eval_group: str = ''):
        GlobalConfig.read_config_file(custom_config)
        cls.apply_config_rule()
        cls.apply_config_llm()
        if GlobalConfig.config:
            if GlobalConfig.config.rule_list or GlobalConfig.config.prompt_list:
                if eval_group in Model.rule_groups or eval_group in Model.prompt_groups:
                    raise KeyError(f'eval group: [{eval_group}] already in Model, please input other name.')
        cls.apply_config_rule_list(eval_group)
        cls.apply_config_prompt_list(eval_group)

    @classmethod
    def apply_config_for_spark_driver(cls, custom_config: Optional[str | dict], eval_group: str = ''):
        GlobalConfig.read_config_file(custom_config)
        cls.apply_config_rule()
        cls.apply_config_llm()
        cls.apply_config_rule_list(eval_group)
        cls.apply_config_prompt_list(eval_group)

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

        # rule auto register
        for file in os.listdir(os.path.join(this_module_directory, 'prompt')):
            path = os.path.join(this_module_directory, 'prompt', file)
            if os.path.isfile(path) and file.endswith('.py') and not file == '__init__.py':
                try:
                    importlib.import_module('dingo.model.prompt.' + file.split('.')[0])
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
