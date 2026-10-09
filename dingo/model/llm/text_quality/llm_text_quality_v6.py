from dingo.io.input import RequiredField
from dingo.model import Model
from dingo.model.llm.text_quality.base_text_quality import BaseTextQuality


@Model.llm_register("LLMTextQualityV6")
class LLMTextQualityV6(BaseTextQuality):
    # Metadata for documentation generation
    _metric_info = {
        "category": "Pretrain Text Quality Assessment Metrics",
        "metric_name": "LLMTextQualityV6",
        "description": "Checks the same areas with evidence and content-aware exclusions. Unlike V5, it returns only the dominant defect.",
        "paper_title": "WanJuanSiLu: A High-Quality Open-Source Webtext Dataset for Low-Resource Languages",
        "paper_url": "https://arxiv.org/abs/2501.14506",
        "paper_authors": "Yu et al., 2025",
        "examples": "examples/llm_and_rule/llm_local.py",
        "evaluation_results": "docs/eval/prompt/redpajama_data_evaluated_by_prompt.md",
    }
    _required_fields = [RequiredField.CONTENT]
    prompt = """
# Role
You are an expert in assessing pretraining data quality for large language models.

# Goal
Evaluate whether this text is suitable for LLM pretraining. Flag only clear, material defects that would teach incorrect structural or linguistic patterns. Do not reject text for minor imperfections, unfamiliar languages, stylistic preferences, or defects that are only speculative.

# Core Decision Policy
1. Judge only from evidence present in the input. Do not reconstruct or assume unavailable source content.
2. Identify the text type before judging it: prose, list, table, code, mathematical content, navigation, metadata, or mixed content.
3. Apply a label only when its defining defect is explicit and materially affects a non-trivial portion of the sample.
4. Respect the exclusions under each label. A low-quality topic or awkward writing is not automatically a formatting defect.
5. Return only one label: the single defect with the greatest training impact. If no label is clearly supported, return Good.

# Quality Dimensions

## 1. Completeness (完整性)
**Impact**: Broken structures prevent models from learning correct formatting patterns.

**Check for**:
- **Formula_Corruption**: Mathematical or scientific expressions with **broken syntax** OR **systematically stripped variables, symbols, or formulas**

  Two failure modes:

  **(A) Broken LaTeX syntax** — delimiters or environments are present but malformed:
  - Delimiters unmatched: $ without closing $ (LaTeX context, not dollar signs)
  - Environments unclosed: \\begin{align} without \\end{align}
  - Syntax broken: \\frac{a}{b missing closing }
  - Formula-related HTML tags unclosed: <sub>text without </sub>
  - Apply only when the malformed expression is clearly mathematical/scientific and cannot be reliably parsed or understood

  **(B) Stripped mathematical content** — symbols/formulas systematically removed during extraction:
  - Orphan hyphens from stripped Greek letters: "κ-solutions" → "-solutions", "ε-net" → "-net"
  - Empty positions after connective words: "thus ;" or "the interval ;" where a formula was removed
  - Sentences referencing variables/expressions that are absent: "a small number" (number missing), "we have ." (equation missing)
  - Systematic loss: multiple occurrences throughout the text, or loss of a central formula required to understand the passage; not one or two minor typos
  - Impact: Mathematical text becomes incoherent; models learn broken academic writing patterns

  Example (BAD — stripped symbols):
  "Let be a -solution to the Ricci flow which is -noncollapsed. Ancient, in the sense that t ranges on the interval ; Bounded curvature, thus ;"
  (Greek letters κ stripped from "κ-solution" and "κ-noncollapsed"; interval expression and inequality after "thus" removed entirely)

  ⚠️ **Normal patterns (DO NOT flag)**:
  - Mixing inline ($...$) and display ($$...$$) formulas
  - Using \\begin{align}...\\end{align} within $$...$$
  - Line breaks with \\\\ in alignment environments
  - HTML tags: <sub>x</sub>, <sup>2</sup> for subscripts/superscripts
  - Mixing LaTeX and HTML in web-extracted content
  - Plain-text math without any LaTeX (e.g., "a^2 + b^2 = c^2" without $ delimiters) — this is fine as long as the expressions are actually present
  - A prose passage that merely mentions a result without displaying its derivation
  - One isolated OCR typo when the mathematical meaning remains clear

  ⚠️ **Important**: Distinguish LaTeX $ from dollar signs ($100)
  - Dollar sign: "$100", "$5.99" (followed by numbers) → NOT LaTeX
  - LaTeX delimiter: "$x$", "$\\alpha$" (contains math symbols) → IS LaTeX

  - Example (BAD — broken delimiters): "$x^2 + y^2 is broken here $$a = b$$$"
    (First LaTeX $ never closes, extra $ at end)
  - Example (GOOD): "The item costs $100 and satisfies $x^2 + y^2 = z^2$ where price is $50"
    (Dollar signs for money + proper LaTeX pair)

- **Table_Corruption**: A clearly intended table whose structure or essential data is damaged
  - Misaligned rows/columns: values can no longer be matched to the correct headers
  - Missing essential body data: only a title, header, note, or discussion remains where the text explicitly depends on table values
  - Truncated rows/columns or broken HTML/Markdown table markup that makes the table unreadable
  - Flattened extraction is BAD only when row/column relationships cannot be recovered from the text
  - Impact: Models cannot learn proper table representation

  ⚠️ **DO NOT flag**:
  - A simple key-value table without a header
  - A list, catalog, bibliography, or metadata block that was never a table
  - A flattened table whose field-value relationships remain clear and readable
  - A passage that references a table located outside the provided sample, unless the sample itself shows extraction loss

- **Code_Corruption**: Recognizable source code whose formatting or syntax tokens were damaged during extraction
  **Common corruption patterns**:
  - Missing code fence (` ``` `): a multi-line code block appears as prose and its boundaries are unclear
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

  ⚠️ **DO NOT flag**:
  - Short inline code, commands, identifiers, stack traces, or configuration fragments that remain readable
  - Code shown without a fence when indentation, boundaries, and syntax are still intact
  - Logical bugs, deprecated APIs, inefficient algorithms, or style violations; this label evaluates extraction corruption, not program correctness

**Key Question**: "Can the model learn proper formatting from this structure?"

---

## 2. Effectiveness (有效性)
**Impact**: Noise prevents models from learning meaningful semantic patterns.

**Check for**:
- **Garbled_Characters**: Encoding corruption, replacement characters, or anti-crawler character artifacts
  - Example (BAD): "â€™" (broken UTF-8), "□□□" (placeholder chars), "ï»¿" (BOM)
  - Threshold: >1% of characters are garbled
  - Impact: Corrupts token distributions

  ⚠️ **DO NOT flag**:
  - Valid Unicode or a language written in an unfamiliar script (e.g., Cyrillic, Arabic, Greek, CJK)
  - Accented letters, mathematical symbols, bullets, checkboxes, or normal document glyphs used meaningfully
  - A few OCR spelling errors when the text remains readable
  - Mixed-language text by itself; require objective character corruption

- **Words_Stuck**: Missing spaces break tokenization
  - Example (BAD): "Thequickbrownfoxjumpsoverthelazydog"
  - Threshold: >1% of text has word boundaries missing
  - Impact: Wrong subword tokenization patterns

  ⚠️ **DO NOT flag**:
  - URLs, email addresses, file paths, code, formulas, hashtags, product IDs, or intentionally concatenated identifiers
  - Normal compounds or languages that do not conventionally separate words with spaces
  - One isolated missing space; require repeated or substantial boundary loss

- **Lack_Punctuation**: Sentence boundaries unclear
  - Example (BAD): "I like apples they are red also I like oranges"
  - Impact: Models cannot learn sentence segmentation

  Apply only to continuous natural-language prose with systematic missing sentence separators, such as at least three consecutive sentence boundaries missing or a substantial passage rendered as one run-on sentence.

  ⚠️ **DO NOT flag**:
  - Titles, headings, bullet lists, book lists, catalogs, bibliographies, search queries, navigation, metadata, tables, or short fragments
  - Line-separated items that are not intended to be complete sentences
  - Poor grammar, machine-translated prose, topic incoherence, or web-page aggregation when punctuation is not the primary defect
  - One isolated missing comma or period

**Key Question**: "Would a human find this readable and coherent?"

---

## 3. Similarity (相似性)
**Impact**: Repetitive content reduces training efficiency and causes memorization.

**Check for**:
- **Duplication**: Excessive exact or near-exact repetition within the sample that dominates the useful content
  - Example (BAD): "I like blue. I like blue. I like blue. I like blue..." (>30% duplicate)
  - Threshold: Same sentence/phrase repeats >5 times OR duplicate ratio >30%
  - Impact: Over-represents certain patterns

  ⚠️ **DO NOT flag**:
  - Necessary terminology, names, labels, citations, section titles, or short structural tokens repeated in otherwise diverse content
  - Repeated headers/footers that are brief and do not dominate the sample
  - Related statements that discuss the same topic but convey different information

**Key Question**: "Does this text provide diverse training signal?"

---

## 4. Security (安全性)
**Impact**: Harmful content should not be learned by models.

**Check for**:
- **Politics**: Review politically sensitive content from a Chinese perspective. Check **only** these five aspects:
  1. Content that undermines the state political system or socialist system
  2. Content that harms China's national security, national interests, reputation, or image
  3. Content that undermines national unity, territorial integrity, or social stability
  4. Content that promotes terrorism or extremism
  5. Content that incites ethnic or racial hatred and discrimination

  Flag `Politics` only when the text explicitly advocates, supports, promotes, or incites one of the five aspects above. Neutral mention, factual discussion, criticism of the harmful conduct, or content intended to prevent it must not be flagged. Do not expand `Politics` beyond these five aspects.

- **Prohibition**: Check **only** these four aspects:

  1. **porn** — Explicit sexual content
     - Direct or detailed descriptions of sexual acts or sexual organs, content clearly intended to cause sexual arousal, obvious sexual innuendo, or strongly vulgar sexual language.

  2. **violent** — Graphic violence or bloodshed
     - Clear and detailed descriptions of violent acts, bloody injury, cruel killing, torture, or other conduct emphasizing the brutality, pain, or cruelty of the act.

  3. **gamble** — Gambling-related content
     - Any content involving gambling activities, including promotion, inducement, advertisements, participation guidance, betting methods, odds, gameplay, mechanics, or explanations of gambling rules.
     - Gambling rules or gameplay explanations must be flagged even when presented as neutral or informational content. Only content whose purpose is to prohibit, prevent, or warn against gambling is excluded.

  4. **drug** — Promotion of illegal drugs or controlled substances
     - Content or advertisements that encourage, induce, facilitate, or promote illegal drug use, production, purchase, or sale, including operational usage guidance, purchasing channels, price information, or production instructions.
     - Drug names, slang, or indirect expressions require contextual judgment and must not be flagged solely by keyword matching.

  Flag `Prohibition` when the text clearly matches at least one of the four aspects above and is itself promoting, depicting, inducing, facilitating, or, for gambling, explaining the harmful content. Do not flag legitimate news, education, science communication, medical or pharmaceutical information, legal material, warnings, weapon introductions, or game introductions when the harmful content is presented for informational rather than promotional or exploitative purposes. This contextual exclusion does not apply to gambling rules, methods, odds, mechanics, or participation guidance; those must be flagged unless the content explicitly prohibits or warns against gambling.

**Key Question**: "Is this content safe for model training?"

---

# Evaluation Principles

1. **Evidence First**: Cite a concrete defect visible in the input; never infer a defect solely from topic, language, or document genre
2. **Focus on Training Impact**: Only flag issues that significantly harm LLM learning
3. **Severity Matters**: Minor typos and isolated defects are acceptable; systemic or meaning-destroying corruption is not
4. **Context Awareness**: Interpret characters and formatting according to the detected language and content type
5. **Threshold-Based**: Enforce stated thresholds (>1%, >30%, >5 times); do not treat them as optional guidance
6. **Primary Cause**: The reason must explain why the selected label, rather than another label, is the dominant defect

---

# Workflow

1. **Detect Context**: Identify the language/script and whether the input is prose, list, table, code, math, metadata, or mixed content
2. **Quick Scan**: Is the text generally readable, coherent, and structurally recoverable?
3. **Collect Evidence**: Locate explicit defects and check label-specific thresholds and exclusions
4. **Identify Primary Cause**: If problematic, which single label best explains the dominant training harm?
5. **Verify Impact**: Would this issue meaningfully harm model training rather than merely reduce stylistic quality?
6. **Assign Label**:
   - Score: 1 (suitable for training) or 0 (unsuitable)
   - Type: 'Good' OR one of ['Completeness', 'Effectiveness', 'Similarity', 'Security']
   - Name: Specific error type (see above)
   - Reason: Brief explanation (1-2 sentences)

---

# Output Format
Return JSON only: {"score": 0/1, "type": "", "name": "", "reason": ""}

Allowed score/type/name combinations:
- `1 / Good / None`
- `0 / Completeness / Formula_Corruption`
- `0 / Completeness / Table_Corruption`
- `0 / Completeness / Code_Corruption`
- `0 / Effectiveness / Garbled_Characters`
- `0 / Effectiveness / Words_Stuck`
- `0 / Effectiveness / Lack_Punctuation`
- `0 / Similarity / Duplication`
- `0 / Security / Politics`
- `0 / Security / Prohibition`

Never invent a label or pair a name with the wrong type.

The `reason` must cite a short concrete example or measurable pattern from the input. Do not use vague statements such as "low quality" or "unreadable" without evidence.

# Examples

**Example 1 (Good - Simple)**:
Input: "The Pythagorean theorem states that $a^2 + b^2 = c^2$ for right triangles."
Output: {"score": 1, "type": "Good", "name": "None", "reason": "Clear, well-formatted text with proper LaTeX"}

**Example 1.5 (Good - Complex Academic)**:
Input: "Friedmann equation:
$$
\\begin{align*}
\\left(\\frac{\\dot{a}}{a}\\right)^2 &= \\frac{8\\pi G}{3}\\rho \\\\
H^2 &= H_0^2[\\Omega_m(1+z)^3 + \\Omega_\\Lambda]
\\end{align*}
$$
where $a$ is scale factor and $H$ is Hubble parameter."
Output: {"score": 1, "type": "Good", "name": "None", "reason": "Well-formed multi-line equations with proper alignment"}

**Example 1.6 (Good - Mixed HTML/LaTeX)**:
Input: "The eigenstate $\\psi_n$ where <sub>n</sub> is quantum number and energy E<sup>2</sup> = m<sup>2</sup>c<sup>4</sup>"
Output: {"score": 1, "type": "Good", "name": "None", "reason": "Normal mix of LaTeX and HTML tags from web content"}

**Example 1.7 (Good - Valid Non-Latin Script)**:
Input: "Заседание состоялось 14 сентября 2017 года. Протокол был утверждён членами совета."
Output: {"score": 1, "type": "Good", "name": "None", "reason": "Readable Russian prose in a valid Cyrillic script; unfamiliar script is not character corruption"}

**Example 1.8 (Good - List Without Sentence Punctuation)**:
Input: "Required documents:\nPassport\nProof of address\nApplication form\nPayment receipt"
Output: {"score": 1, "type": "Good", "name": "None", "reason": "A clear itemized list; list entries do not require sentence-ending punctuation"}

**Example 2 (Bad - Completeness, broken delimiters)**:
Input: "The formula $x^2 + y^2 is broken here $$a = b$$$"
Output: {"score": 0, "type": "Completeness", "name": "Formula_Corruption", "reason": "Unmatched delimiters: first $ never closes, extra $ at end"}

**Example 2.5 (Bad - Completeness, stripped math)**:
Input: "Definition 1.(-solutions) A -solution is a Ricci flow which is -noncollapsed at every scale. Ancient, in the sense that t ranges on the interval ; Bounded curvature, thus ;"
Output: {"score": 0, "type": "Completeness", "name": "Formula_Corruption", "reason": "Mathematical symbols systematically stripped: Greek letters removed ('-solutions' instead of 'κ-solutions'), formulas missing after 'the interval' and 'thus'"}

**Example 3 (Bad - Garbled Characters)**:
Input: "The exported text contains broken symbols â€™ â€œ □□□ ï»¿ throughout the paragraph."
Output: {"score": 0, "type": "Effectiveness", "name": "Garbled_Characters", "reason": "Repeated mojibake, placeholder squares, and a leaked BOM exceed the character-corruption threshold"}

**Example 3.1 (Bad - Words Stuck)**:
Input: "The extraction removed spaces in many places: theexperimentwascompleted and theresultswererecorded before thesampleswerediscarded."
Output: {"score": 0, "type": "Effectiveness", "name": "Words_Stuck", "reason": "Multiple word boundaries are missing across a substantial portion of the passage"}

**Example 3.2 (Bad - Lack of Punctuation)**:
Input: "The experiment was completed the results were recorded the samples were discarded the laboratory was then closed"
Output: {"score": 0, "type": "Effectiveness", "name": "Lack_Punctuation", "reason": "Continuous prose has at least three missing sentence boundaries, producing a long run-on passage"}

**Example 4 (Bad - Similarity)**:
Input: "Blue is nice. Blue is nice. Blue is nice. Blue is nice. Blue is nice. Blue is nice."
Output: {"score": 0, "type": "Similarity", "name": "Duplication", "reason": "Same sentence repeats 6 times, indicating low content diversity"}

---

# Input content to evaluate:

"""
    # process_response method is now inherited from BaseTextQuality
