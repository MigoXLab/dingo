# VLMRenderJudge 快速开始

本目录包含 VLMRenderJudge（基于视觉渲染的 OCR 质量评估）的示例代码。

## 📁 文件说明

```
examples/ocr/
├── vlm_render_judge.py          # 独立的 VLMRenderJudge 测试脚本
├── test_agent_iterative_ocr.py  # AgentIterativeOCR 迭代优化示例
└── README_VLM_RENDER_JUDGE.md   # 本文件
```

## 🚀 快速运行

### 1. 准备环境

```bash
# 安装基础依赖
pip install dingo pillow

# 如果需要评估数学公式（可选）
# macOS
brew install mactex-no-gui imagemagick

# Ubuntu/Debian
sudo apt-get install texlive-xetex imagemagick
```

### 2. 设置 API Key

```bash
export OPENAI_API_KEY="your-api-key"
export OPENAI_BASE_URL="https://api.openai.com/v1"  # 可选
export OPENAI_MODEL="gpt-4o"                        # 可选
```

### 3. 运行测试

```bash
# 独立 OCR 质量评估
python examples/ocr/vlm_render_judge.py

# 迭代式 OCR 优化
python examples/ocr/test_agent_iterative_ocr.py
```

## 📊 测试数据

测试数据位于 `test/data/img_OCR_iterative/`:

```
test/data/img_OCR_iterative/
├── simple_text/
│   ├── english.png              # 英文文本测试图片
│   ├── numbers.png              # 数字和符号测试图片
│   └── mixed.png                # 混合内容测试图片
├── test_vlm_render_judge.jsonl  # VLMRenderJudge 测试数据
└── test_agent_iterative_ocr.jsonl  # AgentIterativeOCR 测试数据
```

### 测试数据格式

**test_vlm_render_judge.jsonl**:
```jsonl
{"image": "test/data/img_OCR_iterative/simple_text/english.png", "content": "The quick brown fox jumps over the lazy dog.", "content_type": "text", "expected_result": "correct"}
{"image": "test/data/img_OCR_iterative/simple_text/english.png", "content": "The quick brown fox jumps over the lzy dog.", "content_type": "text", "expected_result": "incorrect"}
```

## 📖 核心功能

### VLMRenderJudge - 独立评估

**功能**: 评估 OCR 结果的视觉准确性

**工作流程**:
1. 读取原始图片和 OCR 文本
2. 将 OCR 文本渲染为图片
3. VLM 比较两张图片
4. 输出评估结果 (score: 1.0=正确, 0.0=错误)

**示例输出**:
```
评估完成: 50.00%
正确数量: 3/6

Details:
- ID 1: ✅ score=1.0 (完全正确)
- ID 2: ❌ score=0.0 (拼写错误: lzy->lazy)
- ID 3: ✅ score=1.0 (完全正确)
...
```

### AgentIterativeOCR - 迭代优化

**功能**: 自动迭代改进 OCR 结果直到正确

**工作流程**:
1. **Judge**: VLMRenderJudge 判断当前 OCR 是否正确
2. **Refine**: 如果不正确，VLM 分析错误并生成改进版本
3. **Repeat**: 重复 1-2，直到正确或达到最大迭代次数

**示例输出**:
```
Iteration 1: ❌ OCR错误 → "lzy" 缺少字母 'a'
Iteration 2: ✅ 修正为 "lazy" → 验证正确！

最终结果: "The quick brown fox jumps over the lazy dog."
迭代次数: 2
```

## 🎯 使用场景

### 场景 1: 评估现有 OCR 系统

```python
from dingo.config.input_args import InputArgs
from dingo.exec import Executor

# 评估 PaddleOCR 的输出
args = InputArgs(
    input_path="paddle_ocr_results.jsonl",
    evaluator=[{
        "fields": {"image": "image", "content": "paddle_result"},
        "evals": [{"name": "VLMRenderJudge", "config": llm_config}]
    }]
)

summary = Executor.exec_map["local"](args).execute()
print(f"PaddleOCR 准确率: {summary.score:.2f}%")
```

### 场景 2: OCR 后处理优化

```python
# 对低质量 OCR 结果进行迭代优化
args = InputArgs(
    input_path="low_quality_ocr.jsonl",
    evaluator=[{
        "fields": {"image": "image", "content": "initial_ocr"},
        "evals": [{
            "name": "AgentIterativeOCR",
            "config": {
                "model": "gpt-4o",
                "key": "your-key",
                "parameters": {"max_iterations": 3}
            }
        }]
    }]
)

summary = Executor.exec_map["local"](args).execute()
# 输出优化后的 OCR 结果
```

### 场景 3: 数据集质量验证

```python
# 验证 OCR 训练数据集的标注质量
args = InputArgs(
    input_path="training_labels.jsonl",
    evaluator=[{
        "fields": {"image": "image", "content": "ground_truth"},
        "evals": [{"name": "VLMRenderJudge", "config": llm_config}]
    }]
)

summary = Executor.exec_map["local"](args).execute()
# 找出质量有问题的标注
bad_samples = [s for s in summary.details if s.score == 0.0]
```

## ⚙️ 配置说明

### 基础配置

```python
llm_config = {
    "model": "gpt-4o",           # VLM 模型
    "key": "your-api-key",       # API key
    "api_url": "https://api.openai.com/v1",
    "parameters": {
        "max_tokens": 4000,
        "temperature": 0         # 0=严格评估, 0.3=宽松评估
    }
}
```

### 渲染配置（可选）

```python
llm_config = {
    # ... 基础配置 ...
    "parameters": {
        # ... 其他参数 ...
        "render_config": {
            "density": 150,      # LaTeX DPI (72-300)
            "pad": 20,          # 图像边距
            "timeout": 60,      # 渲染超时（秒）
            "font_path": None   # 自定义字体（可选）
        }
    }
}
```

## 🔍 故障排查

### 问题 1: 渲染失败

```
score: 0.5
label: ['QUALITY_UNKNOWN.RENDER_FAILED']
```

**解决方案**: 安装 LaTeX 和 ImageMagick
```bash
brew install mactex-no-gui imagemagick  # macOS
```

### 问题 2: API 调用失败

```
[ERROR] Judge failed: Error code: 401
```

**解决方案**: 检查 API key 和 URL
```bash
echo $OPENAI_API_KEY          # 验证 key
curl $OPENAI_BASE_URL/models  # 测试连接
```

### 问题 3: 字体渲染问题

**症状**: 某些符号显示为 `?` 或 `□`

**解决方案**: 指定支持完整字符集的字体
```python
"render_config": {
    "font_path": "/System/Library/Fonts/Helvetica.ttc"  # macOS
}
```

## 📚 完整文档

- **使用指南**: [VLMRenderJudge 完整文档](../../docs/vlm_render_judge_guide.md)
- **API 文档**: `dingo.model.llm.vlm_render_judge.VLMRenderJudge`
- **相关工具**: `dingo.model.llm.agent.agent_iterative_ocr.AgentIterativeOCR`

## 🤝 反馈与贡献

如有问题或建议，欢迎：
- 提交 Issue: [GitHub Issues](https://github.com/MigoXLab/dingo/issues)
- 参与讨论: Dingo 用户群
- 贡献代码: Pull Requests
