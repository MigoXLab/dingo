# Search Result Quality 三指标评测说明

本文档说明检索结果的三类评测指标：相关性、内容有效性、权威性，以及对应的单项评测脚本和端到端综合评测脚本。该方案面向无人工 GT 的检索结果质量检查，既可读取预计算的 query+results，也可从 query 文件直接请求 SciVerse Agentic Search、Meta Search 或 OpenAlex，再通过 Dingo Executor 完成评测和分类。

## Agentic Search 主观评测

HTML 实体使用独立标签 `Effectiveness.Error_HTML_Entity`（HTML 实体残留），
例如 `&amp;`、`&#38;`、`&#x26;`、双重转义的 `h&amp;auml;nchen`。
初筛候选为 `RuleHtmlEntity`，开启 LLM 时仍需二次确认和精确证据校验；
未开启 LLM 时使用 `Effectiveness.Error_Rule_HTML_Entity` 候选标签。
`HTML_Tag` 保留给损坏/多余的标签结构，`Special_Char_Noise` 保留给真正的字符噪声，
并非将所有特殊字符标签统一改名。实体教学代码、正常解码字符及完整图片链接地址不自动扣分。
历史报告不自动迁移标签；重新评测后生成对应的分项 JSONL。

综合脚本支持 `--retrieval-backend agentic`。相关性使用 `query + title + chunk`
进行逐条 LLM 判断；有效性采用四个等权子项：`chunk_quality`、`title_quality`、
`abstract_quality`、`source_quality`，各占 0.25。

`source_quality` 使用 Agentic Search 返回的 `doc_id + offset` 调用 `/content`，
读取 200 个字符，并严格比较原始 offset 处的前 50 个 chunk 字符（可通过
`--source-prefix-length` 配置）。只归一化换行符，不去除 HTML、空格、标点，
不搜索邻近窗口、不校准 offset。完全一致记 1.0；任何
低于 1.0 的一致性都会标记
`Effectiveness.Error_Chunk_Source_Inconsistent`。临时接口错误单独标记，不作为
内容低质量分数。

Authority 会按 `doc_id` 批量调用 `/meta-search`，补充被引百分位、FWCI、被引数、
高影响力被引数、期刊、出版社与 DOI。引用影响力优先使用学科/年份归一化百分位，
其次使用 FWCI，最后回退到原始被引数。相同文献的多个 chunk 只参与一次 query 级
Authority 聚合。

同一批元数据请求也获取 `title` 和 `abstract`，仅补全原结果为空或全为空白的字段，
不覆盖已有标题、摘要。补全前值保存在 `_metadata_original_fields`，来源记录在
`_metadata_recovered_fields`。后续评测使用补全后的文本；成功补回的字段不再判定为缺失，
但仍接受文本质量检查。未命中、请求失败或元数据仍为空时不自动豁免缺失。
Agentic 评测根据补全来源生成 `Effectiveness.Error_Title_Recovered`（标题缺失，已补全）
和 `Effectiveness.Error_Abstract_Recovered`（摘要缺失，已补全）两个问题标签。
同一字段与 `Title_Miss` / `Abstract_Miss` 互斥：补全后仍为空只标记缺失。
这两个标签无需 LLM 判断，不额外扣分；补全文本仍按正常质量规则计分。
标签会进入 Executor 的问题分类（即使有效性分数为 1）、问题统计和对应 JSONL，
用于追踪原始响应完整性，不能将这类问题数量直接解释为补全后文本不合格数量。
此逻辑用于 Agentic 的元数据补全流程；直接 Meta Search 的原始响应已默认包含标题和摘要，
不能据此认定所有缺失都能恢复。历史结果需要重新评测才会更新。

```bash
python examples/retrieval/sdk_eval_search_result.py \
  --input-queries dingo/retrieval/tasks/cjk_evalset_v1.json \
  --retrieval-backend agentic \
  --search-api-url https://api.sciverse.space \
  --top-k 100 \
  --max-queries 100 \
  --save-detailed
```

鉴权使用 `SCIVERSE_API_TOKEN`；LLM 使用 `OPENAI_API_KEY`、`OPENAI_BASE_URL`、
`OPENAI_MODEL` 配置，不绑定某个供应商或模型。请求 top100 不保证接口实际返回100条，
以报告 `result_count` 为准。三个评估器均通过注册系统在 `LocalExecutor` 内执行。

### 缓存结果重评

输入支持每行 `{query, results: [...]}` 或 `{query, response: {hits: [...]}}`。
以下命令只复用检索结果，仍会请求原文、元数据和 LLM；如果已保存 enrichment 字段，
省略 `--enrich-precomputed` 即可复用这些证据。

```bash
python examples/retrieval/sdk_eval_search_result.py \
  --input-jsonl responses.jsonl --retrieval-backend precomputed \
  --eval-profile agentic --enrich-precomputed \
  --search-api-url https://api.sciverse.space --top-k 100 --save-detailed
```

原文核验保存 `_source_text`、`_source_http_status`，并保留原始 `doc_id`、`offset`。
200 空文本标记窗口为空；404 标记原文不存在；网络或解析失败标记核验失败。
source_quality 为存在性 0.3 加一致性 0.7；空窗口或404为0。
原文未核验、核验失败或必要的 LLM 复核失败时，Agentic 有效性总分为 null，
不改成三项平均，也不按0分处罚。汇总跳过空分但保留原始排序权重，
通过 `effectiveness_unscored_count` 披露数量，并将相关 query 标记为评测未完成。
`issues/*.jsonl` 按问题标签输出原始记录及评测依据；`issue_counts.json` 记录各标签条数，
同一记录可命中多个标签，不能直接相加作为异常记录总数。复核前端不属于仓库功能。

### 内置中文检索基准（与主观评测独立）

```bash
dingo eval-retrieval --backend agentic --tasks cjk_evalset_v1 \
  --api-url https://api.sciverse.space --api-token "$SCIVERSE_API_TOKEN" --limit 100
```

API token 通过 CLI 支持的配置传入，勿写入数据文件或提交记录。
`cjk_evalset_v1` 内置100条中文 query、分组及源文档 doc_id qrels，复用
`RetrievalExecutor` 的检索指标计算，不调用 LLM。数据随 Python 包分发。
这是 Dingo 内置的 MTEB 风格二元标注任务，不是 MTEB 官方注册任务；不需要本地 corpus，
直接对照服务返回的文献标识。它衡量已标注源文档的找回能力，其他未标注文献可能也相关，
不能将未命中标注等同于语义不相关。当前不可与 SciFact/LitSearch 混合在同一次命令中。
原始 chunk 排序位置保留，重复 doc_id 仅第一次计为命中，不人为补足100条。

## 1. 适用场景

该评测用于回答三个业务问题：

| 指标 | 业务问题 | 评测方式 |
|---|---|---|
| 相关性 `relevance` | 检索结果是否回答了用户 query 的真实检索意图 | LLM 逐条判断 query-result 匹配程度 |
| 内容有效性 `effectiveness` | 结果记录本身是否完整、可读、可用于判断论文价值 | 规则检查字段缺失，RuleSpecialCharacter/RuleInvisibleChar 初筛异常候选，LLM 二次确认；不使用字段长度打分 |
| 权威性 `authority` | 结果是否具备学术可信度和来源影响力信号 | 规则检查 citation、influential citation、venue、DOI |

三个指标关注点不同：

- 相关性判断“是不是用户要找的内容”。
- 内容有效性判断“这条结果记录是否有足够信息可读可用”。
- 权威性判断“这条结果是否有论文影响力、来源、DOI 等可信信号”。

例如，用户搜索 `Wallace Chafe`，rank1 返回标题也是 `Wallace Chafe`，相关性可能较好；但如果该结果没有 abstract、keywords、author，则内容有效性会较低。Publication venue 的缺失由权威性指标负责。

## 2. 输入格式

综合脚本支持两种输入模式。

### 2.1 预计算结果

JSONL 每行一个 query 及其检索结果：

```json
{"query": "PBPK Review", "results": [{"title": "...", "abstract": "..."}]}
```

脚本支持的 query 字段名：

- `query`
- `query_text`
- `q`

脚本支持的结果列表字段名：

- `results`
- `top_results`
- `top_api_results`
- `search_results`

常用输入路径示例：

```bash
outputs/meta_search_97_query_results.jsonl
```

### 2.2 端到端检索

设置 `--retrieval-backend meta_search` 或 `openalex` 后，输入只需要包含 query。支持：

- TXT：每行一个 query；
- CSV：读取 `query`、`query_text` 或 `q` 列；
- JSON/JSONL：字符串或包含上述 query 字段的对象。

```json
{"query": "PBPK相关综述"}
```

端到端模式使用后端默认相关度检索，不添加时间排序或业务过滤；`--top-k` 同时控制请求数量和评测数量。

仓库提供了三条 query 的端到端测试输入：`test/data/test_search_queries.jsonl`。

## 3. 输出文件

综合评测脚本 `sdk_eval_search_result.py` 会在 `--output-dir` 下生成一个时间戳子目录，核心结果都放在该子目录中，例如：

```text
outputs/search_result_eval_97q/20260710_162652_1ac3f3be/
```

默认核心文件如下：

| 文件 | 粒度 | 说明 |
|---|---|---|
| `summary.json` | 全局 | 指标均值、中位数、最小值、最大值、bad/good 数量、阈值、LLM 配置等 |
| `query_scores.csv` | query 级 | 每个 query 的 top-k 排名加权平均分、label、eval_status |
| `result_scores.csv` | result 级 | 每个 query 的每条 top-k 结果分数和诊断信息 |
| `all_results.jsonl` | result 级原始明细 | executor 输出的逐条评测结果，保留三个指标的完整 `eval_details` |
| `retrieval_results.jsonl` | query 级检索结果 | 仅端到端模式生成，保存可复跑的 query+results |
| `retrieval_request_log.jsonl` | query 级请求日志 | 仅端到端模式生成，记录状态码、耗时、结果数和错误，不含 token |
| `bad/` | query 级分类 | 只包含三种 query 聚合指标低分记录，每行一个 query 及其完整 results |
| `good/` | query 级分类 | 使用 `--save-good` 时保存通过的 query 记录 |

`detailed_results.json` 默认不生成；需要完整嵌套诊断时加 `--save-detailed`。

单独运行 `sdk_eval_effectiveness.py`、`sdk_eval_relevancy.py`、`sdk_eval_authority.py` 时，会保留 Dingo executor 的单指标 result 级分类目录，例如 `search_result/Effectiveness/Error_*.jsonl`。

分类 label 示例：

```text
QUALITY_BAD.SEARCH_RESULT_RELEVANCE_LOW
QUALITY_BAD.SEARCH_RESULT_EFFECTIVENESS_LOW
QUALITY_BAD.SEARCH_RESULT_AUTHORITY_LOW
QUALITY_GOOD.SEARCH_RESULT_METRICS_PASS
```

单独运行 `sdk_eval_effectiveness.py` 时，`summary.json` 采用类似 `sdk_chunk_eval.py` 的 result 级结构：每个 query 的每条 top-k 检索文献都是一个测试对象，`total`、`num_good`、`num_bad` 和 `score` 都按 result 级计算。`type_ratio.search_result` 中会统计 `Effectiveness.Error_*` 和 `QUALITY_GOOD` 的比例，`metrics_score.search_result` 中会统计 `LLMSearchResultEffectiveness` 的 result 级分数分布。

内容有效性还会额外输出 result 级错误类型文件，例如：

```text
Effectiveness/Error_Title_Miss.jsonl
Effectiveness/Error_Abstract_Miss.jsonl
Effectiveness/Error_Keywords_Miss.jsonl
Effectiveness/Error_Author_Miss.jsonl
Effectiveness/Error_HTML_Tag.jsonl
Effectiveness/Error_Mojibake.jsonl
Effectiveness/Error_Invisible_Char.jsonl
Effectiveness/Error_Unreadable_Text.jsonl
Effectiveness/Error_Special_Char_Noise.jsonl
Effectiveness/Error_LLM_Quality_Parse.jsonl
QUALITY_GOOD.jsonl
```

只有实际出现的错误类型会生成对应文件。

## 4. Query 级汇总逻辑

三个指标都先对 top-k 中每条 result 打分，然后使用排名折扣加权平均汇总到 query 级。第 `rank` 条结果的权重为：

```text
weight(rank) = 1 / log2(rank + 1)
query_score = sum(result_score_i * weight_i) / sum(weight_i)
```

rank1 权重最高，越靠后的结果权重越低。综合脚本的 bad/good 判定只比较这三个 query 级加权平均分和统一阈值；result 级分数仍保留在 `result_scores.csv` 与 `all_results.jsonl` 中用于定位问题，但不生成 result 级 bad/good 分类文件。空结果 query 的三个聚合分均为 `0`。

## 5. 相关性 Relevance

### 5.1 业务逻辑

相关性判断每条检索结果与 query 是否匹配，重点看：

- result 是否直接回答或覆盖 query 意图。
- 标题和摘要是否围绕 query 主题。
- 对短词、人名、论文题名、中文长 query 等非 DOI query，LLM 根据语义进行判断。
- DOI query 使用结构化精确匹配：规范化 query DOI 与结果 `doi`、`unique_id` 或 location DOI，完全一致才算命中。
- DOI 前缀相似、同出版社或主题相似但 DOI 不一致时，result 相关性为 0，不允许 LLM 猜测。

### 5.2 输入字段

| 输入 | 来源 |
|---|---|
| `query` | query 字段 |
| `title` | result 的 `title` 或 `display_name` |
| `abstract` | result 的 `abstract`、`summary` 或 `content` |
| `doi` | DOI query 的精确标识符匹配 |
| `unique_id`、`locations` | result 缺少顶层 DOI 时的标识符补充来源 |

### 5.3 Result 级输出

| 字段 | 说明 |
|---|---|
| `relevance` | result 总相关性分数 |
| `query_relevance` | query 与 result 的语义匹配程度 |
| `result_quality` | result 内容质量辅助判断 |
| `content_issues` | LLM 判断是否存在内容问题 |
| `confidence` | LLM 对评分的置信度 |
| `error` | LLM 输出解析失败等错误 |
| `reasoning` | 简短原因 |

DOI query 不调用 LLM。Result 级完全匹配为 `1.0`，否则为 `0.0`；reason 中记录 expected DOI 和 result DOI。

DOI query 的 result 级相关性仍按精确匹配得到 `1.0` 或 `0.0`，query 级相关性按精确命中的排名折扣：

```text
doi_relevance = max(exact_match_i / log2(rank_i + 1))
```

因此 rank1 精确命中为 `1.0`，rank2 命中为 `0.63093`，没有精确命中为 `0.0`。

### 5.4 LLM 解析异常

单独运行相关性脚本时，如果某个 query 的任意 rank 出现 LLM JSON 解析失败，会增加诊断 label：

```text
QUALITY_BAD.SEARCH_RESULT_RELEVANCE_PARSE_ERROR
```

这类 label 表示运行/解析质量告警，不一定代表业务相关性低。综合端到端脚本仍会记录 `relevance_error_count` 和错误文本，但 bad 目录只使用三个指标低分 label；解析失败导致相关性分数低于阈值时，统一归入 `SEARCH_RESULT_RELEVANCE_LOW`。

使用单项评测结果分析低相关时建议区分：

- `SEARCH_RESULT_RELEVANCE_LOW`：业务低相关。
- `SEARCH_RESULT_RELEVANCE_PARSE_ERROR`：LLM 输出格式或解析异常。

### 5.5 可调参数

| 参数 | 默认值 | 说明 |
|---|---:|---|
| `--top-k` | 10 | 每个 query 评测前 k 条结果 |
| `--threshold` | 0.15 | query 级 hard bad 阈值 |
| `--llm-max-tokens` | 1024 | LLM 输出最大 token 数 |
| `--llm-workers` | 4 | 并发 LLM 调用数 |
| `--llm-timeout` | 60 | 单次 LLM 请求超时秒数 |
| `--prompt-mode` | `detailed` | prompt 模式 |
| `OPENAI_MODEL` | `gpt-5.4-mini` | LLM 模型名，可通过环境变量覆盖 |
| `OPENAI_BASE_URL` | 空 | OpenAI compatible endpoint |
| `OPENAI_TEMPERATURE` | 0.0 | LLM temperature |

### 5.6 LLM 模型选择建议

全量检索评测需要逐条判断 query-result 对，LLM 调用量通常接近 `query 数 × top-k`。建议优先使用低延迟的 Flash 类模型，例如：

```text
OPENAI_MODEL=gpt-5.4-mini
```

- **全量评测和日常回归**：推荐 Flash 类模型，可显著缩短相关性判断时间，并降低长时间批处理中的超时风险。
- **疑难样本复核**：Pro 类模型更适合抽取少量低分、边界或争议样本进行人工辅助复核，不建议直接用于数百至数千条 result 的常规全量评测。
- **新旧版本对比**：两次评测必须固定相同模型、prompt、`max_tokens` 和 temperature；建议设置 `OPENAI_TEMPERATURE=0`，减少 LLM 随机波动。
- **并发设置**：建议从 `--llm-workers 2` 至 `4` 开始，根据模型服务的限流和稳定性逐步调整。并发过高可能增加 5xx、超时或空响应。

模型名称由实际 OpenAI-compatible 服务决定，当前推荐使用 `gpt-5.4-mini` 兼顾判断质量与运行速度，但它不是 Dingo 的强制依赖。

## 6. 内容有效性 Effectiveness

### 6.1 业务逻辑

内容有效性判断的是一条检索结果记录是否“可读、完整、可用于用户判断”，不判断它是否与 query 相关。

当前不按 `metadata_type` 做差异化处理。也就是说，`paper`、`ebook`、未来新增类型都使用相同的 title、abstract、keywords、author 完整性标准。Venue 是否存在及其来源可信度统一交给权威性指标，避免对 ebook 等类型重复惩罚。

### 6.2 字段权重

单条 result 的分数为：

```text
Effectiveness =
  title_score * 0.30
+ abstract_score * 0.50
+ keywords_score * 0.10
+ author_score * 0.10
```

| 子项 | 权重 | 业务含义 |
|---|---:|---|
| `title_score` | 0.30 | 标题是否存在、是否可读 |
| `abstract_score` | 0.50 | 摘要是否存在、是否可读 |
| `keywords_score` | 0.10 | 是否至少存在一个非空关键词 |
| `author_score` | 0.10 | 是否至少存在一个非空作者值；不按作者数量额外加分 |

字段为空时，该字段直接得 0 分。

示例：如果 result 只有非空且无异常的标题，其他字段为空，则 `title_score=1.0`：

```text
1.0 * 0.30 + 0 + 0 + 0 = 0.30
```

### 6.3 字段评分逻辑

每个字段先做基础质量判断：

- 为空：0 分。
- title、abstract、keywords、author 四个字段参与有效性评分并进行缺失检查。venue 不参与有效性加权，也不会因为缺失产生问题；其来源可信度由权威性指标负责。
- title、abstract、keywords、venue、author 五个字段都会进行异常检查。venue 有值时仍检查 HTML 泄漏、乱码、不可见字符和严重特殊字符噪声。HTML 标签和 Unicode 替换字符 `�` 出现即进入 LLM 二次确认；其他异常字符按规则阈值筛选。乱码筛选还包括 UTF-8 被误按 Latin-1 解码产生的 `Ð...`、`Ñ...` 序列及 C1 控制字符。
- HTML 初筛要求 `<` 后直接出现合法标签名；`< Previous page | Next page >` 等翻页或比较文本不视为 HTML，`<span>`、`<i>`、`<sub>`、`<scp>` 等真实标签仍进入 LLM 二次确认。
- 字段非空：基础分为 1 分，不因字符长度、token 数、关键词数量或作者数量增减。
- 字段存在 HTML 泄漏、乱码、不可见字符、不可读文本或严重特殊字符噪声：规则先召回候选，LLM 确认后降低相应字段分数。
- 长文本不会获得额外加分，短文本也不会仅因长度被扣分。

`keywords` 只判断是否至少有一个非空值；空列表计为缺失，关键词数量不影响分数。

`venue` 读取优先级：

```text
publication_venue_name_unified
publication_venue_name
venue
source
```

`author` 兼容 `author`、`authors` 字段以及字符串、对象、对象列表等常见结构。存在至少一个非空作者值时，作者基础分为 1；作者名称长度和作者数量不会影响基础分。乱码、HTML 或特殊字符噪声仍会进入异常检查。

对比不同检索后端时，需要把后端原始作者信息统一映射到 `author` 或 `authors`。未映射作者字段会被视为缺失并使单条 result 的有效性总分降低 `0.10`。

### 6.4 Issues 类型

| issue | 含义 |
|---|---|
| `missing_title` | 标题为空 |
| `missing_abstract` | 摘要为空 |
| `missing_keywords` | 关键词为空 |
| `missing_author` | 作者为空 |
| `title:html_tag` / `abstract:html_tag` / `venue:html_tag` / `author:html_tag` | LLM 判断字段中有 HTML/XML 标签泄漏 |
| `*:mojibake` | LLM 判断字段存在乱码或编码错误 |
| `*:invisible_char` | LLM 判断字段存在不可见/控制字符 |
| `*:unreadable_text` | LLM 判断字段整体不可读 |
| `*:special_char_noise` | LLM 判断字段中特殊字符噪声已经影响阅读 |
| `llm_quality_parse_error` | LLM 字段质量判断调用或解析失败 |

注意：

- `RuleSpecialCharacter` 和 `RuleInvisibleChar` 只用于快速召回疑似异常字段，不直接作为最终扣分依据。
- LaTeX、化学符号、单位、希腊字母、`|` 分隔符等正常学术表达不应被 LLM 判为问题。
- HTML 高亮标签、明显 mojibake、不可见字符、严重乱码会由 LLM 输出字段级 issue，并降低对应字段分数。
- 分析 bad 样本时建议结合原始 title、abstract、keywords、venue、author 和 `llm_quality_reason` 进行人工抽查。

### 6.5 可调参数

| 参数 | 默认值 | 说明 |
|---|---:|---|
| `--top-k` | 10 | 每个 query 评测前 k 条结果 |
| `--threshold` | 0.15 | query 级 hard bad 阈值 |
| `--llm-max-tokens` | 1024 | 内容有效性 LLM 字段质量判断的最大 token 数 |
| `--llm-workers` | 4 | 内容有效性 LLM 二次复核并发数 |
| `--llm-timeout` | 60 | LLM 请求超时秒数 |
| `--disable-llm-quality` | false | 关闭 LLM 字段质量判断；保留字段缺失检查，并由规则候选直接触发异常扣分 |

阈值建议：

- `0.15` 适合作 hard bad，只筛严重不可用结果。
- 如果要发现 metadata 缺失、摘要不足等一般质量问题，可额外关注 `< 0.45` 的 warning 区间。

## 7. 权威性 Authority

### 7.1 业务逻辑

权威性判断检索结果是否具备学术可信度和影响力信号，主要来自：

- 引用数。
- 高影响引用数。
- 期刊/会议/来源类型。
- DOI。

该指标不判断 query 相关性，也不判断内容字段是否完整。它是独立的学术权威信号，不建议单独用于硬判“结果错误”。

### 7.2 字段权重

单条 result 的权威性分数为：

```text
authority =
  0.45 * citation_score
+ 0.20 * influential_citation_score
+ 0.25 * venue_score
+ 0.10 * doi_score
```

| 子项 | 权重 | 业务含义 |
|---|---:|---|
| `citation_score` | 0.45 | 普通引用影响力 |
| `influential_citation_score` | 0.20 | 高影响引用 |
| `venue_score` | 0.25 | 来源/期刊/会议可信度 |
| `doi_score` | 0.10 | 是否具备 DOI 标识 |

### 7.3 Citation 归一化

引用数使用 log 归一化，避免高引用老论文过度碾压。

```text
citation_score = log(1 + citation_count) / log(1 + 500)

influential_citation_score =
  log(1 + influential_citation_count) / log(1 + 50)
```

分数会被限制在 `[0, 1]`。

### 7.4 Venue 评分

`venue` 读取优先级：

```text
publication_venue_name_unified
publication_venue_name
venue
source
```

当前规则：

| 条件 | `venue_score` | reason |
|---|---:|---|
| 已知 repository 或 preprint（优先判断） | 0.45 | `repository_or_preprint` |
| 明确的学术 book series 或 ebook platform（优先判断） | 0.55 | `academic_book_series` |
| 明确命中权威期刊/会议家族 | 0.85 | `prestigious_venue_family` |
| 命中正规学术出版机构或来源组织 | 0.75 | `recognized_scholarly_publisher_or_venue` |
| `publication_venue_type` 是 journal/conference，或存在有效 ISSN | 0.65 | `structured_journal_or_conference` |
| 只有非空来源名称 | 0.40 | `named_venue` |
| 未知或低信号来源 | 0.25 | `unknown_or_low_signal_venue` |

权威期刊家族使用带边界的规则匹配，包括：

```text
Nature 及 Nature 学科子刊、Nature Communications、npj 系列、
Communications 系列、Scientific Reports/Data、Science 官方期刊家族、
部分 Cell Press 旗舰刊、NEJM、Lancet、JAMA、The BMJ、PNAS、
JACS、PRL 以及主要 AI 会议
```

匹配前会移除 HTML 高亮标签，并按 `|` 拆分中英文来源别名。规则不再使用无限制的普通子串：`Science Translational Medicine` 会命中 Science 家族，而 `Chemical Engineering Science` 不会。

正规出版机构包括 Springer Nature、Elsevier、Wiley、Oxford University Press、Cambridge University Press、IEEE、ACM、ACS、RSC、IOP、BMJ、PLOS、Royal Society、De Gruyter、CRC Press、World Scientific 等。出版商只能提供正规学术来源信号，因此分数低于明确命中的旗舰期刊。

ISSN 和 journal/conference 类型是防止白名单漏判的主要兜底：专业期刊即使不在硬编码刊名列表中，只要具有结构化来源信息，也能获得 0.65，而不是被直接判成低信号来源。

### 7.5 DOI 评分

```text
doi_score = 1.0
```

条件：

- result 有 `doi` 字段；或
- `locations` 中包含 `doi.org`。

否则：

```text
doi_score = 0.0
```

### 7.6 使用注意

权威性对以下 query 类型可能偏保守：

- 人名，例如 `Michael Pecht`、`张文宏`。
- 泛词，例如 `Jerry`、`pam`。
- 书籍、访谈、百科式结果。
- 缺少 citation、DOI、venue 元数据但实际有用的结果。

因此，权威性低不一定表示检索结果不相关，只表示该结果缺少学术权威信号。

## 8. 统一阈值与分类

综合脚本不计算 overall，也不为三个指标设置权重。默认统一阈值为 `0.15`：

```text
relevance < 0.15      → SEARCH_RESULT_RELEVANCE_LOW
effectiveness < 0.15  → SEARCH_RESULT_EFFECTIVENESS_LOW
authority < 0.15      → SEARCH_RESULT_AUTHORITY_LOW
```

三个 query 级聚合指标均不低于阈值时才判为 good。同一 query 可以同时命中多个低分标签。空结果的三个指标均记为 `0`，因此会同时进入三类低分文件，不再产生额外的 `EMPTY` bad 类型。LLM 解析错误保留在诊断字段中，但不会形成第四种 bad 分类。

## 9. 使用命令

以下命令均在项目根目录执行。

综合脚本启动时会自动读取项目根目录 `.env`，且不会覆盖已经存在的系统环境变量。可复制 `.env.example` 的字段结构创建本地 `.env`；`.env` 已被 `.gitignore` 忽略，禁止提交真实 token 或 key。

### 内置测试数据

仓库提供了 `test/data/test_search_result.jsonl`，用于在提交代码前快速验证单指标和综合评测流程。该文件包含3条 query、9条 result：

| Query | 场景 |
|---|---|
| `BiMLP` | 正常学术论文结果 |
| `海带` | 元数据中包含检索高亮 HTML |
| `pam` | 字段稀疏的 ebook 结果 |

综合 smoke test：

```powershell
python examples/retrieval/sdk_eval_search_result.py `
  --input-jsonl test/data/test_search_result.jsonl `
  --output-dir outputs/search_result_quality_smoke `
  --top-k 3 `
  --llm-max-tokens 1024 `
  --effectiveness-llm-max-tokens 1024 `
  --threshold 0.15 `
  --save-good
```

相关性、有效性和综合 smoke test 需要预先设置 OpenAI-compatible 环境变量；权威性是纯规则评测，不需要 LLM API。

综合脚本只生成 query 级分类目录：

```text
<run_dir>/
├── bad/
│   └── QUALITY_BAD/
│       ├── SEARCH_RESULT_RELEVANCE_LOW.jsonl
│       ├── SEARCH_RESULT_EFFECTIVENESS_LOW.jsonl
│       └── SEARCH_RESULT_AUTHORITY_LOW.jsonl
└── good/                         # 仅使用 --save-good 时生成
    └── QUALITY_GOOD/
        └── SEARCH_RESULT_METRICS_PASS.jsonl
```

- 每行是一个唯一 query，包含三个排名加权平均分、分类 label 和完整 `results`。
- 每个 result 的 `_evaluation` 字段记录 rank 和三个单条分数。
- 同一 query 的多个聚合指标低于阈值时，会分别写入对应的低分文件。
- result 级细分问题仍保留在 `all_results.jsonl` 的 `eval_details` 中。

### 9.1 单独跑相关性

```bash
export OPENAI_API_KEY="<your_api_key>"
export OPENAI_BASE_URL="<your_openai_compatible_base_url>"
export OPENAI_MODEL="gpt-5.4-mini"
export OPENAI_TEMPERATURE="0"

python examples/retrieval/sdk_eval_relevancy.py \
  --input-jsonl outputs/meta_search_97_query_results.jsonl \
  --output-dir outputs/search_result_relevancy_97q \
  --top-k 10 \
  --threshold 0.15 \
  --llm-max-tokens 1024 \
  --llm-workers 3 \
  --llm-timeout 60 \
  --save-good
```

Windows PowerShell 示例：

```powershell
$env:OPENAI_API_KEY="<your_api_key>"
$env:OPENAI_BASE_URL="<your_openai_compatible_base_url>"
$env:OPENAI_MODEL="gpt-5.4-mini"
$env:OPENAI_TEMPERATURE="0"

python examples/retrieval/sdk_eval_relevancy.py `
  --input-jsonl outputs/meta_search_97_query_results.jsonl `
  --output-dir outputs/search_result_relevancy_97q `
  --top-k 10 `
  --threshold 0.15 `
  --llm-max-tokens 1024 `
  --llm-workers 3 `
  --llm-timeout 60 `
  --save-good
```

### 9.2 单独跑内容有效性

```bash
export OPENAI_API_KEY="<your_api_key>"
export OPENAI_BASE_URL="<your_openai_compatible_base_url>"
export OPENAI_MODEL="gpt-5.4-mini"
export OPENAI_TEMPERATURE="0"

python examples/retrieval/sdk_eval_effectiveness.py \
  --input-jsonl outputs/meta_search_97_query_results.jsonl \
  --output-dir outputs/search_result_effectiveness_97q \
  --top-k 10 \
  --threshold 0.15 \
  --llm-max-tokens 1024 \
  --llm-workers 8 \
  --llm-timeout 60 \
  --save-good
```

### 9.3 单独跑权威性

```bash
python examples/retrieval/sdk_eval_authority.py \
  --input-jsonl outputs/meta_search_97_query_results.jsonl \
  --output-dir outputs/search_result_authority_97q \
  --top-k 10 \
  --threshold 0.15 \
  --save-good
```

### 9.4 评测预计算结果

```bash
export OPENAI_API_KEY="<your_api_key>"
export OPENAI_BASE_URL="<your_openai_compatible_base_url>"
export OPENAI_MODEL="gpt-5.4-mini"
export OPENAI_TEMPERATURE="0"

python examples/retrieval/sdk_eval_search_result.py \
  --input-jsonl outputs/meta_search_97_query_results.jsonl \
  --output-dir outputs/search_result_quality_97q \
  --top-k 10 \
  --threshold 0.15 \
  --llm-max-tokens 1024 \
  --effectiveness-llm-max-tokens 512 \
  --llm-timeout 60 \
  --save-good
```

### 9.5 端到端评测 SciVerse Meta Search

```powershell
$env:SCIVERSE_API_TOKEN="<your_sciverse_token>"
$env:SEARCH_API_URL="https://api.sciverse.space/meta-search"
$env:OPENAI_API_KEY="<your_llm_key>"
$env:OPENAI_BASE_URL="<your_openai_compatible_base_url>"
$env:OPENAI_MODEL="gpt-5.4-mini"
$env:OPENAI_TEMPERATURE="0"

python examples/retrieval/sdk_eval_search_result.py `
  --input-queries outputs/query.txt `
  --retrieval-backend meta_search `
  --output-dir outputs/meta_search_end_to_end_97q `
  --top-k 10 `
  --threshold 0.15 `
  --search-workers 4 `
  --llm-workers 4 `
  --batch-size 10
```

### 9.6 端到端评测 OpenAlex

OpenAlex 默认使用普通 `search`，不需要 API key；如有 key，可设置 `OPENALEX_API_KEY`。

```powershell
$env:OPENALEX_API_KEY="<optional_openalex_key>"
$env:SEARCH_API_URL="https://api.openalex.org/works"

python examples/retrieval/sdk_eval_search_result.py `
  --input-queries outputs/query.txt `
  --retrieval-backend openalex `
  --output-dir outputs/openalex_end_to_end_97q `
  --top-k 10 `
  --threshold 0.15 `
  --search-workers 4 `
  --llm-workers 4 `
  --batch-size 10
```

## 10. 阈值解释

当前默认统一阈值为：

```text
0.15
```

该阈值的含义是 hard bad，即只标记严重问题：

- 相关性几乎不匹配。
- 内容字段严重缺失或不可读。
- 权威信号极弱。

分析建议：

| 分数段 | 建议解释 |
|---|---|
| `< 0.15` | hard bad，优先人工排查 |
| `0.15 - 0.30` | 低分边缘，适合抽样检查 |
| `0.30 - 0.45` | 一般质量问题，尤其适合看 metadata 缺失 |
| `>= 0.45` | 通常可接受，但仍需结合业务 query 类型 |

不同指标的阈值敏感性不同：

- 相关性 `0.15` 适合筛严重错召回；如果要分析一般低相关，可关注 `< 0.30`。
- 内容有效性 `0.15` 很宽松；如果要推动元数据补全，可关注 `< 0.45`。
- 权威性 `0.15` 不宜轻易提高太多，因为很多人名、书籍、访谈、非标准论文结果天然 citation/DOI/venue 信号弱。

## 11. 常见分析方法

### 11.1 查看 query 级低分

```powershell
Import-Csv outputs/search_result_relevancy_97q/query_scores.csv |
  Sort-Object {[double]$_.relevance} |
  Select-Object -First 20 query,relevance,error_count,label
```

### 11.2 查看 result 级有效性 issues

```powershell
Import-Csv outputs/search_result_effectiveness_97q/result_scores.csv |
  Where-Object {$_.issues -ne ""} |
  Select-Object query,rank,title,Effectiveness,issues
```

### 11.3 查看权威性低分原因

```powershell
Import-Csv outputs/search_result_authority_97q/result_scores.csv |
  Sort-Object {[double]$_.authority} |
  Select-Object -First 20 query,rank,title,authority,citation_score,influential_citation_score,venue_score,doi_score,reason
```

### 11.4 区分相关性低分和解析错误

```powershell
Import-Csv outputs/search_result_relevancy_97q/query_scores.csv |
  Where-Object {[double]$_.relevance -lt 0.15} |
  Select-Object query,relevance,error_count,label
```

```powershell
Import-Csv outputs/search_result_relevancy_97q/query_scores.csv |
  Where-Object {[int]$_.error_count -gt 0} |
  Select-Object query,relevance,error_count,label
```

## 12. 相关代码位置

评测器：

- `dingo/model/llm/llm_search_result_relevance.py`
- `dingo/model/llm/llm_search_result_effectiveness.py`
- `dingo/model/llm/llm_search_result_authority.py`

脚本：

- `examples/retrieval/sdk_eval_relevancy.py`
- `examples/retrieval/sdk_eval_effectiveness.py`
- `examples/retrieval/sdk_eval_authority.py`
- `examples/retrieval/sdk_eval_search_result.py`
- `examples/retrieval/search_result_eval_utils.py`

## 13. 已知注意事项

1. 相关性使用 LLM，temperature 大于 0 时，同一批数据重跑可能有轻微分数波动。
2. LLM 相关性结果可能出现 JSON 解析失败，脚本会保留解析错误诊断；该条分数为低分时统一归入 `SEARCH_RESULT_RELEVANCE_LOW`。
3. 内容有效性当前不按 `metadata_type` 放宽 title、abstract、keywords、author 的字段要求；venue 缺失不再降低有效性分数，由权威性指标统一判断。
4. 内容有效性使用 `RuleSpecialCharacter` / `RuleInvisibleChar` / `RuleMojibake` 做快速初筛，再用 LLM 二次确认 HTML 泄漏、乱码、不可见字符和严重特殊字符噪声；正常公式、LaTeX、单位符号不应被扣分。
5. 权威性低不一定表示结果不相关，可能只是 citation、DOI、venue 元数据不足。

### 有效性 LLM 二次确认的误报控制

- 特殊字符初筛支持带分号的已知 HTML 命名实体（如 `&amp;`、`&nbsp;`）及十进制/十六进制数字实体（如 `&#38;`、`&#x26;`）。出现一处即可进入 `RuleSpecialCharacter` 候选，不受字符占比门槛限制；正常 `&`、未知实体名称、图片路径不因此触发。此项仅扩展初筛，未新增实体业务标签或修改 HTML 标签后置校验；启用 LLM 时，命中候选不等于最终扣分，实体教学示例等仍需语境判断。

- 正常的内联 Markdown 图片链接允许保留，包括相对路径、哈希文件名、查询参数和空 alt。规则检测排除图片语法及路径，但继续检查 alt 文本和周围正文；LLM 仅以图片链接或其中路径为证据时，不采纳扣分。此放行不代表图片可访问，不执行图片网络请求，也不改变原文 offset 一致性核验。

- 规则命中只表示异常候选，不代表最终问题。正常 HTML 表格（含 rowspan/colspan、html/body 包装）、作者上标、化学下标、Markdown 和 LaTeX 不应仅因存在标记而扣分；只有确实妨碍阅读的破损或多余标记才属于 HTML 残留。
- 正常排版空格、页码中的负号以及“凤”“解”等汉字不视为特殊字符噪声；乱码和控制字符仍保留检测。
- LLM 只判断字段可读性，不判断主题相关性、技术参数重复或科学正确性。扣分必须同时有低分、有效问题类别及原字段中精确存在的 evidence 片段；缺失或无法匹配的证据不支持扣分。
- 输出中的 `llm_quality_evidence` 保留 LLM 返回的字段证据，便于复核。证据能匹配原文不代表判断必然正确，仍需结合阅读影响审核。
- 以上 LLM 确认约束仅用于启用 LLM 的模式，缺字段和来源核验仍由各自规则处理。修改提示词不会自动重算历史分数或更新已导出的复核标签。
