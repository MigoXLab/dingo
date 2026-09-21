# 用自然语言运行 Dingo SaaS 评测

Dingo SaaS Skill 让你通过自然语言管理数据集和指标、运行实验并分析报告。你只需要说明评测目标，代理会查找资源、调用 Dingo SaaS API，并按正确顺序完成操作。

## 开始之前

你需要：

- Dingo SaaS 网站地址；
- 一个有效的 API Key。

登录 Dingo SaaS 后，进入 `Dashboard → Settings`（`/dashboard/settings`）创建 API Key。完整 Key 只会在创建时显示一次，请及时保存。

## 连接 Dingo SaaS

第一次使用时输入：

```text
使用 $dingo-saas 连接我的 Dingo SaaS。
```

代理会询问网站地址和 API Key，并在本地保存连接。随后用一个只读请求验证连接：

```text
检查连接，并列出我的数据集、指标组和最近 5 份报告。不要修改任何资源。
```

连接成功后，代理会返回资源名称和 ID，但不会在回答中显示完整 API Key。

## 运行第一次完整质检

你可以在一条消息里描述完整目标：

```text
上传 Skill 目录中的 assets/mineru_pdf.jsonl，创建“MinerU PDF 抽取结果”数据集。
从已有 Metric 中列出适合检查 PDF 抽取内容质量的指标，并说明各自的评判标准，让我选择一个。
选择后创建并运行质检实验。质检完成后，将报告发送给我。
```

代理会依次完成：

1. 上传 JSONL 文件并创建数据集；
2. 从已有 Metric 中筛选适合的指标；
3. 等你选定 Metric 后创建并启动实验；
4. 持续检查状态，完成后将报告发送给你。

完成后，你会收到类似结果：

| 项目 | 结果示例 |
| --- | --- |
| 数据集 | MinerU PDF 抽取结果 |
| 质检 Metric | PDF 内容完整性检查 |
| 实验状态 | `success` |
| 报告 | MinerU PDF 抽取质量测试_20260914_093000 |
| 交付内容 | 完整质检报告 |

## 还可以这样使用

```text
预览“MinerU PDF 抽取结果”数据集，告诉我有哪些字段，并显示前 3 条记录。
```

```text
如果没有合适的 Metric，帮我起草一个“PDF 内容抽取质量”自定义指标，先给我看评判标准，不要保存。
```

```text
把“MinerU PDF 抽取质量测试”实验设置为工作日每天 09:30 执行，时区使用 Asia/Shanghai。
```

```text
找到最近一次 MinerU 抽取质量报告并发送给我。
```

还可以通过 Skill 完成更多数据集、指标、实验和报告操作。完整动作和执行约束见 [SKILL.md](SKILL.md)。
