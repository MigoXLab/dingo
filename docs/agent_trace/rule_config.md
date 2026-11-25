# Agent Trace 规则配置

规则使用默认值时可以不填写 `evals[].config`。需要调整阈值时，在该规则自己的配置块中覆盖。

参数放在该规则自己的 `evaluator[].evals[].config` 里。不写 `config` 时使用规则默认值。
本页参数中的 `threshold` 在配置模型中显式声明；`min_assistant_messages` 和 `min_repeats`
走现有 `extra="allow"` 扩展机制，由各自规则读取和校验，无需修改通用配置字段或快照白名单。
`threshold` 纳入 `InputArgs.to_dict()` 配置快照白名单；`min_assistant_messages` 和
`min_repeats` 可以参与执行，但目前不会出现在配置快照里。需要复现这些自定义配置时，请保留原始配置文件。

字段映射见 [ms-swift converter 用户说明](ms_swift.md)。

<a id="token-plan-storage"></a>

## RuleAgentTrajectoryMediaIntegrity

每位提交者通过规则的 `config.s3_config` 提供自己的 endpoint、AK 和 SK。
`s3_addressing_style` 默认为 `path`，也接受 `virtual` 或 `auto`。
`media_config.partition_date` 为必填的单日原始分区，格式 YYYY-MM-DD；
`raw_base_uri` 默认使用下例路径。这两个自定义配置块只参与运行，配置快照会省略它们。

```json
{
  "name": "RuleAgentTrajectoryMediaIntegrity",
  "config": {
    "s3_config": {
      "s3_endpoint_url": "https://s3.example.org",
      "s3_ak": "<当前用户的 AK>",
      "s3_sk": "<当前用户的 SK>"
    },
    "media_config": {
      "partition_date": "2026-10-31",
      "raw_base_uri": "s3://agent-trajectory/lakehouse/token-plan/raw/v001/"
    }
  }
}
```

[图片定位和结果口径](ms_swift.md#token-plan-images)

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
| `min_assistant_messages` | int | `0` | 非负整数；0 不过滤单轮记录，低于此数量时返回 N/A，相等时正常检测；不接受 bool、浮点数或字符串 |

```json
{
  "fields": {"messages": "messages"},
  "evals": [{
    "name": "RuleAgentTraceReasoningSparsity",
    "config": {"threshold": 0.7, "min_assistant_messages": 0}
  }]
}
```

非法阈值抛出 `ValueError`。没有 assistant、messages 结构不可读取或 assistant 的
reasoning 字段缺失/类型不正确时返回 N/A；合法的空字符串、纯空白字符串计为空。
assistant 数量小于配置下限时返回 `insufficient_assistant_messages`；为 0 时仍返回
`no_assistant_messages`，即使下限设为 0 也不能计算零分母。
结果文案包含 assistant 总数、空值数、占比和阈值，不输出具体位置。

默认保留单轮记录：一条 assistant 的 reasoning 为空时，占比为 100%，表示该轨迹没有记录在
此字段中的显式思考链，无法提供对应的显式推理过程监督信号，因此是合理的稀疏特征标签。
需要限定多轮轨迹时可显式设置 `min_assistant_messages=2`。该参数作为 extra 传入，
未填写时由规则默认使用 0，不在通用配置模型中声明字段。执行器将它合并到规则实例的
`dynamic_config`，由规则读取和校验。该参数不在 `InputArgs.to_dict()` 的快照白名单中，
不会写入 `summary.json.input_args`，不影响执行时使用自定义值。
示例脚本的 config 显式写出 `"min_assistant_messages": 0`。

保存结果时设置 `result_save.bad=true, good=true, all_labels=true, merge=true`，
保留命中的 `status=true` 结果，以及未命中和 N/A 的 `status=false` 详情。完整输出语义见
[ms-swift 确定性规则中的 reasoning 稀疏章节](ms_swift.md#reasoning-sparsity)。

可运行示例：`python examples/agent/reasoning_sparsity.py`（随附完整标准化样本）。

## RuleAgentTraceEmptyAssistantTurn

不需要 `config`，没有比例阈值或最少轮次参数。规则直接遍历原生 `messages` 中全部 assistant，
不检查 loss，统计 content、reasoning_content 均为空或纯空白且无工具调用的回合总数。
完成遍历后，空回合数大于 0 即 `status=true`，命中文案包含检查总数和空回合总数，不列位置。
只有 reasoning 或有工具调用的回合不计为空；不继承 EmptySupervision 的仅结束标记分支。

```json
{
  "fields": {"messages": "messages"},
  "evals": [{"name": "RuleAgentTraceEmptyAssistantTurn"}]
}
```

支持 `jsonl`、`ms_swift`，不增加 prepare 或派生字段。必要结构不可读取时整条返回
`invalid_messages` 的 N/A；没有 assistant 时为 `no_assistant_messages`。
`status=true` 按现有执行器计入 `num_bad`，没有发现空回合时返回 `QUALITY_GOOD`。
完整输入、处理边界和结果见 [ms-swift 确定性规则](ms_swift.md#empty-assistant-turn)。

运行 `python examples/agent/empty_assistant_turn.py` 可使用 `test/data/agent` 中的完整样本。
示例开启 `bad=true, good=true, all_labels=true, merge=true`，保留全部结果详情。
