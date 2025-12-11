# VLMDocumentParsingQuality 文档解析评估工具 使用文档

Dingo 提供了一种基于VLM的文档解析质量评估与可视化工具，可帮助您：
- 评估文档解析模型输出质量
- 生成模型质量报告

## 工具介绍

### VLMDocumentParsingQuality：文档解析评估工具

#### 功能说明
该工具用于评估文档解析模型效果，具体功能包括：
- 定义了公式、表格、O分行分段、列表项、代码项、OCR、阅读顺序等维度的文档解析错误类别
- 对比原始文档以及模型解析后的md结果
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
  │       └── prompt_document_parsing.py      # 评估提示词
  │── examples/
  │   └── document_parser/
  │       └── vlm_document_parser_quality.py  # 单条评估示例
  └── test/                  # 测试输入输出目录
      └── data/                 # 图像相关数据
        ├── test_img_md.jsonl      # 输入的jsonl示例
        └── c6be64e4-1dd4-4bd4-b923-55a63a6de397_page_1.jpg     # 输入的示例图片
```

##### 评估提示词
我们的评估效果依赖于精心设计的 Prompt。其核心思想是：

1. 分层错误标签：我们将文档解析问题分为10个大类（一级标签），如公式、表格、OCR识别等。每个大类下又细分了具体的二级标签，以实现更精确的错误归因。
2. 结构化输出：我们要求 VLM 模型为每张图片生成一个结构化的 JSON 报告，直接对应于上文提到的输出格式，便于程序化处理。


#### 输入数据格式

```python
input_data = {
        "input_path": "/path/to/your/input.jsonl",
        "dataset": {
            "source": "local",
            "format": "image",
            "field": {
                "id": "id",
                "content": "content", # 模型解析的markdown结果
                "image": "img"        # 需要解析的image图片
            }
        },
        "executor": {
            "prompt_list": ["PromptDocumentParsingQuality"],
            "result_save": {
                "bad": True,
                "good": True
            }
        },
        "evaluator": {
            "llm_config": {
                "VLMDocumentParsingQuality": {
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
    # 准备数据
    input_data = {
        "input_path": "../../test/data/test_img_md.jsonl",
        "dataset": {
            "source": "local",
            "format": "image",
            "field": {
                "id": "id",
                "content": "content",
                "image": "img"
            }
        },
        "executor": {
            "prompt_list": ["PromptDocumentParsingQuality"],
            "result_save": {
                "bad": True,
                "good": True
            }
        },
        "evaluator": {
            "llm_config": {
                "VLMDocumentParsingQuality": {
                    "key": "",
                    "api_url": "",
                }
            }
        }
    }
    input_args = InputArgs(**input_data)
    executor = Executor.exec_map["local"](input_args)

    # 执行评估
    result = executor.execute()

    # 查看结果
    print(result)
```

### JSONL数据格式

```jsonl
{"id": "1", "content": "content xxx", "img": "path/to/your/image.jpg"}
```
id: 数据id，可以自定义
content：带质检的文本
img：图片路径

## 最佳实践
### 评估模型
1. 务必使用VLM模型：
此工具的原理是将图片和文本同时输入给模型进行对比评估。因此，必须使用支持多模态输入的 VLM（视觉语言模型），否则模型将无法处理图片输入。
2. 推荐使用高性能VLM：
推荐使用Gemini 2.5 Pro 这样先进的 VLM。更强大的模型在图像理解、空间关系识别和细微错误发现方面表现更出色，能提供更准确、更可靠的评估结果。

## 完整示例

### 评估示例
参考: `examples/document_parser/vlm_document_parser_quality.py`

### 测试数据
参考: `test/data/test_img_md.jsonl`


## 参考资料

1. [Dingo 文档](https://deepwiki.com/MigoXLab/dingo) - 完整的 API 文档和更多示例
