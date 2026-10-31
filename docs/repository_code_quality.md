# Repository Code Quality Pipeline

`LLMRepositoryCodeQualityPipeline` is the initial repository-code quality entry point.
It combines per-record model review with deterministic and cross-record rules.

| Requested check | Public label | Implementation |
|---|---|---|
| Missing required field | `Effectiveness.Missing_Required` | Requires `track_id`, `source`, `content`, and `language` |
| Empty required/non-empty field | `Effectiveness.Empty_Required` | Rejects null and blank required fields; optional SHA cannot be empty when present |
| Field type mismatch | `Effectiveness.Field_Type_Mismatch` | `track_id` is string/integer; source/content/language/SHA are strings |
| Field length out of range | `Effectiveness.Field_Length_Out_Of_Range` | `source` ≤4096 and `language` ≤64 characters |
| Field format mismatch | `Effectiveness.Field_Regex_Mismatch` | Source URI/path/name format and lowercase 64-hex SHA-256 |
| Empty or whitespace-only content | `Effectiveness.Empty_Content` | Deterministic hard gate |
| Whole-record placeholder | `Effectiveness.Placeholder_Content` | ≤32 chars and placeholder vocabulary |
| Error/fetch placeholder | `Effectiveness.Error_Placeholder_Content` | ≤128 chars and error-status vocabulary |
| Invalid Unicode | `Effectiveness.Invalid_Unicode` | Surrogates, mojibake sequences, or excessive U+FFFD |
| Illegal control characters | `Effectiveness.Illegal_Control_Characters` | Unexplained C0/C1 characters with language/literal allowances |
| Extreme content dimensions | `Effectiveness.Extreme_Length` | Character, maximum-line, and average-line thresholds |
| Content hash mismatch | `Effectiveness.Content_SHA256_Mismatch` | UTF-8 SHA-256 against `sha256`/`dedup_content_sha256` |
| Code truncated at EOF | `Completeness.Code_Truncation` | Tree-sitter ERROR/MISSING in final 512 UTF-8 bytes plus an independent lexical tail signal |
| Advertisement or unrelated promotion | `Effectiveness.Advertisement` | `LLMTextAdvertisement` |
| PII and sensitive information | `Security.PII_Exposure`, `Security.Internal_Endpoint_Exposure` | Checksum/context rules first; ambiguous redacted candidates use contextual LLM review |
| Secret credentials | `Security.Secret_Credentials` | Provider signatures and credential structures first; ambiguous redacted candidates use contextual LLM review |
| Pornography, gambling, drugs | `Security.Porn`, `Security.Gamble`, `Security.Drug` | Repository adapter based on `LLMSecurityProhibition` |
| Harmful political content | `Security.Politics` | Repository adapter based on `LLMSecurityPolitics` |
| Repetition inside one record | `Similarity.Intra_Document_Repetition` | zlib ratio below 8%, or at least 20 non-empty lines with unique-line ratio below 8% |
| Normalized token duplicate | `Similarity.Normalized_Token_Duplicate` | Comment/whitespace-insensitive token hash |
| Token-shingle near duplicate | `Similarity.Token_Shingle_Near_Duplicate` | 5-token shingles, token ratio at least 0.80, Jaccard at least 0.90 |
| Repeated license header | `Similarity.License_Header_Duplicate` | Normalized leading comment/license block |

Cross-record findings are prepared in input order before concurrent evaluation. The first
record in a duplicate group is retained as the representative and is not marked duplicate.
Schema, input/content, and truncation checks are hard gates: a hit marks the record bad and
skips all LLM stages for that record. Truncation applies to code with 80–2,000,000 characters,
excludes document/configuration/lock formats, and requires both parser-tail evidence and an
unclosed string/comment/delimiter, trailing operator/comma/open delimiter, or a Python suite
header without a body. Unsupported languages or unavailable parsers are coverage gaps and are
never reported as truncation.
Security findings include the raw matched value in `EvalDetail.reason` so reviewers can
verify each hit. Raw values remain local and are removed from candidates before contextual
LLM review. The evaluator only detects and reports findings; it never replaces or mutates
`content`. Treat result files as sensitive artifacts and restrict their access accordingly.

## Sensitive-data coverage

High-confidence rule matches are reported directly. These include Chinese identity cards
(region/date/checksum), context-bound US SSN/EIN and credit cards, IMEI (Luhn), IBAN (mod-97),
Australian TFN/ABN, Italian tax IDs, ABA routing numbers, private-key markers, provider
API/cloud-token signatures, JWT/Bearer authorization, password hashes, literal passwords,
complete PEM private-key blocks, and credential-bearing database/HTTP URLs.

Email, phone, person name, IP address, MAC address, blockchain address, bank account,
CVV, cookie, password/API-key assignments, standalone private-key markers, and internal
endpoint candidates depend on source-code context. They are
passed to `LLMRepositorySensitiveReview` with only the candidate type, line number,
validator name, and a scrubbed line hint. The original source and matched sensitive value
are not included in that LLM request. Placeholder and example values are excluded before
review where deterministic checks can establish that safely.

## LocalExecutor entry point

The supported batch entry point uses Dingo's standard `LocalExecutor`:

```bash
pip install -e ".[repository]"

export OPENAI_API_KEY="..."
export OPENAI_BASE_URL="https://example.com/v1"
export OPENAI_MODEL="model-name"

PYTHONPATH=. python examples/repository_code_quality/evaluate_repository_executor.py \
  --input /path/to/repository.jsonl \
  --output outputs/repository-code-quality \
  --workers 6 \
  --batch-size 100
```

Use `--start-index` and `--end-index` for bounded smoke tests. Evaluator field mapping
is intentionally empty so all repository metadata remains available to tokenization,
duplicate grouping, and result traceability. Input uses Dingo's standard `jsonl` converter;
malformed JSON is treated as a data-loading error rather than a repository quality label.
