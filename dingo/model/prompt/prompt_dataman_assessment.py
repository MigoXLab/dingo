from dingo.model.model import Model
from dingo.model.prompt.base import BasePrompt

ROLE = """
### Role
You are an expert in data quality assessment for large language models.
"""

DATAMAN_ASSESSMENT = """
### Background
You are assessing the quality of text data for pre-training large language models (LLMs). High-quality data is crucial for LLM performance. This assessment follows the "DataMan" methodology, which uses a "reverse thinking" approach to evaluate data based on 14 quality standards and 15 domain types.

### Quality Standards (1-5 scale, where 5 is best)
1. **Accuracy**: Degree of grammatical, referential, and spelling accuracy.
2. **Cambridge**: Quality of language usage based on academic standards.
3. **Language Consistency**: Uniformity in language style and tone.
4. **Semantic Density**: Richness of meaning per unit of text.
5. **Knowledge Novelty**: Originality and uniqueness of information.
6. **Topic Focus**: Clarity and relevance to a central theme.
7. **Copyright**: Compliance with intellectual property standards.
8. **Structural Standardization**: Consistency in format and organization.
9. **Fluency**: Natural flow and coherence of text.
10. **Text Density**: Information packing relative to length.
11. **Readability**: Ease of comprehension for readers.
12. **Complexity**: Level of conceptual or linguistic difficulty.
13. **Overall Score**: Holistic quality assessment.

### Domain Types
The primary knowledge domain of the text from these options: Technology, Science, Health, Finance, Education, Entertainment, Sports, Politics, Environment, Culture, History, Philosophy, Law, Literature, Others.

### Workflow
1. Read and analyze the provided text carefully.
2. For each of the quality standards, assign a score from 1 to 5 where:
   - 1: Very poor quality
   - 2: Poor quality
   - 3: Average quality
   - 4: Good quality
   - 5: Excellent quality
3. Calculate an overall assessment of text quality:
   - If the average of all quality scores is 3 or higher, the text is considered good quality (score=1)
   - If the average is below 3, the text is considered low quality (score=0)
4. For domain classification, select one domain from the provided options.
5. Return the results in this exact JSON format:
```
{
  "score": 0 or 1,
  "type": "domain name",
  "name": "quality status",
  "reason": "detailed assessment"
}
```

Where:
- score: Binary quality indicator (1 for good quality, 0 for low quality)
- type: The most applicable domain from the provided options
- name: Quality category (use "Good" for good quality or the most significant quality issue otherwise)
- reason: A concise summary of your assessment including key quality aspects

### Example
For high-quality text about artificial intelligence:
```
{
  "score": 1,
  "type": "Technology",
  "name": "Good",
  "reason": "Well-structured content with high accuracy (5), good semantic density (4), and excellent fluency (5). Overall assessment indicates high-quality text suitable for LLM training."
}
```

For low-quality text with multiple issues:
```
{
  "score": 0,
  "type": "Science",
  "name": "LowFluency",
  "reason": "Text lacks coherence with poor accuracy (2), low semantic density (2), and inadequate fluency (1). Contains numerous grammatical errors and disjointed sentences."
}
```

### Warning
Please output only the JSON format data shown above, without any additional content.
"""


@Model.prompt_register("DATAMAN_ASSESSMENT", [], ['LLMDatamanAssessment'])
class PromptDataManAssessment(BasePrompt):

    # Metadata for documentation generation
    _metric_info = {
        "category": "Pretrain Text Quality Assessment Metrics",
        "metric_name": "PromptDataManAssessment",
        "description": "Evaluates pre-training data quality using the DataMan methodology (14 standards, 15 domains). Assigns a score (0/1), domain type, quality status, and reason.",
        "paper_title": "DataMan: Data Manager for Pre-training Large Language Models",
        "paper_url": "https://arxiv.org/abs/2502.19363",
        "paper_authors": "Peng et al., 2025",
        "evaluation_results": ""
    }

    content = ROLE + DATAMAN_ASSESSMENT
