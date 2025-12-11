# PromptMinerURecognizeQuality 文档解析OCR和格式问题评估工具 使用文档

Dingo 提供了一种基于LLM的文档OCR解析质量评估工具，可帮助您：
- 评估文档解析模型输出质量
- 生成模型质量报告

## 工具介绍

### PromptMinerURecognizeQuality：文档OCR解析评估工具

#### 功能说明
该工具用于评估文档解析模型效果，具体功能包括：
- 定义了公式、表格、分行分段、列表项、代码项等维度的文档解析错误类别
- 对比原始文档的gt_markdown以及模型解析后的md结果
- 从端到端的维度识别模型存在的错误，并报告错误类型和原因
- 输出详细的评估报告

#### 技术细节
##### 文件结构

```
dingo/
  ├── model/
  │   ├── llm/
  │   │   └── vlm_document_parsing.py         # 评估器实现
  │   └── prompt/
  │       └── prompt_mineru_recognize.py      # 评估提示词
  │── examples/
  │   └── document_parser/
  │       └── document_parsing_quality_ocr.py  # 单条评估示例
  └── test/                  # 测试输入输出目录
      └── data/                 # 图像相关数据
        ├── test_document_OCR_recognize.jsonl      # 输入的jsonl示例
```

##### 评估提示词
我们的评估效果依赖于精心设计的 Prompt。其核心思想是：

1. 分层错误标签：我们将文档解析问题分为6个大类（一级标签），如公式、表格、OCR识别等。每个大类下又细分了具体的二级标签，以实现更精确的错误归因。
2. 结构化输出：我们要求 LLM 模型为每个文档生成一个结构化的 JSON 报告，直接对应于上文提到的输出格式，便于程序化处理。


#### 输入数据格式

```python
input_data = {
        "input_path": "../../test/data/test_document_OCR_recognize.jsonl",
        "dataset": {
            "source": "local",
            "format": "jsonl",
            "field": {
                "id": "id",
                "content": "pred_content",
                "prompt": "gt_markdown",
            }
        },
        "executor": {
            "prompt_list": ["PromptMinerURecognizeQuality"],
            "result_save": {
                "bad": True,
                "good": True
            }
        },
        "evaluator": {
            "llm_config": {
                "LLMMinerURecognizeQuality": {
                    "key": "",
                    "api_url": "",
                }
            }
        }
    }
```

#### 输出结果格式

```python
# result 是 ModelRes 对象，包含以下字段：
result.type          # 错误问题一级标签: prompt中定义的一级错误大类
result.name          # 错误问题二级标签: 一级错误大类对应的详细错误标签 List[str]
result.error_status  # 错误状态: False 或 True
result.reason        # 评估原因: List[str]
```


## 使用示例

### 基础用法

```python
from dingo.config import InputArgs
from dingo.exec import Executor

if __name__ == '__main__':
    input_data = {
        "input_path": "../../test/data/test_document_OCR_recognize.jsonl",
        "dataset": {
            "source": "local",
            "format": "jsonl",
            "field": {
                "id": "id",
                "content": "pred_content",
                "prompt": "gt_markdown",
            }
        },
        "executor": {
            "prompt_list": ["PromptMinerURecognizeQuality"],
            "result_save": {
                "bad": True,
                "good": True
            }
        },
        "evaluator": {
            "llm_config": {
                "LLMMinerURecognizeQuality": {
                    "key": "",
                    "api_url": "",
                }
            }
        }
    }
    input_args = InputArgs(**input_data)
    executor = Executor.exec_map["local"](input_args)
    result = executor.execute()
    print(result)

```

### JSONL数据格式

```jsonl
示例请查看test/data/test_document_OCR_recognize.jsonl
```


## 最佳实践
### 评估模型
务必使用LLM模型：
此工具的原理是将图片和文本同时输入给模型进行对比评估。因此，必须使用支持多模态输入的 LLM（视觉语言模型），否则模型将无法处理图片输入。


## 完整示例

### 评估示例
参考: `examples/document_parser/document_parsing_quality_ocr.py`

### 测试数据
参考: `test/data/test_document_OCR_recognize.jsonl`


## 参考资料

1. [Dingo 文档](https://deepwiki.com/MigoXLab/dingo) - 完整的 API 文档和更多示例
