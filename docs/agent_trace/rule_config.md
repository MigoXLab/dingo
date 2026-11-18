# Agent Trace 规则配置

规则使用默认值时可以不填写 `evals[].config`。需要调整阈值时，在该规则自己的配置块中覆盖。

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

## RuleAgentTraceReasoningSparsity

直接读取原生 `messages`，在规则内统计每条轨迹的空 reasoning assistant 消息占比。
无需 converter prepare；支持 `jsonl` 和 `ms_swift`。这是分布特征，超过阈值时设置 `status=true`，
按现有 Dingo 执行器计入 `num_bad`；未超过时为 false。

| 参数 | 类型 | 默认 | 约束 |
|---|---|---|---|
| `threshold` | float | `0.7` | 有限数，`0 <= threshold <= 1`；空值占比严格大于阈值才命中，相等不命中 |

```json
{
  "fields": {"messages": "messages"},
  "evals": [{
    "name": "RuleAgentTraceReasoningSparsity",
    "config": {"threshold": 0.7}
  }]
}
```

非法阈值抛出 `ValueError`。没有 assistant、messages 结构不可读取或 assistant 的
reasoning 字段缺失/类型不正确时返回 N/A；合法的空字符串、纯空白字符串计为空。
结果文案包含 assistant 总数、空值数、占比和阈值，不输出具体位置。

保存结果时设置 `result_save.bad=true, good=true, all_labels=true, merge=true`，
保留命中的 `status=true` 结果，以及未命中和 N/A 的 `status=false` 详情。完整输出语义见
[ms-swift 确定性规则中的 reasoning 稀疏章节](ms_swift.md#reasoning-sparsity)。

可运行示例：`python examples/agent/reasoning_sparsity.py`（随附完整标准化样本）。
