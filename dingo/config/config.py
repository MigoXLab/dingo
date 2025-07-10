import json
from typing import Dict, List, Optional

from pydantic import BaseModel

from dingo.utils import log


class DynamicRuleConfig(BaseModel):
    threshold: Optional[float] = None
    pattern: Optional[str] = None
    key_list: Optional[List[str]] = None
    refer_path: Optional[List[str]] = None


class DynamicLLMConfig(BaseModel):
    model: Optional[str] = None
    key: Optional[str] = None
    api_url: Optional[str] = None
    parameters: Optional[dict] = None


class Config(BaseModel):
    rule_list: Optional[List[str]] = []
    prompt_list: Optional[List[str]] = []
    rule_config: Optional[Dict[str, DynamicRuleConfig]] = {}
    llm_config: Optional[Dict[str, DynamicLLMConfig]] = {}


class GlobalConfig:
    config = None

    @classmethod
    def read_config_file(cls, custom_config: Optional[str | dict]):
        if custom_config is None:
            cls.config = Config()
            return
        data_json = {}
        try:
            if isinstance(custom_config, dict):
                data_json = custom_config
            else:
                with open(custom_config, "r", encoding="utf-8") as f:
                    data_json = json.load(f)
        except FileNotFoundError:
            log.error("No config file found, error path.")

        try:
            cls.config = Config(
                rule_list=data_json.get("rule_list", []),
                prompt_list=data_json.get("prompt_list", []),
                rule_config={
                    i: DynamicRuleConfig(**rule_config)
                    for i, rule_config in data_json.get("rule_config", {}).items()
                },
                llm_config={
                    i: DynamicLLMConfig(**llm_config)
                    for i, llm_config in data_json.get("llm_config", {}).items()
                },
            )
        except Exception as e:
            raise RuntimeError(f"Error loading config: {e}")
