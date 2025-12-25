"""
Dingo ATS Resume Optimizer Example

This example demonstrates how to use LLMResumeOptimizer for ATS-focused resume optimization.

Two optimization modes:
1. General Mode: Polish resume with STAR method (no context provided)
2. Targeted Mode: Inject missing keywords from KeywordMatcher report (context provided)

Input Requirements:
- input_data.content: Resume text (required)
- input_data.prompt: Target position (optional)
- input_data.context: KeywordMatcher match report JSON (optional, triggers Targeted Mode)

Output:
- Optimized resume sections with before/after comparison
- Keywords added/de-emphasized summary
- Section-by-section changes
"""

import os

from dingo.config.input_args import EvaluatorLLMArgs
from dingo.io.input import Data
from dingo.model.llm.llm_resume_optimizer import LLMResumeOptimizer

# Configure LLM (从环境变量读取)
LLMResumeOptimizer.dynamic_config = EvaluatorLLMArgs(
    key=os.getenv("OPENAI_API_KEY", ""),
    api_url=os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com"),
    model=os.getenv("OPENAI_MODEL", "deepseek-chat"),
)


def example_1_general_polish():
    """Example 1: General resume polish using STAR method"""
    print("=== Example 1: General Polish Mode ===")

    resume = """
    张三
    Python开发工程师

    工作经历：
    2020.01-至今 | ABC公司 | 开发工程师
    - 做了很多开发工作
    - 参与了系统优化
    - 负责API开发
    """

    data = Data(
        data_id='optimize_test_1',
        content=resume,
        prompt='高级Python开发工程师'
        # No context = General Mode
    )

    result = LLMResumeOptimizer.eval(data)

    print(f"Error Status: {result.error_status}")
    print(f"Reason:\n{result.reason[0]}")

    # Access full optimization result
    if hasattr(result, 'optimized_content'):
        opt = result.optimized_content
        print(f"\nSection Changes:")
        for change in opt.get('section_changes', []):
            print(f"  - {change.get('section_name')}: {change.get('changes')}")
    print()


def example_2_targeted_optimization():
    """Example 2: Targeted optimization with missing keywords injection"""
    print("=== Example 2: Targeted Optimization Mode ===")

    resume = """
    张三
    Python开发工程师 | 5年经验

    专业技能：
    Python, Django, MySQL, Git

    工作经历：
    2020.01-至今 | ABC公司 | 后端开发
    - 负责公司后端系统开发
    - 优化数据库性能
    """

    # Simulating KeywordMatcher output (missing skills)
    match_report = {
        "match_details": {
            "missing": [
                {"skill": "Kubernetes", "importance": "Required"},
                {"skill": "Docker", "importance": "Required"},
                {"skill": "Redis", "importance": "Nice-to-have"}
            ],
            "negative_warnings": []
        }
    }

    import json
    data = Data(
        data_id='optimize_test_2',
        content=resume,
        prompt='高级Python开发工程师',
        context=json.dumps(match_report)  # Triggers Targeted Mode
    )

    result = LLMResumeOptimizer.eval(data)

    print(f"Error Status: {result.error_status}")
    print(f"Reason:\n{result.reason[0]}")

    if hasattr(result, 'optimized_content'):
        opt = result.optimized_content
        summary = opt.get('optimization_summary', {})
        print(f"\nKeywords Added: {summary.get('keywords_added', [])}")
        print(f"Keywords Associative: {summary.get('keywords_associative', [])}")
        print(f"Keywords Unused: {summary.get('keywords_unused', [])}")
    print()


def example_3_full_pipeline():
    """Example 3: Full pipeline - Match then Optimize"""
    print("=== Example 3: Full Pipeline (Match -> Optimize) ===")

    from dingo.model.llm.llm_keyword_matcher import LLMKeywordMatcher

    # Configure KeywordMatcher
    LLMKeywordMatcher.dynamic_config = LLMResumeOptimizer.dynamic_config

    resume = """
    王五
    软件工程师

    技能：Java, Spring Boot, MySQL
    经验：3年后端开发
    """

    jd = """
    后端工程师
    要求：Python（必需）、Docker（必需）、AWS（加分）
    """

    # Step 1: Match
    match_data = Data(data_id='pipeline_1', content=resume, prompt=jd)
    match_result = LLMKeywordMatcher.eval(match_data)
    print(f"Match Score: {getattr(match_result, 'score', 'N/A')}")

    # Step 2: Optimize (use match result as context)
    # In real usage, extract missing keywords from match_result
    optimize_data = Data(
        data_id='pipeline_2',
        content=resume,
        prompt='后端工程师',
        context='{"match_details": {"missing": [{"skill": "Python", "importance": "Required"}]}}'
    )
    opt_result = LLMResumeOptimizer.eval(optimize_data)
    print(f"Optimization:\n{opt_result.reason[0]}")
    print()


if __name__ == "__main__":
    print("📝 Dingo ATS Resume Optimizer Examples")
    print("=" * 50)
    print()
    print("⚠️  Please set your API key before running!")
    print()

    example_1_general_polish()
    # example_2_targeted_optimization()
    # example_3_full_pipeline()

    print("✅ Examples completed!")
