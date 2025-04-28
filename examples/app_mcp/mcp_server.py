from fastmcp import FastMCP

from dingo.config.config import DynamicLLMConfig
from dingo.io.input.MetaData import MetaData
from dingo.model import Model
from dingo.model.llm.base import BaseLLM
from dingo.model.prompt.base import BasePrompt
from dingo.model.rule.rule_common import *

mcp = FastMCP("Dingo Mcp Server")

@mcp.tool()
def get_rule_list() -> list:
    return Model.get_rule_list()

@mcp.tool()
def get_prompt_list() -> list:
    return Model.get_prompt_list()

@mcp.tool()
def create_rule_task(data: MetaData, rule_name: str):
    rule: BaseRule = Model.get_rule_by_name(rule_name)
    res = rule.eval(data)
    return res

@mcp.tool()
def create_llm_task(data: MetaData, prompt_name: str, llm_name: str, llm_config: DynamicLLMConfig):
    prompt:BasePrompt = Model.get_prompt_by_name(prompt_name)
    llm: BaseLLM = Model.get_llm(llm_name)
    llm.prompt = prompt
    llm.dynamic_config = llm_config
    res = llm.eval(data)
    return res

if __name__ == '__main__':
    mcp.run()
    # mcp.run(transport='sse', port=8000, host='0.0.0.0')
