"""
Dingo Scout - Strategic Job Hunting Analysis Example

This example demonstrates how to use LLMScout for strategic job hunting analysis
based on industry reports and user profiles.

LLMScout analyzes:
- Industry reports (company extraction, financial signals)
- User profiles (skills, experience, preferences)
- Person-job fit scoring with sub-scores
- Search strategy and interview preparation tips

Input Requirements:
- input_data.content: Industry report text (required)
- input_data.prompt: User profile (required)
- input_data.context: Resume text (optional, improves skill matching)

Output:
- Target companies with match scores and tiers
- Financial status analysis with evidence
- Search keywords and platform recommendations
- Interview style predictions
"""

import os

from dingo.config.input_args import EvaluatorLLMArgs
from dingo.io.input import Data
from dingo.model.llm.llm_scout import LLMScout

# Configure LLM
LLMScout.dynamic_config = EvaluatorLLMArgs(
    key=os.getenv("OPENAI_API_KEY", ""),
    api_url=os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com"),
    model=os.getenv("OPENAI_MODEL", "deepseek-chat"),
)


def example_1_basic_analysis():
    """Example 1: Basic industry report analysis"""
    print("=== Example 1: Basic Scout Analysis ===")

    industry_report = """
    2024年Q3科技行业报告

    1. 字节跳动
    - 财务状况：ROE持续上升，2024年营收增长25%
    - 招聘动态：计划扩招2000人，重点招聘AI算法工程师
    - 业务方向：大模型、短视频、电商

    2. 阿里巴巴
    - 财务状况：ROE平稳，云业务增长放缓
    - 招聘动态：优化人员结构，技术岗位保持招聘
    - 业务方向：云计算、电商、本地生活

    3. 某创业公司A
    - 财务状况：B轮融资完成，资金充裕
    - 招聘动态：急招后端工程师
    - 业务方向：AI Agent
    """

    user_profile = """
    我是2024届CS硕士，有以下背景：
    - 技术栈：Python, PyTorch, LangChain
    - 实习经历：某大厂AI实验室实习
    - 求职偏好：想去大厂，偏好稳定
    - 地点偏好：北京、上海
    """

    data = Data(
        data_id='scout_test_1',
        content=industry_report,
        prompt=user_profile
    )

    result = LLMScout.eval(data)

    print(f"Score: {getattr(result, 'score', 'N/A')}")
    print(f"Status: {'Pass' if not result.status else 'Has Issues'}")
    print(f"Analysis:\n{result.reason[0]}")

    # Access full strategy context
    if hasattr(result, 'strategy_context'):
        ctx = result.strategy_context
        print(f"\nTarget Companies: {len(ctx.get('target_companies', []))}")
        for company in ctx.get('target_companies', []):
            print(f"  - {company.get('name')}: {company.get('tier')} "
                  f"(Score: {company.get('match_score', 0):.0%})")
    print()


def example_2_with_resume():
    """Example 2: Analysis with resume for better skill matching"""
    print("=== Example 2: Scout with Resume Context ===")

    industry_report = """
    AI行业快报

    OpenAI中国区合作伙伴招聘：
    - 财务：获得新一轮融资，expansion阶段
    - 岗位：LLM工程师、Prompt工程师
    - 要求：熟悉大模型微调、RAG系统开发
    """

    user_profile = "应届生，想做AI方向，风险偏好中等"

    resume = """
    教育背景：清华大学 计算机硕士
    技能：Python, PyTorch, Transformers, LangChain
    项目经验：
    - 基于LLaMA的领域微调项目
    - RAG知识库问答系统
    - Prompt工程优化实践
    """

    data = Data(
        data_id='scout_test_2',
        content=industry_report,
        prompt=user_profile,
        context=resume  # Provides resume for skill extraction
    )

    result = LLMScout.eval(data)

    print(f"Score: {getattr(result, 'score', 'N/A')}")
    print(f"Analysis:\n{result.reason[0]}")
    print()


def example_3_low_confidence():
    """Example 3: Report with insufficient data"""
    print("=== Example 3: Low Confidence Report ===")

    # Vague report without specific financial data
    industry_report = """
    某行业概述：
    - 市场前景广阔
    - 各公司都在积极布局
    - 人才需求旺盛
    """

    user_profile = "3年经验Python开发"

    data = Data(
        data_id='scout_test_3',
        content=industry_report,
        prompt=user_profile
    )

    result = LLMScout.eval(data)

    print(f"Score: {getattr(result, 'score', 'N/A')}")
    print(f"Analysis:\n{result.reason[0]}")
    print()


if __name__ == "__main__":
    print("Dingo Scout - Strategic Job Hunting Analysis")
    print("=" * 50)
    print()
    print("Please set OPENAI_API_KEY environment variable before running!")
    print()

    example_1_basic_analysis()
    # example_2_with_resume()
    # example_3_low_confidence()

    print("Examples completed!")
