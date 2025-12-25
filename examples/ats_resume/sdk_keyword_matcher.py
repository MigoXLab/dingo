"""
Dingo ATS Keyword Matcher Example

This example demonstrates how to use LLMKeywordMatcher for ATS (Applicant Tracking System)
resume-job description matching analysis.

LLMKeywordMatcher analyzes:
- Job description requirements extraction
- Resume keyword matching against JD
- Weighted match score calculation
- Missing skills identification

Input Requirements:
- input_data.content: Resume text
- input_data.prompt: Job description text

Output:
- Match score (0.0-1.0)
- Detailed keyword analysis
- Missing required/nice-to-have skills
"""

import os

from dingo.config.input_args import EvaluatorLLMArgs
from dingo.io.input import Data
from dingo.model.llm.llm_keyword_matcher import LLMKeywordMatcher

# Configure LLM (set your API key via environment variable OPENAI_KEY)
LLMKeywordMatcher.dynamic_config = EvaluatorLLMArgs(
    key=os.getenv("OPENAI_KEY", "YOUR_API_KEY"),  # Replace with your API key or set OPENAI_KEY env var
    api_url=os.getenv("OPENAI_URL", "https://api.openai.com/v1"),
    model=os.getenv("OPENAI_MODEL", "gpt-4o"),
)


def example_1_basic_matching():
    """Example 1: Basic resume-JD keyword matching"""
    print("=== Example 1: Basic Keyword Matching ===")

    resume = """
    张三
    高级Python开发工程师 | 5年经验

    专业技能：
    - Python, Django, Flask, FastAPI
    - MySQL, PostgreSQL, Redis
    - Docker, Linux
    - Git, CI/CD

    工作经历：
    2020.01 - 至今 | ABC科技公司 | 高级后端开发
    - 负责公司核心业务系统开发，使用Python/Django技术栈
    - 优化数据库查询性能，提升50%响应速度
    - 设计并实现RESTful API接口
    """

    jd = """
    高级Python开发工程师

    岗位要求：
    - 5年以上Python开发经验（必需）
    - 精通Django或Flask框架（必需）
    - 熟悉MySQL/PostgreSQL数据库（必需）
    - 熟悉Docker容器化部署（加分）
    - 有Kubernetes经验优先（加分）
    - 熟悉消息队列如Kafka/RabbitMQ（加分）
    """

    data = Data(
        data_id='match_test_1',
        content=resume,
        prompt=jd
    )

    result = LLMKeywordMatcher.eval(data)

    print(f"Match Score: {getattr(result, 'score', 'N/A')}")
    print(f"Status: {result.status}")  # True = has issues, False = passed
    print(f"Reason:\n{result.reason[0]}")
    print()


def example_2_english_resume():
    """Example 2: English resume matching"""
    print("=== Example 2: English Resume Matching ===")

    resume = """
    John Smith
    Senior Software Engineer | 6 Years Experience

    Skills:
    - Python, Java, Go
    - React, TypeScript
    - AWS, Docker, Kubernetes
    - PostgreSQL, MongoDB, Redis

    Experience:
    2019 - Present | Tech Corp | Senior Engineer
    - Led development of microservices architecture
    - Implemented CI/CD pipelines using GitHub Actions
    - Mentored junior developers
    """

    jd = """
    Senior Backend Engineer

    Requirements:
    - 5+ years of software development experience (Required)
    - Proficiency in Python or Go (Required)
    - Experience with AWS or GCP (Required)
    - Kubernetes and Docker experience (Required)
    - Experience with message queues (Kafka/RabbitMQ) (Nice-to-have)
    - Machine Learning experience (Nice-to-have)
    """

    data = Data(
        data_id='match_test_2',
        content=resume,
        prompt=jd
    )

    result = LLMKeywordMatcher.eval(data)

    print(f"Match Score: {getattr(result, 'score', 'N/A')}")
    print(f"Status: {result.status}")  # True = has issues, False = passed
    print(f"Reason:\n{result.reason[0]}")
    print()


def example_3_low_match():
    """Example 3: Low match score scenario"""
    print("=== Example 3: Low Match Score ===")

    resume = """
    李四
    前端开发工程师

    技能：JavaScript, React, Vue.js, CSS, HTML
    """

    jd = """
    后端开发工程师

    要求：
    - Python/Java开发经验（必需）
    - 数据库设计能力（必需）
    - Linux运维经验（必需）
    """

    data = Data(
        data_id='match_test_3',
        content=resume,
        prompt=jd
    )

    result = LLMKeywordMatcher.eval(data)

    print(f"Match Score: {getattr(result, 'score', 'N/A')}")
    print(f"Status: {result.status}")  # True = has issues (low match), False = passed
    print(f"Reason:\n{result.reason[0]}")
    print()


if __name__ == "__main__":
    print("🎯 Dingo ATS Keyword Matcher Examples")
    print("=" * 50)
    print()
    print("⚠️  Please set your API key before running!")
    print()

    example_1_basic_matching()
    # example_2_english_resume()
    # example_3_low_match()

    print("✅ Examples completed!")
