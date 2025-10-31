# 图像质量评估工具使用指南

## 1. 概述

本文档详细介绍了 Dingo 框架中的图像质量评估工具，包含五个核心规则：
- RuleImageValid：无效图像检测
- RuleImageSizeValid：图像尺寸验证
- RuleImageQuality：图像清晰度质量评估
- RuleImageRepeat：重复图像检测
- RuleImageTextSimilarity：图像文本语义相似度评估

这些工具旨在帮助用户全面评估数据集中图像的质量，识别各种潜在问题，并提供可配置的评估标准和详细报告。

## 2. 工具列表与功能说明

### 2.1 RuleImageValid - 无效图像检测

**功能说明**：检测数据集中无效的图像文件，包括无法打开、损坏或格式不受支持的图像，以及全白或全黑的图像。

**核心参数**：
- 无特定配置参数，使用默认配置即可

**评估结果**：
- `error_status`：布尔值，表示图像是否无效
- `reason`：详细错误信息，如"Image is not valid: all white or black"

**支持的图像格式**：
- JPEG/JPG
- PNG
- BMP
- GIF
- WEBP
- 其他标准图像格式

### 2.2 RuleImageSizeValid - 图像尺寸验证

**功能说明**：验证图像的尺寸是否符合指定的要求，可配置最小和最大尺寸限制，以及宽高比例范围。

**核心参数**：
- 默认有效宽高比范围为0.25-4（即图像不能过于狭长或过短过宽）

**评估结果**：
- `error_status`：布尔值，表示图像尺寸是否无效
- `reason`：详细错误信息，包含具体的宽高比值

### 2.3 RuleImageQuality - 图像清晰度质量评估

**功能说明**：使用神经网络图像评估方法(NIMA)对图像质量进行评分，评估图像的清晰度和视觉质量。

**核心参数**：
- `threshold`：质量评分阈值（默认5.5），低于此值的图像被标记为低质量

**评估结果**：
- `error_status`：布尔值，表示图像质量是否不满足要求
- `reason`：详细错误信息，包含具体的质量评分（1-10分）

### 2.4 RuleImageRepeat - 重复图像检测

**功能说明**：检测目录中是否存在重复或高度相似的图像，使用PHash和CNN两种方法进行综合判断。

**核心参数**：
- CNN方法默认使用0.97作为相似度阈值
- 需通过content字段提供图像目录路径

**评估结果**：
- `error_status`：布尔值，表示是否存在重复图像
- `reason`：包含重复图像对的列表和重复率

### 2.5 RuleImageTextSimilarity - 图像文本语义相似度评估

**功能说明**：评估图像内容与描述文本之间的语义相关性，使用CLIP模型计算相似度得分。

**核心参数**：
- `threshold`：相似度阈值（默认0.17），低于此值认为图像与文本相关性不足
- `refer_path`：可选，CLIP模型路径，如未指定将自动下载

**评估结果**：
- `error_status`：布尔值，表示图像与文本相似度是否不足
- `reason`：详细错误信息，包含具体的相似度得分

## 3. 文件结构

```
dingo/
├── dingo/                     # 核心代码目录
│   ├── model/                 # 模型与评估器目录
│   │   └── rule/              # 规则类评估器目录
│   │       └── rule_image.py  # 图像质量相关评估器实现
│   │           ├── class RuleImageValid(BaseRule)          # 无效图像检测
│   │           ├── class RuleImageSizeValid(BaseRule)      # 图像尺寸验证
│   │           ├── class RuleImageQuality(BaseRule)        # 图像质量评估
│   │           ├── class RuleImageRepeat(BaseRule)         # 重复图像检测
│   │           └── class RuleImageTextSimilarity(BaseRule) # 图像文本相似度
├── examples/                  # 示例代码目录
│   └── image/                 # 图像规则相关示例
│       ├── sdk_image.py       # 图像质量评估使用示例
│       └── outputs/           # 结果报告
├── test/                      # 测试输入输出目录
│   └── data/                  # 图像相关数据
│       ├── img_builtin/       # 内置图像测试数据
│       └── test_local_img.jsonl # 测试数据配置
└── docs/                      # 文档目录
```

## 4. 使用场景

### 场景一：评估单个图像的基本质量

#### json数据示例：

```json
{"id": "0", "img": "../../test/data/img_builtin/valid_image.jpg"}
```

#### 工具位置:

```python
./dingo/model/rule/rule_image.py

class RuleImageValid(BaseRule):
class RuleImageSizeValid(BaseRule):
class RuleImageQuality(BaseRule):
```

#### 执行示例：

```python
from dingo.config import InputArgs
from dingo.exec import Executor


def image_quality():
    input_data = {
        "input_path": "../../test/data/test_local_img.jsonl",
        "dataset": {
            "source": "local",
            "format": "image",
            "field": {
                "id": "id",
                "image": "img"
            }
        },
        "executor": {
            "rule_list": ["RuleImageValid", "RuleImageSizeValid", "RuleImageQuality"],
            "result_save": {
                "bad": True,
                "good": True
            }
        }
    }
    input_args = InputArgs(**input_data)
    executor = Executor.exec_map["local"](input_args)
    result = executor.execute()
    print(result)


if __name__ == '__main__':
    image_quality()
```

### 场景二：检测图像目录中的重复图像

#### json数据示例：

```json
{"id": "0", "content": "../../test/data/img_builtin/"}
```

#### 工具位置:

```python
./dingo/model/rule/rule_image.py

class RuleImageRepeat(BaseRule):
```

#### 执行示例：

```python
from dingo.config import InputArgs
from dingo.exec import Executor


def image_repeat():
    input_data = {
        "input_path": "../../test/data/test_local_img_repeat.jsonl",
        "dataset": {
            "source": "local",
            "format": "jsonl",
            "field": {
                "id": "id",
                "content": "content"
            }
        },
        "executor": {
            "rule_list": ["RuleImageRepeat"],
            "result_save": {
                "bad": True,
                "good": True
            }
        }
    }
    input_args = InputArgs(**input_data)
    executor = Executor.exec_map["local"](input_args)
    result = executor.execute()
    print(result)


if __name__ == '__main__':
    image_repeat()
```

### 场景三：评估图像与文本的相关性

#### json数据示例：

```json
{"id": "0", "content": "cat sitting on a chair", "img": "../../test/data/img_builtin/cat.jpg"}
```

#### 工具位置:

```python
./dingo/model/rule/rule_image.py

class RuleImageTextSimilarity(BaseRule):
```

#### 执行示例：

```python
from dingo.config import InputArgs
from dingo.exec import Executor


def image_text_similarity():
    input_data = {
        "input_path": "../../test/data/test_local_img_text.jsonl",
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
            "rule_list": ["RuleImageTextSimilarity"],
            "evaluator": {
                "rule_config": {
                    "RuleImageTextSimilarity": {
                        "threshold": 0.2  # 自定义阈值
                    }
                }
            },
            "result_save": {
                "bad": True,
                "good": True
            }
        }
    }
    input_args = InputArgs(**input_data)
    executor = Executor.exec_map["local"](input_args)
    result = executor.execute()
    print(result)


if __name__ == '__main__':
    image_text_similarity()
```

## 5. 最佳实践

### 5.1 配置建议
- 对于高质量图像要求的场景，可提高`RuleImageQuality`的阈值至6.5
- 对于特定应用场景（如文档扫描），可调整`RuleImageSizeValid`的宽高比范围
- 对于图像-文本匹配严格的场景（如多模态训练），可提高`RuleImageTextSimilarity`的阈值至0.3

### 5.2 批量处理策略
- 对于大规模图像处理，建议先使用轻量级规则（如RuleImageValid和RuleImageSizeValid）进行初步过滤
- 再使用计算密集型规则（如RuleImageQuality和RuleImageTextSimilarity）进行深入评估
- 对于重复检测，建议对整个数据集进行批量处理，而非单个图像

### 5.3 结果整合策略
- 结合多个评估规则的结果，可以获得更全面的图像质量评估
- 对于不同质量维度的优先级，可以设置不同的权重
- 建立图像质量评分系统，综合多个规则的评估结果

## 6. 参考示例

完整的综合使用示例可在以下文件中找到：
- `examples/image/sdk_image.py`：展示基本的图像规则使用示例
- `examples/image/sdk_image_repeat.py`：展示图像重复规则使用示例
- `examples/image/sdk_image_text_similar.py`：展示图像文本语义相似度评估使用示例

请根据实际需求修改和调整这些示例代码。

## 7. 评估报告详解

### 7.1 报告格式

评估完成后，系统会生成详细的评估报告，包含以下信息：

- **总体统计**：
  - 数据总量
  - 高质量数据数量
  - 低质量数据数量
  - 总体得分

- **问题类型分布**：
  - 按规则分类的问题数量和比例
  - 每种规则检测到的具体问题类型统计

- **问题详情**：
  - 每条低质量数据的具体问题描述
  - 相关评分和阈值信息
  - 建议的处理方式

### 7.2 报告示例

```json
{
  "summary": {
    "score": 0.85,
    "total": 1000,
    "good": 850,
    "bad": 150,
    "type_ratio": {
      "RuleImageValid": 0.05,
      "RuleImageSizeValid": 0.08,
      "RuleImageQuality": 0.12,
      "RuleImageRepeat": 0.25,
      "RuleImageTextSimilarity": 0.5
    }
  },
  "bad_info": [
    {
      "id": "001",
      "img": "/path/to/corrupt.jpg",
      "error_type": "RuleImageValid",
      "error_message": "无法打开图像文件"
    },
    {
      "id": "002",
      "img": "/path/to/small.jpg",
      "error_type": "RuleImageSizeValid",
      "width": 50,
      "height": 50,
      "min_width": 100,
      "min_height": 100
    },
    {
      "id": "003",
      "img": "/path/to/blur.jpg",
      "error_type": "RuleImageQuality",
      "quality_score": 8.5,
      "threshold": 7.0
    },
    {
      "id": "004",
      "content": "一只狗在跑步",
      "img": "/path/to/cat.jpg",
      "error_type": "RuleImageTextSimilarity",
      "similarity_score": 0.12,
      "threshold": 0.17
    }
  ]
}
```

## 8. 高级配置与优化

### 8.1 自定义阈值设置

每个规则都支持自定义阈值，以适应不同的数据质量需求：

- **RuleImageQuality**：
  - 高质量要求：提高阈值至6.5
  - 一般要求：使用默认值5.5
  - 宽松要求：降低阈值至4.5

- **RuleImageTextSimilarity**：
  - 严格匹配：提高阈值至0.3
  - 一般匹配：使用默认值0.17
  - 宽松匹配：降低阈值至0.1

### 8.2 性能优化建议

- **批量处理**：对于大规模数据集，可适当调整批处理大小以提高效率
- **GPU加速**：对于RuleImageQuality和RuleImageTextSimilarity，可在有GPU环境下配置CUDA使用
- **内存管理**：对于RuleImageRepeat，处理大量图像时需注意内存使用

## 9. 常见问题解答

### 9.1 RuleImageTextSimilarity 首次运行速度慢

**问题**：首次运行时下载CLIP模型较慢

**解决方案**：
- 确保网络连接稳定
- 可以预先下载模型并通过refer_path参数指定本地路径

### 9.2 RuleImageQuality 依赖问题

**问题**：运行时提示缺少NIMA相关依赖

**解决方案**：
- 安装所需依赖：`pip install -r requirements/optional.txt`

### 9.3 RuleImageRepeat 检测不到相似图像

**问题**：检测结果显示没有重复图像，但实际上应该存在重复

**解决方案**：
- 检查图像目录路径是否正确
- 尝试调整相似度阈值

## 10. 技术细节

### 10.1 核心代码结构

图像质量评估规则的核心代码位于 `dingo/model/rule/rule_image.py` 文件中，主要包含以下类：

- **RuleImageValid**: 验证图像文件是否有效
- **RuleImageSizeValid**: 验证图像尺寸是否符合要求
- **RuleImageQuality**: 评估图像质量分数
- **RuleImageRepeat**: 检测重复或高度相似的图像
- **RuleImageTextSimilarity**: 评估图像与文本的语义相似度

所有规则类都继承自 `BaseRule`，遵循统一的接口规范。

### 10.2 输出结果格式

#### RuleImageValid 输出结果格式：

```python
ModelRes(
    name="RuleImageValid",
    type="QUALITY_BAD_IMG_EFFECTIVENESS",
    error_status=True/False,  # 是否为无效图像
    reason=["Image is not valid: all white or black"]  # 错误原因
)
```

#### RuleImageSizeValid 输出结果格式：
```python
ModelRes(
    name="RuleImageSizeValid",
    type="QUALITY_BAD_IMG_EFFECTIVENESS",
    error_status=True/False,  # 图像尺寸是否无效
    reason=["Image size is not valid, the ratio of width to height: 比值"]  # 错误原因
)
```

#### RuleImageQuality 输出结果格式：
```python
ModelRes(
    name="RuleImageQuality",
    type="QUALITY_BAD_IMG_EFFECTIVENESS",
    error_status=True/False,  # 图像质量是否不满足要求
    reason=["Image quality is not satisfied, ratio: 评分值"]  # 错误原因
)
```

#### RuleImageRepeat 输出结果格式：
```python
ModelRes(
    name="RuleImageRepeat",
    type="QUALITY_BAD_IMG_SIMILARITY",
    error_status=True/False,  # 是否存在重复图像
    reason=["图像1 -> [重复图像列表]", ..., {"duplicate_ratio": 重复率}]
)
```

#### RuleImageTextSimilarity 输出结果格式：
```python
ModelRes(
    name="RuleImageTextSimilarity",
    type="QUALITY_BAD_IMG_RELEVANCE",
    error_status=True/False,  # 图像与文本相似度是否不足
    reason=["Image quality is not satisfied, ratio: 相似度值"]  # 错误原因
)
```

## 11. 错误处理

常见错误及对应解决方法如下：
- **图像路径无效**：检查 `image` 字段是否正确指向图像文件，确保路径不存在拼写错误、文件未被移动或删除。
- **模型加载失败**：对于RuleImageQuality和RuleImageTextSimilarity，确保已安装相关依赖（pyiqa、similarities等），并检查网络连接是否正常。
- **CUDA内存不足**：对于RuleImageQuality，可设置使用CPU进行评估，通过修改代码中的device设置。
- **目录权限问题**：对于RuleImageRepeat，确保对图像目录有读取权限，且目录不为空。

## 12. 参考资料

1. [Dingo 文档](https://deepwiki.com/MigoXLab/dingo) - 完整的 API 文档和更多示例
