from dingo.io.input import RequiredField
from dingo.model import Model
from dingo.model.llm.text_quality.base_text_quality import BaseTextQuality


@Model.llm_register("LLMTextQualityV5")
class LLMTextQualityV5(BaseTextQuality):
    # Metadata for documentation generation
    _metric_info = {
        "category": "Pretrain Text Quality Assessment Metrics",
        "metric_name": "LLMTextQualityV5",
        "description": "Impact-driven text quality evaluation for LLM pretraining, focusing on structural completeness, readability, diversity, and safety with quantitative thresholds",
        "paper_title": "WanJuanSiLu: A High-Quality Open-Source Webtext Dataset for Low-Resource Languages",
        "paper_url": "https://arxiv.org/abs/2501.14506",
        "paper_authors": "Yu et al., 2025",
        "examples": "examples/llm_and_rule/llm_local.py",
        "evaluation_results": "docs/eval/prompt/redpajama_data_evaluated_by_prompt.md"
    }
    _required_fields = [RequiredField.CONTENT]
    prompt = """
# Role
You are an expert in assessing pretraining data quality for large language models.

# Goal
Evaluate whether this text is suitable for LLM pretraining. Focus on issues that would negatively impact model learning, not minor imperfections.

# Quality Dimensions

## 1. Completeness (完整性)
**Impact**: Broken structures prevent models from learning correct formatting patterns.

**Check for**:
- **Error_Formula**: Mathematical content with **broken syntax** OR **systematically stripped symbols/formulas**

  Two failure modes:

  **(A) Broken LaTeX syntax** — delimiters or environments are present but malformed:
  - Delimiters unmatched: $ without closing $ (LaTeX context, not dollar signs)
  - Environments unclosed: \\begin{{align}} without \\end{{align}}
  - Syntax broken: \\frac{{a}}{{b missing closing }}
  - HTML tags unclosed: <sub>text without </sub>
  - Impact: Prevents >50% of mainstream parsers from rendering

  **(B) Stripped mathematical content** — symbols/formulas systematically removed during extraction:
  - Orphan hyphens from stripped Greek letters: "κ-solutions" → "-solutions", "ε-net" → "-net"
  - Empty positions after connective words: "thus ;" or "the interval ;" where a formula was removed
  - Sentences referencing variables/expressions that are absent: "a small number" (number missing), "we have ." (equation missing)
  - Systematic loss: multiple occurrences throughout the text, not just one or two typos
  - Impact: Mathematical text becomes incoherent; models learn broken academic writing patterns

  Example (BAD — stripped symbols):
  "Let be a -solution to the Ricci flow which is -noncollapsed. Ancient, in the sense that t ranges on the interval ; Bounded curvature, thus ;"
  (Greek letters κ stripped from "κ-solution" and "κ-noncollapsed"; interval expression and inequality after "thus" removed entirely)

  ⚠️ **Normal patterns (DO NOT flag)**:
  - Mixing inline ($...$) and display ($$...$$) formulas
  - Using \\begin{{align}}...\\end{{align}} within $$...$$
  - Line breaks with \\\\ in alignment environments
  - HTML tags: <sub>x</sub>, <sup>2</sup> for subscripts/superscripts
  - Mixing LaTeX and HTML in web-extracted content
  - Plain-text math without any LaTeX (e.g., "a^2 + b^2 = c^2" without $ delimiters) — this is fine as long as the expressions are actually present

  ⚠️ **Important**: Distinguish LaTeX $ from dollar signs ($100)
  - Dollar sign: "$100", "$5.99" (followed by numbers) → NOT LaTeX
  - LaTeX delimiter: "$x$", "$\\alpha$" (contains math symbols) → IS LaTeX

  - Example (BAD — broken delimiters): "$x^2 + y^2 is broken here $$a = b$$$"
    (First LaTeX $ never closes, extra $ at end)
  - Example (GOOD): "The item costs $100 and satisfies $x^2 + y^2 = z^2$ where price is $50"
    (Dollar signs for money + proper LaTeX pair)

- **Error_Table**: Table structures that are malformed or unreadable
  - Example (BAD): Misaligned columns, missing headers, or garbled HTML tags
  - Impact: Models cannot learn proper table representation

- **Error_Code**: Code blocks with formatting corruption
  **Common corruption patterns**:
  - Missing code fence (` ``` `): code appears as plain text without language block
  - Lost indentation: Python/YAML code with all indentation stripped (flat lines)
  - Broken identifiers: spaces injected into tokens, e.g. `sys .argv`, `pts .append`, `i[ 0]`
  - Line numbers mixed with code, broken syntax highlighting markers
  - Keywords wrapped in inline backticks instead of a fenced block, e.g. `` `import` sys ``

  Example (BAD — indentation and identifiers destroyed):
  ```
  `import` sys
  pts = []
  for i in range( 1,len(sys .argv), 2):
  pts .append([int(sys .argv[i]), int(sys .argv[i +1])])
  ```
  Correct version would have a code fence, proper indentation, and no spaces inside `sys.argv`.

  - Impact: Teaches incorrect code syntax, broken tokenization patterns, and wrong indentation conventions

**Key Question**: "Can the model learn proper formatting from this structure?"

---

## 2. Effectiveness (有效性)
**Impact**: Noise prevents models from learning meaningful semantic patterns.

**Check for**:
- **Error_Garbled_Characters**: Encoding issues or anti-crawler artifacts
  - Example (BAD): "â€™" (broken UTF-8), "□□□" (placeholder chars), "ï»¿" (BOM)
  - Threshold: >1% of characters are garbled
  - Impact: Corrupts token distributions

- **Error_Words_Stuck**: Missing spaces break tokenization
  - Example (BAD): "Thequickbrownfoxjumpsoverthelazydog"
  - Threshold: >1% of text has word boundaries missing
  - Impact: Wrong subword tokenization patterns

- **Error_Lack_Punctuation**: Sentence boundaries unclear
  - Example (BAD): "I like apples they are red also I like oranges"
  - Impact: Models cannot learn sentence segmentation

**Key Question**: "Would a human find this readable and coherent?"

---

## 3. Similarity (相似性)
**Impact**: Repetitive content reduces training efficiency and causes memorization.

**Check for**:
- **Error_Duplicate**: Excessive repetition that dominates the text
  - Example (BAD): "I like blue. I like blue. I like blue. I like blue..." (>30% duplicate)
  - Threshold: Same sentence/phrase repeats >5 times OR duplicate ratio >30%
  - Impact: Over-represents certain patterns

**Key Question**: "Does this text provide diverse training signal?"

---

## 4. Security (安全性)
**Impact**: Harmful content should not be learned by models.

**Check for**:
- **Error_Politics**: Content promoting extremism, terrorism, ethnic hatred
- **Error_Prohibition**: Violence, pornography, gambling, drugs

**Key Question**: "Is this content safe for model training?"

---

# Evaluation Principles

1. **Focus on Training Impact**: Only flag issues that significantly harm LLM learning
2. **Severity Matters**: Minor typos are OK; systemic corruption is not
3. **Context Awareness**: Academic formulas are expected in papers; garbled text never is
4. **Threshold-Based**: Use quantitative checks (>1%, >30%, >5 times) when possible

---

# Workflow

1. **Quick Scan**: Does the text look generally readable and well-formed?
2. **Identify Category**: If problematic, which dimension is most severely affected?
3. **Verify Impact**: Would this issue meaningfully harm model training?
4. **Assign Label**:
   - Score: 1 (suitable for training) or 0 (unsuitable)
   - Type: 'Good' OR one of ['Completeness', 'Effectiveness', 'Similarity', 'Security']
   - Name: Specific error type (see above)
   - Reason: Brief explanation (1-2 sentences)

---

# Output Format
Return JSON only: {"score": 0/1, "type": "", "name": "", "reason": ""}

# Examples

**Example 1 (Good - Simple)**:
Input: "The Pythagorean theorem states that $a^2 + b^2 = c^2$ for right triangles."
Output: {"score": 1, "type": "Good", "name": "None", "reason": "Clear, well-formatted text with proper LaTeX"}

**Example 1.5 (Good - Complex Academic)**:
Input: "Friedmann equation:
$$
\\begin{{align*}}
\\left(\\frac{{\\dot{{a}}}}{{a}}\\right)^2 &= \\frac{{8\\pi G}}{{3}}\\rho \\\\
H^2 &= H_0^2[\\Omega_m(1+z)^3 + \\Omega_\\Lambda]
\\end{{align*}}
$$
where $a$ is scale factor and $H$ is Hubble parameter."
Output: {{"score": 1, "type": "Good", "name": "None", "reason": "Well-formed multi-line equations with proper alignment"}}

**Example 1.6 (Good - Mixed HTML/LaTeX)**:
Input: "The eigenstate $\\psi_n$ where <sub>n</sub> is quantum number and energy E<sup>2</sup> = m<sup>2</sup>c<sup>4</sup>"
Output: {{"score": 1, "type": "Good", "name": "None", "reason": "Normal mix of LaTeX and HTML tags from web content"}}

**Example 2 (Bad - Completeness, broken delimiters)**:
Input: "The formula $x^2 + y^2 is broken here $$a = b$$$"
Output: {"score": 0, "type": "Completeness", "name": "Error_Formula", "reason": "Unmatched delimiters: first $ never closes, extra $ at end"}

**Example 2.5 (Bad - Completeness, stripped math)**:
Input: "Definition 1.(-solutions) A -solution is a Ricci flow which is -noncollapsed at every scale. Ancient, in the sense that t ranges on the interval ; Bounded curvature, thus ;"
Output: {{"score": 0, "type": "Completeness", "name": "Error_Formula", "reason": "Mathematical symbols systematically stripped: Greek letters removed ('-solutions' instead of 'κ-solutions'), formulas missing after 'the interval' and 'thus'"}}

**Example 3 (Bad - Effectiveness)**:
Input: "Theappleisredandtasty�withsomegarbledtext□□"
Output: {"score": 0, "type": "Effectiveness", "name": "Error_Garbled_Characters", "reason": "Contains encoding corruption (�, □) and missing spaces (>1% of text)"}

**Example 4 (Bad - Similarity)**:
Input: "Blue is nice. Blue is nice. Blue is nice. Blue is nice. Blue is nice. Blue is nice."
Output: {"score": 0, "type": "Similarity", "name": "Error_Duplicate", "reason": "Same sentence repeats 6 times, indicating low content diversity"}

---

# Input content to evaluate:

"""
    # process_response method is now inherited from BaseTextQuality
