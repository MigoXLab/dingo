# Repository Code Quality Pipeline V2

`LLMRepositoryCodeQualityPipelineV2` keeps the V1 contract (same required fields, same
schema/content/truncation hard gates, same advertisement, sensitive, prohibition, politics,
repetition, and duplicate checks documented in
[repository_code_quality.md](repository_code_quality.md)) and adds the checks below.

Versions are frozen snapshots, following `LLMTextQualityV7` / `LLMTextQualityV8`: V1 does not
inherit anything from V2, so existing runs keep their behaviour. Select a version by
evaluator name.

## What V2 adds

| Requested check | Public label | Implementation |
|---|---|---|
| Zero-width, private-use, or unassigned code points | `Effectiveness.Contextual_Character_Anomaly` | Hard gate with a script/context exemption whitelist (BOM, soft hyphen in justified text, emoji ZWJ, icon-font paths, ABAP comment columns) |
| Ambiguous format characters | `Effectiveness.Contextual_Format_Character_Review` | Review level: format characters in document-boundary or comment context |
| Non-code artifact | `Effectiveness.Archive_Artifact` | Archive suffix, RCS/CVS `,v` path, or RCS archive header signature |
| Declared language disagrees with content | `Effectiveness.Language_Content_Mismatch` | Content-signature audit (confirmed mismatch); suspected cases go to `Effectiveness.Language_Mismatch_Review` |
| TODO stub | `Effectiveness.Todo_Empty_Implementation` | TODO-commented empty body, with a test-path exemption |
| NotImplemented placeholder | `Effectiveness.NotImplemented_Placeholder` | Unconditional `raise NotImplementedError` / `throw new NotImplementedException` body |
| Abstract or extension contract | `Effectiveness.Placeholder_Implementation_Review` | Review level: placeholder bodies that a subclass is expected to override |
| License declaration block | `Security.License_Header` | 18-family signature scan of the file head plus LICENSE/COPYING documents emits candidates; `LLMRepositoryLicenseReview` confirms before the cleaning span is reported |
| License wording without a granting clause | `Security.License_Reference_Review` | Pointer, tag, and URL shapes, plus candidates the model rejects as payload rather than a strippable header |
| Reverse shell | `Security.Reverse_Shell` | Ported YARA condition emits bounded candidates; `LLMRepositoryReverseShellReview` confirms operational payloads |
| Malware signature hit | `Security.ClamAV_Detection` | Optional `clamdscan`/`clamscan` scan (`DINGO_CLAMAV_COMMAND`, `DINGO_CLAMAV_TIMEOUT`, `CLAMAV_DATABASE`); skipped silently when no engine is installed |

Copyright-only notices, confidential or restrictive clauses, and unrelated literal uses of
the word "license" (for example a `LicenseManager` class or licence-plate code) stay silent:
they declare no rights and are not cleaning targets.

## Candidate-then-confirm stages

Two checks combine a deterministic candidate stage with model adjudication, mirroring the
handover flow (`YARA_RULE_MATCH` -> `GPT_MALWARE_CONTEXT_CONFIRMED`):

- `Security.Reverse_Shell`: the ported `Suspicious_Reverseshell_Code` condition (`/dev/tcp/`
  with `/bin/sh`, `nc -e`, or `.connect((` with `os.dup2(` and `subprocess.call(`) emits at
  most six candidates per record, each with a six-line excerpt around the match. The model
  confirms operational payloads only, so detection rules, signature blocklists, tests, inert
  prose, and reachability probes such as `echo >/dev/tcp/$host/80` are dropped. A runnable
  payload still counts when it is embedded in documentation.
- `Security.License_Header`: family signatures over the first 100 lines emit one candidate
  with the license-block line span (block comments, `--[[ ]]`, `=begin/=end`, and `%` comment
  styles included) plus a bounded excerpt; a file named `LICENSE`/`COPYING` is treated as a
  whole-file license document. The model confirms licensing boilerplate and rejects license
  wording carried by data content — JSON/XML/YAML metadata fields, HTML page titles,
  CVRF/CVE legal notes, and corpus prose — which is reported as
  `Security.License_Reference_Review` instead of a cleaning span.

Rejected candidates are not reported. When a confirmation stage fails (timeout or invalid
model output), the record keeps the deterministic verdict and is additionally marked
`REVIEW_EXECUTION_ERROR.license` or `REVIEW_EXECUTION_ERROR.reverse_shell`, so an LLM outage
never hides a hit. Confirmed findings append the triggering signature evidence as
`Rule evidence: ...` for traceability. Both stages only run for records with candidates,
which was 7.4% (license) and 0.02% (reverse shell) of a 10,000-record sample.

On that sample, model adjudication removed all six rule-only license false positives
(90 candidates -> 84 confirmed, 6 downgraded to review) without dropping a genuine header.

## Optional dependencies

- `regex` (in `requirements/optional.txt`) makes unassigned-code-point detection exact; with
  the standard library `unicodedata` alone, code points assigned after the runtime's Unicode
  version are reported only when they are unassigned there too.
- ClamAV is an external command and is never required: without `clamdscan`/`clamscan` on
  `PATH` (or `DINGO_CLAMAV_COMMAND`), the scan is skipped and no label is produced.

## Running V2

```bash
export OPENAI_API_KEY="..."
export OPENAI_BASE_URL="https://example.com/v1"
export OPENAI_MODEL="model-name"

PYTHONPATH=. python examples/repository_code_quality/evaluate_repository_executor.py \
  --input /path/to/repository.jsonl \
  --output outputs/repository-code-quality-v2 \
  --evaluator LLMRepositoryCodeQualityPipelineV2 \
  --workers 6 --batch-size 100
```

Omit `--evaluator` to run V1. Input format, field mapping, cross-record duplicate annotation,
and result layout are identical to V1; see
[repository_code_quality.md](repository_code_quality.md#localexecutor-entry-point).
