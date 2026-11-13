# Agent Trace 规则配置

目前只有 `RuleAgentTraceLoopDetection` 需要填写 `evals[].config`。其他规则不用写 `config`。

参数放在该规则自己的 `evaluator[].evals[].config` 里。`threshold` 是 `EvaluatorRuleArgs` 的已有字段，`min_repeats` 走 `extra="allow"`，不用改配置模型。不写 `config` 时使用默认值。`InputArgs.to_dict()` 的白名单只保留 `threshold`，`min_repeats` 可以执行，但不会出现在配置快照里。

字段映射见 [ms-swift converter 用户说明](ms_swift.md)。

## RuleAgentTraceLoopDetection

结果正文相似度阈值，以及连续重复多少次才算循环。字符 5-gram 和 Jaccard 比较写死在规则里，不能通过 config 修改。

| 参数 | 类型 | 默认 | 约束 |
|---|---|---|---|
| `threshold` | float | `0.95` | 有限数，且 `0 < threshold <= 1`。相等也算达到阈值 |
| `min_repeats` | int | `3` | 整数，且 `>= 2`。不接受 bool |

非法值在评估入口抛出 `ValueError`，不会变成一条质量判定。

```json
{
  "fields": {"content": "RuleAgentTraceLoopDetection_content"},
  "evals": [{
    "name": "RuleAgentTraceLoopDetection",
    "config": {"threshold": 0.95, "min_repeats": 3}
  }]
}
```

可运行示例：`python examples/agent/loop_detection.py C:/path/to/traces.jsonl --threshold 0.95 --min-repeats 3`。

判定行为（缺失结果、user 分段、N/A）见 [ms_swift.md 第 5 节](ms_swift.md)。
