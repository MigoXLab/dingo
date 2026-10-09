from dingo.model import Model
from dingo.model.llm.text_quality.base_text_quality_v2 import BaseTextQualityV2


@Model.llm_register("LLMTextQualityV7")
class LLMTextQualityV7(BaseTextQualityV2):
    """Multi-label text quality evaluator with a self-contained prompt."""

    _statistics_fields = (
        "formula_count",
        "table_count",
        "code_count",
        "error_formula_count",
        "error_table_count",
        "error_code_count",
        "Formula_Missing",
        "Formula_Partial_Loss",
        "Formula_Token_Corruption",
        "Formula_Unparseable",
        "Formula_Structure_Corruption",
        "Formula_Layout_Corruption",
        "Formula_Extra_Content",
        "Table_Missing",
        "Table_Unparseable",
        "Table_Partial_Loss",
        "Table_Cell_Corruption",
        "Table_Header_Corruption",
        "Table_Structure_Corruption",
        "Table_Layout_Corruption",
        "Table_Extra_Content",
        "Code_Missing",
        "Code_Unparseable",
        "Code_Partial_Loss",
        "Code_Token_Corruption",
        "Code_Layout_Corruption",
        "Code_Extra_Content",
    )

    _metric_info = {
        "category": "Pretrain Text Quality Assessment Metrics",
        "metric_name": "LLMTextQualityV7",
        "description": "Checks formula, table, code, readability, duplication, and safety in detail. Unlike V6, it supports multiple findings and counts formula, table, and code structures.",
        "paper_title": "WanJuanSiLu: A High-Quality Open-Source Webtext Dataset for Low-Resource Languages",
        "paper_url": "https://arxiv.org/abs/2501.14506",
        "paper_authors": "Yu et al., 2025",
        "examples": "examples/llm_and_rule/llm_local.py",
        "evaluation_results": "docs/eval/prompt/redpajama_data_evaluated_by_prompt.md",
    }
    prompt = r"""
# Role
You are an expert in assessing pretraining data quality for large language models.

# Goal
Evaluate whether this text is suitable for LLM pretraining. Flag only clear, material defects that would teach incorrect structural or linguistic patterns. Do not reject text for minor imperfections, unfamiliar languages, stylistic preferences, or defects that are only speculative.

# Core Decision Policy
1. Judge only from evidence present in the input. Do not reconstruct or assume unavailable source content.
2. Identify the text type before judging it: prose, list, table, code, mathematical content, navigation, metadata, or mixed content.
3. Apply a label only when its defining defect is explicit and materially affects a non-trivial portion of the sample.
4. Respect the exclusions under each label. A low-quality topic or awkward writing is not automatically a formatting defect.
5. Return every clearly supported label. Each label must describe a distinct material defect; do not emit duplicates or speculative secondary labels. If no label is clearly supported, return only Good.

# Quality Dimensions

## 1. Completeness (完整性)
**Impact**: Broken structures prevent models from learning correct formatting patterns.

**Check for**:
- **Formula quality labels**: Evaluate extraction or representation defects in mathematical formulas, equations, chemical formulas, chemical structures, and formula-like scientific notation. Do not evaluate whether a mathematically well-formed statement is factually true.

  **Shared formula policy**:
  - Use only evidence visible in the input. Do not reconstruct a source formula from outside knowledge.
  - A defect must be explicit and materially affect understanding, parsing, or display. Do not flag a harmless isolated style difference.
  - For one damaged span, return the single label that most directly describes the defect. Do not describe the same missing brace, symbol, or fragment with multiple labels.
  - Multiple formula labels are allowed only for independent defects, such as one entirely missing formula and a different formula contaminated by a page header.
  - Ordinary prose typos, game notation, navigation, numbering, and non-formula text are outside these labels.

  **Formula_Missing** — An entire formula, equation, matrix, or chemical structure that should visibly be present is absent.
  - Flag when an introduction such as "the formula is", "we obtain", "the matrix is", or "the structure is" is followed by no formula.
  - Flag when only a formula number or placeholder such as `[Formula 1]`, `[Chemical Formula 1]`, or `(I)` remains, while following text defines variables from the absent formula.
  - Flag when a formula position is replaced by an unrelated page header, page number, or paragraph, leaving the surrounding derivation broken.
  - Flag repeated references to absent equations only when the current sample visibly depends on them and the missing content breaks the derivation.
  - Do not flag an external citation, an explicitly omitted derivation, a harmless gap in equation numbering, or a passage that merely mentions a result without promising to display it.
  - Do not infer that a formula was missing merely because a formula would be useful.

  **Formula_Partial_Loss** — A formula remains, but a meaningful mathematical or scientific component has been removed.
  - Components include variables, constants, operators, relation or mapping symbols, operands, numerator or denominator, equation sides, function arguments, sum/integral limits, piecewise branches, chemical subscripts, charges, or complete subexpressions.
  - Examples include `T(s,a,s') [0,1]` with a visibly missing mapping arrow, `x+y=` with the right-hand side absent, a fraction with no denominator, or a chemical formula with a clearly missing element count.
  - Use this label when meaningful formula content is absent. If erroneous or garbled characters remain in its place, use Formula_Token_Corruption instead.
  - If only a LaTeX delimiter, required brace, or environment terminator is missing and parsing fails, use Formula_Unparseable instead.
  - Do not flag valid shorthand, an omitted derivation, or a term that is only suspected to be absent from domain knowledge.

  **Formula_Token_Corruption** — Formula characters, numbers, variables, or symbols are misrecognized, substituted, split, merged, or replaced by garbage.
  - Examples include `1.18` becoming `1 1 8`, `10^{-3}` becoming `1 0^{-3}`, `N_2` becoming `\Nu_2`, `lx` becoming `1x`, a variable becoming `�` or `□`, or `Var` becoming `V a r`.
  - Include corrupted decimal points, Greek/Latin letter substitutions, wrong OCR lookalikes, repeated garbage characters, and damaged chemical symbols when the input itself supports the corruption.
  - Do not flag valid Unicode math, legitimate variable naming, harmless LaTeX spacing, or unfamiliar notation.
  - If an external citation, page number, question number, or word is inserted into a formula, use Formula_Extra_Content instead.
  - Do not use domain knowledge alone to replace one valid-looking symbol with another.

  **Formula_Unparseable** — Broken LaTeX, Markdown, HTML, or MathML syntax prevents a standard parser from reliably identifying or rendering the formula.
  - Flag unmatched mathematical `$` or `$$` delimiters, unmatched `\(`/`\)` or `\[`/`\]`, missing required braces, mismatched or unclosed `\begin{...}`/`\end{...}` environments, unfinished commands, or unclosed formula-related HTML/MathML tags.
  - Flag raw LaTeX without math delimiters only when the target is clearly Markdown math and the commands consequently appear as unrendered source text.
  - Distinguish mathematical dollar delimiters from currency such as `$100` and `$5.99`.
  - Do not mechanically compare delimiter counts without context. `\left(a,b\right]` may be a valid half-open interval, and `\left.` or `\right.` is a valid invisible delimiter.
  - Do not flag well-formed `align`, `aligned`, `cases`, matrices, normal `\\` line breaks, or mixed LaTeX/HTML that renders correctly.
  - If the formula parses but its internal organization is damaged, use Formula_Structure_Corruption. If it parses but is placed or broken across lines incorrectly, use Formula_Layout_Corruption.

  **Formula_Structure_Corruption** — A formula can be parsed or rendered, but its internal hierarchy or component relationships were damaged during extraction.
  - Flag a multiplicative term moved into an exponent, a numerator and denominator placed incorrectly, reversed or displaced sum/integral limits, an operator with the wrong scope, a subscript attached to the wrong base, or formula fragments placed in the wrong internal order.
  - Flag damaged matrix rows or columns, lost array separators, corrupted determinants, malformed piecewise branches, or a `cases` expression converted into an unrelated structure such as `\binom`.
  - Require visible extraction evidence: an internal contradiction with a nearby definition, an intact copy elsewhere in the input, obvious layout reconstruction artifacts, or an unmistakably displaced formula component.
  - Do not flag a structurally complete statement solely because it is mathematically false, such as `2+2=5`.
  - Do not flag unusual but valid notation, or rewrite a formula merely because a more familiar form exists.
  - A single misrecognized character belongs to Formula_Token_Corruption; a missing component belongs to Formula_Partial_Loss; a parser failure belongs to Formula_Unparseable.

  **Formula_Layout_Corruption** — Formula content and internal structure are intact and parseable, but their placement, line breaks, or inline/display relationship with surrounding text is damaged.
  - Flag an inline formula forced onto its own line when this breaks sentence flow or produces abnormal display.
  - Flag one continuous equation split into separate math blocks, especially when one block ends with a dangling `+`, `-`, or `=` and the next block continues it.
  - Flag a display formula flattened into prose, a formula number separated from its formula, a formula moved to the wrong paragraph, or formula explanations placed in the wrong order.
  - Do not flag intentional display equations, harmless wrapping, normal multiline `align`/`cases`/matrix layouts, or an inline formula that merely wraps visually because of page width.
  - If a line break damages the delimiters and prevents parsing, use Formula_Unparseable. If unrelated text is inserted, use Formula_Extra_Content.

  **Formula_Extra_Content** — Non-formula content is inserted into a formula or attached to it in a way that forms an incorrect expression.
  - Flag a stray standalone `latex` token left after formulas, or leaked extractor/HTML markers.
  - Flag page headers, page footers, journal titles, author names, page numbers, dates, footnotes, captions, navigation, or unrelated prose inserted into a formula or derivation.
  - Flag citation numbers fused into formula exponents or subscripts, such as citation `[42]` turning `cm^{-1}` into `cm^{-142}`.
  - Flag question numbers fused into results, such as the next item number `1` turning an unfinished exercise into `145 × 12 = 1`.
  - Do not flag normal `\tag{3}`, a citation placed cleanly after a closed formula, normal explanatory prose following a formula, legitimate `\text{if}`/`\text{otherwise}`, units, or a document that is genuinely discussing LaTeX.
  - If there is only a placement or line-break problem and no foreign content was inserted, use Formula_Layout_Corruption.

  **Normal formula patterns (DO NOT flag)**:
  - Mixing inline `$...$` and display `$$...$$` formulas.
  - Using `\begin{align}...\end{align}` within `$$...$$`.
  - Normal `\\` line breaks in alignment, cases, or matrix environments.
  - Correct formula-related HTML such as `<sub>x</sub>` and `<sup>2</sup>`.
  - Mixing LaTeX and HTML in web-extracted content when the expressions remain correct and readable.
  - Plain-text math such as `a^2 + b^2 = c^2` without LaTeX delimiters when the target format allows it and the expression is complete.
  - A prose passage that mentions a result without displaying its derivation.
  - An isolated recoverable OCR typo that does not materially affect formula meaning.

- **Table quality labels**: Evaluate extraction or representation defects in HTML, Markdown, or plain-text tables. Do not evaluate whether a well-formed table is factually correct.

  **Shared table policy**:
  - Use only evidence visible in the input. Do not reconstruct a source table from outside knowledge.
  - A defect must be explicit and materially affect table parsing, field relationships, content, or display. Do not flag a harmless style difference.
  - For one damaged span, return the single label that most directly describes the defect. Do not describe the same missing cell, broken tag, or shifted value with multiple labels.
  - Multiple table labels are allowed only for independent defects, such as one entirely missing table and a different table contaminated by an image-storage URL.
  - A list, catalog, bibliography, metadata block, or key-value passage is not automatically a table.

  **Table_Missing** — An entire table or all meaningful body data that should visibly be present is absent.
  - Flag when an introduction such as "shown in the table below" or "parameters are as follows" is followed by no table before the next section or the end of the sample.
  - Flag when only a table number, caption, header, unit, legend, footnote, continuation marker, or source remains and no meaningful body rows survive.
  - Flag title-only gaps among neighboring numbered tables when the current text explicitly depends on the absent values.
  - Do not flag a table located outside the provided sample, an external reference, an intentionally omitted table, or a harmless gap in table numbering.
  - If meaningful rows or cells remain, use Table_Partial_Loss. If the content remains but is split or flattened, use Table_Layout_Corruption.

  **Table_Unparseable** — Broken HTML, Markdown, or other table markup prevents a standard parser from reliably identifying the table, rows, or cells.
  - Flag unclosed, orphaned, truncated, or wrongly nested `<table>`, `<tr>`, `<td>`, or `<th>` tags.
  - Flag malformed tag attributes or quotes when they destroy tag boundaries, such as an unfinished `<td colsp`.
  - Flag a Markdown table whose required separator row or cell delimiters are damaged so severely that row and column boundaries cannot be parsed.
  - Flag unescaped cell pipes only when they materially destabilize Markdown column parsing.
  - Do not mechanically compare tag or pipe counts; confirm that parsing actually fails or becomes unreliable.
  - If markup parses but grid relationships are wrong, use Table_Structure_Corruption. If valid table blocks are merely separated or displaced, use Table_Layout_Corruption.

  **Table_Partial_Loss** — A recognizable table remains, but meaningful rows, columns, cells, or contiguous content have been removed.
  - Flag missing numbered row ranges, an essential column left empty throughout, rows that retain labels but lose all values, or a table truncated after its first portion.
  - Flag cells cut off mid-value or mid-sentence when the missing continuation is explicit.
  - Flag a missing subgroup, year range, result column, total, parameter, or other necessary part when the surviving table makes the loss visible.
  - Do not flag intentional blank cells, valid merged cells, or explicit `N/A`, `NaN`, dash, or undisclosed values without evidence of extraction loss.
  - If no meaningful body data remains, use Table_Missing. If erroneous or garbage characters remain in place of the content, use Table_Cell_Corruption.

  **Table_Cell_Corruption** — A body cell remains in a recoverable row and column position, but its internal text, number, symbol, unit, or code is misrecognized, substituted, split, merged, repeated, or replaced by garbage.
  - Flag truncated or mangled entity names, OCR lookalike substitutions, damaged decimal points or signs, lost characters in identifiers, and corrupted IPA, currency, percentage, or unit symbols.
  - Flag long repetitive character runs or meaningless placeholder tokens that replace expected cell content.
  - Require visible extraction evidence, such as an intact form elsewhere in the input, a consistent table pattern, or unmistakable OCR artifacts.
  - If two neighboring fields or columns are fused into one cell, use Table_Structure_Corruption. If the damaged cell is a header, use Table_Header_Corruption.
  - If an external URL, page header, paragraph, or extractor marker is inserted, use Table_Extra_Content.
  - Do not use this label solely because a readable value seems factually or statistically implausible.

  **Table_Header_Corruption** — The body remains, but column names, grouped headers, subheaders, row-heading schemes, or header spans are missing, wrong, duplicated, truncated, or fused.
  - Flag an essential column with no header, two different years carrying the same year label, a header copied from an unrelated table, or multiple column names compressed into one header cell.
  - Flag a grouped header whose `rowspan` or `colspan` contradicts its visible subheaders, making the column meaning incomplete or wrong.
  - Flag a repeated header inserted into the table body only when it disrupts the header hierarchy rather than serving as a normal continuation header.
  - Do not flag valid multilevel headers, repeated headers on continuation pages, standard abbreviations, or a simple table that does not need an explicit header.
  - If the header is correct but body values are shifted, use Table_Structure_Corruption. If only a header remains with no body, use Table_Missing.

  **Table_Structure_Corruption** — The table markup can be parsed and content remains, but row, column, header, cell, or span relationships in the internal grid are damaged.
  - Flag rows shifted left or right, labels shifted between records, header and body column counts that cannot be reconciled, or values placed under the wrong headers.
  - Flag adjacent fields fused into one cell, one logical record split across rows, several records collapsed into a cell, or broken category hierarchies.
  - Flag incorrect `rowspan` or `colspan` usage that makes values cover the wrong rows or columns.
  - Do not flag valid merged cells merely because different rows contain different numbers of `<td>` elements.
  - If the markup itself cannot be parsed, use Table_Unparseable. If one cell's position is clear and only its tokens are damaged, use Table_Cell_Corruption.
  - Do not flag a readable value solely because it appears implausible; require visible evidence of extraction or relationship damage.

  **Table_Layout_Corruption** — Table content may remain locally parseable, but block-level placement, order, boundaries, or association among the header, body, caption, continuation, and surrounding section is damaged.
  - Flag one logical table split into disconnected blocks, a header separated from its body, rows dropped outside `</table>`, or a continuation detached from the original table.
  - Flag a multicolumn table flattened into disjoint lists only when row-to-value or header-to-value relationships can no longer be recovered.
  - Flag a table body placed under the wrong caption or section, or neighboring table captions and bodies placed in the wrong order.
  - Do not flag normal continuation tables, intentionally separate table blocks, harmless page wrapping, or plain-text tables whose relationships remain clear.
  - If the internal grid is damaged within one table, use Table_Structure_Corruption. If foreign material is inserted inside a table, use Table_Extra_Content.

  **Table_Extra_Content** — Content not belonging to the current table is inserted into the table or attached to a cell as incorrect data.
  - Flag raw S3 or extractor URLs, internal storage paths, leaked HTML/extractor markers, UI text, page headers, page footers, page numbers, or navigation inserted into cells.
  - Flag body paragraphs, section headings, captions, source lines, annotations, or an unrelated table inserted into the current table's row sequence.
  - Flag citations or footnote numbers fused into numeric values only when they form incorrect table data rather than a cleanly separated reference.
  - Do not flag legitimate notes, sources, units, formulas, images, links, or multiline descriptions that are valid table content.
  - If the table is merely positioned under the wrong caption or section, use Table_Layout_Corruption. If a cell itself contains OCR garbage without foreign material, use Table_Cell_Corruption.

  **Normal table patterns (DO NOT flag)**:
  - A simple key-value table without an explicit header.
  - Valid multilevel headers, `rowspan`, `colspan`, empty cells, totals, footnotes, and continuation headers.
  - A list, catalog, bibliography, or metadata block that was never intended to be a table.
  - A flattened or plain-text table whose field-value relationships remain clear and readable.
  - A passage that references a table outside the provided sample without visible evidence of extraction loss.
  - A syntactically valid, structurally coherent table containing unusual values; table labels evaluate extraction and representation, not factual truth.

- **Code quality labels**: Evaluate extraction or representation defects in source code, scripts, configuration, JSON, XML, and similar machine-readable snippets. Do not evaluate whether well-formed code is logically correct, efficient, secure, or runnable in the current environment.

  **Shared code policy**:
  - Use only evidence visible in the input. Do not reconstruct source code from external knowledge or preferred coding style.
  - A defect must be explicit and materially affect parsing, tokenization, block structure, or the boundary between code and surrounding content.
  - For one damaged span, return the single label that most directly describes the defect. Do not report the same truncated statement, broken delimiter, or inserted line number under several labels.
  - Multiple code labels are allowed only for independent defects, such as corrupted operators in one listing and IDE annotations inserted into a separate function.
  - A compiler error alone is not extraction evidence. Undefined variables, missing dependencies, logical bugs, deprecated APIs, and incomplete project context are outside these labels.

  **Code_Missing** — An entire code, script, configuration, or program listing that should visibly be present is absent.
  - Flag when "the code is shown below", "example implementation", or a similar introduction is followed by no code before the next section or the end of the sample.
  - Flag when only a listing number, caption, language marker, empty code container, output, or variable explanation remains while the referenced code is absent.
  - Flag a missing program in an exercise that explicitly asks the reader to analyze that program's output.
  - Do not flag external repository references, intentionally omitted implementations, prose that merely discusses an algorithm, or a code listing outside the provided sample.
  - If meaningful code remains, use Code_Partial_Loss. If the code remains but its fence, whitespace, or placement is damaged, use Code_Layout_Corruption.

  **Code_Unparseable** — Structural syntax boundaries are damaged so the relevant language parser cannot reliably build strings, expressions, statements, tags, or blocks.
  - Flag unmatched or wrongly nested quotes, parentheses, brackets, braces, tags, or language-specific block delimiters.
  - Flag malformed JSON escapes such as `\u00b`, broken JSON separators, malformed XML declarations, unclosed XML tags, or corrupted attribute quotes.
  - Flag code ending inside an unfinished string, expression, function call, tag, or other structural construct.
  - Do not mechanically count delimiters; account for comments, strings, escapes, language syntax, and intentionally partial examples.
  - If a specific wrong keyword, identifier, operator, or character visibly remains, use Code_Token_Corruption. If a substantial program tail is absent, use Code_Partial_Loss.
  - Do not flag code that parses but has runtime, type, dependency, API, or logical errors.

  **Code_Partial_Loss** — Recognizable code remains, but a meaningful function, statement, declaration, branch, loop, return path, or contiguous program portion has been removed.
  - Flag a function or program truncated inside nested control flow, especially when references or the next document section begin before the required closing logic.
  - Flag a listing that starts with local statements while its function signature, parameters, or necessary opening portion is visibly missing.
  - Flag a missing implementation phase, subgroup of configuration entries, program tail, or return logic when the surviving code explicitly shows the gap.
  - Do not flag deliberate `...`, `pass`, `TODO`, pseudocode, core-algorithm excerpts, diffs, or documented omission.
  - If the entire listing is absent, use Code_Missing. If only a structural delimiter is broken, use Code_Unparseable. If erroneous tokens remain in place of missing content, use Code_Token_Corruption.

  **Code_Token_Corruption** — Keywords, identifiers, operators, numbers, string characters, paths, escapes, or other lexical tokens are misrecognized, substituted, split, fused, or replaced by garbage.
  - Flag `int` becoming `at`, `-=` becoming `μ=`, MATLAB `[~, EEG]` becoming `[-, EEG]`, or an identifier acquiring unrelated characters.
  - Flag spaces removed between a function and its argument, such as `(setq ss ...)` becoming `(setqss ...)`, or spaces injected inside identifiers, paths, and operators.
  - Flag corrupted decimal points, prefixes, array indices, command names, quotation characters, and long repetitive garbage strings such as `UUUU...` when they replace code tokens.
  - Require visible OCR or extraction evidence, such as an intact occurrence elsewhere, a consistent local pattern, or unmistakable garbage characters.
  - If lost line breaks merge complete statements or comments, use Code_Layout_Corruption. If foreign markup, line numbers, or UI text is inserted, use Code_Extra_Content.
  - Do not flag unconventional but valid naming, Unicode identifiers, unfamiliar domain syntax, or a token suspected to be wrong only from outside knowledge.

  **Code_Layout_Corruption** — Code tokens and statements largely remain, but line breaks, indentation, fences, comment boundaries, block order, or placement relative to prose is damaged.
  - Flag lost line breaks that cause `//` comments to swallow later declarations or statements.
  - Flag a preprocessor directive or continuation split across lines so that its meaning changes, such as `#define name` separated from its value.
  - Flag indentation loss in Python, YAML, Makefiles, or other indentation-sensitive formats when block hierarchy can no longer be recovered.
  - Flag a wrapped MATLAB comment whose continuation loses `%` and becomes code, or a code listing split into disconnected blocks or interleaved with prose.
  - Flag missing fences only when code/prose boundaries or code structure become unclear; a fence is not mandatory by itself.
  - Do not flag valid minified code, harmless wrapping, alternate brace style, normal continuation syntax, or code in a recognizable `<pre>`, `<code>`, or extractor-specific code container.
  - If substantive code is absent, use Code_Partial_Loss. If foreign content is inserted into code, use Code_Extra_Content.

  **Code_Extra_Content** — Line numbers, IDE annotations, question text, LaTeX markup, page artifacts, extractor markers, or other content not belonging to the program is inserted into code.
  - Flag IDE text such as `1 usage` or `3 references` embedded beside a function definition.
  - Flag PDF line numbers copied into code tokens, or a subsequent exam question inserted before the current function or loop closes.
  - Flag LaTeX wrappers such as `$...$`, `\mathtt{...}`, or `\equiv` injected into assignments, identifiers, or code punctuation.
  - Flag page headers, page footers, storage URLs, image placeholders, navigation, captions, or unrelated program fragments inserted into a listing.
  - Do not flag legitimate comments, docstrings, license headers, clearly separated display line numbers, REPL or shell prompts, debug output, or code that intentionally demonstrates LaTeX/HTML/Markdown syntax.
  - If the material after a mathematical formula is only a stray `latex` token, use Formula_Extra_Content rather than a code label.
  - If valid code lines are excessively repeated, use the existing Duplication label; do not invent Code_Duplication.

  **Normal code patterns (DO NOT flag)**:
  - Readable code without Markdown fences when its boundaries, indentation, and syntax remain clear.
  - Short inline code, commands, identifiers, stack traces, configuration fragments, diffs, REPL sessions, and pseudocode used appropriately.
  - Valid compact or minified code, unconventional formatting, Unicode identifiers, and language-specific syntax.
  - A snippet that is not a complete project and therefore lacks imports, dependencies, surrounding declarations, tests, or runtime context.
  - Logical bugs, deprecated APIs, insecure practices, style violations, inefficient algorithms, or code that does not produce the intended result without visible extraction damage.

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
2. **Collect Statistics**: Count each distinct formula, table, and code structure, then count how many distinct present structures in each category have at least one supported defect
3. **Quick Scan**: Is the text generally readable, coherent, and structurally recoverable?
4. **Collect Evidence**: Locate explicit defects and check label-specific thresholds and exclusions
5. **Identify Defects**: Collect every distinct label whose threshold is independently met.
6. **Verify Impact**: Would this issue meaningfully harm model training rather than merely reduce stylistic quality?
7. **Assign Labels**:
   - Return one object per supported defect, each with score 0
   - If no defect is supported, return exactly one Good object with score 1
   - Type: 'Good' OR one of ['Completeness', 'Effectiveness', 'Similarity', 'Security']
   - Name: Specific error type (see above)
   - Reason: Brief explanation (1-2 sentences)

---

# Output Format
Return one JSON object only:
{"statistics": {"formula_count": 0, "table_count": 0, "code_count": 0, "error_formula_count": 0, "error_table_count": 0, "error_code_count": 0, "Formula_Missing": 0, "Formula_Partial_Loss": 0, "Formula_Token_Corruption": 0, "Formula_Unparseable": 0, "Formula_Structure_Corruption": 0, "Formula_Layout_Corruption": 0, "Formula_Extra_Content": 0, "Table_Missing": 0, "Table_Unparseable": 0, "Table_Partial_Loss": 0, "Table_Cell_Corruption": 0, "Table_Header_Corruption": 0, "Table_Structure_Corruption": 0, "Table_Layout_Corruption": 0, "Table_Extra_Content": 0, "Code_Missing": 0, "Code_Unparseable": 0, "Code_Partial_Loss": 0, "Code_Token_Corruption": 0, "Code_Layout_Corruption": 0, "Code_Extra_Content": 0}, "findings": [{"score": 0/1, "type": "", "name": "", "reason": ""}]}

Statistics rules:
- Count only structures in the input content after `# Input content to evaluate:`; never count structures shown in this prompt or its examples.
- `formula_count`: Count each distinct inline formula, display equation, equation environment, MathML formula, chemical formula, or formula-like scientific expression as one. A multi-line equation environment is one formula structure.
- `table_count`: Count each complete or partial logical table as one, regardless of its number of rows, columns, or markup blocks.
- `code_count`: Count each distinct code, script, configuration, JSON, XML, or other machine-readable snippet as one. A fenced block is one code structure.
- `error_formula_count`: Count distinct present formula structures that have at least one supported `Formula_*` defect.
- `error_table_count`: Count distinct present table structures that have at least one supported `Table_*` defect.
- `error_code_count`: Count distinct present code structures that have at least one supported `Code_*` defect.
- Classify by semantic purpose: table markup counts as a table rather than code, and formula markup counts as a formula rather than code. Do not double-count the same structure across categories.
- Count defective, partial, and unparseable structures as present when their boundaries or surviving content identify them. Include them in both the category total and its error count.
- Count each defective structure only once in its error count even when it has multiple supported defect labels. Error counts measure defective structures, not labels or defect occurrences.
- For every allowed `Formula_*`, `Table_*`, and `Code_*` label, return a same-named key in `statistics` containing the number of distinct structures with that label. Always return all label-count keys, using zero for labels that do not occur. For example, `"Formula_Token_Corruption": 3` means three formulas are affected, `"Table_Cell_Corruption": 2` means two tables are affected, and `"Code_Unparseable": 1` means one code structure is affected.
- Do not add any other key to `statistics`. General findings such as `Words_Stuck`, `Garbled_Characters`, `Lack_Punctuation`, and `Duplication` belong only in `findings`, not in `statistics`.
- Count a structure once under each applicable label. If one structure has two independent supported defects with different labels, it contributes one to each label count, while still contributing only one to its category's `error_*_count`.
- `Formula_Missing`, `Table_Missing`, and `Code_Missing` count distinct explicitly missing structures even though those absent structures do not contribute to their category total or `error_*_count`.
- Every positive label count requires the matching object in `findings`, and every `Formula_*`, `Table_*`, or `Code_*` finding requires a positive matching count. Each non-Missing label count must not exceed its corresponding category total.
- A completely missing structure represented only by prose, a caption, or a placeholder contributes zero to both its category total and its error count. A `Formula_Missing`, `Table_Missing`, or `Code_Missing` finding alone therefore does not increase an error count.
- Each error count must be less than or equal to its corresponding total count.
- If an error count is greater than zero, `findings` must contain at least one matching non-Missing defect label for that category. Conversely, a supported non-Missing `Formula_*`, `Table_*`, or `Code_*` finding requires at least one error structure in that category.
- If `findings` contains only the Good object, all three error counts must be zero.
- All six counts must be non-negative integers.

For defective text, include all independently supported labels. Do not include a Good object together with defect objects. Emit each label at most once.

Allowed score/type/name combinations:
- `1 / Good / None`
- `0 / Completeness / Formula_Missing`
- `0 / Completeness / Formula_Partial_Loss`
- `0 / Completeness / Formula_Token_Corruption`
- `0 / Completeness / Formula_Unparseable`
- `0 / Completeness / Formula_Structure_Corruption`
- `0 / Completeness / Formula_Layout_Corruption`
- `0 / Completeness / Formula_Extra_Content`
- `0 / Completeness / Table_Missing`
- `0 / Completeness / Table_Unparseable`
- `0 / Completeness / Table_Partial_Loss`
- `0 / Completeness / Table_Cell_Corruption`
- `0 / Completeness / Table_Header_Corruption`
- `0 / Completeness / Table_Structure_Corruption`
- `0 / Completeness / Table_Layout_Corruption`
- `0 / Completeness / Table_Extra_Content`
- `0 / Completeness / Code_Missing`
- `0 / Completeness / Code_Unparseable`
- `0 / Completeness / Code_Partial_Loss`
- `0 / Completeness / Code_Token_Corruption`
- `0 / Completeness / Code_Layout_Corruption`
- `0 / Completeness / Code_Extra_Content`
- `0 / Effectiveness / Garbled_Characters`
- `0 / Effectiveness / Words_Stuck`
- `0 / Effectiveness / Lack_Punctuation`
- `0 / Similarity / Duplication`
- `0 / Security / Politics`
- `0 / Security / Prohibition`

Never invent a label or pair a name with the wrong type.

The `reason` must cite a short concrete example or measurable pattern from the input. Do not use vague statements such as "low quality" or "unreadable" without evidence.

# Examples

The example outputs below show only the contents of the `findings` array for readability. The actual response must always use the complete JSON object required by `# Output Format`, including `statistics`.

**Example 1 (Good - Simple)**:
Input: "The Pythagorean theorem states that $a^2 + b^2 = c^2$ for right triangles."
Output: [{"score": 1, "type": "Good", "name": "None", "reason": "Clear, well-formatted text with proper LaTeX"}]

**Example 1.5 (Good - Complex Academic)**:
Input: "Friedmann equation:
$$
\begin{align*}
\left(\frac{\dot{a}}{a}\right)^2 &= \frac{8\pi G}{3}\rho \\
H^2 &= H_0^2[\Omega_m(1+z)^3 + \Omega_\Lambda]
\end{align*}
$$
where $a$ is scale factor and $H$ is Hubble parameter."
Output: [{"score": 1, "type": "Good", "name": "None", "reason": "Well-formed multi-line equations with proper alignment"}]

**Example 1.6 (Good - Mixed HTML/LaTeX)**:
Input: "The eigenstate $\psi_n$ where <sub>n</sub> is quantum number and energy E<sup>2</sup> = m<sup>2</sup>c<sup>4</sup>"
Output: [{"score": 1, "type": "Good", "name": "None", "reason": "Normal mix of LaTeX and HTML tags from web content"}]

**Example 1.7 (Good - Valid Non-Latin Script)**:
Input: "Заседание состоялось 14 сентября 2017 года. Протокол был утверждён членами совета."
Output: [{"score": 1, "type": "Good", "name": "None", "reason": "Readable Russian prose in a valid Cyrillic script; unfamiliar script is not character corruption"}]

**Example 1.8 (Good - List Without Sentence Punctuation)**:
Input: "Required documents:
Passport
Proof of address
Application form
Payment receipt"
Output: [{"score": 1, "type": "Good", "name": "None", "reason": "A clear itemized list; list entries do not require sentence-ending punctuation"}]

**Example 1.9 (Good - Valid Multilevel Table)**:
Input: "<table><tr><th rowspan='2'>Region</th><th colspan='2'>Sales</th></tr><tr><th>2023</th><th>2024</th></tr><tr><td>North</td><td>120</td><td>135</td></tr></table>"
Output: [{"score": 1, "type": "Good", "name": "None", "reason": "The multilevel header and merged cells form a valid, recoverable table structure"}]

**Example 1.10 (Good - Readable Code Without Fences)**:
Input: "def total(values):
    return sum(values)

print(total([1, 2, 3]))"
Output: [{"score": 1, "type": "Good", "name": "None", "reason": "The Python code has clear boundaries, valid indentation, and intact syntax even without a Markdown fence"}]

**Example 2 (Bad - Entire Formula Missing)**:
Input: "The compound has the following structure: [Chemical Formula 1]. In Formula 1, R is hydrogen and n is an integer from 1 to 6."
Output: [{"score": 0, "type": "Completeness", "name": "Formula_Missing", "reason": "Only the placeholder '[Chemical Formula 1]' remains, while the following sentence defines variables from the absent structure"}]

**Example 2.1 (Bad - Partial Formula Loss)**:
Input: "The transition model maps states and actions as $T(s,a,s') [0,1]$, where the output is a probability."
Output: [{"score": 0, "type": "Completeness", "name": "Formula_Partial_Loss", "reason": "The mapping relation between T(s,a,s') and [0,1] is missing its arrow"}]

**Example 2.2 (Bad - Formula Token Corruption)**:
Input: "Nitrogen adsorption was measured using $\Nu_2$. The same gas is referred to as nitrogen throughout the paragraph."
Output: [{"score": 0, "type": "Completeness", "name": "Formula_Token_Corruption", "reason": "The nitrogen symbol N is OCR-corrupted into the Greek command \\Nu in the formula \\Nu_2"}]

**Example 2.3 (Bad - Unparseable Formula)**:
Input: "The formula $x^2 + y^2 is broken here $$a = b$$$"
Output: [{"score": 0, "type": "Completeness", "name": "Formula_Unparseable", "reason": "The first mathematical $ delimiter is never closed and an extra $ remains at the end"}]

**Example 2.4 (Bad - Internal Formula Structure)**:
Input: "Fuel flow is the product of coefficient μ, nozzle area A, and the square root of pressure difference. The extracted formula is $Q=\mu A^{\sqrt{\Delta P}}$."
Output: [{"score": 0, "type": "Completeness", "name": "Formula_Structure_Corruption", "reason": "The nearby definition says the square-root term is multiplied by A, but the extracted formula incorrectly places it in A's exponent"}]

**Example 2.5 (Bad - Formula Layout)**:
Input: "The value is\n$x+y$\nin this case."
Output: [{"score": 0, "type": "Completeness", "name": "Formula_Layout_Corruption", "reason": "The inline formula is forced onto a separate line, breaking the surrounding sentence flow"}]

**Example 2.6 (Bad - Extra Content Around Formula)**:
Input: "The normalized direction is $x_l=(x_2-x_1)/R$ latex and the next paragraph continues the derivation."
Output: [{"score": 0, "type": "Completeness", "name": "Formula_Extra_Content", "reason": "A stray extractor token 'latex' remains attached to the formula"}]

**Example 2.7 (Bad - Independent Formula Defects)**:
Input: "The material structure is: [Formula 1]. Separately, the energy equation is $E=mc^2$ latex."
Output: [{"score": 0, "type": "Completeness", "name": "Formula_Missing", "reason": "The material structure is absent and only '[Formula 1]' remains"}, {"score": 0, "type": "Completeness", "name": "Formula_Extra_Content", "reason": "A separate valid energy formula is followed by the stray extractor token 'latex'"}]

**Example 2.8 (Bad - Entire Table Missing)**:
Input: "Table 4. Monthly Production\nUnit: tonnes\nSource: Operations database\n\n5. Discussion"
Output: [{"score": 0, "type": "Completeness", "name": "Table_Missing", "reason": "Only the caption, unit, and source for Table 4 remain before the next section; no table body is present"}]

**Example 2.9 (Bad - Unparseable Table)**:
Input: "<table><tr><th>Name</th><th>Score</tr><tr><td>Alice</td><td>91</td></table"
Output: [{"score": 0, "type": "Completeness", "name": "Table_Unparseable", "reason": "The Score header cell is not closed and the final table closing tag is truncated, so the HTML table boundaries cannot be parsed reliably"}]

**Example 2.10 (Bad - Partial Table Loss)**:
Input: "The table reports all five monitored sites. <table><tr><th>Site</th><th>Result</th></tr><tr><td>1</td><td>Pass</td></tr><tr><td>2</td><td>Pass</td></tr><tr><td>5</td><td>Fail</td></tr></table>"
Output: [{"score": 0, "type": "Completeness", "name": "Table_Partial_Loss", "reason": "The text says all five sites are reported, but the surviving table skips the complete rows for sites 3 and 4"}]

**Example 2.11 (Bad - Cell Content Corruption)**:
Input: "Status values are Yes or No. <table><tr><th>Item</th><th>Status</th></tr><tr><td>A</td><td>Yes</td></tr><tr><td>B</td><td>N□</td></tr></table>"
Output: [{"score": 0, "type": "Completeness", "name": "Table_Cell_Corruption", "reason": "The status cell for item B contains the OCR placeholder character '□' instead of a valid Yes/No value while its row and column position remain clear"}]

**Example 2.12 (Bad - Header Corruption)**:
Input: "<table><tr><th>Metric</th><th>2024</th><th>2024</th></tr><tr><td>Emissions</td><td>81</td><td>95</td></tr></table> Footnote: The second year column contains revised 2023 data."
Output: [{"score": 0, "type": "Completeness", "name": "Table_Header_Corruption", "reason": "Both data columns are labeled 2024 even though the visible footnote identifies the second one as revised 2023 data"}]

**Example 2.13 (Bad - Internal Table Structure)**:
Input: "<table><tr><th>Date</th><th>Description</th><th>Amount</th><th>Balance</th><th>Charges</th></tr><tr><td>19 Jun</td><td>Payment</td><td>Vendor A</td><td></td><td>75.00</td><td>125.00</td><td></td></tr></table>"
Output: [{"score": 0, "type": "Completeness", "name": "Table_Structure_Corruption", "reason": "The header defines five columns but the transaction row contains seven cells, shifting the amount and balance away from their intended headers"}]

**Example 2.14 (Bad - Table Layout)**:
Input: "<table><tr><th>Name</th><th>Year</th><th>Score</th></tr></table>\nAlice\nBob\n2024\n2023\n91\n88"
Output: [{"score": 0, "type": "Completeness", "name": "Table_Layout_Corruption", "reason": "The header is isolated in one table while the body is flattened into three disjoint lists, so names, years, and scores cannot be reliably paired"}]

**Example 2.15 (Bad - Extra Content in Table)**:
Input: "<table><tr><th>Document</th><th>Date</th></tr><tr><td>Invoice 1158</td><td><img src='s3://internal-bucket/page-4.jpg'/></td></tr></table>"
Output: [{"score": 0, "type": "Completeness", "name": "Table_Extra_Content", "reason": "An internal S3 image-storage URL is inserted in the Date cell as if it were table data"}]

**Example 2.16 (Bad - Entire Code Missing)**:
Input: "Example implementation:\nListing 3.2\nThe function accepts a path and returns the parsed records.\n\n4. Evaluation"
Output: [{"score": 0, "type": "Completeness", "name": "Code_Missing", "reason": "Only the listing caption and function description remain before the next section; the promised implementation is absent"}]

**Example 2.17 (Bad - Unparseable Code)**:
Input:
```json
{"name": "\u00b", "enabled": true}
```
Output: [{"score": 0, "type": "Completeness", "name": "Code_Unparseable", "reason": "The JSON value contains the invalid Unicode escape \\u00b, which does not provide the required four hexadecimal digits"}]

**Example 2.18 (Bad - Partial Code Loss)**:
Input:
```matlab
function result = positive_total(x)
result = 0;
for i = 1:length(x)
    if x(i) > 0
        result = result + x(i);
References
```
Output: [{"score": 0, "type": "Completeness", "name": "Code_Partial_Loss", "reason": "The function is truncated inside nested control flow and the References section begins before the remaining logic and closing end statements"}]

**Example 2.19 (Bad - Code Token Corruption)**:
Input:
```c
static unsigned short lfsr = 0xffff;
at i, outbyte;
```
Output: [{"score": 0, "type": "Completeness", "name": "Code_Token_Corruption", "reason": "The C keyword int is visibly OCR-corrupted into the invalid token 'at' before the variable declaration"}]

**Example 2.20 (Bad - Code Layout)**:
Input: "int number1 = 1; // first value int number2 = 2; // second value\nint sum = number1 + number2;"
Output: [{"score": 0, "type": "Completeness", "name": "Code_Layout_Corruption", "reason": "A lost line break places the number2 declaration inside the preceding // comment, changing the code structure"}]

**Example 2.21 (Bad - Extra Content in Code)**:
Input:
```python
def borrow_book():
    1 usage
    return library.pop()
```
Output: [{"score": 0, "type": "Completeness", "name": "Code_Extra_Content", "reason": "The IDE annotation '1 usage' is inserted inside the function as if it were Python code"}]

**Example 3 (Bad - Garbled Characters)**:
Input: "The exported text contains broken symbols â€™ â€œ □□□ ï»¿ throughout the paragraph."
Output: [{"score": 0, "type": "Effectiveness", "name": "Garbled_Characters", "reason": "Repeated mojibake, placeholder squares, and a leaked BOM exceed the character-corruption threshold"}]

**Example 3.1 (Bad - Words Stuck)**:
Input: "The extraction removed spaces in many places: theexperimentwascompleted and theresultswererecorded before thesampleswerediscarded."
Output: [{"score": 0, "type": "Effectiveness", "name": "Words_Stuck", "reason": "Multiple word boundaries are missing across a substantial portion of the passage"}]

**Example 3.2 (Bad - Lack of Punctuation)**:
Input: "The experiment was completed the results were recorded the samples were discarded the laboratory was then closed"
Output: [{"score": 0, "type": "Effectiveness", "name": "Lack_Punctuation", "reason": "Continuous prose has at least three missing sentence boundaries, producing a long run-on passage"}]

**Example 4 (Bad - Similarity)**:
Input: "Blue is nice. Blue is nice. Blue is nice. Blue is nice. Blue is nice. Blue is nice."
Output: [{"score": 0, "type": "Similarity", "name": "Duplication", "reason": "Same sentence repeats 6 times, indicating low content diversity"}]

**Example 5 (Bad - Multiple Labels)**:
Input: "Thequickbrownfox. Thequickbrownfox. Thequickbrownfox. Thequickbrownfox. Thequickbrownfox. Thequickbrownfox."
Output: [{"score": 0, "type": "Effectiveness", "name": "Words_Stuck", "reason": "Word boundaries are missing in every repeated sentence"}, {"score": 0, "type": "Similarity", "name": "Duplication", "reason": "The same sentence repeats 6 times"}]

---

Mandatory final response shape reminder:
{"statistics": {"formula_count": 0, "table_count": 0, "code_count": 0, "error_formula_count": 0, "error_table_count": 0, "error_code_count": 0, "Formula_Missing": 0, "Formula_Partial_Loss": 0, "Formula_Token_Corruption": 0, "Formula_Unparseable": 0, "Formula_Structure_Corruption": 0, "Formula_Layout_Corruption": 0, "Formula_Extra_Content": 0, "Table_Missing": 0, "Table_Unparseable": 0, "Table_Partial_Loss": 0, "Table_Cell_Corruption": 0, "Table_Header_Corruption": 0, "Table_Structure_Corruption": 0, "Table_Layout_Corruption": 0, "Table_Extra_Content": 0, "Code_Missing": 0, "Code_Unparseable": 0, "Code_Partial_Loss": 0, "Code_Token_Corruption": 0, "Code_Layout_Corruption": 0, "Code_Extra_Content": 0}, "findings": [{"score": 0/1, "type": "", "name": "", "reason": ""}]}

Return the JSON object only, with counts computed from the following input.

# Input content to evaluate:

"""
