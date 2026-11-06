# Changelog

## 2.6.0

### Added

- `dingo.__version__` and `dingo._build.GIT_SHA` (defaults to `"unknown"`; the
  packaging script writes the real commit). Downstream services report
  `<__version__>+<GIT_SHA>` as the SDK version of evaluation results.
- Six agent-trace safety rules in the `AGENT_TRACE_SAFETY` metric group
  (`dingo/model/rule/rule_agent.py`, rule group `agent_trace_safety`):
  - `RuleAgentTraceDestructiveAction`: irreversible actions in tool arguments
    (forced recursive deletes, schema destruction, unscoped row deletion,
    history-rewriting VCS commands, privilege escalation).
  - `RuleAgentTraceSensitiveAccess`: tool calls touching credential-bearing paths
    (`~/.ssh`, `.env`, `.aws/credentials`, `id_rsa`, ...).
  - `RuleAgentTraceSecretExposure`: credential material in a tool result
    (private-key blocks, AWS key ids, GitHub/OpenAI-style tokens, JWTs); matches are redacted.
  - `RuleAgentTraceGatewayBypass`: reaching the network directly from executed
    code after the policy layer refused a managed network tool.
  - `RuleAgentTraceIntegrity`: trace carries fewer tool spans than its source
    expected, so the evidence other safety rules read is incomplete.
  - `RuleAgentTraceSandboxExplicitlyDisabled`: a tool call that sets
    `dangerouslyDisableSandbox`.
