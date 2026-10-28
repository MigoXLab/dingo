# ms-swift converter 用户说明

使用 `dataset.format="ms_swift"` 读取 Agent 轨迹 JSONL：每行一个 JSON 对象，
包含 `messages` 数组，一行转换成一个评估样本。本地目录输入只读取 `.jsonl` 文件。
当前支持以下 16 个指标，只处理主轨迹，不展开 `sub_agent_trajectory`。

converter 只为 `evaluator[].evals` 中选中的指标生成辅助字段，并保留原始记录。
每个指标单独配置 `evaluator[].fields`，映射到自己的 `<指标名>_<字段名>`。
全部指标同时选择时共生成 24 个辅助字段；同一指标重复配置时，每条记录只转换一次。
每个 preparer 独立提取；源字段缺失、类型错误或其他提取异常只会使该指标负责的
辅助字段置为空，不会阻断同一条记录的其他 preparer。当前 24 个辅助字段的运行时
类型均为字符串，因此失败值均为 `""`；合法的空工具调用仍保留为 JSON 字符串
`{"tool_calls":[]}`（或对应的合法空结构），不与提取失败混淆。

下文每节都给出 **fields 配置、源字段映射、转换步骤、输入示例和转换结果**。
`content` 辅助字段的实际类型是 **JSON 字符串**；为便于阅读，示例展示其
**解析后的 JSON 值**。表格中的 `tool_calls`、`steps` 等路径也指解析后的值。
`prompt` 和 `context` 的实际值则在各节中单独说明。示例只展示输入适配，不代表指标已判定通过或失败。

## 一、输入约定

- converter 保留原始记录并为所选指标生成辅助字段，不执行完整交付格式校验。需要检查《轨迹数据的标准化格式》时，配置不带 `fields` 映射的 `RuleMsSwiftSchema`；该规则直接读取完整原始记录，并与其他指标独立执行。
- 顶层必选字段为：`messages`、`tools`、`termination`、`source`、`harness`、`model`、`total_rounds`、`total_tool_calls`、`tool_counts`、`reasoning_total_tokens`、`tool_defs_tag`、`missing_tool_defs`、`tool_call_tag`、`tool_call_check`、`server_tool_calls`、`metadata`、`completeness_tag`、`completeness`。字段必须存在且类型正确，允许规范明确支持的空字符串、空数组或空对象。
- `sub_agent_trajectory` 和 `sub_agent_relay_mounts` 是可选字段；存在 `sub_agent_trajectory` 时递归校验每个子轨迹。子轨迹不要求顶层专属的 `completeness_tag` 和 `completeness`。
- 所有消息必须包含字符串型 `role` 和 `content`；允许的角色为 `system`、`developer`、`user`、`assistant`、`tool`。assistant 消息还必须包含字符串型 `reasoning_content`；tool 消息还必须包含字符串型 `tool_call_id` 和 `name`。
- `tool_calls` 仅在至少有一次调用时出现。每个调用必须包含 `type="function"`、字符串型 `id`，以及含 `name`、`arguments` 的 `function` 对象。
- `tools` 中每个定义必须包含 `type="function"`、`name`、`description` 和对象类型的 `parameters`。
- `total_rounds`、`total_tool_calls`、`tool_counts` 和 `tool_call_check.total_calls` 必须与当前节点的 `messages` 一致；tool 消息的 `tool_call_id` 必须能匹配当前节点中的调用。
- 工具调用没有返回、调用缺少工具定义、参数与 schema 不一致或轨迹没有最终回复属于质量或完整性问题，不属于格式错误；这些情况由质量标签、`tool_call_check` 和 `completeness` 表达。
- 读取工具调用时，仅读取 `role="assistant"` 的 `tool_calls`；该键可以缺失，存在时必须是数组，空数组按规范保留，不能用 `null` 代替。
- 每次调用必须有 `type="function"`、字符串型唯一 `id`、对象类型的 `function`、非空字符串 `function.name` 和 `function.arguments`。`arguments` 可以是任意 JSON 值；为兼容旧数据，其中可解析的 JSON 字符串仍会在构造规则输入时解析，但不会修改原始记录。
- tool 消息的 `tool_call_id` 必须匹配当前节点的调用；调用不一定有工具返回。重复调用 ID 会按格式错误处理；preparer 需要建立返回索引时也会拒绝重复的工具返回 ID。

## 二、确定性规则

### 1. RuleAgentTraceDestructiveAction（破坏性操作）

将每次工具调用的名称和参数交给规则，供其扫描删除、数据库破坏或提权命令。

**fields 配置**

```json
{
  "content": "RuleAgentTraceDestructiveAction_content"
}
```

生成 `RuleAgentTraceDestructiveAction_content`，类型为 JSON 字符串。

**读取与映射**

| 源字段或统计方式 | 转换后的路径 | 处理方式 |
|---|---|---|
| `messages[role=assistant].tool_calls[].function.name` | `tool_calls[].tool_name` | 原样复制 |
| `messages[role=assistant].tool_calls[].function.arguments` | `tool_calls[].args` | 对象直接使用；JSON 字符串解析为对象 |

**转换步骤**

1. 按消息顺序遍历所有 `assistant` 消息，再按各消息中的 `tool_calls` 顺序遍历调用。
2. 每个调用生成一个对象，`function.name` 写入 `tool_name`，解析后的 `function.arguments` 写入 `args`；缺少参数时使用 `{}`。
3. 参数键和值全部保留。`cmd` 不改名为 `command`，也不从命令内容推断工具类型。
4. 将这些对象装入 `{"tool_calls": [...]}`，序列化后写入 `RuleAgentTraceDestructiveAction_content`。不加入调用 ID、工具返回或执行状态。

**输入示例**

```json
{
  "messages": [
    {
      "role": "assistant",
      "tool_calls": [
        {"id":"delete-1","function":{"name":"exec_command","arguments":"{\"cmd\":\"rm -rf /srv/demo\"}"}},
        {"id":"delete-2","function":{"name":"shell","arguments":{"command":"DROP TABLE demo","timeout":30}}}
      ]
    }
  ]
}
```

**转换结果**（`content` 解析后）

```json
{
  "tool_calls": [
    {"tool_name":"exec_command","args":{"cmd":"rm -rf /srv/demo"}},
    {"tool_name":"shell","args":{"command":"DROP TABLE demo","timeout":30}}
  ]
}
```

**缺失情况与使用边界**

没有工具调用时输出 `{"tool_calls": []}`。现有规则读取 `args.command/source/script`，不读取 `args.cmd`；因此第一条调用的 `cmd` 虽然成功转换，仍可能漏检。

### 2. RuleAgentTraceGatewayBypass（网关绕过）

将工具调用、网关返回和明确的执行状态放到同一个调用对象中，供规则识别受阻后使用代码直接联网的行为。

**fields 配置**

```json
{
  "content": "RuleAgentTraceGatewayBypass_content"
}
```

生成 `RuleAgentTraceGatewayBypass_content`，类型为 JSON 字符串。

**读取与映射**

| 源字段或统计方式 | 转换后的路径 | 处理方式 |
|---|---|---|
| `assistant.tool_calls[].function.name` | `tool_calls[].tool_name` | 原样复制 |
| `assistant.tool_calls[].function.arguments` | `tool_calls[].args` | 解析为对象，保留原始参数名 |
| `assistant.tool_calls[].id` | `tool_calls[].call_id` | 仅保留非空字符串 |
| 匹配的 `tool` 消息的 `content` | `tool_calls[].result` | 按 ID 匹配；字段存在时原样复制 |
| 调用或匹配工具消息的 `status/duration/duration_seconds/group/type` | 调用对象上的同名字段 | 逐字段取值，工具消息优先 |

**转换步骤**

1. 先收集所有 `role="tool"` 消息，以非空字符串 `tool_call_id` 建立索引。
2. 按原始顺序遍历 `assistant.tool_calls`，解析名称和参数。调用的非空字符串 `id` 写入 `call_id`，再用该 ID 查找工具消息。
3. 匹配消息有 `content` 键时写入 `result`；没有匹配消息或没有该键时，省略 `result`。显式 `content=null` 会保留为 `result=null`。
4. 对 `status`、`duration`、`duration_seconds`、`group`、`type` 分别检查：匹配工具消息有该键时使用其值，否则使用调用上的值；两处都没有则省略。即使工具消息的值为 `null`，也不会回退到调用值。
5. 输出 `{"tool_calls": [...]}`。返回顺序不改变调用顺序，也不从 `"GATEWAY BLOCKED"` 等文本推断 `status`。

**输入示例**

```json
{
  "messages": [
    {
      "role": "assistant",
      "tool_calls": [
        {
          "id": "web-1",
          "type": "function",
          "status": "timeout",
          "duration": 9,
          "function": {"name":"WebFetch","arguments":{"url":"https://example.org"}}
        },
        {
          "id": "exec-1",
          "status": "success",
          "function": {"name":"shell","arguments":{"command":"curl https://example.org"}}
        }
      ]
    },
    {"role":"tool","tool_call_id":"web-1","content":"GATEWAY BLOCKED","status":"error","duration":0.1}
  ]
}
```

**转换结果**（`content` 解析后）

```json
{
  "tool_calls": [
    {
      "tool_name": "WebFetch",
      "args": {"url":"https://example.org"},
      "call_id": "web-1",
      "result": "GATEWAY BLOCKED",
      "status": "error",
      "duration": 0.1,
      "type": "function"
    },
    {"tool_name":"shell","args":{"command":"curl https://example.org"},"call_id":"exec-1","status":"success"}
  ]
}
```

**缺失情况与使用边界**

示例中 `web-1` 的工具消息覆盖了调用上的 `status` 和 `duration`；`exec-1` 没有工具返回，仍保留调用及其显式状态。重复有效调用 ID 或工具返回 ID 会报错。现有规则不识别 `exec_command` 或 `args.cmd`；缺少状态时沿用原有判定，不自动转成 N/A。

### 3. RuleAgentTraceIntegrity（轨迹完整性）

将当前文件中的工具调用计数和配对情况转换成完整性统计字段。

**fields 配置**

```json
{
  "content": "RuleAgentTraceIntegrity_content"
}
```

生成 `RuleAgentTraceIntegrity_content`，类型为 JSON 字符串。

**读取与映射**

| 源字段或统计方式 | 转换后的路径 | 处理方式 |
|---|---|---|
| 顶层 `total_tool_calls` | `tool_calls_expected` | 仅在源键存在时复制，不重新估算或转换类型 |
| 所有 `assistant.tool_calls` 中的实际调用数量 | `tool_spans_recorded` | 逐次统计，始终输出整数 |
| 没有有效 ID 或没有同 ID 工具消息的调用数量 | `open_observation_count` | 逐次统计，始终输出整数 |
| 顶层 `trace_truncated` | `trace_truncated` | 仅在源键存在时原样复制 |

**转换步骤**

1. 索引所有带非空字符串 `tool_call_id` 的工具消息，并遍历全部 `assistant.tool_calls`。当前实现仍校验调用名称和参数结构，但不把名称和参数写入统计结果。
2. 每遇到一个有效结构的调用，`tool_spans_recorded` 加 1。
3. 调用的 `id` 缺失、为空或不是字符串，或者没有相同 `tool_call_id` 的工具消息时，`open_observation_count` 加 1。配对只检查 ID，匹配工具消息不必有 `content`。
4. 源记录有 `total_tool_calls` 时复制为 `tool_calls_expected`；有 `trace_truncated` 时复制同名值。缺少时省略这两个字段，不推断截断状态。
5. 序列化统计对象。仅有工具返回而没有对应调用，不会增加调用数或未配对调用数。

**输入示例**

```json
{
  "total_tool_calls": 3,
  "trace_truncated": true,
  "messages": [
    {
      "role": "assistant",
      "tool_calls": [
        {"id":"a","function":{"name":"search","arguments":{"query":"Dingo"}}},
        {"id":"b","function":{"name":"read","arguments":{"path":"notes.txt"}}}
      ]
    },
    {"role":"tool","tool_call_id":"b"}
  ]
}
```

**转换结果**（`content` 解析后）

```json
{
  "tool_spans_recorded": 2,
  "open_observation_count": 1,
  "tool_calls_expected": 3,
  "trace_truncated": true
}
```

**缺失情况与使用边界**

示例中实际有 2 次调用，只有 `b` 配对成功，因此未配对调用数为 1。没有调用且无顶层统计字段时输出 `{"tool_spans_recorded": 0, "open_observation_count": 0}`。重复有效 ID 会报错。这只能检查交付文件内部一致性；现有规则不一定将未配对或截断信息本身判为缺陷。

### 4. RuleAgentTraceLatencyAnomaly（耗时异常）

将工具调用转换成带名称、显式耗时和分组信息的步骤列表。

**fields 配置**

```json
{
  "content": "RuleAgentTraceLatencyAnomaly_content"
}
```

生成 `RuleAgentTraceLatencyAnomaly_content`，类型为 JSON 字符串。

**读取与映射**

| 源字段或统计方式 | 转换后的路径 | 处理方式 |
|---|---|---|
| `assistant.tool_calls[].function.name` | `steps[].name` | 原样复制，目标键是 `name` |
| 调用或匹配工具消息的 `duration` | `steps[].duration` | 工具消息有该键时优先 |
| 调用或匹配工具消息的 `duration_seconds` | `steps[].duration_seconds` | 独立复制，不换算单位 |
| 调用或匹配工具消息的 `group/type` | `steps[].group/type` | 逐字段复制，不从工具名称推断 |

**转换步骤**

1. 索引工具消息，按调用的非空字符串 `id` 与 `tool_call_id` 配对，保持调用顺序。仍校验调用参数，即使它们不会出现在输出中。
2. 每个调用先生成 `{"name": function.name}`。
3. 对 `duration`、`duration_seconds`、`group`、`type` 分别取值：匹配工具消息有该键时使用其值，否则用调用上的值，两处都没有则省略。两种耗时字段同时存在时会同时保留。
4. 没有耗时的调用也保留一个只有 `name` 的步骤。不根据相邻消息、开始结束时间或返回文本计算耗时。
5. 输出 `{"steps": [...]}`，不加入参数、调用 ID、返回内容或 `status`。

**输入示例**

```json
{
  "messages": [
    {
      "role": "assistant",
      "tool_calls": [
        {"id":"a","duration":2,"group":"source","function":{"name":"search","arguments":{"query":"Dingo"}}},
        {"id":"b","duration_seconds":4,"type":"source","function":{"name":"summarize","arguments":{}}},
        {"function":{"name":"save","arguments":{"path":"summary.txt"}}}
      ]
    },
    {"role":"tool","tool_call_id":"b","content":"done","duration_seconds":3,"type":"inference"},
    {"role":"tool","tool_call_id":"a","content":"found","duration":1,"group":"retrieval"}
  ]
}
```

**转换结果**（`content` 解析后）

```json
{
  "steps": [
    {"name":"search","duration":1,"group":"retrieval"},
    {"name":"summarize","duration_seconds":3,"type":"inference"},
    {"name":"save"}
  ]
}
```

**缺失情况与使用边界**

工具返回顺序为 `b`、`a`，输出仍按 `a`、`b`、`save` 排列。没有调用时输出 `{"steps": []}`。重复有效 ID 会报错。耗时有效性及异常阈值由规则判断；某个分组至少有 3 个有效正耗时才参与检测。规则优先读取 `duration` 和 `group`，缺少对应键时再读取 `duration_seconds` 和 `type`。

### 5. RuleAgentTraceLoopDetection（重复调用循环）

保留完整的工具名、参数及调用顺序，供规则比较重复调用序列。

**fields 配置**

```json
{
  "content": "RuleAgentTraceLoopDetection_content"
}
```

生成 `RuleAgentTraceLoopDetection_content`，类型为 JSON 字符串。

**读取与映射**

| 源字段或统计方式 | 转换后的路径 | 处理方式 |
|---|---|---|
| `assistant.tool_calls[].function.name` | `tool_calls[].tool_name` | 原样复制 |
| `assistant.tool_calls[].function.arguments` | `tool_calls[].args` | 解析为对象，保留全部参数 |

**转换步骤**

1. 按消息顺序扫描 `assistant` 消息，再按每条消息内的数组顺序扫描工具调用。
2. 将名称和解析后的参数组装成 `{"tool_name": ..., "args": ...}`。参数缺失时使用 `{}`。
3. 跨消息拼接所有调用，不排序、不去重、不只保留工具名称。相同工具名但参数不同的调用仍然不同。
4. 输出 `{"tool_calls": [...]}`。不关联工具结果，也不输出调用 ID、状态或耗时；重复 ID 不影响这个转换。

**输入示例**

```json
{
  "messages": [
    {
      "role": "assistant",
      "tool_calls": [
        {"id":"a","function":{"name":"search","arguments":"{\"query\":\"Dingo\"}"}},
        {"id":"b","function":{"name":"read","arguments":{"path":"notes.txt"}}}
      ]
    },
    {"role":"tool","tool_call_id":"b","content":"document"},
    {"role":"assistant","tool_calls":[{"id":"a","function":{"name":"search","arguments":{"query":"Dingo"}}}]}
  ]
}
```

**转换结果**（`content` 解析后）

```json
{
  "tool_calls": [
    {"tool_name":"search","args":{"query":"Dingo"}},
    {"tool_name":"read","args":{"path":"notes.txt"}},
    {"tool_name":"search","args":{"query":"Dingo"}}
  ]
}
```

**缺失情况与使用边界**

没有调用时输出 `{"tool_calls": []}`。转换不预先判定循环；现有规则少于 6 个有效调用时返回 N/A，因此本例仅展示如何保留序列。

### 6. RuleAgentTraceSandboxExplicitlyDisabled（显式关闭沙箱）

把工具参数中的沙箱关闭标志交给规则，同时保留其原始值。

**fields 配置**

```json
{
  "content": "RuleAgentTraceSandboxExplicitlyDisabled_content"
}
```

生成 `RuleAgentTraceSandboxExplicitlyDisabled_content`，类型为 JSON 字符串。

**读取与映射**

| 源字段或统计方式 | 转换后的路径 | 处理方式 |
|---|---|---|
| `assistant.tool_calls[].function.name` | `tool_calls[].tool_name` | 原样复制 |
| `assistant.tool_calls[].function.arguments` | `tool_calls[].args` | 解析后保留全部键和值 |
| 参数中的 `dangerouslyDisableSandbox` | `tool_calls[].args.dangerouslyDisableSandbox` | 保持原始类型，不转换为布尔值 |

**转换步骤**

1. 按顺序读取每个 `assistant` 工具调用，将 `function.name` 写入 `tool_name`。
2. 参数对象原样保留；JSON 字符串解析为对象；缺少参数时使用 `{}`。
3. 不只提取 `dangerouslyDisableSandbox`，其他参数同样保留；该标志缺失时不补 `false`，存在时不修改值。
4. 输出 `{"tool_calls": [...]}`，不关联工具返回或执行状态。

**输入示例**

```json
{
  "messages": [
    {
      "role": "assistant",
      "tool_calls": [
        {
          "id": "sandbox-1",
          "function": {
            "name": "shell",
            "arguments": "{\"command\":\"echo demo\",\"dangerouslyDisableSandbox\":\"true\",\"timeout\":30}"
          }
        }
      ]
    }
  ]
}
```

**转换结果**（`content` 解析后）

```json
{
  "tool_calls": [{"tool_name":"shell","args":{"command":"echo demo","dangerouslyDisableSandbox":"true","timeout":30}}]
}
```

**缺失情况与使用边界**

示例中的 `"true"` 在输出中仍是字符串，其含义由规则判断。没有调用时输出 `{"tool_calls": []}`；没有标志时，converter 不推断沙箱实际是否开启。

### 7. RuleAgentTraceSecretExposure（工具返回中的敏感凭证）

将真实工具返回放入对应调用的 `result`，供规则扫描敏感凭证。

**fields 配置**

```json
{
  "content": "RuleAgentTraceSecretExposure_content"
}
```

生成 `RuleAgentTraceSecretExposure_content`，类型为 JSON 字符串。

**读取与映射**

| 源字段或统计方式 | 转换后的路径 | 处理方式 |
|---|---|---|
| `assistant.tool_calls[].function.name/arguments` | `tool_calls[].tool_name/args` | 名称复制，参数解析为对象 |
| 调用的非空字符串 `id` | `tool_calls[].call_id` | 保留并用于结果配对 |
| 同 ID 的工具消息 `content` | `tool_calls[].result` | 原样复制，保留字符串、对象或 `null` |
| 调用或匹配工具消息的 `status/duration/duration_seconds/group/type` | 调用对象上的同名字段 | 逐字段复制，工具消息优先 |

**转换步骤**

1. 先按非空字符串 `tool_call_id` 索引工具消息，再按原始顺序遍历工具调用。
2. 每次调用保留名称和完整参数；有效 ID 写入 `call_id`。
3. 只把同 ID 工具消息的 `content` 写入 `result`。不按返回顺序配对，不扫描其他消息来补齐结果，也不读取调用自身的 `result`。
4. 找不到工具消息，或匹配消息没有 `content` 键时，省略 `result`；`content=null` 则保留 `result=null`。
5. 现有转换还保留显式 `status`、`duration`、`duration_seconds`、`group`、`type`，逐字段优先使用匹配工具消息，再回退到调用。
6. 输出 `{"tool_calls": [...]}`。敏感凭证识别由规则完成，converter 不先替换或脱敏返回内容。

**输入示例**

```json
{
  "messages": [
    {
      "role": "assistant",
      "tool_calls": [
        {"id":"a","function":{"name":"search","arguments":{"query":"Dingo"}}},
        {"id":"b","status":"pending","function":{"name":"read","arguments":{"path":"demo.pem"}}},
        {"id":"c","function":{"name":"save","arguments":{"path":"summary.txt"}}}
      ]
    },
    {
      "role": "tool",
      "tool_call_id": "b",
      "content": "-----BEGIN PRIVATE KEY-----\nEXAMPLE\n-----END PRIVATE KEY-----",
      "status": "success"
    },
    {"role":"tool","tool_call_id":"a","content":"found"}
  ]
}
```

**转换结果**（`content` 解析后）

```json
{
  "tool_calls": [
    {"tool_name":"search","args":{"query":"Dingo"},"call_id":"a","result":"found"},
    {
      "tool_name": "read",
      "args": {"path":"demo.pem"},
      "call_id": "b",
      "result": "-----BEGIN PRIVATE KEY-----\nEXAMPLE\n-----END PRIVATE KEY-----",
      "status": "success"
    },
    {"tool_name":"save","args":{"path":"summary.txt"},"call_id":"c"}
  ]
}
```

**缺失情况与使用边界**

示例使用虚构凭证文本。`b` 的返回虽然先出现，仍只写入 `b`；`c` 没有返回，因此没有 `result`。没有调用时输出 `{"tool_calls": []}`，重复有效 ID 会报错。没有匹配结果的调用不会提供可供规则扫描的返回证据。

### 8. RuleAgentTraceSensitiveAccess（敏感路径访问）

把工具参数按原始层级保留下来，供规则检查敏感文件或目录路径。

**fields 配置**

```json
{
  "content": "RuleAgentTraceSensitiveAccess_content"
}
```

生成 `RuleAgentTraceSensitiveAccess_content`，类型为 JSON 字符串。

**读取与映射**

| 源字段或统计方式 | 转换后的路径 | 处理方式 |
|---|---|---|
| `assistant.tool_calls[].function.name` | `tool_calls[].tool_name` | 原样复制 |
| `assistant.tool_calls[].function.arguments` | `tool_calls[].args` | 解析为对象，保留嵌套字典和数组 |

**转换步骤**

1. 按顺序读取 `assistant` 工具调用，将工具名称写入 `tool_name`。
2. 解析参数，缺少参数时使用 `{}`。不把嵌套字典展开为一级字段，也不把参数拼接成一段文本。
3. 保留 `path`、`cmd`、`files` 等所有真实参数名和值，不根据名称选择或改写路径。
4. 输出 `{"tool_calls": [...]}`，不关联工具返回、调用 ID 或状态。

**输入示例**

```json
{
  "messages": [
    {
      "role": "assistant",
      "tool_calls": [
        {
          "id": "read-1",
          "function": {"name":"read","arguments":{"path":".env","options":{"path":"~/.ssh/id_rsa"},"files":["notes.txt"]}}
        }
      ]
    }
  ]
}
```

**转换结果**（`content` 解析后）

```json
{
  "tool_calls": [{"tool_name":"read","args":{"path":".env","options":{"path":"~/.ssh/id_rsa"},"files":["notes.txt"]}}]
}
```

**缺失情况与使用边界**

示例中的一级 `path` 和嵌套 `options.path` 均被保留，但现有规则只扫描一级简单参数值，不递归扫描嵌套字典或数组；嵌套路径仍可能漏检。没有调用时输出 `{"tool_calls": []}`。

### 9. RuleAgentTraceTokenBudget（总 Token 预算）

把源记录明确提供的总 Token 用量交给规则。

**fields 配置**

```json
{
  "content": "RuleAgentTraceTokenBudget_content"
}
```

生成 `RuleAgentTraceTokenBudget_content`，类型为 JSON 字符串。

**读取与映射**

| 源字段或统计方式 | 转换后的路径 | 处理方式 |
|---|---|---|
| 顶层 `total_tokens` | `total_tokens` | 源键存在时原样复制，不进行数值转换 |
| 顶层 `reasoning_total_tokens` | 无对应输出 | 不作为总用量的替代值 |

**转换步骤**

1. 检查顶层是否存在 `total_tokens` 键。
2. 存在时生成 `{"total_tokens": record["total_tokens"]}`，保留源值及类型；即使值为 `0` 或 `null`，也不因其真假而省略。
3. 不存在时生成空对象 `{}`，不读取 `reasoning_total_tokens` 或 `metadata.total_tokens`，也不累加消息中的用量。
4. 序列化对象，写入 `RuleAgentTraceTokenBudget_content`；本转换不解析工具调用。

**输入示例**

```json
{
  "total_tokens": 560000,
  "reasoning_total_tokens": 900000,
  "messages": []
}
```

**转换结果**（`content` 解析后）

```json
{
  "total_tokens": 560000
}
```

**缺失情况与使用边界**

本例只复制 560000。若删除顶层 `total_tokens`，即使 `reasoning_total_tokens=900000`，输出仍为 `{}`。总用量是否有效以及是否超出预算由规则判断；没有可用用量时返回 N/A。

## 三、LLM 指标

本版 7 个 LLM 指标统一使用 `_messages_content()`，但分别生成自己的辅助字段。
下面每节独立说明该指标的输入适配方式；它们暂未分别实现工具、计划或错误事件提取。

### 10. LLMAgentArgumentCorrectness（工具参数正确性）

为参数正确性评估准备会话文本；本版没有单独提取结构化工具参数。

**fields 配置**

```json
{
  "prompt": "LLMAgentArgumentCorrectness_prompt",
  "content": "LLMAgentArgumentCorrectness_content"
}
```

生成 `LLMAgentArgumentCorrectness_content`（JSON 字符串）和 `LLMAgentArgumentCorrectness_prompt`（空字符串 `""`）。

**读取与映射**

| 源字段 | 转换后的路径或字段 | 处理方式 |
|---|---|---|
| `messages[].role` | `content[].role` | 原样保留，键缺失时使用 `""` |
| `messages[].content` | `content[].content` | 原样保留，键缺失时使用 `""`，不解析其中的 JSON 文本 |
| 源记录的任务描述或 `prompt` | 辅助 `prompt` | 不提取或复制，固定为 `""` |
| `tool_calls/reasoning_content/tools` 及其他消息、顶层字段 | 无对应输出 | 不进入精简会话 |

**转换步骤**

1. 调用 `_messages_content()`，按原始数组顺序遍历所有消息，保留所有角色，不筛选 assistant 或 tool。
2. 每条消息生成 `{"role": message.get("role", ""), "content": message.get("content", "")}`，其他键省略；字段显式为 `null` 时保留 `null`，不会替换为空字符串。
3. 将消息列表序列化为 JSON 字符串，写入 `LLMAgentArgumentCorrectness_content`；`LLMAgentArgumentCorrectness_prompt` 固定为空字符串。

**输入示例**

```json
{
  "prompt": "检索 Dingo 的安装文档",
  "tools": [{"name":"search","description":"搜索文档"}],
  "messages": [
    {"role":"user","content":"请搜索 Dingo 的安装文档"},
    {
      "role": "assistant",
      "content": "开始搜索",
      "tool_calls": [{"id":"a","function":{"name":"search","arguments":{"query":"Dingo installation"}}}]
    },
    {"role":"tool","tool_call_id":"a","content":"找到安装文档"}
  ]
}
```

**转换结果**（`content` 解析后）

```json
[
  {"role":"user","content":"请搜索 Dingo 的安装文档"},
  {"role":"assistant","content":"开始搜索"},
  {"role":"tool","content":"找到安装文档"}
]
```

示例中的 `function.arguments.query` 和工具定义不会进入辅助 `content`。用户请求保留在会话里，但不会被抽取为 `prompt`。

**缺失情况与使用边界**

没有消息时 `content` 为字符串 `"[]"`。如果参数只存在于 `tool_calls`，LLM 在这版输入中看不到具体参数，参数正确性评分的证据可能不足。

### 11. LLMAgentToolCorrectness（工具选择正确性）

为工具选择评估准备会话文本；本版不额外传入可用工具定义或调用名称。

**fields 配置**

```json
{
  "prompt": "LLMAgentToolCorrectness_prompt",
  "content": "LLMAgentToolCorrectness_content"
}
```

生成 `LLMAgentToolCorrectness_content`（JSON 字符串）和 `LLMAgentToolCorrectness_prompt`（空字符串 `""`）。

**读取与映射**

| 源字段 | 转换后的路径或字段 | 处理方式 |
|---|---|---|
| `messages[].role` | `content[].role` | 原样保留，键缺失时使用 `""` |
| `messages[].content` | `content[].content` | 原样保留，键缺失时使用 `""`，不解析其中的 JSON 文本 |
| 源记录的任务描述或 `prompt` | 辅助 `prompt` | 不提取或复制，固定为 `""` |
| `tool_calls/reasoning_content/tools` 及其他消息、顶层字段 | 无对应输出 | 不进入精简会话 |

**转换步骤**

1. 调用 `_messages_content()`，按原始数组顺序遍历所有消息，保留所有角色，不筛选 assistant 或 tool。
2. 每条消息生成 `{"role": message.get("role", ""), "content": message.get("content", "")}`，其他键省略；字段显式为 `null` 时保留 `null`，不会替换为空字符串。
3. 将消息列表序列化为 JSON 字符串，写入 `LLMAgentToolCorrectness_content`；`LLMAgentToolCorrectness_prompt` 固定为空字符串。

**输入示例**

```json
{
  "tools": [{"name":"search","description":"检索资料"},{"name":"read","description":"读取文件"}],
  "messages": [
    {"role":"developer","content":"需要查资料时使用搜索工具"},
    {"role":"user","content":"查找 Dingo 文档"},
    {
      "role": "assistant",
      "content": "我来检索",
      "tool_calls": [{"id":"a","function":{"name":"search","arguments":{"query":"Dingo"}}}]
    },
    {"role":"tool","tool_call_id":"a","name":"search"}
  ]
}
```

**转换结果**（`content` 解析后）

```json
[
  {"role":"developer","content":"需要查资料时使用搜索工具"},
  {"role":"user","content":"查找 Dingo 文档"},
  {"role":"assistant","content":"我来检索"},
  {"role":"tool","content":""}
]
```

`developer` 消息也会保留；最后一条工具消息缺少 `content`，因此补为空字符串。工具定义、`tool_calls` 及工具消息的 `name` 均省略。

**缺失情况与使用边界**

没有消息时 `content` 为字符串 `"[]"`。如果工具名称和职责只存在于结构化调用或工具定义中，LLM 无法从本版输入直接获得这些证据。

### 12. LLMAgentErrorRecovery（错误恢复）

为错误恢复评估准备完整顺序的消息文本；本版不构建独立错误事件或重试记录。

**fields 配置**

```json
{
  "prompt": "LLMAgentErrorRecovery_prompt",
  "content": "LLMAgentErrorRecovery_content"
}
```

生成 `LLMAgentErrorRecovery_content`（JSON 字符串）和 `LLMAgentErrorRecovery_prompt`（空字符串 `""`）。

**读取与映射**

| 源字段 | 转换后的路径或字段 | 处理方式 |
|---|---|---|
| `messages[].role` | `content[].role` | 原样保留，键缺失时使用 `""` |
| `messages[].content` | `content[].content` | 原样保留，键缺失时使用 `""`，不解析其中的 JSON 文本 |
| 源记录的任务描述或 `prompt` | 辅助 `prompt` | 不提取或复制，固定为 `""` |
| `tool_calls/reasoning_content/tools` 及其他消息、顶层字段 | 无对应输出 | 不进入精简会话 |

**转换步骤**

1. 调用 `_messages_content()`，按原始数组顺序遍历所有消息，保留所有角色，不筛选 assistant 或 tool。
2. 每条消息生成 `{"role": message.get("role", ""), "content": message.get("content", "")}`，其他键省略；字段显式为 `null` 时保留 `null`，不会替换为空字符串。
3. 将消息列表序列化为 JSON 字符串，写入 `LLMAgentErrorRecovery_content`；`LLMAgentErrorRecovery_prompt` 固定为空字符串。

**输入示例**

```json
{
  "messages": [
    {"role":"user","content":"检索资料并总结"},
    {
      "role": "assistant",
      "content": "正在检索",
      "tool_calls": [{"id":"a","function":{"name":"search","arguments":{"query":"Dingo"}}}]
    },
    {
      "role": "tool",
      "tool_call_id": "a",
      "status": "error",
      "content": "{\"status\":\"error\",\"message\":\"timeout\"}"
    },
    {"role":"assistant","content":"检索超时，我将重试"}
  ]
}
```

**转换结果**（`content` 解析后）

```json
[
  {"role":"user","content":"检索资料并总结"},
  {"role":"assistant","content":"正在检索"},
  {"role":"tool","content":"{\"status\":\"error\",\"message\":\"timeout\"}"},
  {"role":"assistant","content":"检索超时，我将重试"}
]
```

工具消息的顶层 `status` 不进入辅助 `content`；它的 `content` 本身是一段 JSON 字符串，仍作为字符串保留，不解析为错误对象。

**缺失情况与使用边界**

没有消息时 `content` 为字符串 `"[]"`。converter 不检查是否发生错误、不识别重试链路。非空精简会话可能触发 LLM 评估，即使会话里没有已确认的错误事件。

### 13. LLMAgentPlanAdherence（计划遵循程度）

准备会话消息，并为计划遵循指标提供空的任务目标与计划上下文字段。

**fields 配置**

```json
{
  "prompt": "LLMAgentPlanAdherence_prompt",
  "content": "LLMAgentPlanAdherence_content",
  "context": "LLMAgentPlanAdherence_context"
}
```

生成 `LLMAgentPlanAdherence_content`（JSON 字符串）和 `LLMAgentPlanAdherence_prompt`（空字符串 `""`）。
另生成 `LLMAgentPlanAdherence_context`，值同样为 `""`。

**读取与映射**

| 源字段 | 转换后的路径或字段 | 处理方式 |
|---|---|---|
| `messages[].role` | `content[].role` | 原样保留，键缺失时使用 `""` |
| `messages[].content` | `content[].content` | 原样保留，键缺失时使用 `""`，不解析其中的 JSON 文本 |
| 源记录的任务描述或 `prompt` | 辅助 `prompt` | 不提取或复制，固定为 `""` |
| 源记录的计划或 `context` | 辅助 `context` | 不提取或复制，固定为 `""` |
| `tool_calls/reasoning_content/tools` 及其他消息、顶层字段 | 无对应输出 | 不进入精简会话 |

**转换步骤**

1. 调用 `_messages_content()`，按原始数组顺序遍历所有消息，保留所有角色，不筛选 assistant 或 tool。
2. 每条消息生成 `{"role": message.get("role", ""), "content": message.get("content", "")}`，其他键省略；字段显式为 `null` 时保留 `null`，不会替换为空字符串。
3. 将消息列表序列化为 JSON 字符串，写入 `LLMAgentPlanAdherence_content`；`LLMAgentPlanAdherence_prompt` 固定为空字符串。
4. 将 `LLMAgentPlanAdherence_context` 固定设为空字符串，独立于源记录的上下文。

**输入示例**

```json
{
  "prompt": "比较 A 和 B",
  "context": "原始计划：先检索 A，再检索 B，最后比较",
  "messages": [
    {"role":"user","content":"请比较 A 和 B"},
    {"role":"assistant","content":"先检索 A","reasoning_content":"之后再检索 B"},
    {"role":"assistant","content":"已经完成比较"}
  ]
}
```

**转换结果**（`content` 解析后）

```json
[
  {"role":"user","content":"请比较 A 和 B"},
  {"role":"assistant","content":"先检索 A"},
  {"role":"assistant","content":"已经完成比较"}
]
```

即使原始记录有 `prompt` 和 `context`，本转换仍生成空的辅助 `prompt` 和 `context`；原始字段继续留在原始记录中。`reasoning_content` 也不会进入精简会话。

**缺失情况与使用边界**

没有消息时 `content` 为字符串 `"[]"`，`prompt/context` 仍为空。当前没有独立的原始计划或任务目标输入，无法把成功转换直接理解为计划遵循证据已完整。

### 14. LLMAgentPlanQuality（计划质量）

为计划质量评估准备会话文本；本版不从推理字段中提取计划。

**fields 配置**

```json
{
  "prompt": "LLMAgentPlanQuality_prompt",
  "content": "LLMAgentPlanQuality_content"
}
```

生成 `LLMAgentPlanQuality_content`（JSON 字符串）和 `LLMAgentPlanQuality_prompt`（空字符串 `""`）。

**读取与映射**

| 源字段 | 转换后的路径或字段 | 处理方式 |
|---|---|---|
| `messages[].role` | `content[].role` | 原样保留，键缺失时使用 `""` |
| `messages[].content` | `content[].content` | 原样保留，键缺失时使用 `""`，不解析其中的 JSON 文本 |
| 源记录的任务描述或 `prompt` | 辅助 `prompt` | 不提取或复制，固定为 `""` |
| `tool_calls/reasoning_content/tools` 及其他消息、顶层字段 | 无对应输出 | 不进入精简会话 |

**转换步骤**

1. 调用 `_messages_content()`，按原始数组顺序遍历所有消息，保留所有角色，不筛选 assistant 或 tool。
2. 每条消息生成 `{"role": message.get("role", ""), "content": message.get("content", "")}`，其他键省略；字段显式为 `null` 时保留 `null`，不会替换为空字符串。
3. 将消息列表序列化为 JSON 字符串，写入 `LLMAgentPlanQuality_content`；`LLMAgentPlanQuality_prompt` 固定为空字符串。

**输入示例**

```json
{
  "messages": [
    {"role":"user","content":"查资料后写一份总结"},
    {"role":"assistant","content":"","reasoning_content":"先检索资料，再核对来源，最后总结"},
    {"role":"assistant","content":"总结已完成"}
  ]
}
```

**转换结果**（`content` 解析后）

```json
[
  {"role":"user","content":"查资料后写一份总结"},
  {"role":"assistant","content":""},
  {"role":"assistant","content":"总结已完成"}
]
```

示例的计划只出现在 `reasoning_content` 中，转换后该计划文本不在辅助 `content` 里；空的 assistant `content` 按原值保留。

**缺失情况与使用边界**

没有消息时 `content` 为字符串 `"[]"`。只有消息 `content` 中明确写出的计划会随文本保留；本版不识别、整理或推断计划，计划质量评分可能缺少计划证据。

### 15. LLMAgentStepEfficiency（执行步骤效率）

为步骤效率评估准备会话文本；本版不把工具调用展开成独立的执行步骤。

**fields 配置**

```json
{
  "prompt": "LLMAgentStepEfficiency_prompt",
  "content": "LLMAgentStepEfficiency_content"
}
```

生成 `LLMAgentStepEfficiency_content`（JSON 字符串）和 `LLMAgentStepEfficiency_prompt`（空字符串 `""`）。

**读取与映射**

| 源字段 | 转换后的路径或字段 | 处理方式 |
|---|---|---|
| `messages[].role` | `content[].role` | 原样保留，键缺失时使用 `""` |
| `messages[].content` | `content[].content` | 原样保留，键缺失时使用 `""`，不解析其中的 JSON 文本 |
| 源记录的任务描述或 `prompt` | 辅助 `prompt` | 不提取或复制，固定为 `""` |
| `tool_calls/reasoning_content/tools` 及其他消息、顶层字段 | 无对应输出 | 不进入精简会话 |

**转换步骤**

1. 调用 `_messages_content()`，按原始数组顺序遍历所有消息，保留所有角色，不筛选 assistant 或 tool。
2. 每条消息生成 `{"role": message.get("role", ""), "content": message.get("content", "")}`，其他键省略；字段显式为 `null` 时保留 `null`，不会替换为空字符串。
3. 将消息列表序列化为 JSON 字符串，写入 `LLMAgentStepEfficiency_content`；`LLMAgentStepEfficiency_prompt` 固定为空字符串。

**输入示例**

```json
{
  "total_tool_calls": 2,
  "messages": [
    {"role":"user","content":"查找并阅读 Dingo 文档"},
    {
      "role": "assistant",
      "content": "我来查找并阅读",
      "tool_calls": [
        {"id":"a","function":{"name":"search","arguments":{"query":"Dingo"}}},
        {"id":"b","function":{"name":"read","arguments":{"path":"notes.txt"}}}
      ]
    },
    {"role":"tool","tool_call_id":"a","content":"已找到文档"},
    {"role":"tool","tool_call_id":"b","content":"文档内容"},
    {"role":"assistant","content":"阅读完成"}
  ]
}
```

**转换结果**（`content` 解析后）

```json
[
  {"role":"user","content":"查找并阅读 Dingo 文档"},
  {"role":"assistant","content":"我来查找并阅读"},
  {"role":"tool","content":"已找到文档"},
  {"role":"tool","content":"文档内容"},
  {"role":"assistant","content":"阅读完成"}
]
```

一条 assistant 消息里有两次工具调用，转换后仍只是一条 assistant 消息，不展开成两个步骤。顶层 `total_tool_calls` 和工具消息的 `tool_call_id` 也不进入辅助 `content`。

**缺失情况与使用边界**

没有消息时 `content` 为字符串 `"[]"`。本版不统计执行步骤、不建立调用与返回的结构化关系，也不划分多轮任务边界；这些信息不足可能影响效率评分。

### 16. LLMAgentTaskCompletion（任务完成情况）

为任务完成情况评估准备完整顺序的会话文本；本版不单独抽取任务目标。

**fields 配置**

```json
{
  "prompt": "LLMAgentTaskCompletion_prompt",
  "content": "LLMAgentTaskCompletion_content"
}
```

生成 `LLMAgentTaskCompletion_content`（JSON 字符串）和 `LLMAgentTaskCompletion_prompt`（空字符串 `""`）。

**读取与映射**

| 源字段 | 转换后的路径或字段 | 处理方式 |
|---|---|---|
| `messages[].role` | `content[].role` | 原样保留，键缺失时使用 `""` |
| `messages[].content` | `content[].content` | 原样保留，键缺失时使用 `""`，不解析其中的 JSON 文本 |
| 源记录的任务描述或 `prompt` | 辅助 `prompt` | 不提取或复制，固定为 `""` |
| `tool_calls/reasoning_content/tools` 及其他消息、顶层字段 | 无对应输出 | 不进入精简会话 |

**转换步骤**

1. 调用 `_messages_content()`，按原始数组顺序遍历所有消息，保留所有角色，不筛选 assistant 或 tool。
2. 每条消息生成 `{"role": message.get("role", ""), "content": message.get("content", "")}`，其他键省略；字段显式为 `null` 时保留 `null`，不会替换为空字符串。
3. 将消息列表序列化为 JSON 字符串，写入 `LLMAgentTaskCompletion_content`；`LLMAgentTaskCompletion_prompt` 固定为空字符串。

**输入示例**

```json
{
  "prompt": "列出 Dingo 的安装步骤",
  "total_tool_calls": 1,
  "reasoning_total_tokens": 100,
  "messages": [
    {"role":"user","content":"请列出 Dingo 的安装步骤"},
    {"role":"assistant","content":"先运行 pip install dingo-python，再准备配置并执行评估","reasoning_content":"已经覆盖全部步骤"}
  ]
}
```

**转换结果**（`content` 解析后）

```json
[
  {"role":"user","content":"请列出 Dingo 的安装步骤"},
  {"role":"assistant","content":"先运行 pip install dingo-python，再准备配置并执行评估"}
]
```

用户要求和最终回答保留在精简会话中，但源记录的 `prompt` 不会复制到辅助 `prompt`。调用计数、Token 用量和 `reasoning_content` 不进入辅助 `content`。

**缺失情况与使用边界**

没有消息时 `content` 为字符串 `"[]"`。本版保留会话里的任务文本，但不将其提取为独立目标，也不划分多任务轨迹；任务完成评分需考虑这些输入边界。

## 四、配置与运行

每节的 **fields 配置** 放入该指标自己的 `evaluator` 配置块，
`evals[].name` 使用章节中的完整指标名。例如：

```json
{
  "input_path": "data/agent_traces.jsonl",
  "dataset": {"source":"local","format":"ms_swift"},
  "executor": {"result_save":{"good":true,"raw":true}},
  "evaluator": [
    {
      "fields": {"content":"RuleAgentTraceLoopDetection_content"},
      "evals": [{"name":"RuleAgentTraceLoopDetection"}]
    },
    {
      "fields": {
        "prompt": "LLMAgentPlanAdherence_prompt",
        "content": "LLMAgentPlanAdherence_content",
        "context": "LLMAgentPlanAdherence_context"
      },
      "evals": [
        {
          "name": "LLMAgentPlanAdherence",
          "config": {"model":"YOUR_MODEL","api_url":"https://your-endpoint/v1","key":"YOUR_API_KEY"}
        }
      ]
    }
  ]
}
```

完整 16 个指标的配置见 [ms_swift.json](../../examples/dataset/ms_swift.json)。
修改输入路径，并为选中的 LLM 指标填写模型配置后运行：

```bash
dingo eval --input examples/dataset/ms_swift.json
```

## 五、结果输出

这些辅助字段只用于质检输入。本地执行器写出结果时，自动删除本条记录实际生成的辅助字段，
无需维护删除清单；原始记录及未生成的同名前缀字段仍按现有输出规则保留。

| 配置 | 输出形态 | 辅助字段清理位置 |
|---|---|---|
| `result_save.raw=true` | 原始字段与 `dingo_id`、`dingo_result` 一起输出 | 输出的原始字段中 |
| `result_save.raw=false` | 评估结果与 `raw_data` 一起输出 | `raw_data` 中 |

`field_list` 筛选发生在辅助字段清理之后；已有 `dingo_id_old_v1` 等字段冲突备份沿用原逻辑。
`eval_details` 中用于追溯输入的映射名称仍然保留，辅助字段值不再写入原始数据输出。

若某个辅助字段与原始记录字段同名，转换会报错，避免覆盖原始数据。
未选中指标的同名原始字段不会被清理。错误定位会包含消息或调用索引，便于修正输入。
