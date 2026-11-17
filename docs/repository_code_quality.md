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
| Zero-width, private-use, or unassigned code points | `Effectiveness.Contextual_Character_Anomaly` | Deterministic hard gate with an exemption whitelist; ambiguous boundary contexts go to `Effectiveness.Contextual_Format_Character_Review` |
| Non-code artifact | `Effectiveness.Archive_Artifact` | Archive suffix, RCS/CVS `,v` path, or RCS archive header signature |
| Declared language disagrees with content | `Effectiveness.Language_Content_Mismatch` | Content-signature audit; suspected mismatches go to `Effectiveness.Language_Mismatch_Review` |
| TODO stub or NotImplemented body | `Effectiveness.Todo_Empty_Implementation`, `Effectiveness.NotImplemented_Placeholder` | Empty-body and placeholder-raise detection with a test-path exemption; abstract contracts go to `Effectiveness.Placeholder_Implementation_Review` |
| Code truncated at EOF | `Completeness.Code_Truncation` | Tree-sitter ERROR/MISSING in final 512 UTF-8 bytes plus an independent lexical tail signal |
| Advertisement or unrelated promotion | `Effectiveness.Advertisement` | `LLMTextAdvertisement` |
| PII and sensitive information | `Security.PII_Exposure`, `Security.Internal_Endpoint_Exposure` | Checksum/context rules first; ambiguous redacted candidates use contextual LLM review |
| Secret credentials | `Security.Secret_Credentials` | Provider signatures and credential structures first; ambiguous redacted candidates use contextual LLM review |
| Pornography, gambling, drugs | `Security.Porn`, `Security.Gamble`, `Security.Drug` | Repository adapter based on `LLMSecurityProhibition` |
| Harmful political content | `Security.Politics` | Repository adapter based on `LLMSecurityPolitics` |
| License declaration block | `Security.License_Header` | 18-family signature scan of the file head plus LICENSE/COPYING documents emits candidates; `LLMRepositoryLicenseReview` confirms before the cleaning span is reported |
| License wording without a granting clause | `Security.License_Reference_Review` | Pointer, tag, and URL shapes, plus candidates the model rejects as payload rather than a strippable header |
| Reverse shell | `Security.Reverse_Shell` | Ported YARA condition emits bounded candidates; `LLMRepositoryReverseShellReview` confirms operational payloads |
| Malware signature hit | `Security.ClamAV_Detection` | Optional `clamdscan`/`clamscan` scan (`DINGO_CLAMAV_COMMAND`); skipped silently when no engine is installed |
| Repetition inside one record | `Similarity.Intra_Document_Repetition` | zlib ratio below 8%, or at least 20 non-empty lines with unique-line ratio below 8% |
| Normalized token duplicate | `Similarity.Normalized_Token_Duplicate` | Comment/whitespace-insensitive token hash |
| Token-shingle near duplicate | `Similarity.Token_Shingle_Near_Duplicate` | 5-token shingles, token ratio at least 0.80, Jaccard at least 0.90 |

Cross-record findings are annotated by the `repository_code_jsonl` converter in input order
during the load phase, before concurrent evaluation. The first
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

## Candidate-then-confirm stages

Two checks combine a deterministic candidate stage with model adjudication, mirroring the
handover flow (`YARA_RULE_MATCH` -> `GPT_MALWARE_CONTEXT_CONFIRMED`):

- `Security.Reverse_Shell`: the ported `Suspicious_Reverseshell_Code` condition
  (`/dev/tcp/` with `/bin/sh`, `nc -e`, or `.connect((` with `os.dup2(` and
  `subprocess.call(`) emits at most six candidates per record, each with a six-line
  excerpt around the match. The model confirms operational payloads only, so detection
  rules, signature blocklists, tests, inert prose, and reachability probes such as
  `echo >/dev/tcp/$host/80` are dropped. A runnable payload still counts when it is
  embedded in documentation.
- `Security.License_Header`: family signatures over the first 100 lines emit one candidate
  with the license-block line span (block comments, `--[[ ]]`, `=begin/=end`, and `%`
  comment styles included) plus a bounded excerpt; a file named `LICENSE`/`COPYING` is
  treated as a whole-file license document. The model confirms licensing boilerplate and
  rejects license wording carried by data content — JSON/XML/YAML metadata fields, HTML
  page titles, CVRF/CVE legal notes, and corpus prose — which is reported as
  `Security.License_Reference_Review` instead of a cleaning span.

Rejected candidates are not reported. When a confirmation stage fails (timeout or invalid
model output), the record keeps the deterministic verdict and is additionally marked
`REVIEW_EXECUTION_ERROR.license` or `REVIEW_EXECUTION_ERROR.reverse_shell`, so an LLM
outage never hides a hit. Confirmed findings append the triggering signature evidence as
`Rule evidence: ...` for traceability. Both stages only run for records with candidates,
which was 7.4% (license) and 0.02% (reverse shell) of a 10,000-record sample.

## Sensitive-data coverage

High-confidence rule matches are reported directly. These include Chinese identity cards
(region/date/checksum), context-bound US SSN/EIN and credit cards, IMEI (Luhn), IBAN (mod-97),
Australian TFN/ABN, Italian tax IDs, ABA routing numbers, private-key markers, provider
API/cloud-token signatures, JWT/Bearer authorization, password hashes, literal passwords,
complete PEM private-key blocks, OpenVPN static-key blocks, credential-bearing database/HTTP
URLs, and unquoted credential assignments whose value is a key-shaped literal (mixed character
classes or 16+ hex characters).

Email, phone, person name, copyright/author attributions, routable public IP addresses, MAC
address, bank account, CVV, cookie, quoted password/API-key assignments, URL query credential
parameters, connection-string password segments, identifier-shaped unquoted credentials,
standalone private-key markers, and internal endpoint candidates depend on source-code
context. They are passed to `LLMRepositorySensitiveReview` with only the candidate type, line
number, validator name, and a scrubbed line hint. The original source and matched sensitive
value are not included in that LLM request. Prompt size stays bounded by sending at most six
candidates per kind (40 overall, credentials first) together with the total candidate count.
Scanning stops after 500 candidates per record and reported evidence lists at most 20 matched
values, each with an explicit overflow marker, so huge generated files stay bounded.

Deterministic exclusions are applied before review where they can be established safely:
placeholder values, example domains, role-based mailboxes (`info@`, `support@`, `noreply@`),
asset paths and dummy addresses that merely look like email, organization/team/company names
inside attributions (including `Pte. Ltd.` / `, LLC` suffixes, `University of X, City` forms,
commercial/product nouns such as `Forklift Rentals`, and collective nouns such as
`… Software Development team` / `… Retrieval group` that follow the candidate span),
sentence-initial function words that merely look like a first name (`When Microsoft …`),
attribution wording outside header comments unless the line reads as prose (a documentation
or markup sentence carrying `created by` / `written by` wording or a profession/biography
predicate such as `is a security researcher at …`), environment-variable and identifier
references, type names
and string concatenations instead of credential literals, version-shaped quads (assembly
attributes, RCS `$Id:` keywords), documentation/reserved ranges, well-known public resolvers,
import and package lines, code package names that merely look like internal domains, landline
numbers without phone context, session identifiers that are not literal cookie values,
published payment test fixtures, and blockchain or smart-contract addresses (public ledger
identifiers).

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
duplicate grouping, and result traceability. Input uses the `repository_code_jsonl` converter:
standard JSONL parsing plus streaming cross-record duplicate annotation; malformed JSON is
treated as a data-loading error rather than a repository quality label. The derived field
findings travel to the evaluator as the extra field `repository_duplicate_findings`;
because Dingo only auto-strips derived fields for ms-swift outputs, flagged records also
keep that field in saved result raw_data as duplicate provenance. Under distributed Spark
execution the converter state is worker-local, so cross-record checks degrade to
within-partition scope.
