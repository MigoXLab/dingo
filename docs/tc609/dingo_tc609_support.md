# Dingo 对高质量数据集国家标准的支持

Dingo 参考 TC609 高质量数据集系列技术文件，为数据集说明文档、数据质量和模型应用三个维度提供自动化质量评测能力。当前已覆盖全部说明文档指标和全部一级数据质量指标；模型应用指标尚未提供已注册的评测实现。

## 1. 依赖的国标文件

Dingo 的国标评测能力主要参考以下三个文件：

- 全国数据标准化技术委员会技术文件 TC609—5—2025—02《高质量数据集 格式要求》
- 全国数据标准化技术委员会技术文件 TC609—5—2025—03《高质量数据集 分类指南》
- 全国数据标准化技术委员会技术文件 TC609—5—2025—04《高质量数据集 质量评测规范》

其中，分类指南用于界定高质量数据集的分类和适用范围，格式要求规定数据集及其元数据的组织方式，质量评测规范给出说明文档、数据质量和模型应用三个维度的评测指标。

## 2. 国标指标及 Dingo 支持情况

### 2.1 说明文档指标

说明文档指标关注数据集文档是否完整说明了数据集本身、建设过程和应用方式。Dingo 使用 LLM 对 Markdown 文档的完整性进行评估。

| 编号 | 国标指标 | Dingo metric | 支持状态 |
|---|---|---|---|
| 0101 | 基本信息完整性 | `LLM_TC609_0101_DocBasicInfoCompleteness` | 已支持 |
| 0102 | 内容特征完整性 | `LLM_TC609_0102_DocContentFeatureCompleteness` | 已支持 |
| 0103 | 建设过程完整性 | `LLM_TC609_0103_DocConstructionProcessCompleteness` | 已支持 |
| 0104 | 应用说明完整性 | `LLM_TC609_0104_DocApplicationCompleteness` | 已支持 |

### 2.2 数据质量评测指标

数据质量指标关注数据记录的格式、安全、标注、结构、溯源、一致性和内容干净程度。Dingo 根据指标特点提供规则评测或 LLM 评测；其中部分指标目前只覆盖文本或元数据层面的可自动检查内容。

| 编号 | 国标指标 | Dingo metric | 支持状态 |
|---|---|---|---|
| 0201 | 格式规范性 | `Rule_TC609_0201_FormatCompliance` | 已支持 |
| 0202 | 安全规范性 | `LLM_TC609_0202_SafetyCompliance` | 已支持 |
| 0203 | 标注规范性 | `Rule_TC609_0203_AnnotationCompliance` | 已支持 |
| 0204 | 结构完整性 | `Rule_TC609_0204_StructuralCompleteness` | 已支持 |
| 0205 | 内容真实性 | `Rule_TC609_0205_ContentAuthenticity` | 部分支持：检查溯源字段及 URL 格式 |
| 0206 | 内容一致性 | `LLM_TC609_0206_ContentConsistency` | 已支持 |
| 0207 | 类型一致性 | `LLM_TC609_0207_DataTypeConsistency` | 已支持 |
| 0208 | 内容干净性 | `Rule_TC609_0208_ContentCleanliness` | 部分支持：当前主要覆盖文本检查，尚未覆盖全部模态细项 |

0208 在标准附录中还可进一步细分为文本、图像、视频和音频指标，例如文本困惑程度、图像清晰度、视频帧率和音频信噪比等。Dingo 当前注册的是 0208 一级聚合指标，这些附录细项尚未作为独立 TC609 metric 提供。

### 2.3 模型应用指标

模型应用指标通过数据集在模型训练、微调或评测任务中的实际表现，判断数据集是否满足预期用途。

| 编号 | 国标指标 | Dingo metric | 支持状态 |
|---|---|---|---|
| 0301 | 内容多样性 | — | 暂未支持 |
| 0302 | 规模完整性 | — | 暂未支持 |
| 0303 | 内容时效性 | — | 暂未支持 |
| 0304 | 标注准确性 | — | 暂未支持 |
| 0305 | 模型适配性 | — | 暂未支持 |

## 3. 测试数据要求

### 3.1 说明文档评测

说明文档使用 Markdown（`.md`）文件作为输入。文档内容应尽量覆盖数据集基本信息、内容特征、建设过程和应用说明。Dingo 读取 Markdown 全文并映射到内部 `content` 字段，再由 0101–0104 四个 LLM metric 分别评测。

推荐目录结构：

```text
dataset/
├── README.md
└── data.jsonl
```

配置时使用本地数据源和 `md` 格式：

```json
{
  "input_path": "dataset/README.md",
  "dataset": {
    "source": "local",
    "format": "md"
  }
}
```


### 3.2 数据质量评测

数据质量评测使用符合《高质量数据集 格式要求》的元数据记录。推荐使用 UTF-8 编码的 JSONL 文件，每行表示一条独立数据记录。

一条典型记录包含：

```json
{
  "id": "8e00bc48-63f1-4ef0-a2aa-95b714d48801",
  "rid": [],
  "data_content": [
    {
      "media_type": "text",
      "content": "示例文本内容"
    }
  ],
  "annotation": {
    "label": [{"topic": "科技", "language": "zh-CN"}],
    "annotation_method": "人工标注",
    "annotator": "专业标注员"
  },
  "original_time": "2026-07-25",
  "last_modified_time": "2026-07-25",
  "version": "1.0.0",
  "license": "Apache-2.0",
  "source": "项目人工编写",
  "source_details": "https://github.com/MigoXLab/dingo",
  "generated_data_indicator": 0
}
```

执行评测前应确认每行 JSON 均可独立解析、记录标识唯一、字段类型稳定，且媒体内容或路径与 `media_type` 一致。

### 3.3 模型应用评测

Dingo 当前尚未注册 0301–0305 模型应用 metric，因此暂未定义统一的模型应用测试数据格式。后续实现这类指标时，除标准元数据外，通常还需要提供目标任务、模型信息、训练或评测配置，以及人工基准、标签真值或模型效果结果。

## 4. 相关文档

- [TC609 Rule 指标说明](rules_tc609.md)
- [TC609 LLM 指标说明](llm_tc609.md)
- [Dingo 完整指标清单](../metrics.md)
