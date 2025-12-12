from dingo.model.model import Model
from dingo.model.prompt.base import BasePrompt

# Complete synonym mapping for keyword normalization
SYNONYM_MAP = {
    "k8s": "Kubernetes",
    "js": "JavaScript",
    "ts": "TypeScript",
    "py": "Python",
    "tf": "TensorFlow",
    "react.js": "React",
    "reactjs": "React",
    "vue.js": "Vue.js",
    "vuejs": "Vue.js",
    "node.js": "Node.js",
    "nodejs": "Node.js",
    "next.js": "Next.js",
    "nextjs": "Next.js",
    "express.js": "Express.js",
    "expressjs": "Express.js",
    "nest.js": "NestJS",
    "nestjs": "NestJS",
    "postgres": "PostgreSQL",
    "postgresql": "PostgreSQL",
    "mysql": "MySQL",
    "mongo": "MongoDB",
    "mongodb": "MongoDB",
    "aws": "Amazon Web Services",
    "gcp": "Google Cloud Platform",
    "azure": "Microsoft Azure",
    "ci/cd": "CI/CD",
    "cicd": "CI/CD",
    "ml": "Machine Learning",
    "dl": "Deep Learning",
    "ai": "Artificial Intelligence",
    "nlp": "Natural Language Processing",
    "cv": "Computer Vision",
    "golang": "Go",
    "cpp": "C++",
    "csharp": "C#",
    "dotnet": ".NET",
    "pt": "PyTorch",
    "pytorch": "PyTorch",
    "sklearn": "scikit-learn",
    "scikit-learn": "scikit-learn",
}


def get_synonym_map_str() -> str:
    """Format SYNONYM_MAP for prompt injection."""
    return "\n".join([f"  - {k} → {v}" for k, v in SYNONYM_MAP.items()])


@Model.prompt_register("KEYWORD_MATCHER", ["resume", "ats"], ["LLMKeywordMatcher"])
class PromptKeywordMatcher(BasePrompt):
    """
    ATS-optimized keyword matching prompt.
    Evaluates how well a resume matches a job description for ATS optimization.

    Features:
    - Semantic matching (not just string matching)
    - Negative constraint recognition ("No need for X" → Excluded)
    - Evidence-based matching (quotes from resume)
    - Weighted scoring (Required × 2, Nice-to-have × 1)
    - Four match types: Exact, Substring, Semantic, Alias
    """

    _metric_info = {
        "category": "Resume ATS Matching Metrics",
        "metric_name": "PromptKeywordMatcher",
        "description": "Semantic keyword matching between resume and job description for ATS optimization",
        "paper_title": "N/A",
        "paper_url": "",
        "paper_authors": "Dingo Team",
        "evaluation_results": ""
    }

    content = """You are an expert ATS (Applicant Tracking System) Analyzer. Your goal is to assess how well a candidate's resume matches a specific Job Description (JD).

### 1. KNOWN ALIASES (Synonyms)
Use these strict mappings for matching. If the resume uses an alias, count it as a match.
""" + get_synonym_map_str() + """

### 2. ANALYSIS LOGIC (Step-by-Step)

**Step 1: JD Extraction & Classification**
Extract technical skills/keywords from the JD and classify their importance:
- **Required**: Core skills, "must have", "proficient in", "X years of experience in"
- **Nice-to-have**: "Plus", "preferred", "bonus", "familiarity with"
- **Excluded**: Negative constraints like "No need for X", "Not X", "Unlike X", "We don't use X", "X is not required"

**Step 2: Evidence Verification**
For each skill found in JD, search the Resume for evidence:
- **Exact**: String appears exactly (case-insensitive). Example: JD "Python" → Resume "Python"
- **Substring**: Keyword exists inside a phrase. Example: JD "SQL" → Resume "MySQL" or "PostgreSQL"
- **Semantic**: Different words but same meaning. Example: JD "GPU Optimization" → Resume "TensorRT" (because TensorRT IS a GPU optimization tool)
- **Alias**: Known synonym from the alias list. Example: JD "Kubernetes" → Resume "k8s"

**Step 3: Frequency Count**
Count how many times the keyword appears in both JD and Resume.

### 3. OUTPUT SCHEMA (Strict JSON)
Return ONLY a valid JSON object. No markdown, no code blocks, no commentary.

{{{{
  "jd_analysis": {{{{
    "job_title": "String (extracted job title, or null if not found)",
    "skills_total": Integer
  }}}},
  "keyword_analysis": [
    {{{{
      "keyword": "String (normalized form, e.g., 'Kubernetes' not 'k8s')",
      "importance": "Required" | "Nice-to-have" | "Excluded",
      "match_status": "Matched" | "Missing",
      "match_type": "Exact" | "Substring" | "Semantic" | "Alias" | "None",
      "evidence": "String (max 50 chars quote from resume, or null if missing)",
      "reasoning": "String (ONLY for Semantic match, explain why they are related, else null)",
      "frequency": {{{{
        "jd": Integer,
        "resume": Integer
      }}}}
    }}}}
  ]
}}}}

### 4. IMPORTANT RULES
1. **Excluded + Matched**: If a skill is Excluded in JD but present in Resume, set match_status to "Matched". (Python logic will flag this as a warning)
2. **Excluded + Missing**: If a skill is Excluded in JD and NOT in Resume, set match_status to "Missing". (This is GOOD - user correctly lacks excluded skill)
3. **Focus on HARD SKILLS**: Do not extract generic terms like "Communication", "Teamwork", "Problem Solving" unless explicitly technical context.
4. **Alias Priority**: If resume uses an alias (e.g., "k8s"), normalize to standard form ("Kubernetes") in keyword field, set match_type to "Alias".
5. **Evidence Length**: Keep evidence under 50 characters. Truncate with "..." if needed.
6. **Reasoning**: ONLY provide reasoning for Semantic matches. For Exact/Substring/Alias, set reasoning to null.

**Input Data:**
Job Description:
{}

Resume:
{}

Please analyze and return the JSON result:
"""
