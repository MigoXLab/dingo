"""
Task Difficulty Evaluator - 任务难度评估器

Based on recent research:
- Measuring Difficulty of Math Problems (OpenAI, 2024)
- Task Complexity in Instruction Following (Google DeepMind, 2023)
- Self-Instruct: Aligning Language Models with Self-Generated Instructions (2023)

评估维度：
1. Cognitive Complexity: 认知复杂度
2. Step Complexity: 步骤复杂度
3. Domain Knowledge: 领域知识要求
4. Constraint Density: 约束条件密度
"""

from dingo.io.output.eval_detail import EvalDetail
from dingo.model import Model
from dingo.model.llm.base_openai import BaseOpenAI
from dingo.utils import log


@Model.llm_register("LLMTaskDifficulty")
class LLMTaskDifficulty(BaseOpenAI):
    """
    LLM-based task difficulty evaluator

    评估任务的难度级别，包括：
    - 认知复杂度：需要的推理深度
    - 步骤复杂度：任务分解的复杂程度
    - 领域知识：专业知识要求
    - 约束密度：限制条件的数量和复杂性
    """

    # Metadata for documentation generation
    _metric_info = {
        "category": "SFT Data Assessment Metrics",
        "quality_dimension": "TASK_DIFFICULTY",
        "metric_name": "LLMTaskDifficulty",
        "description": "Evaluates task difficulty across cognitive complexity, step complexity, domain knowledge, and constraint density",
        "paper_source": "OpenAI Math Problem Difficulty (2024), Google DeepMind Task Complexity (2023)",
        "evaluation_results": "Returns difficulty level (1-10) with detailed breakdown",
        "examples": "examples/sft/evaluate_instruction_quality.py"
    }

    prompt = """
# Role
You are an expert in assessing task complexity and difficulty for LLM training data evaluation.

# Task
Evaluate the difficulty level of the given instruction across four dimensions.

# Evaluation Dimensions

## 1. Cognitive Complexity (认知复杂度) - Weight: 30%
**Definition**: Mental processing depth required to complete the task.

Based on Bloom's Taxonomy:
- **Level 1-2 (Simple)**: Remember, Understand
  - Example: "Define photosynthesis." (Score: 1.5/3.0)
  - Requires recall or basic comprehension

- **Level 3-4 (Moderate)**: Apply, Analyze
  - Example: "Compare and contrast mitosis and meiosis, explaining their biological significance." (Score: 2.0/3.0)
  - Requires application of knowledge or analytical thinking

- **Level 5-6 (Complex)**: Evaluate, Create
  - Example: "Design a novel experimental protocol to test the efficacy of a new drug compound, considering ethical constraints, statistical power, and cost-effectiveness." (Score: 3.0/3.0)
  - Requires synthesis, evaluation, or creation of new knowledge

**Scoring**: 0.0-3.0 points

## 2. Step Complexity (步骤复杂度) - Weight: 30%
**Definition**: Number and interdependency of steps required.

**Scoring**:
- **Simple (0.5-1.0)**: Single-step task
  - Example: "Translate '你好' to English."
  - 1 step: direct translation

- **Moderate (1.5-2.0)**: Multi-step with linear dependency
  - Example: "Calculate the area of a circle with radius 5, then find what percentage it is of a square with side 15."
  - Steps: Calculate circle area → Calculate square area → Compute percentage

- **Complex (2.5-3.0)**: Multi-step with branching logic or loops
  - Example: "Write a program that recursively traverses a file system, identifies all Python files, runs linting on each, aggregates results by error type, and generates a ranked report of most common issues."
  - Steps: Recursive traversal + Conditional filtering + External tool execution + Data aggregation + Sorting + Report generation

**Scoring**: 0.0-3.0 points

## 3. Domain Knowledge (领域知识要求) - Weight: 20%
**Definition**: Specialized knowledge required beyond general education.

**Scoring**:
- **General (0.5-0.7)**: Common knowledge
  - Example: "Write a recipe for chocolate chip cookies."

- **Specialized (1.0-1.5)**: Professional or technical knowledge
  - Example: "Explain how OAuth 2.0 authorization code flow works with PKCE extension."

- **Expert (1.5-2.0)**: Deep domain expertise required
  - Example: "Derive the Navier-Stokes equations from first principles and discuss conditions for existence of smooth solutions in 3D."

**Scoring**: 0.0-2.0 points

## 4. Constraint Density (约束条件密度) - Weight: 20%
**Definition**: Number and strictness of constraints/requirements.

**Scoring**:
- **Low (0.5-0.7)**: 0-2 constraints, flexible
  - Example: "Write a story about a cat."

- **Medium (1.0-1.5)**: 3-5 constraints, some strictness
  - Example: "Write a 500-word story about a cat, set in Victorian London, with a mystery plot."

- **High (1.5-2.0)**: 6+ constraints, very strict
  - Example: "Write exactly 500 words (+/- 10 words) story about a black cat named Midnight, set in 1890s London, mystery genre, must include: a pocket watch, a letter, and a twist ending, maintain past tense, use British English spelling, target audience: young adults."

**Scoring**: 0.0-2.0 points

# Total Difficulty Score
- **Score Range**: 0-10 (sum of weighted scores)
- **Difficulty Levels**:
  - 0-3: Easy (适合快速蒸馏的简单任务)
  - 4-6: Moderate (标准 SFT 任务)
  - 7-8: Hard (高质量复杂任务)
  - 9-10: Expert (需要专家级能力的任务)

# Output Format
Return JSON only:
```json
{
    "difficulty_score": 7.5,
    "difficulty_level": "Hard",
    "dimensions": {
        "cognitive_complexity": 2.5,
        "step_complexity": 2.0,
        "domain_knowledge": 1.5,
        "constraint_density": 1.5
    },
    "estimated_time": "10-20 minutes",
    "suitable_for": ["Advanced fine-tuning", "Expert model training"],
    "key_challenges": [
        "Requires multi-step reasoning",
        "Needs domain expertise in X",
        "Multiple strict constraints"
    ],
    "reason": "This is a hard task requiring advanced reasoning and domain knowledge..."
}
```

# Important Notes
1. Consider the realistic capability of current LLMs
2. A task is only "Expert" level if it challenges even GPT-4 level models
3. Don't confuse verbosity with difficulty - a long simple task is still simple
4. Open-ended creative tasks can still be difficult if they require skill/expertise

# Examples

**Example 1 - Easy Task (Score: 2.5)**
Input: "将'Hello World'翻译成法语。"

Output:
```json
{
    "difficulty_score": 2.5,
    "difficulty_level": "Easy",
    "dimensions": {
        "cognitive_complexity": 1.0,
        "step_complexity": 0.5,
        "domain_knowledge": 0.5,
        "constraint_density": 0.5
    },
    "estimated_time": "< 1 minute",
    "suitable_for": ["Basic fine-tuning", "Quick knowledge distillation"],
    "key_challenges": [],
    "reason": "Simple single-step translation task requiring only basic language knowledge. No complex reasoning or constraints."
}
```

**Example 2 - Moderate Task (Score: 5.5)**
Input: "编写一个Python函数,接受一个整数列表,返回列表中所有质数的和。包含错误处理和单元测试。"

Output:
```json
{
    "difficulty_score": 5.5,
    "difficulty_level": "Moderate",
    "dimensions": {
        "cognitive_complexity": 2.0,
        "step_complexity": 1.5,
        "domain_knowledge": 1.0,
        "constraint_density": 1.0
    },
    "estimated_time": "5-10 minutes",
    "suitable_for": ["Standard SFT", "Code generation training"],
    "key_challenges": [
        "Requires algorithm knowledge (prime checking)",
        "Multiple components (function + error handling + tests)",
        "Need to consider edge cases"
    ],
    "reason": "Moderate coding task requiring algorithm knowledge and multiple components. Needs understanding of prime numbers, error handling, and unit testing, but within standard programming curriculum."
}
```

**Example 3 - Hard Task (Score: 8.0)**
Input: "设计一个分布式系统架构,支持每秒10万次请求,保证99.99%可用性,具有水平扩展能力。需要包括:1)服务拆分方案 2)数据一致性策略 3)故障恢复机制 4)性能监控方案。画出架构图并详细说明每个组件的职责和交互方式。考虑CAP定理的权衡。"

Output:
```json
{
    "difficulty_score": 8.0,
    "difficulty_level": "Hard",
    "dimensions": {
        "cognitive_complexity": 2.5,
        "step_complexity": 2.5,
        "domain_knowledge": 1.5,
        "constraint_density": 1.5
    },
    "estimated_time": "30-60 minutes",
    "suitable_for": ["Expert model training", "Architecture knowledge evaluation"],
    "key_challenges": [
        "Requires deep distributed systems knowledge",
        "Multi-dimensional problem with trade-offs (CAP theorem)",
        "Multiple strict requirements (throughput, availability)",
        "Complex deliverables (architecture diagram + detailed explanation)",
        "Need to balance multiple concerns simultaneously"
    ],
    "reason": "Hard system design task requiring expert-level distributed systems knowledge. Involves multiple complex constraints, trade-off analysis, and requires synthesis of knowledge across several domains (scalability, consistency, reliability). The task demands creating a comprehensive solution with multiple interdependent components."
}
```

**Example 4 - Expert Task (Score: 9.5)**
Input: "Prove or disprove: For any continuous function f: [0,1] → ℝ satisfying ∫₀¹ f(x)² dx < ∞, there exists a sequence of polynomials {pₙ} such that ||f - pₙ||₂ → 0 as n → ∞. Provide rigorous proof using measure theory and functional analysis. Discuss the rate of convergence and relate your findings to Weierstrass approximation theorem."

Output:
```json
{
    "difficulty_score": 9.5,
    "difficulty_level": "Expert",
    "dimensions": {
        "cognitive_complexity": 3.0,
        "step_complexity": 2.5,
        "domain_knowledge": 2.0,
        "constraint_density": 2.0
    },
    "estimated_time": "1-2 hours",
    "suitable_for": ["Research-level model training", "Mathematical reasoning evaluation"],
    "key_challenges": [
        "Requires graduate-level mathematics",
        "Need rigorous proof construction",
        "Multiple advanced mathematical concepts (measure theory, functional analysis)",
        "Requires connecting multiple theorems",
        "Demanding formal rigor and precision"
    ],
    "reason": "Expert-level mathematical task requiring graduate mathematics knowledge. Demands rigorous proof construction, deep understanding of measure theory and functional analysis, and ability to connect advanced concepts. This would challenge even specialized mathematical AI systems."
}
```

# Now evaluate this instruction:
"""

    @classmethod
    def process_response(cls, response: str) -> EvalDetail:
        """处理 LLM 响应并生成评估结果"""
        import json

        log.info(f"LLM Response: {response}")
        result = EvalDetail(metric=cls.__name__)

        try:
            # 解析 JSON 响应
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.startswith("```"):
                response = response[3:]
            if response.endswith("```"):
                response = response[:-3]
            response = response.strip()

            parsed = json.loads(response)

            # 提取信息
            difficulty_score = float(parsed.get("difficulty_score", 0))
            difficulty_level = parsed.get("difficulty_level", "Unknown")
            dimensions = parsed.get("dimensions", {})
            estimated_time = parsed.get("estimated_time", "Unknown")
            suitable_for = parsed.get("suitable_for", [])
            key_challenges = parsed.get("key_challenges", [])
            reason = parsed.get("reason", "")

            # 构建详细的 reason
            detailed_reason = f"任务难度评分: {difficulty_score}/10 ({difficulty_level})\n\n"
            detailed_reason += "维度得分:\n"
            detailed_reason += f"  - 认知复杂度: {dimensions.get('cognitive_complexity', 0)}/3.0\n"
            detailed_reason += f"  - 步骤复杂度: {dimensions.get('step_complexity', 0)}/3.0\n"
            detailed_reason += f"  - 领域知识: {dimensions.get('domain_knowledge', 0)}/2.0\n"
            detailed_reason += f"  - 约束密度: {dimensions.get('constraint_density', 0)}/2.0\n\n"

            detailed_reason += f"预计耗时: {estimated_time}\n\n"

            if suitable_for:
                detailed_reason += "适用场景:\n"
                for s in suitable_for:
                    detailed_reason += f"  • {s}\n"
                detailed_reason += "\n"

            if key_challenges:
                detailed_reason += "关键挑战:\n"
                for c in key_challenges:
                    detailed_reason += f"  ⚠ {c}\n"
                detailed_reason += "\n"

            detailed_reason += f"总结: {reason}"

            # 设置结果
            result.score = difficulty_score
            result.reason = [detailed_reason]

            # 难度评估没有"通过/不通过"的概念，只是描述性的
            # 但为了兼容框架，我们设置一个合理的默认行为
            # 可以通过 parameters 配置 min_difficulty 和 max_difficulty
            result.status = False  # 默认不标记为问题
            result.label = [f"TASK_DIFFICULTY.{difficulty_level.upper()}"]

            # 如果配置了难度范围要求，进行检查
            if hasattr(cls, 'dynamic_config') and cls.dynamic_config.parameters:
                min_difficulty = cls.dynamic_config.parameters.get('min_difficulty', 0)
                max_difficulty = cls.dynamic_config.parameters.get('max_difficulty', 10)

                if difficulty_score < min_difficulty:
                    result.status = True
                    result.label = ["QUALITY_BAD.TASK_TOO_EASY"]
                elif difficulty_score > max_difficulty:
                    result.status = True
                    result.label = ["QUALITY_BAD.TASK_TOO_HARD"]

        except json.JSONDecodeError as e:
            log.error(f"Failed to parse JSON response: {e}")
            result.status = True
            result.score = 0
            result.label = ["QUALITY_BAD.TASK_DIFFICULTY_ERROR"]
            result.reason = [f"评估失败: JSON 解析错误 - {str(e)}"]
        except Exception as e:
            log.error(f"Error processing response: {e}")
            result.status = True
            result.score = 0
            result.label = ["QUALITY_BAD.TASK_DIFFICULTY_ERROR"]
            result.reason = [f"评估失败: {str(e)}"]

        return result
