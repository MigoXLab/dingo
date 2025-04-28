import asyncio

from dingo.config.config import DynamicLLMConfig
from dingo.io.input.MetaData import MetaData
from fastmcp import Client

client = Client("mcp_server.py")

async def call_get_rule_list():
    async with client:
        result = await client.call_tool("get_rule_list")
        print(result)

asyncio.run(call_get_rule_list())


async def call_get_prompt_list():
    async with client:
        result = await client.call_tool("get_prompt_list")
        print(result)

asyncio.run(call_get_prompt_list())


async def call_create_rule_task(data: MetaData, rule_name: str):
    async with client:
        result = await client.call_tool("create_rule_task", {"data": data, "rule_name": rule_name})
        print(result)

data = MetaData(
        data_id='123',
        prompt="hello, introduce the world",
        content="Hello! The world is a vast and diverse place, full of wonders, cultures, and incredible natural beauty:"
    )
asyncio.run(call_create_rule_task(data, 'RuleColonEnd'))


async def call_create_llm_task(data: MetaData, prompt_name: str, llm_name: str, llm_config: DynamicLLMConfig):
    async with client:
        result = await client.call_tool("create_llm_task", {"data": data, "prompt_name": prompt_name, "llm_name": llm_name, "llm_config": llm_config})
        print(result)

data = MetaData(
        data_id='123',
        prompt="hello, introduce the world",
        content="Hello! The world is a vast and diverse place, full of wonders, cultures, and incredible natural beauty:"
    )
llm_config = DynamicLLMConfig(
        key='',
        api_url='',
        # model='',
    )
asyncio.run(call_create_llm_task(data, 'PromptRepeat', 'detect_text_quality_detail', llm_config))
