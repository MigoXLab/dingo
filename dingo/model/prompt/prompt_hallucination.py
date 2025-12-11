from dingo.model.model import Model
from dingo.model.prompt.base import BasePrompt


@Model.prompt_register("QUALITY_BAD_HALLUCINATION", ["hallucination", "rag"])
class PromptHallucination(BasePrompt):
    """
    Hallucination detection prompt based on DeepEval's HallucinationTemplate
    Evaluates whether LLM outputs contain factual errors or contradictions against given contexts
    """

    # Metadata for documentation generation
    _metric_info = {
        "category": "SFT Data Assessment Metrics",
        "metric_name": "PromptHallucination",
        "description": "Evaluates whether the response contains factual contradictions or hallucinations against provided context information",
        "paper_title": "TruthfulQA: Measuring How Models Mimic Human Falsehoods",
        "paper_url": "https://arxiv.org/abs/2109.07958",
        "paper_authors": "Lin et al., 2021",
        "evaluation_results": ""
    }

    content = """For each context in the provided contexts, please generate a list of JSON objects to indicate whether the given 'actual output' agrees with EACH context. The JSON will have 2 fields: 'verdict' and 'reason'.

The 'verdict' key should STRICTLY be either 'yes' or 'no', and states whether the given response agrees with the context.
The 'reason' is the reason for the verdict. When the answer is 'no', try to provide a correction in the reason.

**IMPORTANT**: Please make sure to only return in JSON format, with the 'verdicts' key as a list of JSON objects.

Example contexts: ["Einstein won the Nobel Prize for his discovery of the photoelectric effect.", "Einstein won the Nobel Prize in 1968."]
Example actual output: "Einstein won the Nobel Prize in 1969 for his discovery of the photoelectric effect."

Example:
{{
    "verdicts": [
        {{
            "verdict": "yes",
            "reason": "The actual output agrees with the provided context which states that Einstein won the Nobel Prize for his discovery of the photoelectric effect."
        }},
        {{
            "verdict": "no",
            "reason": "The actual output contradicts the provided context which states that Einstein won the Nobel Prize in 1968, not 1969."
        }}
    ]
}}

You should NOT incorporate any prior knowledge you have and take each context at face value. Since you are going to generate a verdict for each context, the number of 'verdicts' SHOULD BE STRICTLY EQUAL TO the number of contexts provided.
You should FORGIVE cases where the actual output is lacking in detail, you should ONLY provide a 'no' answer if IT IS A CONTRADICTION.

**Input Data:**
Question/Prompt: {}
Response: {}
Contexts: {}

Please evaluate the response against each context and return the verdicts in JSON format:
"""
