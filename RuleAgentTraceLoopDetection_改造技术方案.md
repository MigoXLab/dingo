# RuleAgentTraceLoopDetection 改造技术方案

日期：2026-11-09（Asia/Shanghai）  
状态：实现前技术方案；本次交付只新增本文档，不修改 Python 实现。  
目标仓库：`C:/Users/renzhifei/qaCode/dingo`

## 1. 目标与已确认约束

本次将 `RuleAgentTraceLoopDetection` 定义为：在当前轨迹节点内，检测连续出现的相同或近重复工具交互模式。一次交互包括工具名、参数和工具结果正文。

本版只检测重复现象，不评估重复是否有意义、是否合理、是否代表进程卡死，也不把命中解释为 Agent 的恶意或任务失败。正常状态轮询可能命中，这是当前口径允许的情况。

### 1.1 已确认的产品约束

1. 纯规则实现，不调用 LLM、embedding 或其他模型服务。
2. 所有工具使用相同逻辑，不为 `write_stdin`、`search` 等工具设置白名单或豁免。
3. 不增加 `schema_version` 字段。
4. 沿用 `RuleAgentTraceLoopDetection_content` 辅助字段和现有 `fields` 映射。
5. 工具结果按返回包装拆分：`result` 保存 `Output:` 后正文，`result_headers` 原样保存前缀。
6. `result_headers` 不解析成独立的 Chunk ID、耗时、Token 数、进程状态等字段；将来其他规则可以自行解析。
7. 原始 `messages` 和其 `content` 不由 converter 修改。
8. 判定使用 `EvalDetail.status=True/False`，不增加 warning、质量分数或第三种正常判定结果。
9. 支持长度为 1 的模式，例如 `AAA`、`AAAA`；不能保留统一的“少于 6 次调用不判断”。
10. 第一个动作候选未通过结果比较后，必须继续搜索其他起点和模式长度。

### 1.2 本文建议的默认值

这些是建议初值，实施后应使用“是否近重复”的标注样本验证，不是行业标准或已经完成数据集校准的结论。

| 项目 | 默认值 | 说明 |
|---|---|---|
| 工具名比较 | 精确 | 区分大小写 |
| 参数比较 | JSON 规范化后精确 | 不比较参数的文本近似度 |
| 结果比较模式 | `ngram` | 字符 n-gram 计数 Jaccard |
| n-gram 长度 | 5 | 不需要分词，兼容中英文和日志 |
| 结果相似度阈值 | 0.95 | 包含边界，即 `similarity >= threshold` |
| 最少连续出现次数 | 3 | 包含第一次，不是“第一次之后再执行三次” |
| 模式长度下界 | 1 | 单调用和多调用统一处理 |
| 用户消息边界 | 分段 | 避免跨不同用户请求组成一个连续模式 |

## 2. 当前实现与问题定位

以下基于编写本文时读取的本地代码。后续实现以函数和类定位为准，行号可能随其他改动变化。

| 位置 | 当前行为 | 本次改造 |
|---|---|---|
| `dingo/data/converter/ms_swift.py::prepare_rule_agent_trace_loop_detection` | 只生成 `tool_name` 和 `args` | 关联工具返回，拆分 headers/body，保留定位字段 |
| `dingo/model/rule/rule_agent.py::RuleAgentTraceLoopDetection.eval` | `len(calls) < 6` 直接返回不适用 | 改为二分类；按模式长度和重复次数判断所需长度 |
| 同类的 `_extract_calls` | 只生成工具名和参数签名 | 保留结果及原始索引，构造可比较交互 |
| 同类的 `_detect_loops` | 搜索长度至少为 2 的签名模式，返回第一个候选 | 从长度 1 开始，候选必须完成结果复核后才可作为命中返回 |
| 同类的 `_detect_repeated_identical_calls` | 单调用补充分支，但受外层 6 次门槛限制 | 合并入统一模式检测，避免两套路径条件不一致 |

### 2.1 现有 6 次门槛为什么会漏检

长度 2 的模式出现 3 次需要 6 次调用：`ABABAB`。但长度 1 的模式出现 3 次只需要 3 次调用：`AAA`。

当前代码先执行 `len(calls) < 6`，导致只有 3～5 次调用的轨迹根本走不到单调用检测。新方案统一采用：

```text
所需调用数 = 模式长度 × 最少连续出现次数
```

### 2.2 当前“第一个候选就返回”的边界

旧算法只检查工具名和参数，找到符合旧定义的第一个模式就返回是可以理解的。加入结果条件后，不能把旧函数返回的第一个动作候选作为唯一检查对象：

```text
A(R1) → A(R2) → A(R2) → A(R2) → A(R2)
```

若只检查整个五次调用，结果不是全部相似，便直接返回 False，会漏掉后四次 `A(R2)`。

必须继续从后续位置寻找满足“工具、参数、结果”共同条件的窗口。这里假设 R1 与 R2 的相似度低于阈值。

## 3. 输入与转换后的数据契约

### 3.1 ms_swift 原始输入

每行一个轨迹对象。Loop preparer 消费当前节点的 `messages`：

```json
{
  "messages": [
    {
      "role": "assistant",
      "content": "",
      "reasoning_content": "",
      "tool_calls": [
        {
          "type": "function",
          "id": "call_01",
          "function": {
            "name": "example_tool",
            "arguments": {"task_id": "task-1"}
          }
        }
      ]
    },
    {
      "role": "tool",
      "tool_call_id": "call_01",
      "name": "example_tool",
      "content": "Chunk ID: chunk-1\nWall time: 30.0014 seconds\nProcess running with session ID 4868\nOriginal token count: 8\nOutput:\nrunning\n"
    }
  ]
}
```

以上只展示本指标需要的输入部分，不是 `RuleMsSwiftSchema` 完整交付校验的最小通过样例。完整 Schema 的其他必选字段仍按原标准提供。

### 3.2 辅助字段

preparer 返回：

```python
{
    "RuleAgentTraceLoopDetection_content": json.dumps(
        {"tool_calls": calls}, ensure_ascii=False
    )
}
```

该字段的类型仍是字符串。解析后的结构如下，不包含 `schema_version`：

```json
{
  "tool_calls": [
    {
      "call_index": 0,
      "call_id": "call_01",
      "tool_name": "example_tool",
      "args": {"task_id": "task-1"},
      "message_index": 0,
      "call_index_in_message": 0,
      "segment_id": 0,
      "result_present": true,
      "result_message_index": 1,
      "result_headers": "Chunk ID: chunk-1\nWall time: 30.0014 seconds\nProcess running with session ID 4868\nOriginal token count: 8\nOutput:\n",
      "result": "running\n"
    }
  ]
}
```

### 3.3 字段说明

| 字段 | 类型 | 定义 |
|---|---|---|
| `call_index` | integer | 当前节点所有 assistant 工具调用中的 0 基索引，不因结果缺失重新编号 |
| `call_id` | string | 原始 `tool_calls[].id`，用于配对和定位，不参与相似度 |
| `tool_name` | string | 原始 `function.name`，区分大小写 |
| `args` | 任意 JSON 值 | 保持现有参数提取兼容行为；保留对象、数组、字符串、数值、布尔或 null |
| `message_index` | integer | 调用所在原始消息的 0 基索引 |
| `call_index_in_message` | integer | 该 assistant 消息内部的 0 基调用索引 |
| `segment_id` | integer | 初始为 0，每遇到一条 user 消息加 1；同一段内寻找连续模式 |
| `result_present` | boolean | 是否唯一关联到一条合法的工具返回消息 |
| `result_message_index` | integer/null | 返回消息位置；没有匹配结果时为 null |
| `result_headers` | string | 识别到的返回头原文，包含 `Output:` 标记行及其行结束符 |
| `result` | string | 标记后的正文；没有识别到包装时为完整原始 content |

除必要的参数兼容解析外，原始消息和参数不原地修改。本版不增加 `result_body`、`execution`、额外 Token/耗时字段或推断出的 status。

### 3.4 缺少返回与空返回

缺少返回：

```json
{
  "result_present": false,
  "result_message_index": null,
  "result_headers": "",
  "result": ""
}
```

确实收到空正文：

```json
{
  "result_present": true,
  "result_message_index": 1,
  "result_headers": "Chunk ID: chunk-1\nWall time: 1 seconds\nOutput:\n",
  "result": ""
}
```

新目标只检测重复，因此两个已存在的空正文按完全相同处理；不能沿用讨论早期的“非空结果才可命中”条件。缺少返回记录则不可作为相同结果处理。

## 4. Converter 的具体修改

### 4.1 两遍扫描与 ID 配对

第一遍：遍历当前节点所有消息，为 `role="tool"` 且拥有合法 `tool_call_id` 的消息建立返回索引，保存消息及原始位置。

第二遍：按 `messages` 顺序和每条 `tool_calls` 内顺序提取 assistant 调用，读取工具名、参数及 call ID，然后关联返回并执行 headers/body 分割。

必须满足：

1. 按 ID 配对，不按数组位置配对，不按工具名配对。
2. 返回乱序不影响配对；调用顺序仍以 assistant 发出顺序为准。
3. 重复调用 ID 或重复返回 ID 不允许静默覆盖，应使该指标提取失败，并由现有提取失败路径报告输入问题。
4. 没有结果不是格式解析异常，保留该调用并设置 `result_present=False`。
5. result `content` 必须是字符串，不二次 JSON 反序列化。
6. 孤立返回无法替代缺失返回；完整格式合法性由 `RuleMsSwiftSchema` 独立检查，不在本 preparer 重复实现所有校验。
7. `call_index` 在追加每条调用时确定，不通过过滤后的数组位置回推。
8. 工具返回的 `name` 为空时仍按 ID 关联，工具名取 assistant 调用中的 `function.name`。

当前 `_tool_call_name_and_arguments()` 对字符串参数保留了 `json.loads()` 兼容处理。第一版沿用该行为，避免在 Loop 改造中同时改变所有规则的参数适配；原始参数仍可从原始消息追溯。文档应说明标准生产者通常已经完成该归一化。

### 4.2 Headers/body 分割函数

建议增加一个纯函数，例如：

```python
def split_tool_result(content: str) -> tuple[str, str]:
    """Return (result_headers, result), preserving the original text."""
```

将来其他指标需要相同分割时可复用该函数。首版可放在 `ms_swift.py` 内；若单独放入工具模块，建议使用 `dingo/data/converter/agent_trace_utils.py`，不依赖 Rule 类或模型服务。

### 4.3 返回头识别与保真原则

本版支持附件中已知的执行器返回头格式。实现应从字符串开头识别由 `Chunk ID:`、`Wall time:` 以及可选进程状态、`Original token count:` 等行组成的包装，并定位独立的 `Output:` 行。

推荐首版要求前缀包含开头的 `Chunk ID:` 与 `Wall time:`，中间只出现支持的头行或空行，再遇到 `Output:`。未知格式整体保留为 result，后续按返回格式扩展识别器，不按工具名称扩展。

识别器仅检查格式，不把字段值转成数字或对象。可能的进程行包括 `Process running with session ID ...` 与 `Process exited with code ...`；实现前应使用实际返回样例补齐允许的头行。遇到未知头行时保守回退，不猜测删除范围。

禁止无条件使用 `content.split("Output:", 1)`：普通文件正文和示例代码也可能出现这个字符串。

分割边界约定：`result_headers` 包含 `Output:` 标记行、该行尾部空白及行结束符；`result` 从后一个字符开始。允许末尾 `Output:` 没有换行且正文为空。

核心不变量：

```python
headers, result = split_tool_result(content)
assert headers + result == content
```

识别过程可检查行的临时视图，但不能对输出使用 `strip()`/`lstrip()`/`rstrip()`，不能重建 header，不能统一原始 CRLF/LF。正文内再次出现的 `Output:` 不再分割。

| 输入情况 | headers | result |
|---|---|---|
| 已知完整包装 | 含标记行的原始前缀 | 标记后全部内容 |
| 无包装的普通文本 | 空字符串 | 原文 |
| JSON 字符串 | 空字符串 | 原始字符串，不转成字典 |
| 未知或不完整包装 | 空字符串 | 原文 |
| 已知包装但正文为空 | 完整头部 | 空字符串 |

### 4.4 轨迹边界

- 只读取当前节点 `messages`，不拼接子 Agent。
- 不把 `server_tool_calls` 加入 client 调用序列。
- 每个 user 消息建立新 segment；不会因为 assistant 的解释文本不同就认为发生进展。
- 当前目标是重复现象，因此不因多个调用属于同一 assistant 消息或并发批次而自动豁免；`call_index_in_message` 只保留定位证据。未来若评估“读到同一反馈后仍机械重试”，再增加因果顺序约束。
- 不把工具结果不存在的调用、格式异常的调用从序列中删除后再拼接两边。它们应中断可比较的重复窗口。

## 5. Rule 内的数据模型与精确比较

### 5.1 调整 `_extract_calls`

当前返回 `(tool_name, signature)` 的 tuple 不足以进行结果比较。建议返回内部数据类或结构化记录，包含：

```text
source_index、call_id、segment_id、tool_name、args_key、
result_present、normalized_result、原始消息定位信息
```

其中 source_index 优先取有效的 `call_index`；直接 SDK 输入没有该字段时取原始数组位置。内部模型不作为 converter 新字段写回。

### 5.2 参数规范化

```python
def canonical_args(args):
    return json.dumps(
        args,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
```

不使用 `default=str` 把不合法对象转为字符串，不排序数组，不删除字符串中的空格，不把参数缺失与明确的 `{}`/`[]`/null 混为一类。布尔值与数值也必须保留 JSON 类型差异。

工具名与 args_key 的组合构成动作键。同一位置只有动作键完全相同，才计算结果相似度。可用完整哈希作为缓存键，但哈希距离不是文本相似度；必要时仍可核验规范化原值。

### 5.3 结果比较副本

保存的 `result` 原文不变。用于比较的临时副本仅执行：

```python
normalized_result = result.replace("\r\n", "\n")
```

不删除数字、百分比、业务时间戳、URL、文件路径、进度行、ANSI 字符或空白缩进，不转小写，不自动解析 JSON 正文。裸 `\r` 仍保留。后续若增加其他归一化，应独立说明行为变化并补测试。

## 6. 单次交互相似度

### 6.1 总体条件

两次交互 i、j 可视为重复，需要同时满足：

```text
tool_name_i == tool_name_j
canonical_args_i == canonical_args_j
result_present_i == result_present_j == True
result_similarity_i_j >= threshold
```

不采用工具名、参数、正文的加权平均，避免长正文掩盖不同参数。`call_id`、headers、时间、Token 数和定位字段不进入比较。

### 6.2 字符 n-gram 计数 Jaccard

将正文拆成长度为 n 的连续字符片段，用 `collections.Counter` 统计每个片段出现次数。设 C1(g)、C2(g) 是片段 g 的计数：

```text
S = Σ min(C1(g), C2(g)) / Σ max(C1(g), C2(g))
```

使用计数而不是集合，可以区分同一段日志出现一次和出现多次。该指标保留局部字符组合，但不保证完整行顺序一致。

参考核心实现：

```python
from collections import Counter


def result_similarity(a: str, b: str, n: int = 5) -> float:
    # 生产实现应在每条调用预处理时归一化并缓存，避免每对重复计算。
    a = a.replace("\r\n", "\n")
    b = b.replace("\r\n", "\n")
    if a == b:
        return 1.0
    if len(a) < n or len(b) < n:
        return 0.0

    ca = Counter(a[i:i + n] for i in range(len(a) - n + 1))
    cb = Counter(b[i:i + n] for i in range(len(b) - n + 1))
    intersection = sum((ca & cb).values())
    union = sum((ca | cb).values())
    return intersection / union
```

边界定义：两个已存在的空正文返回 1；只有一个为空返回 0；文本短于 n 且不完全相同返回 0。缺少结果由 `result_present` 在外层排除，不能交给这个函数当作空字符串相等。

### 6.3 精确模式与阈值解释

建议额外支持 `result_match_mode="exact"`：仅比较归一化正文是否完全相等，不进行 n-gram 运算。

重要：`ngram` 模式的分数为 1，只表示 n-gram 计数一致，不严格保证全文逐字相等。因此 `threshold=1` 不能替代 exact 模式。

0.95 是字符片段计数交并比，不是“95% 的重复概率”，也不等于“95% 字符完全一致”。长文本中的少量重要数值变化仍可能获得高分；这属于文本近重复口径，当前不做语义纠正。

## 7. 单调用与多工具模式的统一检测

### 7.1 模式、出现次数与最少长度

模式长度 p 从 1 开始，最少出现次数 r 默认 3，所需调用数为 p×r。

| 序列 | 最短模式 | 出现次数 | 结果条件满足时 |
|---|---|---:|---|
| AA | A | 2 | False |
| AAA | A | 3 | True |
| AAAA | A | 4 | True |
| ABAB | AB | 2 | False |
| ABABAB | AB | 3 | True |
| ABCABCABC | ABC | 3 | True |

出现次数包含第一次。候选起点可以逐一移动；对已选模式计数时，每轮必须首尾相接且不重叠。不能把 AAAA 中三个重叠的 AA 窗口称作“AA 连续出现三轮”。

### 7.2 多轮最低相似度

对于 AB 模式出现三轮，只比较相同位置：A1/A2/A3 彼此比较，B1/B2/B3 彼此比较，不比较 A 与 B。

```text
S_window = min(
  S(A1,A2), S(A1,A3), S(A2,A3),
  S(B1,B2), S(B1,B3), S(B2,B3)
)
```

所有对应位置的动作键也必须相同。只有 S_window 达到阈值，窗口才命中。

不只比较相邻轮，也不只与第一轮比较：相似度不具传递性，可能出现 A1≈A2、A2≈A3，但 A1 与 A3 已明显不同。新增一轮时要与同位置的全部历史轮次比较，从而保证整组两两达标。

### 7.3 搜索顺序与候选继续扫描

推荐确定性的报告顺序：原始 segment 顺序 → 起点从早到晚 → 模式长度从短到长。这样 AAAA 优先报告 A×4，而不是 AA×2。

每个候选只有在结果条件也通过后才算命中。未通过时继续下一个候选。最终布尔结果只需一个合格命中；不要求第一版罗列全部重叠命中。

### 7.4 算法参考伪代码

```python
def find_repeated_interaction(calls, min_repeats, threshold):
    for segment in contiguous_segments(calls):
        n = len(segment)
        if n < min_repeats:
            continue

        for start in range(n - min_repeats + 1):
            max_period = (n - start) // min_repeats

            for period in range(1, max_period + 1):
                # 每组保存模式某一位置在所有已接纳轮次中的调用。
                groups = [[segment[start + offset]]
                          for offset in range(period)]
                if any(not comparable(group[0]) for group in groups):
                    continue

                repeat_count = 1
                window_min = 1.0

                while start + (repeat_count + 1) * period <= n:
                    next_round = segment[
                        start + repeat_count * period:
                        start + (repeat_count + 1) * period
                    ]
                    accepted = True
                    round_min = 1.0

                    for offset, candidate in enumerate(next_round):
                        if not comparable(candidate):
                            accepted = False
                            break
                        for previous in groups[offset]:
                            if action_key(previous) != action_key(candidate):
                                accepted = False
                                break
                            sim = cached_result_similarity(previous, candidate)
                            if sim < threshold:
                                accepted = False
                                break
                            round_min = min(round_min, sim)
                        if not accepted:
                            break

                    if not accepted:
                        break

                    # 整轮成功后再提交，避免失败半轮污染后面的统计。
                    for offset, candidate in enumerate(next_round):
                        groups[offset].append(candidate)
                    repeat_count += 1
                    window_min = min(window_min, round_min)

                if repeat_count >= min_repeats:
                    return make_hit(
                        segment, start, period, repeat_count, window_min
                    )
                # 当前候选失败不代表整条轨迹失败；继续 period/start。

    return None
```

`comparable` 要求工具名、args 字段及合法字符串结果可比较，且 `result_present=True`；空字符串是合法结果。失败调用不得删除后跨越拼接。需要确保任何未达到 r 轮的候选，都不会通过外层提前 return False。

### 7.5 首个候选失败的具体回归

```text
索引：0       1       2       3       4
交互：A(R1) → A(R2) → A(R2) → A(R2) → A(R2)
```

若 R1 与 R2 不相似，起点 0 的周期 1 候选不能达到三轮，但起点 1 可以达到四轮。预期：True；pattern_length=1；repeat_count=4；call_indices=[1,2,3,4]。

## 8. 配置与代码组织

### 8.1 配置复用

当前 `EvaluatorRuleArgs` 允许 extra 字段，`Model.set_config_rule()` 使用 `model_dump()` 合并非 None 配置。建议先复用该能力，不给全部 Rule 增加专用字段。

| 配置项 | 类型 | 默认值 | 合法范围 |
|---|---|---|---|
| `threshold` | float | 0.95 | 有限数且 0 < 值 <= 1 |
| `min_repeats` | integer | 3 | >= 2；不能把 bool 当作整数接受 |
| `result_ngram_size` | integer | 5 | >= 1；不能接受 bool |
| `result_match_mode` | string | `ngram` | `ngram` 或 `exact` |

对结果本身的 True/False，不增加 warning、verdict 分级或连续质量分。上表各参数应在该 Rule 内验证并初始化为独立的 `EvaluatorRuleArgs` 默认值，避免修改其他 Rule 共享的默认对象。

非法配置应在评测启动校验阶段尽早报错，不能默默回退默认阈值或输出一个质量 False。若当前框架只能在 Rule 首次运行时校验，应明确抛出配置异常并使任务失败，不伪装成轨迹重复问题。

### 8.2 完整配置示例

```json
{
  "input_path": "C:/path/to/trajectory.jsonl",
  "dataset": {"source": "local", "format": "ms_swift"},
  "executor": {
    "max_workers": 1,
    "batch_size": 1,
    "result_save": {
      "bad": true,
      "good": true,
      "all_labels": true,
      "raw": true
    }
  },
  "evaluator": [
    {
      "fields": {"content": "RuleAgentTraceLoopDetection_content"},
      "evals": [
        {
          "name": "RuleAgentTraceLoopDetection",
          "config": {
            "threshold": 0.95,
            "min_repeats": 3,
            "result_ngram_size": 5,
            "result_match_mode": "ngram"
          }
        }
      ]
    }
  ]
}
```

这些 Loop 专用配置是待实现的行为，不应把示例误认为当前代码已经使用了这些参数。当前注册名称、group、`eval_layer` 和 `input_data_type` 保持兼容。

### 8.3 函数级改动清单

| 文件/函数 | 修改内容 |
|---|---|
| `ms_swift.py::prepare_rule_agent_trace_loop_detection` | 两遍扫描、结果关联、分割、索引与 segment；独立处理本指标 |
| `ms_swift.py` 或新工具模块 | 增加 headers/body 的纯分割函数 |
| `rule_agent.py::RuleAgentTraceLoopDetection` | 修改描述、默认配置、输入提取、相似度、统一周期搜索和原因文本 |
| `_detect_repeated_identical_calls` | 删除或变为内部兼容包装；不能保留另一套独立判定条件 |
| `dingo/model/rule/utils/agent_trace_similarity.py`（建议新增） | 纯 Python 的参数规范化、Counter 特征与结果比较；避免导入可选重依赖 |

不修改其他规则的输入投影，也不让公共相似度函数依赖具体工具名称。仓库中其他正在迭代的 Agent 规则须保留原有变更。

## 9. 二分类输出与原因模板

### 9.1 正常检测结果

| 情况 | status | label | 说明 |
|---|---|---|---|
| 至少存在一个合格重复窗口 | True | 原有 `AGENT_TRACE_QUALITY.RuleAgentTraceLoopDetection` | 表示近重复命中，不表明无意义 |
| 有可比较调用但未命中 | False | `QUALITY_GOOD` | 仅表示本规则未命中 |
| 0、1、2 次调用且 r=3 | False | `QUALITY_GOOD` | 原因说明数量不足，取消原少于 6 的 N/A 分支 |
| 有调用但缺少部分结果 | 由完整窗口决定 | 命中/未命中对应标签 | 缺失调用中断窗口，其他完整窗口仍可命中 |
| 所有结果均缺失 | False | `QUALITY_GOOD` | 原因说明缺少结果证据；不声称已完成充分比较 |

正常分支保持 `applicable=True`，不填 warning，不新增 N/A 判定，不设置 `EvalDetail.score`。`verdict` 可沿用默认 None，由现有 status 表达二分类，不修改全局模型。

### 9.2 输入错误与二分类的边界

保留现有空派生 content 的 `_empty_derived_input_result()` 行为：它返回 status=True 和 `<类名>.ContentNull`，表示输入提取失败，不是重复命中。preparer 捕获结构异常后仍只置空本指标辅助字段，不阻断其他指标。

直接 SDK 输入的非 JSON 文本、null 或无法识别的容器可沿用当前容错方向返回 False，并在 reason 说明没有可比较输入；不能添加“已检查全部调用且无重复”的虚假原因。空字符串 content 的既有 ContentNull 分支与“合法 tool 返回空正文”是两回事。

下游若统计重复命中率，应使用完整重复标签区分 ContentNull 等输入错误，不能仅用任何 status=True 都称作 loop。

### 9.3 原因文本

使用固定模板与变量填充，不调用模型。建议保留英文模板以延续现有接口，中文展示可另行本地化；不得在文案中断言“卡死”“无意义”或“没有任务进展”。

命中示例：

```text
Repeated tool interaction detected: pattern ['search', 'read'] occurs
3 consecutive times at calls 10-15; minimum result similarity 0.9720
meets threshold 0.9500.
```

reason[1] 可沿用现有规则常见的 JSON 字符串细节形态：

```json
{
  "pattern_length": 2,
  "repeat_count": 3,
  "start_call_index": 9,
  "end_call_index": 14,
  "call_indices": [9, 10, 11, 12, 13, 14],
  "min_result_similarity": 0.972,
  "threshold": 0.95,
  "result_match_mode": "ngram",
  "result_ngram_size": 5,
  "checked_calls": 20,
  "comparable_calls": 20,
  "missing_result_calls": 0
}
```

上述数值仅为输出格式示例。正文模板给人展示的编号从 1 开始，结构化索引从 0 开始，end 为包含端点。

False 原因应区分：未发现动作模式、存在动作模式但结果相似度不足、调用数不足、缺少返回证据。若同一记录存在多种情况，至少写明总调用数、可比较调用数及缺失结果数。

## 10. 性能与确定性

1. 每条调用只规范化一次参数和结果，按需创建并缓存 Counter。
2. 先比较动作键，只有相同动作位置才执行正文相似度计算。
3. 相似度按调用索引的无序对缓存，避免不同候选重复计算。
4. 不对整条轨迹的所有调用预先两两求相似度；默认只计算周期候选所需的对。
5. Counter 构造与正文长度线性相关；每对 Counter 比较与不同片段数相关。整个候选搜索和多轮两两复核不是线性算法，长同构轨迹可能开销较大。
6. 每条记录评测结束释放其缓存；两两分数可使用有上限的 LRU 缓存，缓存淘汰只导致重算，不得改变判定结果。
7. 不用只取开头、结尾或前 N 字符代替全文，否则会把正文尾部差异漏掉。若上游已经截断，只能比较已记录内容；本版不判断未记录部分。
8. 第一版不隐式限制模式长度。将来若增加上限，必须成为显式配置并在文档中说明检测范围。
9. exact 模式可采用规范化原文相等快速判断；ngram 模式相等正文也可直接返回 1。
10. 稳定搜索顺序、稳定参数序列化和固定阈值保证同输入同配置得到同结果。

## 11. 输出层与兼容性

### 11.1 派生字段清理

当前 LocalExecutor 对 ms_swift 使用 `without_derived_fields()` 清理转换器辅助字段。继续维持此机制：新 headers/body 在评测期间可读，但默认不会作为结构化执行记录单独落盘。

原始 `messages[].content` 仍包含完整执行器头部和正文，未来规则可以重新提取。若需要把拆分后的结构长期导出，应作为独立的可选输出功能设计，不在本次偷偷关闭所有派生字段清理。

### 11.2 JSON 字符串写出问题

当前 `ResultInfo._normalize_value()` 会尝试把看起来像 JSON 的字符串解析成对象，可能改变 ms_swift `messages[].content` 的类型。converter 的保真要求不能只检查写出前 Data。

本方案要求补充 ms_swift 输出往返测试。若该测试失败，建议增加内部序列化选项，例如 `preserve_string_values=False`，默认保持其他格式行为，仅由 LocalExecutor 的 ms_swift 输出路径传 True；递归规范化仍可处理 Decimal/date 等值，但停止对字符串做容器反序列化。

该选项是内部方法参数，不新增用户必填配置。`to_dict`、`to_raw_dict` 的字段筛选、冲突备份和派生字段清理顺序必须保持。Spark 输出路径若存在同类转换，也应在对应序列化处验证，而不能宣称 Local 修复自动覆盖 Spark。

### 11.3 旧输入和旧测试

- 旧 ms_swift 原始记录不需要迁移，重跑新 converter 即可生成新输入。
- 已经只有 `tool_name + args` 的直接 Rule 输入没有结果证据，不能再按旧逻辑判 True；返回 False 并说明缺少结果。
- 直接输入若已有字符串 `result` 但没有 `result_present`，可按字段存在性推断 present；明确 `result_present=False` 优先，防止将缺失结果占位空串误判为结果。
- 直接输入没有 segment 定位时整段视为一个 segment，没有 call ID 时用原数组位置定位。
- 对 primary `tool_calls=[]` 的语义保持兼容，不回退到其他 steps 冒充工具调用。
- 现有仅构造名称/参数就断言 True 的测试需要补真实结果，不能通过放回旧门槛或 name-only fallback 让旧断言继续通过。

### 11.4 汇总口径

当前 summary 的 num_good/num_bad 基于 status，score 是未计坏样本比例。本次只定义“重复命中”二分类，不将这些比例解释为“任务成功率”或“无意义重复比例”。

取消 <6 的 N/A 后，0～2 次调用也是 False，历史批次的标签统计和适用性分布不可直接比较。报告必须记录本次规则语义和配置；输入中不添加 schema_version 不妨碍在评测配置及文档中记录变更。

## 12. 测试矩阵

使用合成轨迹和短文本作为仓库测试夹具；用户提供的长日志文件仅作本地回归，不复制到仓库。

### 12.1 Converter 测试

| 编号 | 场景 | 必须验证 |
|---|---|---|
| C01 | 普通一对调用与返回 | ID 正确关联，工具名/参数不变 |
| C02 | 返回乱序 | 按 ID 配对，调用顺序不变 |
| C03 | 部分返回缺失 | present=False；不使用无关返回代替 |
| C04 | 返回原文为空 | present=True，headers/body 都允许为空 |
| C05 | 已知 LF 返回头 | 精确拆分，包含 Output 行，拼接等于原文 |
| C06 | CRLF 返回头、正文有缩进 | 原始换行和空格保真 |
| C07 | Output 后正文再次有 Output | 只分割头部一次 |
| C08 | 普通文档出现 Output 或 Wall time | 不误识别为完整执行包装 |
| C09 | JSON 字符串返回 | 不变成 dict/list |
| C10 | 未知、不完整头部 | headers=""，result=原文 |
| C11 | 重复调用或返回 ID | 关联异常不被覆盖；只影响本指标提取 |
| C12 | 参数为对象、数组、标量、null | 不强转对象；兼容旧字符串参数 |
| C13 | 新 user 消息、无 user 的轨迹 | segment 稳定；初始 segment=0 |
| C14 | 子轨迹与 server tool | 不混入当前 client 调用序列 |
| C15 | 只选择 Loop/不选择 Loop/重复选择 | 只生成选中字段，每条记录只准备一次 |
| C16 | 源记录包含同名派生字段 | 保持冲突拒绝行为，不覆盖源字段 |
| C17 | 源数据深拷贝前后比较 | preparer 不原地修改 record |

### 12.2 相似度单元测试

| 编号 | 场景 | 预期 |
|---|---|---|
| S01 | 同名、参数对象键顺序不同 | 动作键相同 |
| S02 | 参数值、类型或数组顺序不同 | 动作键不同 |
| S03 | 参数缺失与明确空对象 | 不混为同一动作 |
| S04 | 相同正文（含两个空串） | 相似度 1 |
| S05 | 单边空串或短于 n 且不等 | 相似度 0 |
| S06 | abcdef 与 abcdeg，n=5 | 交集 1、并集 3，相似度 1/3 |
| S07 | 重复片段数量不同 | 计数 Jaccard 低于 1，不能仅比较集合 |
| S08 | 只有 headers 不同 | 不改变正文相似度 |
| S09 | 对称性、范围、阈值等号 | sim(a,b)=sim(b,a)，0<=sim<=1，等于阈值可命中 |
| S10 | 正文 CRLF/LF | 比较副本可相同，保存原文不变 |
| S11 | 缓存启用/淘汰/不启用 | 结果完全相同 |
| S12 | exact 模式 | 必须原文比较副本相等，不以 n-gram 分数 1 替代 |

### 12.3 模式搜索回归

下表 A/B/C 表示同位置工具及参数一致，结果在需要相似时达到阈值。

| 编号 | 场景 | 预期 |
|---|---|---|
| L01 | 0、1、2 次调用，r=3 | False，无 warning 或 N/A |
| L02 | AAA | True，p=1，count=3 |
| L03 | AAAA / AAAAA | True，p=1，完整计数 4/5 |
| L04 | AAAAAA | 优先 p=1、count=6，不报告 AA×3 |
| L05 | ABAB / ABABAB | 前者 False，后者 True |
| L06 | ABCABCABC | True，p=3，count=3 |
| L07 | 相同工具、不同参数的 research fan-out | False |
| L08 | 相同参数、正文差异低于阈值要求 | False；不使用 name-only fallback |
| L09 | A(R1), A(R2), A(R2), A(R2), A(R2) | True，命中索引 1～4 |
| L10 | 最早起点失败，后面 AB 模式成功 | 继续扫描并命中后面的窗口 |
| L11 | 相邻轮相似、首尾不相似 | 不组成一组两两相似的三轮窗口 |
| L12 | A 相似但 B 不相似 | 多工具窗口 False，不用平均分掩盖 B |
| L13 | 缺失结果夹在相同调用中间 | 不删除该调用后拼成 AAA |
| L14 | 真正返回相同空正文三次 | True，接受正常轮询也可能命中 |
| L15 | 新 user 将 AA 与 A 分开 | 不跨 segment 拼成 AAA |
| L16 | 同一消息中三个相同交互 | 按重复现象口径可命中，不添加工具/并发豁免 |
| L17 | period 扩展过程中半轮失败 | 不提交失败半轮，索引和最低相似度正确 |
| L18 | 只有旧 name+args 输入 | False，reason 说明没有结果证据 |
| L19 | 后续结果变化打断已成立的三轮窗口 | 已成立的窗口仍 True，count 截止到变化前 |

### 12.4 配置、执行器与序列化测试

1. 默认配置、显式配置及 extra 参数传递生效，Local 单进程/多进程结果一致。
2. 阈值越界、NaN/Inf、bool 充当次数、非法模式名尽早报配置错误。
3. 同进程连续执行不同配置，第二次未传参数时恢复本 Rule 默认值，不能继承上一次评测的阈值。
4. 不改变其他 Agent 规则的默认对象、字段准备和注册信息。
5. True/False 标签、固定原因文本、0 基索引和人类 1 基编号正确。
6. 空派生 content 保留 ContentNull，不误写成重复命中。
7. raw=True/False、all_labels、merge、field_list、冲突备份和派生字段清理分别回归。
8. JSON 字符串 tool content 写出后仍为字符串，原始 messages 可以再次按 ms_swift 读取。
9. Spark 可用时验证配置传播、结果序列化及二分类一致性；不可用时明确记录未验证范围。

## 13. 现有测试的具体调整位置

- `test/scripts/model/rule/test_rule_agent.py`：修改名称/参数-only 的 True 夹具，为其提供结果；新增 AAA、AAAA、最低相似度、空结果与后续候选回归；更新原 <6 的 applicable=False 断言。
- `test/scripts/dataset/test_ms_swift_converter.py`：Loop 和 DestructiveAction 的输出断言需要拆开，二者不再拥有同样的精简结构；旧 loop 集成夹具应补 tool 消息，不再用缺少返回的六调用夹具断言命中。
- `test/scripts/dataset/test_ms_swift_agent_metrics.py`：增加 Loop 的 ID 配对、缺失结果、重复 ID、只选中本指标及输出清理测试。
- `test/scripts/exec/test_local.py`：验证新配置、二分类输出和完整 ms_swift 通路。
- 新增 `test/scripts/model/rule/utils/test_agent_trace_similarity.py`（若拆工具模块）：覆盖确定性的纯算法测试。
- 如需修复输出字符串保护，在相应 `ResultInfo` 与 Local 输出测试中补往返类型断言。

不应删除其他已有测试来获得通过，也不应重写与本指标无关的用户改动。

## 14. 文档与示例维护

实施时按仓库 AGENTS.md 同步检查：

| 文件 | 计划 |
|---|---|
| `docs/agent_trace/ms_swift.md` | 更新 Loop 字段映射、headers 分割、空结果与缺失结果、单/多调用示例和边界 |
| `docs/config.md` | 更新 ms_swift 格式行为说明及本指标配置项、默认值、合法范围 |
| `docs/metrics.md`、`docs/rules.md` | 将“无限循环/卡死”描述改为重复交互/近重复模式；保持注册标签 |
| `examples/agent/ms-swift.py` | 使用本地读取路径和新规则配置的可运行示例，无需 API key |
| `examples/dataset` 与 `docs/dataset` | 核对是否有适用指南；只有现存相关示例受影响时更新，不修改无关 datasource 文档 |
| `AGENTS.md` | 若工具模块、字段准备描述已不准确则局部更新；不顺带重写其他规则清单 |

编写本文时 `examples/dataset/ms_swift.json` 未存在，不应继续把它作为已经存在的示例链接。可更新实际存在的 `examples/agent/ms-swift.py`，或在实现中明确新增 JSON 示例并验证路径。

## 15. 建议实施顺序与完成标准

### 15.1 实施顺序

1. 固定新输入契约和 headers/body 保真测试。
2. 改造 Loop preparer，验证 ID 关联、缺失结果及字段选择。
3. 实现参数规范化和两种结果比较模式。
4. 统一 p>=1 的周期搜索，补 AAA/AAAA 与首候选失败测试。
5. 接入配置、原因模板和 True/False 输出；检查配置跨记录/跨任务隔离。
6. 执行端到端序列化测试，必要时加入仅针对 ms_swift 的字符串保护。
7. 更新文档与实际存在的示例，再运行本指标相关回归。

### 15.2 建议验证命令（实现完成后执行）

```powershell
python -m pytest test/scripts/model/rule/test_rule_agent.py test/scripts/dataset/test_ms_swift_converter.py test/scripts/dataset/test_ms_swift_agent_metrics.py test/scripts/exec/test_local.py -q
```

如新建相似度工具测试或修改输出序列化，应在同一次验证中补上对应测试路径。按环境条件运行 Spark 测试。本文交付阶段未运行这些实现测试，不能将本方案视为代码已通过验收。

### 15.3 附件本地回归

前期只读试算使用用户提供文件第一条轨迹的 call #87～#92，将已知返回头分离后，六段正文的字符 5-gram 计数 Jaccard 两两分数约为 0.2358～0.6529。建议默认 0.95 时，此窗口不命中是因为正文近重复程度不足，不是因为工具名称或轮询用途得到豁免。

此试算只证明该片段的正文差异，不保证整条轨迹没有其他重复窗口，也不证明阈值适用于全部数据。第二条记录对应相同调用片段，但返回完整性不应据此假定与第一条完全一致。

### 15.4 验收清单

- [ ] 未新增 schema_version、LLM、embedding 或工具名称豁免。
- [ ] headers 与正文拼接可还原原始 content，headers 不参与相似度。
- [ ] 真空结果可重复；缺失结果不能当作空结果。
- [ ] AAA/AAAA 在不足 6 次调用的轨迹中也能命中。
- [ ] 单调用、多工具共用一套规则；出现次数与模式长度定义明确。
- [ ] 所有对应位置、所有已接纳轮次两两达到结果阈值。
- [ ] 首候选失败不会提前结束整条检测。
- [ ] 正常结果只有 status=True/False，无 warning 或正常 N/A 分支。
- [ ] 相似度进入 reason，不写成质量 score，不声称无意义或卡死。
- [ ] 输入错误、旧无结果输入和部分证据缺失有明确原因。
- [ ] 配置隔离、输出字段清理、原始消息字符串类型通过回归。
- [ ] 已说明默认阈值未完成全量校准，历史 summary 与新口径的差异可追溯。

## 16. 参考依据

- 当前仓库：`dingo/data/converter/ms_swift.py`、`dingo/model/rule/rule_agent.py`、`dingo/config/input_args.py`、`dingo/model/model.py`、`dingo/io/output/eval_detail.py`、`dingo/io/output/result_info.py`、`dingo/exec/local.py`。
- 用户标准说明：`C:/Users/renzhifei/Downloads/轨迹数据的标准化格式.md`。tool content 为字符串，client/server 与主/子轨迹边界依照该说明。
- [Stanford Introduction to Information Retrieval：Near-duplicates and shingling](https://nlp.stanford.edu/IR-book/html/htmledition/near-duplicates-and-shingling-1.html)：连续片段与 Jaccard 的近重复检测思路；本文的字符计数版和阈值为本项目的设计建议。
- [Python difflib 文档](https://docs.python.org/3/library/difflib.html)：对照 SequenceMatcher 的启发式与复杂度；本方案不依赖该算法。

