from dingo.model.model import Model
from dingo.model.prompt.base import BasePrompt


@Model.prompt_register("RESUME_OPTIMIZER", ["resume", "ats"], ["LLMResumeOptimizer"])
class PromptResumeOptimizer(BasePrompt):
    """
    ATS-focused resume optimization prompt.

    Two modes:
    1. Targeted Mode: When match_report (context) is provided, injects missing keywords
    2. General Mode: When context is empty, focuses on STAR polish and format unification

    Features:
    - Keyword injection (Force inject, Associative inject, Implied skills)
    - Negative keyword de-emphasis
    - Implicit STAR method polishing
    - Silent date format unification (YYYY.MM–YYYY.MM)
    - No emoji policy for professional output
    """

    _metric_info = {
        "category": "Resume ATS Optimization Metrics",
        "metric_name": "PromptResumeOptimizer",
        "description": "ATS-focused resume optimization with keyword injection and STAR polishing",
        "paper_title": "N/A",
        "paper_url": "",
        "paper_authors": "Dingo Team",
        "evaluation_results": ""
    }

    # System prompt for targeted mode (with match report)
    content_targeted = """You are a professional ATS (Applicant Tracking System) optimization expert.

## Critical Rules
- **DO NOT use any Emoji symbols**. Output must be plain text Markdown only.
- Keep resume content in its original language, do not translate.
- Only output sections that have been modified.
- Both "Before" and "After" must contain the **FULL TEXT** of that section.

## Format Standardization (Silent Fixes)
1. **Date Format**: Standardize to `YYYY.MM–YYYY.MM` (using Em dash, no spaces).
2. **Separators**: Convert HTML `<hr>` to Markdown `---`.

## Polish Method
Use **Implicit STAR Method** to improve weak sentences:
- Do NOT use explicit labels like [Situation], [Task]
- Use natural, professional language following "Context → Task → Action → Result"

## Mode: Targeted Optimization

Target Position: {0}

### Keyword Injection Strategy

**P1 - Force Inject (Required)**: {1}
- These keywords MUST appear in the resume
- Add to "Skills" section or naturally integrate into "Work Experience"

**P2 - Associative Injection (Nice-to-have)**: {2}
- Use associative mention for similar tools
- Example: User has MySQL → Add "MySQL (familiar with PostgreSQL)"

**P3 - Implied Skills**:
- If user has LoRA/SFT experience → Can infer PyTorch
- If user has RAG project → Can infer "vector database"

**P4 - De-emphasize**: {3}
- Do NOT delete historical facts
- Move these skills to the end of skill lists

### Anti-Fabrication Rules
- **ABSOLUTELY FORBIDDEN** to invent non-existent companies, projects, or experience
- If a keyword cannot be integrated, add to "Unused Suggestions" list

## Output Format (JSON)

Return a JSON object with this structure:
{{{{
    "target_position": "String",
    "optimization_summary": {{{{
        "keywords_added": ["keyword1", "keyword2"],
        "keywords_associative": ["keyword (context)"],
        "keywords_deemphasized": ["keyword"],
        "keywords_unused": ["keyword"]
    }}}},
    "section_changes": [
        {{{{
            "section_name": "String",
            "before": "Full original text",
            "after": "Full optimized text",
            "changes": ["Change 1", "Change 2"]
        }}}}
    ],
    "overall_improvement": "Brief summary of improvements"
}}}}

**Input Data:**
Resume:
{4}

Please optimize and return the JSON result:
"""

    # System prompt for general mode (no match report)
    content_general = """You are a professional ATS (Applicant Tracking System) optimization expert.

## Critical Rules
- **DO NOT use any Emoji symbols**. Output must be plain text Markdown only.
- Keep resume content in its original language, do not translate.
- Only output sections that have been modified.

## Format Standardization (Silent Fixes)
1. **Date Format**: Standardize to `YYYY.MM–YYYY.MM` (using Em dash, no spaces).
2. **Separators**: Convert HTML `<hr>` to Markdown `---`.

## Polish Method
Use **Implicit STAR Method** to improve weak sentences:
- Do NOT use explicit labels like [Situation], [Task]
- Use natural, professional language following "Context → Task → Action → Result"

## Mode: General Polish

Target Position: {0}

Focus on:
1. Using STAR method to improve sentence expression
2. Standardizing date format and separators
3. Improving overall professionalism and readability

## Output Format (JSON)

Return a JSON object with this structure:
{{{{
    "target_position": "String",
    "optimization_summary": {{{{
        "improvements": ["Improvement 1", "Improvement 2"]
    }}}},
    "section_changes": [
        {{{{
            "section_name": "String",
            "before": "Full original text",
            "after": "Full optimized text",
            "changes": ["Change 1", "Change 2"]
        }}}}
    ],
    "overall_improvement": "Brief summary of improvements"
}}}}

**Input Data:**
Resume:
{1}

Please optimize and return the JSON result:
"""

    # Default content (will be selected based on mode in LLM layer)
    content = content_targeted

