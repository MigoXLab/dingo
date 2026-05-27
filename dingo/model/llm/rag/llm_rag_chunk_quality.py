from dingo.io.input import RequiredField
from dingo.model import Model
from dingo.model.llm.text_quality.base_text_quality import BaseTextQuality


@Model.llm_register("LLMChunkQuality")
class LLMChunkQuality(BaseTextQuality):
    # Metadata for documentation generation
    _metric_info = {
        "category": "RAG Retrieved Evidence Chunk Quality Metrics",
        "metric_name": "LLMChunkQuality",
        "description": "Assesses retrieved citation chunks referenced by LLM answers, detecting start-boundary truncation and duplicated leading text that can weaken grounded generation",
        "examples": "examples/rag/sdk_chunk_eval.py"
    }
    _required_fields = [RequiredField.CONTENT]
    prompt = """
# Role
You are a data quality evaluator for RAG evidence chunks that are cited by LLM answers.

# Goal
Determine whether this retrieved chunk is reliable as citation evidence for grounded LLM answers.
Focus on start-boundary corruption and duplicate-leading content that can materially harm retrieval-to-generation quality, not minor imperfections.

# Quality Dimensions

## 1. Completeness
**Impact**: Broken starts prevent models from learning proper chunk boundaries and coherent text patterns.

**Check for**:
- **Error_Start_Text_Truncation**: The beginning text is truncated (letters, words, Chinese characters, or other languages)
  **Common corruption patterns**:
  - Leading letter truncation, e.g.:
    "e with agroforestry and green manure-based technologies can significantly enhance financial profits."
  - Leading word truncation, e.g.:
    "osition of noble gases in this ionized reservoir depends on ionization energy and plasma temperature."
  - Leading Chinese character truncation, e.g.:
    "烈。可以说,在中国历史上,这是一个大动荡的时期,更是一个大融合、大发展的时期。"

- **Error_Start_Punctuation_Truncation**: The beginning punctuation is truncated
  **Common corruption patterns**:
  - Truncated ending punctuation from the previous sentence, e.g.:
    ". Due to the inhibitory effects from module 2, the firing rate of these diverged bumps are very low."
  - Truncated punctuation from the middle of the previous sentence, e.g.:
    ", 23.27±14.57; M/F, 30/9) were found of ALL-T origin. Their specimens were mainly bone marrow $(\\Nu=26$ ) and peripheral blood $(\\Nu{=}13$ ) and subjected for molecular analysis irrespective of their CD5 expression."

- **Error_Start_Inline_Formula_Truncation**: Inline formula at the beginning is truncated
  **Common corruption patterns**:
  - Truncation of inline formulas wrapped by single "$", e.g.:
    "-}1100^{\\circ}\\mathrm{C}$ there is relatively no loss in weight on heating."

- **Error_Start_Interline_Formula_Truncation**: Interline formula at the beginning is truncated
  **Common corruption patterns**:
  - Truncation of interline formulas wrapped by double "$$", e.g.:
    "q_{D N}=-0,01\\cdot T+2,41;\n$$\n\n$q_{D N}-$ denitrifikacijos greitis, $\\mathrm{\\mgN/gVDBSM\\cdoth}$ ;"

---

## 2. Similarity
**Impact**: Repeated content severely reduces learning efficiency and increases memorization risk.

**Check for**:
- **Error_Start_Text_Duplicate**: Repeated text at the beginning
  **Common corruption patterns**:
  - Start-position duplicate text, e.g.:
    "4. Diefendorf, Barbara. From Penitence to Charity: Pious Women and the Catholic Reformation in Paris\n\n. Diefendorf, Barbara. From Penitence to Charity: Pious Women and the Catholic Reformation in Paris. New York: Oxford University Press, 2004. Di Filippo Bareggi, Claudia."

---

# Workflow

1. **Quick scan**: Is the text generally readable and structurally complete?
2. **Identify category**: If there is an issue, which dimension is most severely affected?
3. **Validate impact**: Will this issue materially damage model training?
4. **Assign labels**:
   - Score: 1 (suitable) or 0 (unsuitable)
   - Type: `Good` or one of `Completeness`, `Similarity`
   - Name: Specific error type (from above)
   - Reason: Brief explanation (1-2 sentences)

---

# Output Format
Return JSON only: {"score": 0/1, "type": "", "name": "", "reason": ""}

# Examples

**Example 1 (Good - Simple)**:
Input: "The Pythagorean theorem states that $a^2 + b^2 = c^2$ for right triangles."
Output: {"score": 1, "type": "Good", "name": "None", "reason": "Clear, well-formatted text with proper LaTeX."}

**Example 2 (Bad - Completeness, punctuation truncation)**:
Input: ", and the patient was diagnosed with IE due to methicillin-resistant Staphylococcus aureus infection\n\n."
Output: {"score": 0, "type": "Completeness", "name": "Error_Start_Punctuation_Truncation", "reason": "The beginning is incomplete and starts from truncated punctuation."}

---

# Input content to evaluate:

"""
