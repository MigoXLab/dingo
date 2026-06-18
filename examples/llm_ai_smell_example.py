"""
Example: AI Smell Detection for Requirement Documents

Usage:
    python examples/llm_ai_smell_example.py

This example demonstrates how to use LLMAISmell to detect AI-generated
writing patterns in requirement documents.
"""

from dingo.config.input_args import InputArgs
from dingo.exec.local import LocalExecutor

SAMPLE_DOC_HIGH_AI_SMELL = """
## 智能客服系统需求文档

### 一、背景

在当今数字化转型的大背景下，随着人工智能技术的不断发展和进步，越来越多的企业
开始重视智能化客服系统的建设。为了更好地赋能业务发展，提升用户体验，打造闭环的
客户服务生态，我们提出构建一套高效、智能的客服解决方案，以实现降本增效、价值最大化的战略目标。

### 二、核心目标

本系统旨在通过底层逻辑的重塑和顶层设计的优化，实现以下战略目标：
- 大幅提升客户满意度，打造行业领先的服务体验
- 通过全链路智能化改造，彻底革新传统客服模式
- 赋能一线客服人员，提升整体服务效能，实现降本增效
- 构建可持续发展的智能客服生态，沉淀核心服务能力

### 三、功能需求

#### 3.1 智能问答

系统应支持智能问答功能，能够准确理解用户意图，提供精准的回答。系统需要确保
回答的准确性和及时性，以满足用户的迫切需求。界面设计应符合用户使用习惯，提供
良好的交互体验。系统还应支持多轮对话，能够理解上下文，提供连贯的对话体验。

#### 3.2 工单管理

系统应具备完善的工单管理功能，支持工单的创建、分配、跟踪和关闭全生命周期管理。
工单系统需要满足业务需求，支持多种工单类型，确保处理效率和质量。通过对工单数据
的深度挖掘和分析，为管理决策提供有力支撑，实现数据驱动的精细化运营。

### 四、技术要求

系统性能应满足业务需求，确保在高并发场景下的稳定运行。系统需要具备良好的扩展性
和可维护性，以支撑未来业务的快速发展。安全性方面，系统应符合相关法规要求，保护
用户数据安全。系统架构应采用先进的微服务架构，实现各模块的解耦，提升系统的灵活性
和可靠性。

### 五、总结

综上所述，本智能客服系统将通过技术创新和模式变革，为企业创造巨大的商业价值，
提升核心竞争力，助力企业在激烈的市场竞争中脱颖而出，实现可持续发展。
"""

SAMPLE_DOC_LOW_AI_SMELL = """
## 客服工单系统 v2.1 需求文档

**作者**: 张三  **日期**: 2024-01-15  **评审状态**: 待评审

---

### 1. 背景

当前客服团队每天处理约 2000 张工单，其中 65% 为重复性问题（退款、发货查询、
账号问题）。工单平均处理时间 8 分钟，其中 3 分钟用于查历史记录。本项目目标是
将平均处理时间降至 5 分钟以内。

### 2. 功能需求

#### 2.1 快速回复模板

**需求描述**：客服输入关键词时，系统自动推荐匹配的回复模板。

**详细说明**：
- 输入框输入字符后 300ms 内展示建议列表，最多显示 5 条
- 按相关度排序：完全匹配 > 关键词匹配 > 语义相似
- 客服选择模板后可编辑再发送，不能直接强制发送
- 模板库由运营通过后台维护，支持按一级分类（退款/物流/账号/其他）管理

**不在范围内**：自动发送、客户端展示建议

#### 2.2 历史工单查询

**需求描述**：在工单页面可快速查看同一用户的历史工单。

**详细说明**：
- 侧边栏展示最近 10 张工单的摘要（时间、分类、处理结果）
- 点击展开查看完整内容
- 数据来源：工单系统数据库，实时查询，无需缓存
- 异常情况：用户无历史工单时展示"暂无历史记录"，查询超时（>3s）展示错误提示

### 3. 非功能需求

- 快速回复建议 P95 响应时间 < 500ms（基于当前 500 并发用户）
- 历史工单查询 P99 < 2s
- 暂不考虑国际化
"""


def run_example():
    print("=" * 60)
    print("Example 1: High AI Smell Document")
    print("=" * 60)

    # Configure the executor with LLMAISmell checker.
    # Replace YOUR_API_KEY and api_base with your actual LLM credentials.
    input_args = InputArgs(
        eval_group="llm",
        llm_config={
            "model": "gpt-4o",
            "key": "YOUR_API_KEY",
            "api_base": "https://api.openai.com/v1",
        },
        custom_config={"llm": ["LLMAISmell"]},
    )
    executor = LocalExecutor(input_args=input_args)

    print("\nDocument snippet (high AI smell):")
    print(SAMPLE_DOC_HIGH_AI_SMELL[:200] + "...")
    print("\nExpected: AI_SMELL_DETECTED with high scores on adjective_violence and detail_vacuum")
    print(f"\nExecutor ready: {executor.__class__.__name__}")

    # To run the actual evaluation (requires a valid API key configured above):
    # try:
    #     result = executor.eval_text(SAMPLE_DOC_HIGH_AI_SMELL)
    #     print("\nEvaluation Result:")
    #     print(result.reason[0])
    # except Exception as e:
    #     print(f"\nCould not run evaluation: {e}")

    print("\n" + "=" * 60)
    print("Example 2: Low AI Smell Document")
    print("=" * 60)
    print("\nDocument snippet (low AI smell):")
    print(SAMPLE_DOC_LOW_AI_SMELL[:200] + "...")
    print("\nExpected: AI_SMELL_CLEAN with low scores across all dimensions")


if __name__ == "__main__":
    run_example()
