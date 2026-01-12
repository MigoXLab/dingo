# VLMRenderJudge - 基于视觉渲染的 OCR 质量评估指南

本指南介绍如何在 Dingo 中使用 **VLMRenderJudge**，一个基于视觉比较的 OCR 质量评估指标。该指标实现了 **"Render → Judge"** 模式，通过渲染 OCR 结果为图像并与原图进行 VLM 比较，从而准确评估 OCR 质量。

## 🎯 功能概述

VLMRenderJudge 是一种创新的 OCR 质量评估方法，通过视觉比较而非文本比较来判断 OCR 结果的准确性。该方法特别适用于：

- **数学公式识别评估**: 准确评估复杂公式中的符号、上下标、分数等细节
- **表格结构识别评估**: 验证表格边框、单元格对齐、合并等结构信息
- **文档布局评估**: 检测段落、标题、列表等布局元素是否正确识别
- **多语言 OCR 评估**: 统一评估不同语言的 OCR 质量
- **迭代式 OCR 优化**: 作为 Judge 环节支持 "Judge → Refine" 迭代优化流程

### 与传统方法的对比

| 方法 | 优势 | 劣势 |
|------|------|------|
| **文本相似度** (CER/WER) | 快速、可量化 | 无法评估格式、布局、数学符号 |
| **编辑距离** (Levenshtein) | 简单直观 | 对符号顺序敏感，无视觉感知 |
| **VLMRenderJudge** | 视觉准确、支持复杂格式、接近人类判断 | 需要 VLM API、依赖渲染工具 |

---

## 🔧 核心原理

### Render → Judge 流程

```
┌─────────────┐
│  原始图像    │ ────────┐
└─────────────┘         │
                        ▼
                    ┌──────────┐     ┌─────────────┐
                    │   VLM    │────▶│ EvalDetail  │
                    │  Judge   │     │ score: 0/1  │
                    └──────────┘     └─────────────┘
┌─────────────┐         ▲
│ OCR 结果     │         │
│ (文本)       │─────────┘
│  ↓ 渲染      │    (两张图片比较)
│ ┌─────────┐ │
│ │渲染图像 │ │
│ └─────────┘ │
└─────────────┘
```

**核心步骤**：
1. **接收输入**: 原始图像 + OCR 识别文本
2. **渲染 OCR 结果**: 根据内容类型（text/equation/table）渲染为图像
3. **VLM 视觉比较**: 将原图和渲染图提交给 VLM，判断是否一致
4. **输出结果**:
   - `score = 1.0`: OCR 完全正确 (QUALITY_GOOD)
   - `score = 0.0`: OCR 有错误 (QUALITY_BAD_OCR.VISUAL_MISMATCH)
   - `score = 0.5`: 渲染失败，无法判断 (QUALITY_UNKNOWN.RENDER_FAILED)

### 评判标准

VLM 使用严格的一致性规则（来自 MinerU_Metis 项目）：

- ✅ **忽略差异**: 字体样式、空格数量、换行位置、中英文标点互换
- ❌ **标记为错误**: 字符缺失/增加/替换、符号错误、上下标错误、数字错误

---

## 📋 使用要求

### 环境依赖

```bash
# 基础依赖
pip install dingo pillow

# LaTeX 渲染（用于公式评估，可选）
# macOS
brew install mactex-no-gui imagemagick

# Ubuntu/Debian
sudo apt-get install texlive-xetex imagemagick
```

### 数据格式要求

```python
from dingo.io.input import Data

data = Data(
    data_id="test_1",
    image="path/to/original_image.png",  # 原始文档图像（必需）
    content="The quick brown fox...",     # OCR 识别文本（必需）
    content_type="text"                   # 内容类型（可选，默认 "text"）
)
```

#### 支持的 content_type

| 类型 | 说明 | 渲染方式 |
|------|------|---------|
| `text` | 纯文本、段落、标题 | PIL ImageDraw |
| `equation` | LaTeX 数学公式 | xelatex |
| `table` | HTML 表格 | HTML to Image |

---

## 🚀 快速开始

### 示例 1: 独立使用评估 OCR 质量

```python
from dingo.config.input_args import InputArgs
from dingo.exec import Executor

# 配置评估器
args = InputArgs(
    input_path="test_data.jsonl",
    dataset={
        "source": "local",
        "format": "jsonl"
    },
    evaluator=[{
        "fields": {
            "image": "image",           # 原始图片字段
            "content": "content",       # OCR 文本字段
            "content_type": "content_type"
        },
        "evals": [{
            "name": "VLMRenderJudge",
            "config": {
                "model": "gpt-4o",
                "key": "your-api-key",
                "api_url": "https://api.openai.com/v1",
                "parameters": {
                    "max_tokens": 4000,
                    "temperature": 0,
                    "render_config": {
                        "density": 150,  # LaTeX 渲染 DPI
                        "pad": 20        # 图像边距
                    }
                }
            }
        }]
    }]
)

# 执行评估
executor = Executor.exec_map["local"](args)
summary = executor.execute()

print(f"评估完成: {summary.score:.2f}%")
print(f"正确数量: {summary.num_good}/{summary.total}")
```

### 示例 2: 测试数据格式

**test_data.jsonl** 示例：

```jsonl
{"image": "images/doc1.png", "content": "The quick brown fox jumps over the lazy dog.", "content_type": "text"}
{"image": "images/formula1.png", "content": "E = mc^2", "content_type": "equation"}
{"image": "images/table1.png", "content": "<table><tr><td>A</td><td>B</td></tr></table>", "content_type": "table"}
```

---

## 🔥 完整配置示例

### Python 代码方式

```python
from dingo.model.llm.vlm_render_judge import VLMRenderJudge
from dingo.io.input import Data

# 1. 配置 VLM 模型
VLMRenderJudge.set_config({
    "model": "gpt-4o",
    "key": "your-api-key",
    "api_url": "https://api.openai.com/v1",
    "parameters": {
        "max_tokens": 4000,
        "temperature": 0,
        "render_config": {
            "density": 150,      # LaTeX 渲染 DPI (72-300)
            "pad": 20,           # 图像边距
            "timeout": 60,       # 渲染超时时间（秒）
            "font_path": None,   # 文本渲染自定义字体路径（可选）
            "cjk_font": None     # LaTeX CJK 字体名称（可选，如 'SimSun'/'PingFang SC'/'Noto Sans CJK SC'）
        }
    }
})

# 2. 准备测试数据
data = Data(
    data_id="test_1",
    image="test/images/formula.png",
    content="\\int_{0}^{\\infty} e^{-x^2} dx = \\frac{\\sqrt{\\pi}}{2}",
    content_type="equation"
)

# 3. 执行评估
result = VLMRenderJudge.eval(data)

# 4. 查看结果
print(f"评分: {result.score}")
print(f"标签: {result.label}")
print(f"原因:\n{chr(10).join(result.reason)}")
```

### 输出示例

**正确的 OCR 结果**：
```
评分: 1.0
标签: ['QUALITY_GOOD']
原因:
✅ OCR content verified correct

Judge reason:
Both images show the same mathematical equation with consistent symbols,
subscripts, and superscripts. The content is fully consistent.
```

**错误的 OCR 结果**：
```
评分: 0.0
标签: ['QUALITY_BAD_OCR.VISUAL_MISMATCH']
原因:
❌ OCR content has errors

Judge reason:
GT has "e^{-x^2}" while OCR has "e^-x2". The OCR result is missing the
superscript braces, causing incorrect rendering. This is an actual symbol
difference.

OCR content evaluated:
\int_{0}^{\infty} e^-x2 dx = \frac{\sqrt{\pi}}{2}
```

---

## 🔄 与 AgentIterativeOCR 配合使用

VLMRenderJudge 可作为 **Judge 环节**，与 OCR Refiner 组成迭代优化流程：

```python
from dingo.model.llm.agent.agent_iterative_ocr import AgentIterativeOCR
from dingo.config.input_args import InputArgs

# 配置迭代式 OCR 评估
args = InputArgs(
    input_path="test_data.jsonl",
    dataset={"source": "local", "format": "jsonl"},
    evaluator=[{
        "fields": {
            "image": "image",
            "content": "initial_ocr_result"  # 初始 OCR 结果
        },
        "evals": [{
            "name": "AgentIterativeOCR",
            "config": {
                # VLM Judge 配置
                "model": "gpt-4o",
                "key": "your-api-key",
                "api_url": "https://api.openai.com/v1",
                "parameters": {
                    "max_iterations": 3,  # 最大迭代次数
                    "content_type": "equation"
                }
            }
        }]
    }]
)

# 执行迭代评估
executor = Executor.exec_map["local"](args)
summary = executor.execute()
```

**迭代流程**：
1. **Judge**: VLMRenderJudge 判断当前 OCR 是否正确
2. **Refine**: 如果不正确，调用 VLM 分析错误并生成改进版本
3. **Repeat**: 重复步骤 1-2，直到正确或达到最大迭代次数

---

## ⚙️ 渲染配置详解

### render_config 参数

```python
"render_config": {
    "density": 150,        # LaTeX 渲染 DPI (默认: 150)
                          # - 72: 低质量，速度快
                          # - 150: 平衡质量与速度（推荐）
                          # - 300: 高质量，速度慢

    "pad": 20,            # 图像边距，单位像素 (默认: 20)

    "timeout": 60,        # 渲染超时时间（秒）(默认: 60)

    "font_path": None,    # 文本渲染自定义字体路径（可选）
                          # 例如: "/usr/share/fonts/SimSun.ttc"

    "cjk_font": None      # LaTeX CJK 字体名称（可选）
                          # - Windows: "SimSun", "Microsoft YaHei"
                          # - macOS: "PingFang SC", "Heiti SC"
                          # - Linux: "Noto Sans CJK SC", "WenQuanYi Micro Hei"
}
```

### 字体选择逻辑

#### 文本渲染字体（font_path）

用于普通文本渲染，按以下顺序尝试：

1. `render_config.font_path`（如果指定）
2. `/System/Library/Fonts/Helvetica.ttc` (macOS)
3. `Arial` (Windows/Linux)
4. `Arial Unicode MS` (Unicode 支持)
5. `DejaVuSans` (Linux)
6. `SimSun` (中文字体)
7. 系统默认字体（最后备选）

#### LaTeX CJK 字体（cjk_font）

用于 LaTeX 公式中的中文字符渲染，**自动跨平台适配**：

- 如果指定 `cjk_font`：使用指定字体
- 如果未指定：**自动检测操作系统**并使用默认字体
  - Windows: `SimSun` (宋体)
  - macOS: `PingFang SC` (苹方)
  - Linux: `Noto Sans CJK SC`

**跨平台配置示例**：

```python
# 方式 1: 明确指定字体（推荐，确保一致性）
"render_config": {
    "cjk_font": "SimSun"  # 确保所有平台都安装了此字体
}

# 方式 2: 自动检测（默认，方便但可能导致不同平台渲染结果不同）
"render_config": {
    "cjk_font": None  # 自动根据操作系统选择
}
```

**建议**：
- **英文文档**：使用默认配置
- **中文文档**：
  - 团队协作：明确指定 `cjk_font`，确保所有成员安装相同字体
  - 个人使用：使用自动检测（`cjk_font=None`）
- **混合文档**：指定支持中英文的字体（如 `Arial Unicode MS` + `cjk_font="PingFang SC"`）

---

## 🎯 应用场景

### 场景 1: OCR 模型对比评估

```python
# 评估多个 OCR 模型的输出质量
models = ["paddleocr", "tesseract", "mineru", "surya"]

for model in models:
    args = InputArgs(
        input_path=f"ocr_results_{model}.jsonl",
        evaluator=[{
            "fields": {"image": "image", "content": "ocr_text"},
            "evals": [{"name": "VLMRenderJudge", "config": llm_config}]
        }]
    )

    summary = Executor.exec_map["local"](args).execute()
    print(f"{model}: {summary.score:.2f}%")
```

### 场景 2: 数据集质量验证

```python
# 验证 OCR 训练数据集的标注质量
args = InputArgs(
    input_path="training_data_with_labels.jsonl",
    evaluator=[{
        "fields": {
            "image": "image",
            "content": "ground_truth_label"  # 人工标注的 GT
        },
        "evals": [{"name": "VLMRenderJudge", "config": llm_config}]
    }]
)

summary = Executor.exec_map["local"](args).execute()

# 标记质量有问题的样本
bad_samples = [
    item for item in summary.details
    if item.eval_status and item.eval_details[0].score == 0.0
]

print(f"发现 {len(bad_samples)} 个质量问题样本")
```

### 场景 3: 实时 OCR 质量监控

```python
from dingo.model.llm.vlm_render_judge import VLMRenderJudge
from dingo.io.input import Data

def ocr_with_quality_check(image_path, ocr_function):
    """带质量检查的 OCR 函数"""
    # 1. 执行 OCR
    ocr_text = ocr_function(image_path)

    # 2. 质量评估
    data = Data(image=image_path, content=ocr_text)
    result = VLMRenderJudge.eval(data)

    # 3. 根据质量分数决定是否重试
    if result.score < 0.5:  # 质量不佳
        print(f"⚠️ OCR quality low: {result.score}")
        # 可以触发重试、人工审核等

    return {
        "text": ocr_text,
        "quality_score": result.score,
        "is_reliable": result.score >= 0.8
    }
```

---

## 💡 最佳实践

### 1. 选择合适的 content_type

```python
# ✅ 正确
{"content": "x^2 + y^2 = r^2", "content_type": "equation"}

# ❌ 错误
{"content": "x^2 + y^2 = r^2", "content_type": "text"}  # 无法正确渲染上标
```

### 2. 批量评估时使用合理的 batch_size

```python
args = InputArgs(
    executor={
        "batch_size": 10,     # 平衡速度与内存
        "num_workers": 2      # 并发数量
    }
)
```

### 3. 针对不同场景调整 temperature

```python
# 严格评估（推荐）
"parameters": {"temperature": 0}

# 宽松评估（容忍小差异）
"parameters": {"temperature": 0.3}
```

### 4. 保存渲染图像用于调试

```python
from dingo.model.llm.agent.tools import RenderTool

# 渲染并保存图像
result = RenderTool.execute(
    content="test content",
    content_type="text",
    output_path="debug_render.png"  # 保存到文件
)
```

### 5. 处理大规模数据集

```python
# 使用流式处理，避免内存溢出
args = InputArgs(
    input_path="large_dataset.jsonl",
    executor={
        "batch_size": 5,           # 小批量
        "checkpoint_interval": 100  # 定期保存检查点
    }
)
```

---

## 📊 评估指标解读

### score 含义

| Score | 含义 | 标签 | 建议 |
|-------|------|------|------|
| 1.0 | 完全正确 | QUALITY_GOOD | 无需处理 |
| 0.0 | 有错误 | QUALITY_BAD_OCR.VISUAL_MISMATCH | 需要修正或重新 OCR |
| 0.5 | 渲染失败 | QUALITY_UNKNOWN.RENDER_FAILED | 检查渲染环境 |

### reason 字段说明

```python
result.reason = [
    "✅ OCR content verified correct",  # 或 "❌ OCR content has errors"
    "",
    "Judge reason:",
    "VLM 的详细判断理由...",
    "",
    "OCR content evaluated:",
    "被评估的 OCR 文本内容（前300字）"
]
```

---

## 🔗 相关资源

- **示例脚本**: `examples/ocr/vlm_render_judge.py`
- **测试数据**: `test/data/img_OCR_iterative/`
- **API 文档**: `dingo.model.llm.vlm_render_judge.VLMRenderJudge`
- **相关工具**:
  - `RenderTool`: OCR 内容渲染工具
  - `AgentIterativeOCR`: 迭代式 OCR 优化
- **参考项目**: [MinerU_Metis](https://github.com/opendatalab/MinerU) - Render-Judge 模式的原始实现
