# Agentic Search 系统评测方案

> 面向内部大型数据知识库的 Agentic Search 系统评测体系设计
>
> 调研日期：2026-04-12

---

## 目录

1. [背景与目标](#1-背景与目标)
2. [行业现状与参考系统](#2-行业现状与参考系统)
3. [评测维度总览](#3-评测维度总览)
4. [评测数据集](#4-评测数据集)
5. [评测方法论](#5-评测方法论)
6. [评测指标体系](#6-评测指标体系)
7. [LLM-as-Judge 方法论](#7-llm-as-judge-方法论)
8. [当前难点与挑战](#8-当前难点与挑战)
9. [针对内部知识库的评测方案设计](#9-针对内部知识库的评测方案设计)
10. [实施路线图](#10-实施路线图)
11. [参考资料](#11-参考资料)

---

## 1. 背景与目标

### 1.1 项目背景

构建一个面向内部大型数据知识库的 Agentic Search 系统，类似 [Exa.ai](https://exa.ai) 的模式，但检索目标不是互联网公开数据，而是企业内部知识库。系统需要支持：

- **语义检索**：超越关键词匹配，理解查询意图
- **多步推理检索**（Agentic）：对复杂问题进行查询分解、多轮检索、结果综合
- **RAG 增强**：为下游 LLM 提供准确的上下文信息
- **结构化查询**：支持多条件复合查询（类似 Exa Websets）

### 1.2 评测目标

建立一套完整的评测体系，用于：

1. 衡量系统各组件的质量（索引、检索、内容提取、答案生成）
2. 指导系统迭代优化方向
3. 与基线系统进行对比
4. 监控线上系统质量变化

---

## 2. 行业现状与参考系统

### 2.1 Exa.ai 评测体系概览

Exa 是目前在搜索评测方面最体系化的公司之一，其核心理念和方法值得深入借鉴：

#### 核心哲学：Open Evals vs Closed Evals

Exa 提出了 **Open Evals**（开放评测）的概念，区别于传统的 Closed Evals（如 MS MARCO）：

| 维度 | Closed Evals (传统) | Open Evals (Exa 方式) |
|------|---------------------|----------------------|
| 索引 | 固定文档集 | 不限定索引，可用于任何检索系统 |
| 标签 | 人工标注的相关文档 | LLM 判定相关性 |
| 优点 | 可复现、科学严谨 | 适用于大规模、黑盒系统对比 |
| 缺点 | 假阴性、规模受限、分布偏移 | 依赖 LLM 判分质量 |

Exa 认为传统 Closed Evals 存在以下问题：
- **假阴性问题**：人工标注无法覆盖所有相关文档，好的检索结果可能被误判为不相关
- **规模不匹配**：小规模语料上的表现不代表大规模索引的表现
- **分布偏移**：MS MARCO 等数据集的查询分布不一定匹配实际使用场景
- **需要白盒访问**：无法评测黑盒 API

#### Exa 的评测产品线

| 评测产品 | 目标 | 方法 |
|---------|------|------|
| **API Evals** (SimpleQA / MSMARCO) | 基础搜索质量 | LLM 评分 + RAG 准确率 |
| **Websets Evals** | 复杂多条件查询 | o1 生成查询集 + LLM 判定条件匹配 |
| **WebCode Evals** | 编码 Agent 搜索 | 内容质量 + 检索质量 + 端到端编码任务 |
| **Exa Deep Evals** | Agentic 深度搜索 | HLE-Search, FRAMES, Deep Search QA |
| **通用评测框架** | 日常迭代 | Pointwise/Pairwise 评分 + 人工审核 |

### 2.2 其他参考系统

| 系统/框架 | 定位 | 评测方法 |
|-----------|------|---------|
| **RAGAS** | RAG 评测框架 | Faithfulness, Context Relevancy, Answer Relevancy |
| **ARES** | 自动 RAG 评测 | 合成数据 + 微调 LLM Judge + PPI 置信区间 |
| **RAGPerf** | 端到端 RAG 基准 | 模块化拆分：嵌入、索引、检索、重排、生成 |
| **EKRAG** | 企业知识库 RAG | 跨文档类型（产品发布、技术博客、财报）评测 |
| **SCARF** | 黑盒 RAG 评测 | 模块化、端到端评估 |

---

## 3. 评测维度总览

参考 Exa WebCode 论文的框架，搜索系统评测分为两大维度：

```
┌─────────────────────────────────────────┐
│           Agentic Search 评测           │
├───────────────────┬─────────────────────┤
│   内容质量        │     检索质量        │
│   (Contents)      │     (Retrieval)     │
├───────────────────┼─────────────────────┤
│ 1. 提取忠实度     │ 1. 单步 RAG 问答    │
│ 2. 高亮/摘要质量  │ 2. 多步 Agentic 检索│
│ 3. 结构保持       │ 3. 端到端任务完成   │
│ 4. 代码/表格召回  │ 4. 复杂条件检索     │
└───────────────────┴─────────────────────┘
```

再加上面向内部知识库的特殊维度：

- **语料质量**：文档新鲜度、去重率、元数据完整度、分块质量
- **时效性**：对新增/更新文档的索引延迟
- **权限控制**：不同用户只能检索到授权文档
- **延迟与吞吐**：P50/P99 延迟、QPS 承载

---

## 4. 评测数据集

### 4.1 公开基准数据集

以下数据集可直接使用或适配到内部场景：

#### 4.1.1 低延迟事实问答类

| 数据集 | 规模 | 特点 | 推荐搜索模式 |
|--------|------|------|-------------|
| **SimpleQA** (OpenAI) | 4,326 题 | 短事实问答，答案唯一，评分为 correct/incorrect/not_attempted | Fast / Auto |
| **WebWalkerQA** | - | 导航式查询，模拟真实搜索场景 | Fast / Auto |
| **FreshQA** | - | 时效性查询，测试实时信息获取 | 全模式 + livecrawl |

#### 4.1.2 多步推理检索类

| 数据集 | 规模 | 特点 | 推荐搜索模式 |
|--------|------|------|-------------|
| **FRAMES** (Google) | 824 题 | 多跳问题，需 2-15 篇文档；分单步/Agentic 切片 | 单步: Auto, Agentic: Deep |
| **MultiLoKo** | - | 多跳知识查询，需跨源综合 | Deep |
| **BrowseComp** (OpenAI) | 1,266 题 | 极难的信息定位任务，人类 2 小时内只解决 29.2% | Deep |
| **HLE** | - | Hard/Long/Emerging 问题，压力测试 | Deep |

#### 4.1.3 Agentic 深度研究类

| 数据集 | 规模 | 特点 |
|--------|------|------|
| **DeepResearch-9K** | 9,000 题 | 三级难度（L1-L3），含搜索轨迹，支持多轮交互 |
| **Mind2Web 2** | 130 任务 | 长周期真实网页浏览任务，Agent-as-Judge 评估 |
| **WideSearch** | 200 题 | 大规模信息收集任务，最佳系统仅 5% 成功率 |

#### 4.1.4 传统 IR 数据集

| 数据集 | 规模 | 特点 | 注意事项 |
|--------|------|------|---------|
| **MS MARCO** | 100 万查询 + 320 万文档 | 经典 IR 基准 | 已退役，假阴性严重 |
| **BEIR** | 多领域 | 18 个检索任务集合 | 适合跨域泛化测试 |
| **MTEB** | 综合 | Embedding 模型评测标准 | 更侧重嵌入模型而非系统 |

### 4.2 自建评测数据集（重点）

对于内部知识库场景，需要自建评测集，方法如下：

#### 方法一：从真实查询日志采样

```
真实用户查询 → 采样去重 → 人工标注预期结果 → 评测集
```

- 优点：分布最接近实际使用
- 缺点：需要系统上线后才有日志
- Exa 做法：从 5,000 条真实脱敏查询中构建 "In-the-wild" 评测集

#### 方法二：从文档生成问答对

```
内部文档 → 选取关键片段 → LLM 生成问题 → 人工验证 → 评测集
```

参考 Exa WebCode 的方法：
1. 选择长文档中的 niche 细节片段
2. 构造只有该片段能回答的事实问题
3. 验证前沿模型无法仅凭参数记忆回答（确保必须检索）
4. 使用多个研究 Agent 交叉验证答案

#### 方法三：LLM 一次性生成（用于复杂查询）

参考 Exa Websets 的做法：
- 用 o1 等推理模型**一次性**生成 200 条复杂多条件查询
- 严格只写一次 prompt、运行一次，避免 prompt 调优带来的偏差
- 示例查询："在部门 X 工作超过 3 年、参与过项目 Y、且有 Z 技能的员工"

#### 方法四：手工构造挑战集（Olympiad）

参考 Exa 的 "Exa Olympiad"（~500 题）：
- 人工精心设计，测试语义理解和深层知识
- 覆盖边缘情况和复杂推理
- Exa 发现其优势在挑战集上最为显著

### 4.3 评测集构建原则

| 原则 | 说明 |
|------|------|
| **避免污染** | 确保评测数据不在训练集中（参考 OpenAI 废弃 SWE-bench 的原因） |
| **覆盖多样性** | 涵盖不同文档类型、查询复杂度、时间范围 |
| **可验证性** | 答案应有明确的正误判断标准 |
| **必须检索** | 好的评测问题应要求检索，前沿模型不能仅凭参数记忆回答 |
| **持续更新** | 评测集应随知识库演变定期更新 |

---

## 5. 评测方法论

### 5.1 内容质量评测

参考 Exa WebCode 论文，内容质量评测包含以下层次：

#### 5.1.1 提取忠实度评测（Contents Quality）

**黄金参考构建流程**（Exa 方案）：

```
渲染页面 → 截图 → 截图+DOM 输入多模态模型 → 生成忠实 Markdown → 黄金参考
```

**评测维度**：

| 维度 | 类型 | 说明 |
|------|------|------|
| Completeness | LLM 判定 | 黄金内容是否完整保留 |
| Signal | 确定性指标 | 有效内容占比（黄金长度 / 提取长度） |
| Structure | LLM 判定 | 标题、列表、表格结构是否保持 |
| Accuracy | LLM 判定 | 数字、代码、名称是否准确 |
| Code Recall | 确定性指标 | 代码块是否保留 |
| Table Recall | 确定性指标 | 表格是否保留 |
| ROUGE-L | 确定性指标 | 词级别最长公共子序列 F1 |

**内部知识库适配**：对于内部文档（PDF/Word/Confluence/数据库），需要类似构建 parser 的黄金提取基准。

#### 5.1.2 高亮质量评测（Highlights）

Exa 提出的关键创新 —— 区分 **Correctness** 和 **Groundedness**：

| 指标 | 评测方式 | 说明 |
|------|---------|------|
| **Correctness** (生成式) | 合成答案是否正确，Judge 不看高亮 | 反映合成 LLM 能力，不反映检索质量 |
| **Groundedness** (判别式) | 高亮是否包含正确答案，Judge 不看合成答案 | 真正反映检索/提取质量 |

> **关键发现**：Exa 发现 Correctness 各系统差异很小（~86%），因为它主要反映合成模型能力；而 Groundedness 方差更大，能真正区分不同检索系统的能力。这意味着仅评估最终答案正确性是不够的。

### 5.2 检索质量评测

#### 5.2.1 纯结果评分（Pure Result Grading）

Exa 的核心方法：

```python
for query in query_set:
    results = search_engine.search(query)
    for result in results:
        score = llm_judge.grade(query, result)  # 0.0 ~ 1.0
    query_score = aggregate(scores)  # mean / median / NDCG
overall_score = mean(query_scores)
```

**Exa 的三个测试集**：
- In-the-wild queries: 5,000 条真实脱敏查询
- MS MARCO Queries: 10,000 条（但用 LLM 而非原始标签评分）
- Exa Olympiad: ~500 条手工构造的挑战查询

#### 5.2.2 RAG 问答评测

```python
for question in dataset:
    results = search_engine.search(question)
    context = concatenate(results)
    answer = llm.generate(question, context)
    grade = judge.evaluate(answer, expected_answer)  # correct / partial / incorrect

accuracy = count(correct) / total
```

参考 Exa 在 SimpleQA 上的流程：
- 用 gemini-1.5-flash 生成搜索查询
- 用 4o-mini 基于结果生成答案
- 用 SimpleQA 标准评分

#### 5.2.3 Agentic 多步评测

```python
for question in dataset:
    agent = Agent(llm=gpt5, search_tool=search_engine)
    answer = agent.run(question, max_search_calls=10)
    grade = judge.evaluate(answer, expected_answer)
```

参考 Exa 2.1 的 MCP 评测：允许 Agent 自主决定何时搜索、搜索什么、最多 10 轮。

#### 5.2.4 端到端任务评测

参考 Exa WebCode 的方法：

```
选择目标任务 → 验证模型不能直接解决 → 提供搜索工具 →
在沙箱中执行 → 运行单元测试 → 计算通过率
```

关键设计：
- **知识时效门控**：选择近期发布的内容，确保不在模型训练数据中
- **难度门控**：如果前沿模型无需搜索就能通过，则加固或淘汰任务
- **DNS 隔离**：沙箱中屏蔽除模型 API 外的所有网络请求

### 5.3 复杂条件检索评测（Websets 模式）

适用于知识库中的实体搜索场景（如"找到所有满足条件 A+B+C 的文档/人员/项目"）：

```python
for query in complex_queries:
    criteria = llm.extract_criteria(query)
    results = search_engine.search(query)
    for result in results:
        passed = all(llm.check_criterion(result, c) for c in criteria)
    precision = count(passed) / count(results)
    recall = count(passed) / expected_count  # 如果可估计
```

Exa Websets 评测发现：Google 平均仅返回 16 条正确结果，而 Websets(低算力) 返回 66 条，Websets(高算力) 返回 320 条。

---

## 6. 评测指标体系

### 6.1 检索质量指标

| 指标 | 公式/说明 | 适用场景 |
|------|----------|---------|
| **Precision@K** | 前 K 个结果中相关的比例 | 关注精确度 |
| **Recall@K** | 前 K 个结果覆盖了多少相关文档 | 关注覆盖度 |
| **MRR** | 第一个相关结果的位置的倒数的平均值 | 关注首个好结果 |
| **NDCG@K** | 归一化折扣累积增益，考虑位置和分级相关性 | 综合排序质量 |
| **LLM 相关性评分** | LLM 对 (query, result) 的 0-1 评分均值 | Exa 主要使用 |
| **Citation Precision** | 返回结果中包含正确答案的比例 | 评测检索精度 |

### 6.2 内容质量指标

| 指标 | 说明 |
|------|------|
| **Completeness** | 提取内容相对黄金参考的完整度 |
| **Signal** | 有效内容占总提取量的比例（去噪能力） |
| **ROUGE-L** | 词级最长公共子序列 F1 |
| **Code/Table Recall** | 代码块、表格的保留率 |
| **Structure Score** | 标题、列表等结构的保持程度 |

### 6.3 RAG 端到端指标

| 指标 | 说明 | 来源 |
|------|------|------|
| **Correctness** | 最终答案是否正确 | SimpleQA 标准 |
| **Groundedness** | 检索结果是否包含答案依据 | Exa WebCode 创新 |
| **Faithfulness** | 生成内容是否忠实于检索上下文 | RAGAS/ARES |
| **Context Relevance** | 检索上下文与问题的相关度 | RAGAS/ARES |
| **Answer Relevance** | 生成答案与问题的相关度 | RAGAS/ARES |

### 6.4 系统性能指标

| 指标 | 说明 |
|------|------|
| **P50 / P99 延迟** | 中位数和长尾延迟 |
| **QPS** | 每秒查询数 |
| **索引延迟** | 新文档从入库到可搜的时间 |
| **索引覆盖率** | 已索引文档占全部文档的比例 |
| **可用性 (Uptime)** | 系统可用时间占比 |

### 6.5 Exa 建议的聚合方法

| 方法 | 说明 | 优劣 |
|------|------|------|
| **Pointwise** | 对每个 (query, doc) 独立评分后聚合 | 简单、可控、Exa 默认使用 |
| **Pairwise** | 每对搜索引擎结果比较，计算 ELO | 理论更优，避免绝对分数偏差 |
| **Listwise** | 将多个引擎结果混合排序 | 可评估多样性，但 LLM 处理长上下文有误差 |

Exa 的经验：**Pointwise 和 Pairwise 的结果排序高度一致**，默认使用 Pointwise 因为更简单。

---

## 7. LLM-as-Judge 方法论

### 7.1 核心流程

```
定义查询集 → 执行搜索 → 对每个 (query, result) 调用 LLM 评分 → 聚合
```

### 7.2 评分 Prompt 设计

Exa 分享了他们迭代后的评分 Prompt，核心要点：

```
评分维度：
1. query_relevance (0.0-1.0): 结果与查询的匹配度
2. result_quality (0.0-1.0): 来源权威性、准确性
3. content_issues (True/False): 内容是否有截断、缺失等问题
4. confidence (0.0-1.0): 评分的置信度
5. score (0.0-1.0): 综合评分

关键原则：
- 精确匹配用户意图
- 列表/通用文章不是好结果（当用户想要具体实体时）
- 同时考虑相关性和来源质量
- 结果可能被截断，用判断力补全理解
```

Exa 的经验：精心迭代后的 prompt 与人类偏好一致率达到 97%（简单样本）和 83%（困难/歧义样本）。

### 7.3 验证差距（Verification Gap）问题

LLM 评分面临的核心矛盾：**如果 LLM 已经知道答案，就不需要检索了；但如果不知道，又如何判断检索结果好坏？**

Exa 的解决方案：

1. **大多数搜索系统比 LLM "笨"**：检索系统每文档计算量远小于 LLM，所以 LLM 判定通常比检索排序更可靠
2. **大多数查询是上下文自包含的**：文档本身通常包含足够信息来判定是否匹配查询
3. **提供预期答案**：对于需要事实知识的查询，提供预期答案/条件给 Judge，让它做语义匹配而非精确文档匹配
4. **统计层面可靠**：不需要每个判定都完美，只需要在大量查询上，更好的系统获得更高均分

### 7.4 模型选择

- Exa 使用 **GPT-4.1** 作为 Judge
- 他们验证了 GPT-4o、GPT-4o-mini、GPT-4.1、Gemini Flash 2.5 之间**排名一致性高**
- 绝对分数因模型而异，但相对排序稳定

### 7.5 已知偏差与缓解

| 偏差类型 | 说明 | 缓解方法 |
|---------|------|---------|
| 位置偏差 | LLM 倾向于给先出现的结果更高分 | 随机化结果顺序 |
| 冗余偏差 | 更长的内容可能获得更高分 | 标准化内容长度 |
| 自我偏差 | LLM 更倾向于 LLM 生成的内容 | 使用与生成模型不同的 Judge 模型 |
| 分数校准 | LLM 的绝对分数不一定有意义 | 关注相对排序而非绝对分数 |

---

## 8. 当前难点与挑战

### 8.1 评测数据集构建难题

| 难题 | 说明 | Exa 的应对 |
|------|------|-----------|
| **污染问题** | 模型可能已见过评测数据 | WebCode 使用 2025.8 后的新 API 发布，验证模型无法凭参数记忆回答 |
| **标注成本** | 复杂知识查询标注每条可能需 10 秒到 30 分钟 | 用 LLM-as-Judge 替代大规模人工标注 |
| **假阴性** | 好结果被标为不相关 | 使用 Open Evals，允许 LLM 做语义匹配 |
| **分布不匹配** | 公开数据集不代表真实查询分布 | 从真实查询日志采样 + 手工构造 Olympiad |
| **规模不匹配** | 小规模上的性能不代表大规模 | 直接在生产规模索引上评测 |

### 8.2 系统评测难题

| 难题 | 说明 |
|------|------|
| **端到端 vs 组件** | 端到端分数是标量值，无法定位问题在哪个组件 |
| **Agent 行为不确定性** | Agentic 系统多次运行结果不同，需要多次采样 |
| **搜索时机判断** | Agent 是否在正确时机调用搜索？查询是否合适？ |
| **质量-延迟权衡** | 更高质量通常意味着更高延迟，如何公平比较？ |
| **内容提取 vs 检索** | 检索到了正确页面但提取了错误内容，如何区分？ |

### 8.3 内部知识库特有难题

| 难题 | 说明 |
|------|------|
| **多格式文档** | PDF、Word、PPT、Confluence、代码仓库混合 |
| **权限隔离** | 不同用户的检索范围不同，评测需覆盖 |
| **私有术语** | 内部专有名词、缩写、项目代号等 |
| **文档质量参差** | 有些文档年久失修或内容不准确 |
| **缺乏公开基线** | 没有标准的内部知识库评测集可参考 |
| **知识更新** | 文档频繁变更，评测集也需随之更新 |

---

## 9. 针对内部知识库的评测方案设计

### 9.1 总体框架

```
                    ┌─────────────────────────────────────┐
                    │        评测框架总体架构              │
                    └─────────────────┬───────────────────┘
                                      │
         ┌────────────────────────────┼────────────────────────────┐
         │                            │                            │
    ┌────▼────┐                 ┌─────▼─────┐               ┌─────▼─────┐
    │ 离线评测 │                 │ 在线评测   │               │ 人工评审   │
    │ (Batch) │                 │ (Online)  │               │ (Manual)  │
    └────┬────┘                 └─────┬─────┘               └─────┬─────┘
         │                            │                           │
    ┌────▼─────────┐            ┌─────▼──────┐            ┌──────▼──────┐
    │• 标准数据集   │            │• A/B 测试   │            │• Side-by-side│
    │• 回归测试     │            │• 用户满意度  │            │• 错误分析    │
    │• 组件级评测   │            │• 日志分析    │            │• 边界案例    │
    │• 端到端评测   │            │• 隐式反馈    │            │• 季度审计    │
    └──────────────┘            └─────────────┘            └─────────────┘
```

### 9.2 六层评测模型

参考企业 RAG 评测框架，采用六层评测模型：

#### Layer 1: 语料质量（Corpus Quality）

| 指标 | 计算方法 | 目标 |
|------|---------|------|
| 文档覆盖率 | 已索引 / 应索引 | >99% |
| 内容新鲜度 | 索引版本 vs 源文档版本 | 延迟 <1h |
| 去重率 | 重复文档 / 总文档 | <1% |
| 元数据完整度 | 有完整元数据的文档占比 | >95% |
| 分块质量 | 人工抽检分块合理性 | >90% 合理 |

#### Layer 2: 内容提取质量（Content Extraction）

针对不同文档类型建立黄金提取基准：

```python
doc_types = ["PDF", "Word", "PPT", "Confluence", "Code", "Database"]
for doc_type in doc_types:
    golden_refs = build_golden_references(sample_docs[doc_type], n=50)
    scores = evaluate_extraction(extractor, golden_refs)
    report(doc_type, scores)  # completeness, signal, structure, accuracy
```

#### Layer 3: 检索质量（Retrieval Quality）

**数据集构建**：

| 评测集 | 构建方法 | 规模 | 更新频率 |
|--------|---------|------|---------|
| 日常查询集 | 从查询日志采样 | 1,000+ | 月度 |
| 文档问答集 | 从文档生成 QA 对 | 500+ | 随文档更新 |
| 挑战集 | 人工构造复杂查询 | 200+ | 季度 |
| 多条件查询集 | LLM 一次性生成 | 200 | 季度 |
| 回归测试集 | 历次发现的 bad case | 持续增长 | 实时 |

**评测流程**：

```python
def evaluate_retrieval(search_engine, dataset, judge_model="gpt-4.1"):
    results = []
    for item in dataset:
        search_results = search_engine.search(
            query=item["query"],
            num_results=10
        )

        # Pointwise 评分
        scores = []
        for result in search_results:
            score = judge_model.grade(
                query=item["query"],
                result=result,
                expected_criteria=item.get("criteria", None)
            )
            scores.append(score)

        results.append({
            "query": item["query"],
            "mean_score": mean(scores),
            "ndcg": compute_ndcg(scores),
            "top1_score": scores[0] if scores else 0,
        })

    return aggregate_with_confidence_intervals(results)
```

#### Layer 4: RAG 端到端质量（End-to-End RAG）

```python
def evaluate_rag_e2e(search_engine, llm, dataset, judge):
    for item in dataset:
        # 检索
        results = search_engine.search(item["query"], num_results=10)
        context = format_context(results)

        # 生成
        answer = llm.generate(item["query"], context)

        # 评分（双轴）
        correctness = judge.grade_correctness(
            question=item["query"],
            expected=item["answer"],
            generated=answer
        )
        groundedness = judge.grade_groundedness(
            expected=item["answer"],
            highlights=context
        )
        faithfulness = judge.grade_faithfulness(
            answer=answer,
            context=context
        )
```

#### Layer 5: Agentic 多步评测

```python
def evaluate_agentic(agent_config, dataset):
    for item in dataset:
        agent = Agent(
            llm=agent_config.llm,
            search_tool=agent_config.search_engine,
            max_iterations=10
        )

        # 记录搜索轨迹
        result = agent.run(item["query"])

        # 评分
        grade = judge.evaluate(result.answer, item["expected"])

        # 诊断分析
        diagnostics = {
            "num_searches": result.search_count,
            "search_queries": result.queries_used,
            "total_latency": result.total_time,
            "search_latency": result.search_time,
        }
```

#### Layer 6: 系统级指标

持续监控的生产指标：

| 指标类别 | 具体指标 | 采集方式 |
|---------|---------|---------|
| 延迟 | P50, P95, P99 搜索延迟 | APM 监控 |
| 吞吐 | QPS, 并发数 | APM 监控 |
| 可用性 | Uptime, 错误率 | 健康检查 |
| 索引 | 索引延迟, 覆盖率 | 定期探测 |
| 用户体验 | 点击率, 重搜率, 满意度 | 日志分析 |

### 9.3 对比评测方案

#### 基线系统选择

| 基线 | 说明 |
|------|------|
| BM25 (Elasticsearch) | 词频基线，最低标准 |
| Dense Retrieval (向量检索) | 纯嵌入检索，无重排 |
| Hybrid (BM25 + 向量) | 混合检索 |
| 当前生产系统 | 如已有系统，作为对比 |
| 无检索基线 | LLM 仅凭参数记忆回答，衡量检索增益 |

#### A/B 测试框架

```python
# 在线 A/B 测试
def ab_test_search(query, user):
    variant = assign_variant(user)  # A or B
    if variant == "A":
        results = current_system.search(query)
    else:
        results = new_system.search(query)

    log_implicit_feedback(user, query, results, variant)
    return results

# 隐式信号：点击率、停留时间、重搜率、复制行为
```

### 9.4 评测报告模板

```markdown
## 评测报告 - [日期]

### 概要
- 评测版本: v1.2.3
- 基线版本: v1.2.2
- 评测数据集: 日常查询集(1000) + 挑战集(200)

### 检索质量
| 指标 | 当前版本 | 基线 | 变化 | 95% CI |
|------|---------|------|------|--------|
| Mean Relevance Score | 0.82 | 0.79 | +3.8% | [+2.1%, +5.5%] |
| NDCG@10 | 0.76 | 0.73 | +4.1% | ... |
| Groundedness | 0.88 | 0.84 | +4.8% | ... |

### 按类别分解
| 查询类别 | 当前版本 | 基线 | 说明 |
|---------|---------|------|------|
| 事实查询 | 0.91 | 0.88 | 改善明显 |
| 复杂推理 | 0.72 | 0.65 | 最大改善 |
| 时效性查询 | 0.80 | 0.78 | 小幅改善 |

### 延迟
| 百分位 | 当前版本 | 基线 |
|--------|---------|------|
| P50 | 320ms | 350ms |
| P99 | 1200ms | 1100ms |

### 失败案例分析
[Top 10 失败查询及原因分析]

### 结论与建议
[...]
```

---

## 10. 实施路线图

### Phase 1: 基础评测搭建（第 1-2 周）

- [ ] 搭建评测 pipeline 基础设施
- [ ] 实现 LLM-as-Judge 评分模块
- [ ] 从内部文档生成初始 QA 评测集（200+ 对）
- [ ] 建立 BM25 和向量检索基线
- [ ] 实现基本的 Pointwise 评分 + 聚合

### Phase 2: 评测集完善（第 3-4 周）

- [ ] 构建内容提取黄金参考（每种文档类型 50 个）
- [ ] 人工构造挑战集（Olympiad，200 题）
- [ ] 用 LLM 生成多条件复合查询集（200 题）
- [ ] 实现 Groundedness 评测（区分检索质量和生成质量）
- [ ] 建立评测报告自动生成

### Phase 3: 端到端评测（第 5-6 周）

- [ ] 构建 Agentic 多步评测 harness
- [ ] 实现端到端任务评测（带沙箱执行）
- [ ] 添加延迟、吞吐量等系统指标监控
- [ ] 建立回归测试集与 CI/CD 集成

### Phase 4: 线上评测与迭代（第 7-8 周+）

- [ ] 部署在线 A/B 测试框架
- [ ] 接入用户反馈信号（点击、重搜、满意度）
- [ ] 建立评测集定期更新机制
- [ ] 建立 Side-by-side 人工评审流程
- [ ] 持续扩充评测集和失败案例库

---

## 11. 参考资料

### Exa.ai 官方资料

1. [How we do evals at Exa](https://exa.ai/blog/evals-at-exa) - Exa 评测哲学、Open Evals 方法论、评分 Prompt
2. [Web Search API Evals](https://exa.ai/blog/api-evals) - SimpleQA 和 MSMARCO 评测
3. [Websets Evals](https://exa.ai/blog/websets-evals) - 复杂多条件查询评测
4. [WebCode: Search Evals for Coding Agents](https://exa.ai/blog/webcode) - 内容质量 + 检索质量 + E2E 评测
5. [Introducing Exa 2.1](https://exa.ai/blog/exa-api-2-1) - Fast/Deep 评测方法论
6. [Introducing Exa Deep](https://exa.ai/blog/exa-deep) - Agentic 搜索评测
7. [How to Evaluate Exa Search](https://exa.ai/docs/reference/evaluating-exa-search) - 评测指南、数据集推荐、配置模板

### 学术基准数据集

8. [SimpleQA](https://openai.com/index/introducing-simpleqa/) - OpenAI, 4,326 事实问答
9. [FRAMES](https://huggingface.co/datasets/google/frames-benchmark) - Google, 824 多跳问题 (NAACL 2025)
10. [BrowseComp](https://openai.com/index/browsecomp) - OpenAI, 1,266 难题
11. [MS MARCO](https://microsoft.github.io/msmarco/) - Microsoft, 经典 IR 基准
12. [BEIR](https://github.com/beir-cellar/beir) - 跨域检索基准集合
13. [DeepResearch-9K](https://arxiv.org/abs/2603.01152) - 9,000 多轮深度研究任务
14. [Mind2Web 2](https://osu-nlp-group.github.io/Mind2Web-2/) - 130 长周期浏览任务 (NeurIPS 2025)
15. [WideSearch](https://arxiv.org/html/2508.07999v2) - 200 大规模信息收集任务

### 评测框架

16. [RAGAS](https://docs.ragas.io/) - RAG 评测框架
17. [ARES](https://github.com/stanford-futuredata/ares) - Stanford, 自动 RAG 评测
18. [RAGPerf](https://arxiv.org/abs/2603.10765) - 端到端 RAG 基准框架
19. [EKRAG](https://aclanthology.org/2025.knowledgenlp-1.13/) - 企业知识库 RAG 评测

### 方法论参考

20. [Statistical Approach to Model Evals](https://www.anthropic.com/research/statistical-approach-to-model-evals) - Anthropic, 评测统计方法
21. [LLM 标注在 IR 中的可靠性](https://arxiv.org/html/2405.04727v1) - LLM 评分与人工评分的相关性
22. [密集嵌入的规模问题](https://aclanthology.org/2021.acl-short.77.pdf) - Reimers et al., 嵌入模型在大索引上的性能衰减
23. [Enterprise RAG Evaluation Framework 2026](https://laderalabs.io/blog/enterprise-rag-evaluation-framework-2026) - 六层企业评测框架

---

> **文档维护说明**：本评测方案应随系统开发迭代持续更新，评测数据集至少每季度审查一次，评测指标和方法论在系统架构发生重大变化时需重新评估。
