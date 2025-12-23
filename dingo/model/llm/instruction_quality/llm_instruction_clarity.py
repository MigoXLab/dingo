"""
Instruction Clarity Evaluator - 指令清晰度评估器

Based on recent research:
- IFEval: Instruction Following Evaluation (Google, 2023)
- Self-Instruct (University of Washington, 2023)
- Alpaca: A Strong, Replicable Instruction-Following Model (Stanford, 2023)

评估维度：
1. Self-Descriptiveness: 指令是否自包含，无需额外上下文
2. Consistency: 指令内部是否一致，无矛盾
3. Specificity: 指令是否具体明确，避免歧义
4. Completeness: 指令是否完整，包含所有必要信息
"""

from dingo.io.output.eval_detail import EvalDetail
from dingo.model import Model
from dingo.model.llm.base_openai import BaseOpenAI
from dingo.utils import log


@Model.llm_register("LLMInstructionClarity")
class LLMInstructionClarity(BaseOpenAI):
    """
    LLM-based instruction clarity evaluator

    评估指令的清晰度，包括：
    - 自描述性：是否包含足够信息
    - 一致性：内部是否有矛盾
    - 具体性：是否明确具体
    - 完整性：是否包含所有必要信息
    """

    # Metadata for documentation generation
    _metric_info = {
        "category": "SFT Data Assessment Metrics",
        "quality_dimension": "INSTRUCTION_CLARITY",
        "metric_name": "LLMInstructionClarity",
        "description": "Evaluates instruction clarity across four dimensions: self-descriptiveness, consistency, specificity, and completeness",
        "paper_source": "IFEval (Google, 2023), Self-Instruct (UW, 2023)",
        "evaluation_results": "Returns clarity score (0-10) and detailed analysis",
        "examples": "examples/sft/evaluate_instruction_quality.py"
    }

    prompt = """
# Role
You are an expert in evaluating instruction quality for Large Language Model training data.

# Task
Evaluate the clarity of the given instruction across four dimensions.

# Evaluation Dimensions

## 1. Self-Descriptiveness (自描述性)
**Definition**: Does the instruction contain sufficient information to be understood without additional context?

**Scoring**:
- **High (2.5)**: Complete self-contained instruction with all necessary details
  - Example: "Write a Python function that takes a list of integers and returns the sum of all even numbers. Include docstring and type hints."
- **Medium (1.5)**: Mostly clear but may need minor assumptions
  - Example: "Write a function to sum even numbers in a list."
- **Low (0.5)**: Requires significant external context or assumptions
  - Example: "Do that thing with the numbers."

## 2. Consistency (一致性)
**Definition**: Are all parts of the instruction aligned without contradictions?

**Scoring**:
- **High (2.5)**: Perfectly consistent throughout
  - Example: "Write a formal academic essay on climate change using APA citation style and maintain a professional tone."
- **Medium (1.5)**: Minor inconsistencies that don't fundamentally conflict
  - Example: "Write a casual blog post but use academic references."
- **Low (0.5)**: Major contradictions
  - Example: "Write a 500-word essay in under 100 words."

## 3. Specificity (具体性)
**Definition**: Is the instruction concrete and unambiguous?

**Scoring**:
- **High (2.5)**: Very specific with clear success criteria
  - Example: "Generate exactly 5 creative product names for an eco-friendly water bottle. Each name should be 2-3 words and include at least one nature-related term."
- **Medium (1.5)**: Somewhat specific but allows interpretation
  - Example: "Generate some creative names for a water bottle."
- **Low (0.5)**: Vague and ambiguous
  - Example: "Make something cool."

## 4. Completeness (完整性)
**Definition**: Does the instruction include all necessary information for task completion?

**Scoring**:
- **High (2.5)**: All required elements specified (input, output, constraints, format)
  - Example: "Given a JSON file with user data, extract all email addresses, validate them using regex, and output to a CSV file with columns: name, email, valid_status."
- **Medium (1.5)**: Most elements present but some details missing
  - Example: "Extract email addresses from a file and validate them."
- **Low (0.5)**: Critical information missing
  - Example: "Process the data."

# Scoring System
- **Total Score**: 0-10 (sum of all four dimensions, each worth 2.5 points)
- **Threshold**: Default 6.0 (instructions below this score are considered unclear)

# Output Format
Return JSON only:
```json
{
    "score": 8.5,
    "dimensions": {
        "self_descriptiveness": 2.5,
        "consistency": 2.0,
        "specificity": 2.0,
        "completeness": 2.0
    },
    "issues": [],
    "strengths": ["Clear task definition", "Well-specified output format"],
    "suggestions": ["Could specify tone/style more explicitly"],
    "reason": "High-quality instruction with clear task definition and well-specified constraints. Minor improvement: explicitly specify the desired tone."
}
```

# Important Rules
1. Be strict but fair - real-world instructions aren't always perfect
2. Focus on whether the instruction enables successful task completion
3. Consider the instruction type (creative tasks may be intentionally open-ended)
4. Empty or extremely vague instructions should score 0-2
5. Professional SFT-quality instructions should score 7+

# Examples

**Example 1 - Excellent Instruction (Score: 9.5)**
Input: "Write a Python function named `calculate_discount` that takes two parameters: original_price (float) and discount_percentage (float, 0-100). Return the final price after applying the discount, rounded to 2 decimal places. Include input validation to ensure prices are positive and discounts are between 0-100. Add comprehensive docstring with examples."

Output:
```json
{
    "score": 9.5,
    "dimensions": {
        "self_descriptiveness": 2.5,
        "consistency": 2.5,
        "specificity": 2.5,
        "completeness": 2.0
    },
    "issues": [],
    "strengths": [
        "Specific function name and parameters",
        "Clear input/output specifications",
        "Validation requirements specified",
        "Format requirements (rounding) included"
    ],
    "suggestions": [
        "Could specify return type for type hints"
    ],
    "reason": "Excellent instruction with comprehensive details. Only minor omission: explicit mention of return type annotation."
}
```

**Example 2 - Poor Instruction (Score: 2.0)**
Input: "写个代码"

Output:
```json
{
    "score": 2.0,
    "dimensions": {
        "self_descriptiveness": 0.5,
        "consistency": 0.5,
        "specificity": 0.5,
        "completeness": 0.5
    },
    "issues": [
        "No programming language specified",
        "No task description",
        "No input/output specification",
        "No context provided"
    ],
    "strengths": [],
    "suggestions": [
        "Specify programming language",
        "Describe what the code should do",
        "Define expected inputs and outputs",
        "Add any constraints or requirements"
    ],
    "reason": "Extremely vague instruction lacking all essential information. Impossible to determine what code is needed without additional context."
}
```

**Example 3 - Moderate Instruction (Score: 6.5)**
Input: "Summarize this article in a few sentences."

Output:
```json
{
    "score": 6.5,
    "dimensions": {
        "self_descriptiveness": 1.5,
        "consistency": 2.0,
        "specificity": 1.5,
        "completeness": 1.5
    },
    "issues": [
        "'Few sentences' is ambiguous (2? 3? 5?)",
        "No article content provided (assumes context)",
        "No specification of summary style/focus"
    ],
    "strengths": [
        "Clear task (summarization)",
        "No internal contradictions"
    ],
    "suggestions": [
        "Specify exact number of sentences (e.g., '3-5 sentences')",
        "Include the article content or reference",
        "Optionally specify summary focus (key findings, main argument, etc.)"
    ],
    "reason": "Decent instruction with clear intent but lacks precision. Needs more specific constraints and assumes article context is available."
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
            # 移除可能的 markdown 代码块标记
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.startswith("```"):
                response = response[3:]
            if response.endswith("```"):
                response = response[:-3]
            response = response.strip()

            parsed = json.loads(response)

            # 提取分数和维度信息
            score = float(parsed.get("score", 0))
            dimensions = parsed.get("dimensions", {})
            issues = parsed.get("issues", [])
            strengths = parsed.get("strengths", [])
            suggestions = parsed.get("suggestions", [])
            reason = parsed.get("reason", "")

            # 构建详细的 reason
            detailed_reason = f"指令清晰度评分: {score}/10\n\n"
            detailed_reason += "维度得分:\n"
            detailed_reason += f"  - 自描述性: {dimensions.get('self_descriptiveness', 0)}/2.5\n"
            detailed_reason += f"  - 一致性: {dimensions.get('consistency', 0)}/2.5\n"
            detailed_reason += f"  - 具体性: {dimensions.get('specificity', 0)}/2.5\n"
            detailed_reason += f"  - 完整性: {dimensions.get('completeness', 0)}/2.5\n\n"

            if strengths:
                detailed_reason += "优点:\n"
                for s in strengths:
                    detailed_reason += f"  ✓ {s}\n"
                detailed_reason += "\n"

            if issues:
                detailed_reason += "问题:\n"
                for i in issues:
                    detailed_reason += f"  ✗ {i}\n"
                detailed_reason += "\n"

            if suggestions:
                detailed_reason += "改进建议:\n"
                for s in suggestions:
                    detailed_reason += f"  → {s}\n"
                detailed_reason += "\n"

            detailed_reason += f"总结: {reason}"

            # 设置结果
            result.score = score
            result.reason = [detailed_reason]

            # 判断是否通过（默认阈值 6.0）
            threshold = 6.0
            if hasattr(cls, 'dynamic_config') and cls.dynamic_config.parameters:
                threshold = cls.dynamic_config.parameters.get('threshold', 6.0)

            if score >= threshold:
                result.status = False
                result.label = ["QUALITY_GOOD.INSTRUCTION_CLARITY_PASS"]
            else:
                result.status = True
                result.label = ["QUALITY_BAD.INSTRUCTION_CLARITY_FAIL"]

        except json.JSONDecodeError as e:
            log.error(f"Failed to parse JSON response: {e}")
            result.status = True
            result.score = 0
            result.label = ["QUALITY_BAD.INSTRUCTION_CLARITY_ERROR"]
            result.reason = [f"评估失败: JSON 解析错误 - {str(e)}"]
        except Exception as e:
            log.error(f"Error processing response: {e}")
            result.status = True
            result.score = 0
            result.label = ["QUALITY_BAD.INSTRUCTION_CLARITY_ERROR"]
            result.reason = [f"评估失败: {str(e)}"]

        return result
