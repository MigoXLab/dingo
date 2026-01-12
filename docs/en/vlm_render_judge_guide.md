# VLMRenderJudge - Visual OCR Quality Evaluation Guide

This guide introduces **VLMRenderJudge**, a visual comparison-based OCR quality evaluation metric in Dingo. It implements the **"Render → Judge"** pattern by rendering OCR results as images and comparing them with original images using VLM.

## 🎯 Overview

VLMRenderJudge is an innovative OCR quality assessment method that evaluates accuracy through visual comparison rather than text comparison. It's particularly suitable for:

- **Mathematical Formula Recognition**: Accurately evaluate symbols, subscripts/superscripts, fractions, and other details
- **Table Structure Recognition**: Verify table borders, cell alignment, merging, and structural information
- **Document Layout Assessment**: Detect whether paragraphs, titles, lists, and other layout elements are correctly recognized
- **Multilingual OCR Evaluation**: Unified evaluation of OCR quality across different languages
- **Iterative OCR Optimization**: Serves as the Judge component in "Judge → Refine" iterative workflows

### Comparison with Traditional Methods

| Method | Advantages | Disadvantages |
|--------|-----------|---------------|
| **Text Similarity** (CER/WER) | Fast, quantifiable | Cannot assess format, layout, mathematical symbols |
| **Edit Distance** (Levenshtein) | Simple, intuitive | Symbol order sensitive, no visual perception |
| **VLMRenderJudge** | Visually accurate, supports complex formats, close to human judgment | Requires VLM API, depends on rendering tools |

---

## 🔧 Core Principles

### Render → Judge Workflow

```
┌──────────────┐
│ Original Image│ ────────┐
└──────────────┘         │
                         ▼
                    ┌──────────┐     ┌─────────────┐
                    │   VLM    │────▶│ EvalDetail  │
                    │  Judge   │     │ score: 0/1  │
                    └──────────┘     └─────────────┘
┌──────────────┐         ▲
│ OCR Result   │         │
│ (text)       │─────────┘
│  ↓ Render    │    (Compare two images)
│ ┌──────────┐ │
│ │ Rendered │ │
│ └──────────┘ │
└──────────────┘
```

**Core Steps**:
1. **Receive Input**: Original image + OCR recognized text
2. **Render OCR Result**: Render as image based on content type (text/equation/table)
3. **VLM Visual Comparison**: Submit both images to VLM to judge consistency
4. **Output Result**:
   - `score = 1.0`: OCR completely correct (QUALITY_GOOD)
   - `score = 0.0`: OCR has errors (QUALITY_BAD_OCR.VISUAL_MISMATCH)
   - `score = 0.5`: Render failed, cannot judge (QUALITY_UNKNOWN.RENDER_FAILED)

---

## 📋 Requirements

### Environment Dependencies

```bash
# Basic dependencies
pip install dingo pillow

# LaTeX rendering (for equation type, optional)
# macOS
brew install mactex-no-gui imagemagick

# Ubuntu/Debian
sudo apt-get install texlive-xetex imagemagick
```

### Data Format

```python
from dingo.io.input import Data

data = Data(
    data_id="test_1",
    image="path/to/original_image.png",  # Original document image (required)
    content="The quick brown fox...",     # OCR recognized text (required)
    content_type="text"                   # Content type (optional, default "text")
)
```

---

## 🚀 Quick Start

### Example 1: Standalone OCR Quality Evaluation

```python
from dingo.config.input_args import InputArgs
from dingo.exec import Executor

# Configure evaluator
args = InputArgs(
    input_path="test_data.jsonl",
    dataset={
        "source": "local",
        "format": "jsonl"
    },
    evaluator=[{
        "fields": {
            "image": "image",
            "content": "content",
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
                        "density": 150,   # LaTeX render DPI
                        "pad": 20,        # Image padding
                        "cjk_font": None  # CJK font for LaTeX (auto-detect by default)
                    }
                }
            }
        }]
    }]
)

# Execute evaluation
executor = Executor.exec_map["local"](args)
summary = executor.execute()

print(f"Evaluation complete: {summary.score:.2f}%")
print(f"Correct: {summary.num_good}/{summary.total}")
```

### Example 2: Test Data Format

**test_data.jsonl** example:

```jsonl
{"image": "images/doc1.png", "content": "The quick brown fox jumps over the lazy dog.", "content_type": "text"}
{"image": "images/formula1.png", "content": "E = mc^2", "content_type": "equation"}
{"image": "images/table1.png", "content": "<table><tr><td>A</td><td>B</td></tr></table>", "content_type": "table"}
```

---

## 🔥 Complete Configuration

### Python Code

```python
from dingo.model.llm.vlm_render_judge import VLMRenderJudge
from dingo.io.input import Data

# 1. Configure VLM model
VLMRenderJudge.set_config({
    "model": "gpt-4o",
    "key": "your-api-key",
    "api_url": "https://api.openai.com/v1",
    "parameters": {
        "max_tokens": 4000,
        "temperature": 0,
        "render_config": {
            "density": 150,      # LaTeX render DPI (72-300)
            "pad": 20,           # Image padding
            "timeout": 60,       # Render timeout (seconds)
            "font_path": None,   # Custom font for text rendering (optional)
            "cjk_font": None     # CJK font for LaTeX (auto-detect: SimSun/PingFang SC/Noto Sans CJK SC)
        }
    }
})

# 2. Prepare test data
data = Data(
    data_id="test_1",
    image="test/images/formula.png",
    content="\\int_{0}^{\\infty} e^{-x^2} dx = \\frac{\\sqrt{\\pi}}{2}",
    content_type="equation"
)

# 3. Execute evaluation
result = VLMRenderJudge.eval(data)

# 4. View results
print(f"Score: {result.score}")
print(f"Label: {result.label}")
print(f"Reason:\n{chr(10).join(result.reason)}")
```

---

## 🔄 Integration with AgentIterativeOCR

VLMRenderJudge can serve as the **Judge component** in iterative OCR optimization:

```python
from dingo.model.llm.agent.agent_iterative_ocr import AgentIterativeOCR
from dingo.config.input_args import InputArgs

# Configure iterative OCR evaluation
args = InputArgs(
    input_path="test_data.jsonl",
    dataset={"source": "local", "format": "jsonl"},
    evaluator=[{
        "fields": {
            "image": "image",
            "content": "initial_ocr_result"
        },
        "evals": [{
            "name": "AgentIterativeOCR",
            "config": {
                "model": "gpt-4o",
                "key": "your-api-key",
                "api_url": "https://api.openai.com/v1",
                "parameters": {
                    "max_iterations": 3,
                    "content_type": "equation"
                }
            }
        }]
    }]
)
```

---

## 💡 Best Practices

1. **Choose appropriate content_type**
2. **Use reasonable batch_size** for batch evaluation
3. **Adjust temperature** for different strictness levels
4. **Save rendered images** for debugging
5. **Use streaming** for large datasets

---

## 📊 Metrics Interpretation

| Score | Meaning | Label | Action |
|-------|---------|-------|--------|
| 1.0 | Completely correct | QUALITY_GOOD | No action needed |
| 0.0 | Has errors | QUALITY_BAD_OCR.VISUAL_MISMATCH | Fix or re-OCR |
| 0.5 | Render failed | QUALITY_UNKNOWN.RENDER_FAILED | Check render environment |

---

## 🔗 Related Resources

- **Example Script**: `examples/ocr/vlm_render_judge.py`
- **Test Data**: `test/data/img_OCR_iterative/`
- **API Docs**: `dingo.model.llm.vlm_render_judge.VLMRenderJudge`
- **Related Tools**:
  - `RenderTool`: OCR content rendering
  - `AgentIterativeOCR`: Iterative OCR optimization
- **Reference**: [MinerU_Metis](https://github.com/opendatalab/MinerU) - Original Render-Judge implementation

---

## 📝 Changelog

- **v1.0** (2026-01): Initial release with text/equation/table support
- Aligned with MinerU_Metis Render-Judge pattern
- Supports standalone and Agent integration
