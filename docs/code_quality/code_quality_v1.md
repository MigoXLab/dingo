# LLMCodeQualityV1：代码数据质检规则集

用于网页抽取代码与合成代码数据。沿用 `LLMTextQualityV6` 的证据优先、上下文判断和主问题输出，新增代码分类、多问题标签、代码损坏分类、规则命中二次复核与LLM 凭据判断。结果是**自动候选**；最终比例需人工确认后按样本去重计算。

## 1. 评估器与检查范围

| 注册名称 | 功能 | 分值 |
|---|---|---|
| `LLMCodeQualityV1` | 一次 LLM 调用检查四个方向，并复核可选的规则候选 | 1 无候选；0 有候选 |
| `LLMCodeClassificationV1` | 单独进行 v5 口径的代码相关性评分与代码存在性判断，便于双模型配置 | 0–5；≥4 为 positive |
| `LLMCodeQualityPipeline` | 完整流程：十一规则与综合质检、双模型分类及 LLM 安全判断，合并后交给 Executor | 两模型评分成功且平均分 ≤2 命中代码含量低；执行错误独立标记 |

| 方向 | 覆盖项 | 误判边界 |
|---|---|---|
| 代码分类 | 主体内容识别、0–5 分、代码存在性 | Bash/Shell/PowerShell 算代码，纯公式不算；API 契约可以没有字面源代码但仍达到 4 分 |
| 基础文本质量 | 空内容、无效短内容、特殊字符、异常字符、超长空白、纯 URL、占位文本、文档内重复 | 短而完整的命令、正常缩进/符号、测试样例及必要的结构性重复不应误判 |
| 代码质量 | 代码截断不完整、语言标签冗余/错标、两类明显语法问题 | 缺少围栏不单独判错；工程上下文不完整不自动判错 |
| 代码安全 | 五类政治内容政策、porn/violent/gamble/drug、PII、服务端点、凭据 | 中立材料、粗俗变量名、公开 IP、示例地址及环境变量引用不自动判泄露 |

### 一级、二级问题标签

问题输出采用四个一级类别；内部代码分类细节不再作为第五个一级类别。

| 一级标签 | 二级标签（内部 ID） |
|---|---|
| 有效性 `Effectiveness` | 空内容 `Empty_Content`、过短内容 `Insufficient_Content`、乱码符号 `Special_Characters`、HTML 标记残留 `HTML_Markup`、异常字符 `Abnormal_Characters`、纯 URL `Only_URL`、占位文本 `Placeholder_Content` |
| 有效性 `Effectiveness` | 代码空白与缩进异常 `Code_Whitespace`、语言标签冗余 `Redundant_Language_Label`、语言标签分类错误 `Fence_Language_Mismatch`、基础语法符号错误 `Syntax_Error`、跨语言混用错误 `Cross_Language_Mixing`、代码含量低 `Low_Code_Content` |
| 完整性 `Completeness` | 代码截断 `Code_Truncation` |
| 重复性 `Similarity` | 文档内重复 `Document_Repetition` |
| 安全性 `Security` | PII 泄露 `PII_Exposure`、密钥泄露 `Secret_Credentials`、色情 `Porn`、赌博 `Gamble`、毒品 `Drug` |

上述必需检查共 20 个内部标签，均包含在综合质检默认 Prompt 中，无需逐项启用；其中语言标签问题拆成冗余/错标两项，黄赌毒拆成三项。逐标签 Executor 回归测试覆盖全部 20 项的解析、统计、原始数据保留及一级/二级目录落盘；该测试使用模拟模型回复，不代表真实模型的召回率。

已移除 `Completeness.Undefined_Symbol_Or_Missing_Dependency` 及对应辅助子类。未定义变量/符号、缺少 import 或依赖不再单独判错，即使样本宣称完整可运行；不得改报为语法错误、代码截断或代码含量低。独立存在的括号、引号等基础语法错误仍检测。Prompt 哈希随此次修改变化，历史结果保留，不能用新口径直接续跑旧批次。

现有内部端点、暴力、政治检查仍保留在安全性下，此次只调整标签归属，尚未删除这些额外检查。

“代码含量低”是代码训练相关性评分标签，不是代码行数或字符占比，也不表示完全没有代码。本次仅重命名原 `Effectiveness.Non_Code`，随后已将问题命中阈值收紧为 ≤2 分；历史结果不自动改写，新结果输出到 `Effectiveness/Low_Code_Content.jsonl`。

`Effectiveness.Low_Code_Content` 由 LLM 的代码相关性评分决定（0–2 分命中，3–5 分不命中），综合质检和独立分类评估器使用同一标签。`contains_code` 仍是独立的字面代码存在性字段：有代码不一定适合代码训练，没有字面源代码的有效 API 契约也可能达到 4 分。双模型共识单独保存，不覆盖综合质检的判断。

`RuleAbnormalChar` 内部包含 `RuleSpecialCharacter`；二者命中同一特殊字符证据时，LLM 可以仅保留一个 `Special_Characters` 问题，避免重复标记。正常操作符、测试字符、缩进和对齐不因规则命中而直接判错。

复用十一个基础规则：`RuleContentNull`、`RuleContentShort`、`RuleSpecialCharacter`、`RuleAbnormalChar`、`RuleSpaceMore`、`RuleOnlyUrl`、`RuleLoremIpsum`、`RuleDocRepeat`、`RulePIIDetection`、`RuleHtmlEntity`、`RuleHtmlTag`。`run_code_rules()` 真正运行这十一项；`rule_candidates()` 只传成功且命中的规则名/标签，执行失败单独记录。

`LLMCodeQualityV1` 是单次综合质检组件：未传入 `rule_candidates` 时，先自动运行十一个规则，再将候选交给 LLM 复核。完整批量入口改用 `LLMCodeQualityPipeline`，固定包含双模型分类及 LLM 安全判断。规则和模型执行失败作为执行错误保存。

## 2. 架构和判定边界

- `base_code_quality.py` 集中管理输出 schema、十一规则初筛、配置隔离、响应解析、证据校验和双模型汇总。
- `prompts.py` 集中定义分类与综合质检 Prompt；两个评估器文件各自只引用对应 Prompt。
- `llm_code_classification_v1.py` 只注册独立 0–5 分代码含量分类组件。
- `llm_code_quality_v1.py` 只注册综合质量与安全质检组件。
- `llm_code_quality_pipeline.py` 组合综合质检、两个分类器，保留阶段结果并合并标签。

只报有明确上下文证据的问题。有效短命令、合法空格和对齐、函数签名简写、教学错误和修复对照、调试提问、主动省略与正常预览不自动判错。缺少 Markdown 围栏本身不算问题。未定义符号、缺少依赖、算法逻辑、类型/API 契约及业务配置语义不纳入语法检查。

代码空白与缩进异常统一使用 `Code_Whitespace`，同一证据不重复计入 `Syntax_Error`；代码截断须有实际断点和非预览证据。完整判定口径以 [Prompt](../../dingo/model/llm/code_quality/prompts.py) 为准，结果记录 Prompt SHA-256。

## 3. 输出与分类

保留 V6 风格 `score/type/name/reason`。通过 `CodeQualityDetail` 扩展 `EvalDetail`：`label` 保存全部两级问题标签，`reason` 与标签逐项对齐；主问题保留在 `details.type/name/reason`，完整结构存入 `details`，标签副本存入 `details.all_labels`，不改动全局输出模型。

| 字段 | 说明 |
|---|---|
| `classification` | 0–5 分、`contains_code`、理由；与正确性分开 |
| `findings` | `type/name/reason/line_start/line_end`；原始正文行号从 1 开始，文档级问题可为 null |
| `code_error.primary` | 下表三类之一、mixed 或 null |
| `code_error.tags` | 全部独立损坏成分；不能用 mixed 代替 |
| `code_error.syntax_subtypes` | 语法语义细分；无此问题时为空 |
| `politics` | 五主题的 neg/pos/none 判断 |
| `rule_reviews` | 每个传入规则候选的二次复核结论与理由 |
| `review_required` | 是否需人工确认 |

| 辅助 code_error 主类 ID | 当前允许范围 |
|---|---|
| `truncated_or_missing_code` | 已展示代码的明确中断；排除正常预览、主动省略及仅承诺但未展示代码；沿用原 ID |
| `code_fence_block_boundary_corruption` | 仅限代码块语言标签冗余或明确错标；沿用原 ID |
| `invalid_code_syntax_or_semantics` | 仅限下述两类明显问题；沿用原 ID |
| `mixed_multiple_corruptions` | 至少两个独立的上述成分共存 |

`code_error` 仅保留辅助技术细节，schema 校验其与二级问题标签一致；不能替代 `findings` 中的具体标签。

明显语法问题仅保留两个子类：

- `syntax_delimiter_parser_error`：明确的括号/引号不闭合、必要冒号/分隔符缺失等基础语法问题。缩进仅在必需代码块明确不合法时纳入，不评价排版风格。不声称实际运行了解析器。
- `cross_language_transpilation_artifact`：同一目标语言作用域内混入不兼容的可执行语法。分块展示多语言、字符串内 SQL、模板或合法嵌入不算错误；单纯围栏错标只记语言标签问题。

围栏成分必须同时给出 `Effectiveness.Redundant_Language_Label` 或 `Effectiveness.Fence_Language_Mismatch`；不再输出 `CodeQuality.Error_Code` 总括标签。没有围栏、围栏未闭合、嵌套和布局本身不纳入当前范围。合法语言别名、通用 text 标签、解释器命令和变量名不算标签错误。

函数签名展示与实际实现分开判断：明确标为 Function Signature/API signature 的签名可省略函数体及实现用冒号，例如 `def f(x: int) -> bool`，即使放在 Python 围栏中也不据此判错；后文完整实现可作为佐证，但不是放行的必要条件。若代码已包含实际函数体而缺少冒号，仍检测为语法错误，不能仅凭标题放行。新增 6 个签名/实现对照样例，包括 C++ 关键字误用的保留检测样例；这些预期用于模型回归，不等同于已验证的模型准确率。

只缺一个右括号通常记基础语法问题，不能直接推断抽取截断；mixed 也不能用同一个症状重复计数。教学错误、调试提问、修复前后对照、明确省略和上下文不足不自动判问题。

不再独立判断算法逻辑、性能、类型/API 契约、运行时内存安全、SQL 语义、构建配置或一般抽取噪声。抽取损坏只有明确导致上述允许问题时才纳入，不能改用基础文本标签绕过范围限制。旧版其他成分、语法子类和旧一级标签不再被当前 schema 接受；历史结果按 `rubric_version` 区分，不与新口径直接合并。总体问题数仍按样本去重。

解析器拒绝非法分数、未知/重复标签、不一致的分类、遗漏规则复核、越界行号及 Good/问题混搭。模型超时、拒答、无效 JSON、调用超时返回 `applicable=False`、`not_applicable_kind=execution_error`、`score=None`，不是质量通过或失败。

## 4. 使用

已设置 `OPENAI_API_KEY`、`OPENAI_BASE_URL` 后，在仓库根目录直接执行已有 JSONL（每行包含 `content`）：

```shell
python examples/code_quality/evaluate_code_executor.py --input samples.jsonl --output outputs/code_qc --workers 4 --max-tokens 16384 --reasoning-effort low
```

`--input` 模式检查输入文件中的全部记录，只保存 Executor 原生结果（一级标签目录、二级标签 JSONL 和统计），不生成抽样文件或人工审核表，也不执行脚本层面的补跑。Session ID 自动生成，无需手动设置 `LOCAL_DEPLOYMENT_MODE`。默认综合质检模型为 `bailian/deepseek-v4.1-flash`，可通过 `OPENAI_MODEL` 更换。

正式批量运行只维护 `evaluate_code_executor.py` 一个入口，见下方命令。任意已有数据集也可通过标准 `dingo eval --input config.json` 调用 `LLMCodeQualityPipeline`；不必使用按两类语料抽样的示例脚本。

默认分类模型为 `glm-5.3-flash` 和 `bailian/deepseek-v4.1-flash`，可以通过 `--classification-models` 更换。两模型均评分成功后，以未四舍五入的平均分判断：平均分 ≤2 时 `low_code_content=true`，否则为 false。任一评分失败时，`average_score` 和 `low_code_content` 均为 null，不根据单个分数生成低代码含量标签，同时记录执行错误。平均分保存在 `details.classification_consensus.average_score`；原始模型评分仍保留。例如 2+5 不命中、1+3 命中、0+5 不命中。此变更更新 Pipeline 的 rubric_version，旧结果不自动重算。

完整流程由两个独立分类器决定最终 `Low_Code_Content`，综合质检内部评分保留供追溯，不作为第三个投票。两模型均 ≥4 的 positive 筛选标准单独保留；单个 3 分不能独立决定是否命中，例如 3+1 命中、3+3 不命中。分歧的复核要求保存在 `details.review_required`。

## 5. 验证范围

```powershell
python -m pytest test/scripts/model/llm/test_code_quality_pipeline.py test/scripts/model/llm/test_code_quality_v1.py test/scripts/model/llm/test_code_executor_runner.py test/scripts/exec/test_local.py -q
```

测试覆盖解析、分类、混合标签、输入不变、配置隔离、规则复核完整性、错误状态及脱敏。模型调用使用模拟响应验证。

[`code_quality_v1_regression.jsonl`](../../test/data/code_quality_v1_regression.jsonl) 提供 63 个合成样例及预设期望：无围栏、短命令、纯公式、合法空格、多 include、标签冗余/错标、混合问题、Markdown 嵌套、教学/调试错误、截断、两类明显语法问题、跨块依赖、合法语言嵌入、范围外逻辑问题、IP、变量名误判等。这些不是模型实测成绩；需用目标模型试跑并人工复核后再计算准召率。仓库不包含历史生产语料或真实凭据。

### 使用 Dingo Executor 按一级/二级问题输出

完整流程注册名为 `LLMCodeQualityPipeline`，设置 `result_save` 为 `{"bad": true, "good": true, "all_labels": true}`。标准 `dingo eval --input config.json` 或 `LocalExecutor(InputArgs(...)).execute()` 均可运行，使用原生按标签输出能力。单独配置 `LLMCodeQualityV1` 仍只运行综合质检组件。配置隔离仅在代码质检公共基类 BaseCodeEvaluation 内实现：Executor 为实例设置配置后，由实例创建独立运行类执行原有类方法，并在结束（包括异常）时关闭客户端。实例从声明时的默认配置开始，不继承其他任务留在注册类上的参数；直接通过 configured_evaluator 调用类方法的方式保持兼容。LocalExecutor 保持 dev 实现，不改变其他业务评估器的执行方式。

```text
content/
├── Effectiveness/
│   ├── Low_Code_Content.jsonl
│   ├── Syntax_Error.jsonl
│   └── ...
├── Completeness/
│   └── Code_Truncation.jsonl
├── Similarity/Document_Repetition.jsonl
├── Security/...
├── REVIEW_EXECUTION_ERROR/...
└── QUALITY_GOOD.jsonl
```

只生成实际命中的目录/文件。同一条多标签数据会写入多个文件，但总体数量按 sample_id 去重。每行保持 Dingo 的 `raw_data`、`eval_status`、`eval_details` 结构，保留输入字段和完整 findings，不再只按主问题归档。

两类本地语料的抽样执行入口：

```powershell
python -m examples.code_quality.evaluate_code_executor --nemotron <Nemotron.jsonl> --zh <中文网页.jsonl> --en <英文网页.jsonl> --output outputs/code_executor_run --count 100 --seed 20260911 --workers 6 --max-tokens 16384 --classification-models glm-5.3-flash bailian/deepseek-v4.1-flash
```

读取 `OPENAI_API_KEY`、`OPENAI_BASE_URL`、`OPENAI_MODEL`。默认 Nemotron 抽 100 条，网页按中文/英文各 50 条抽样；原始字段保留，新增 `_code_qc` 来源与内容哈希。输出包含 manifest、Prompt 快照、抽样文件和两个数据类别目录。每轮 API 调用附带构造的 session ID。

每个类别下 `attempts/` 是标准 Executor 的原始运行目录；`results_*/` 是通过同一 Executor writer 合并去重的最新结果目录，路径记录在 `latest.json`。默认失败最多重试两轮；中断后同命令增加 `--resume` 可读取已落盘的成功记录，仅处理失败或缺失项。恢复时校验模型、API 地址、Prompt、样本文件哈希及结果中的原始输入。只允许忽略中断造成的末尾未完成 JSONL 行，中间损坏或非法标签会报错。已有成功结果不会被后续失败覆盖。所有轮次保留，不覆盖历史结果；重试结束后仍有失败或缺失时，进程以退出码 1 结束，已完成的结果仍会保存。

`results_*/summary.json` 与总 `run_summary.json` 明确分开 good、automatic_candidates、execution_errors、missing；不将执行失败视为质量通过。原生 Executor 的 attempt summary 也保留，其 num_good 会包含 status=False 的执行错误，分析时以最终去重汇总为准。人工复核队列另存 JSONL/CSV，当前只统计自动候选，不计算人工确认的问题率。

对推理模型可显式传 `--reasoning-effort low`（需服务支持）。调整推理强度的恢复轮次会保存独立配置，不更改 Prompt 或截断输入，分析结果时应保留各轮参数差异。DeepSeek 参数说明见 https://api-docs.deepseek.com/guides/thinking_mode/ 。


### 安全检测边界

安全性由综合质检 LLM 判断，无需额外安装本地扫描器。

LLM 按值的实际用途判断，不以字段名、随机字符串、prd 字样或点分数字直接认定泄露。占位密钥/URL、User-Agent 版本、普通账号名单、数据库索引与文档 ID、存储名称以及明确模拟认证的口令均排除。排除按证据生效，不对整篇文章豁免；真实部署语境的弱口令仍需检测。


### 完整流程输出与失败处理

`details` 包含 `quality`、`classification_models`、两个 `classification` 结果、`classification_consensus`、合并后的 `findings` 和 `execution_errors`。成功阶段的发现不会因其他阶段失败丢失；整条结果 `applicable=false`，最终汇总计入执行错误并重试。重试单位为整条样本，包含该样本的全部阶段。总体 Token 用量合并，分模型用量保留在各阶段结果中。

每条样本通常有三次 LLM 请求：一次综合质检和两次独立分类；失败重试可能增加调用。每个 LLM 阶段都携带 session ID。恢复要求完整流程 Prompt、两个分类模型、质量模型及 API 地址一致；历史单模型结果不能用于新流程续跑。

以下为标准 CLI 的 evaluator 配置片段；key/api_url 使用调用环境注入，切勿提交真实凭据：

```json
{"name":"LLMCodeQualityPipeline","config":{"model":"bailian/deepseek-v4.1-flash","classification_models":["glm-5.3-flash","bailian/deepseek-v4.1-flash"],"max_tokens":16384}}
```

Pipeline 默认对 `bailian/deepseek-v4.1-flash` 使用 `extra_body.enable_thinking=false`（显式公共 extra_body 可覆盖），对分类阶段的 `glm-5.3-flash` 单独使用 `extra_body.reasoning_effort=low`，不继承公共关闭 thinking 参数。GLM 不支持关闭 thinking；显式的分类模型覆盖配置优先于此默认值。其他模型不自动套用这些参数。

分类模型需要不同请求参数时，可配置 `classification_request_overrides`，键必须是
`classification_models` 中的模型名，目前仅支持覆盖 `extra_body`。覆盖会整体替换该模型
继承的 `extra_body`，不影响综合质检或另一个分类模型。例如公共配置为
`"extra_body": {"enable_thinking": false}` 时，可单独配置
`"classification_request_overrides": {"glm-5.3-flash": {"extra_body": {"reasoning_effort": "low"}}}`。
这些参数需由所选服务实际支持；此示例不代表所有模型服务均支持相同参数。

### HTML 标记残留与乱码符号

`Effectiveness.Special_Characters` 仅针对乱码替换符或异常符号簇；`[email protected]` 等保护性占位文本不因自身出现而判错，也不换标规避排除。`Abnormal_Characters` 保留编码乱码和有害控制字符；同一证据不重复标记。

新增 `Effectiveness.HTML_Markup`，复用 `RuleHtmlEntity` 和 `RuleHtmlTag` 初筛，再由 LLM 复核。`if(intRecv&gt;0)` 这类未解码实体损坏代码的情况归入此标签，不同时计为特殊字符或语法错误。正常 HTML/XML/Vue/JSX、文档表格、HTML 生成代码、实体转义教学和字符串测试不因标记出现就判错。现有规则有密度阈值，单个实体可能不触发初筛；全量 LLM 仍独立检查关键段落。历史结果不重写，新 Prompt 产生新的 rubric_version。
