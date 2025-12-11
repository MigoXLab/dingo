# 图像标注质量评估与可视化工具使用指南

Dingo 提供了两种图像标注相关的评估与可视化工具，可帮助您：
- 检测图像标注中边界框的重叠情况（完全重叠/部分重叠）
- 生成带标注边界框和类别标签的可视化图像，辅助人工检查标注准确性

## 工具介绍

### RuleImageLabelOverlap：标注框重叠检测工具

#### 功能说明
该工具用于检测图像标注中边界框的重叠情况，具体功能包括：
- 识别并标记完全重叠（IOU≥0.9）和部分重叠（0.1≤IOU<0.9）的边界框对
- 统计重叠边界框的数量和比例
- 生成带有颜色标记的重叠区域可视化图像
- 输出详细的重叠检测结果

#### 核心参数
- `iou_partial_threshold`：部分重叠阈值（默认0.1），低于此值不视为重叠
- `iou_full_threshold`：完全重叠阈值（默认0.9），高于此值视为完全重叠
- `dynamic_config.refer_path`：可视化图像保存路径（默认`../../test/data/overlap_visual_image`）

#### 评估结果说明
工具返回的结果包含：
- `has_overlap`：是否存在符合阈值的重叠
- `overlap_stats`：重叠统计信息（完全重叠对数、部分重叠对数、总边界框数）
- `visualization_path`：可视化图像保存路径
- `error_status`：是否存在重叠（可用于标记异常数据）


### RuleImageLabelVisualization：标注可视化工具

#### 功能说明
该工具用于生成带有标注信息的可视化图像，具体功能包括：
- 绘制各类别标注的边界框
- 显示标注的类别标签
- 支持递归处理包含子元素的复杂标注结构
- 对不同类别使用预设或随机颜色进行区分
- 统计标注数量（总标注数和顶层标注数）

#### 核心参数
- `font_size`：标签字体大小（默认50）
- `color_map`：类别-颜色映射（预设了table、figure等常见类别）
- `dynamic_config.refer_path`：可视化图像保存路径（默认`../../test/data/label_visual_image`）

#### 支持的标注类型
工具可处理包含以下信息的标注数据：
- `poly`：多边形坐标（用于计算边界框）
- `category_type`：标注类别
- `line_with_spans`：包含子元素的复杂标注
- 自动过滤标记为"abandon"或包含"mask"的标注


## 文件结构

```

dingo/
├── dingo/                     # 核心代码目录
│   ├── model/                 # 模型与评估器目录
│   │   └── rule/              # 规则类评估器目录
│   │       └── rule_image.py  # 图像标注相关评估器实现
│   │           ├── class RuleImageLabelOverlap(BaseRule)  # 标注重叠检测
│   │           └── class RuleImageLabelVisualization(BaseRule)  # 标注可视化
├── examples/                  # 示例代码目录
│   └── image/                 # 图像规则相关示例
│       ├── sdk_image_label_overlap.py        # 标注重叠检测使用示例
│       ├── sdk_image_label_visualization.py  # 标注可视化使用示例
│       └── outputs/              # 结果报告
├── test/                  # 测试输入输出目录
│   └── data/                 # 图像相关数据
│       ├── image_label/        # 图片标注输入示例(含图片和标注数据json)
│       ├── overlap_visual_image/      # 重叠可视化输出示例
│       └──label_visual_image/             # 标签可视化输出示例
└── docs/                      # 文档目录



```


## 使用场景

### 场景一：检测图像的标注重叠情况

#### json数据示例：

```json

{"id": "0", "content": "{\"width\": 1958, \"height\": 2890, \"valid\": true, \"rotate\": 0, \"step_1\": {\"toolName\": \"rectTool\", \"dataSourceStep\": 0, \"result\": [{\"x\": 4.981718543237025, \"y\": 77.19413876889965, \"width\": 145.52294067118865, \"height\": 35.95272651876426, \"attribute\": \"abandon\", \"valid\": true, \"id\": \"nMlHKIW8\", \"sourceID\": \"\", \"textAttribute\": \"\", \"order\": 1}, {\"x\": 582.0452071564865, \"y\": 44.27276441450883, \"width\": 552.1299835355262, \"height\": 83.36740372434366, \"attribute\": \"abandon\", \"valid\": true, \"id\": \"pVn6KGgl\", \"sourceID\": \"\", \"textAttribute\": \"\", \"order\": 2}]}}", "img": "../../test/data/img_label/overlap_0.jpg"}


```

#### 工具位置:

```python

./dingo/model/rule/rule_image.py

class RuleImageLabelOverlap(BaseRule):

```

#### 执行示例：


```python
from dingo.config import InputArgs
from dingo.exec import Executor


def image_label_overlap():
    input_data = {
        "input_path": "../../test/data/img_label/test_img_label_overlap.jsonl",
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
            "rule_list": ["RuleImageLabelOverlap"],
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
    image_label_overlap()

```


### 场景二：生成图像的标注可视化

#### json数据示例：

```json

{"id": "0", "content": "{\"page_info\": {\"image_path\": \"visualization_0.png\", \"page_no\": 79, \"page_attribute\": {\"data_source\": \"other\", \"language\": \"en\", \"layout\": \"other\", \"with_watermark\": false}, \"width\": 4559, \"height\": 5996}, \"layout_dets\": [{\"category_type\": \"title\", \"anno_id\": 1, \"order\": 1, \"ignore\": false, \"poly\": [281.3333333333333, 417.3333333333333, 761.3333333333334, 417.3333333333333, 761.3333333333334, 489.3333333333333, 281.3333333333333, 489.3333333333333], \"line_with_spans\": [], \"attribute\": {\"text_language\": \"text_english\", \"text_background\": \"white\", \"text_rotate\": \"normal\"}, \"text\": \"Museum moves\"}, {\"category_type\": \"title\", \"anno_id\": 2, \"order\": 2, \"ignore\": false, \"poly\": [288, 517.3333333333334, 1322.6666666666667, 517.3333333333334, 1322.6666666666667, 657.3333333333334, 288, 657.3333333333334], \"line_with_spans\": [], \"attribute\": {\"text_language\": \"text_english\", \"text_background\": \"white\", \"text_rotate\": \"normal\"}, \"text\": \"What's in store?\"}]}}", "img": "../../test/data/img_label/visualization_0.png"}

```

#### 工具位置:

```python

./dingo/model/rule/rule_image.py

class RuleImageLabelVisualization(BaseRule):

```


#### 执行示例：

```python
from dingo.config import InputArgs
from dingo.exec import Executor


def image_label_overlap():
    input_data = {
        "input_path": "../../test/data/img_label/test_img_label_visualization.jsonl",
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
            "rule_list": ["RuleImageLabelVisualization"],
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
    image_label_overlap()



```



## 最佳实践

### 路径配置：
- 建议为不同工具设置独立的保存路径，避免可视化图像混淆
- 使用绝对路径可减少文件找不到的错误
- 确保保存目录有写入权限

### 阈值调整：
- 严格场景（如精确标注要求高的任务）可提高`iou_full_threshold`至 0.95
- 宽松场景可降低`iou_partial_threshold`至 0.05
- 根据业务需求调整重叠判断标准

### 颜色管理：
- 对于自定义类别，建议在`color_map`中预设颜色以保持一致性
- 重要类别使用高对比度颜色（如红色、蓝色）
- 相关类别使用相似色调（如不同深浅的蓝色）

### 结果分析：
- 定期检查重叠率高的图像，可能提示标注规范存在问题
- 结合两种工具的结果，先通过可视化确认标注质量，再通过重叠检测筛选异常
- 对批量处理结果进行统计分析，识别标注质量的整体趋势


## 技术细节

### 输出结果格式

#### RuleImageLabelOverlap 输出结果格式：

```python
ModelRes(
    name="RuleImageLabelOverlap" or "GOOD_IMG_LABEL",
    type="IMG_LABEL_OVERLAP" or "NO_LABEL_OVERLAP",
    error_status=True/False,  # 是否存在符合阈值的重叠
    reason=[json.dumps({
        "id": data_id,
        "has_overlap": True/False,
        "overlap_stats": {
            "full_overlap_pairs": 完全重叠框数量,
            "partial_overlap_pairs": 部分重叠框数量,
            "total_boxes": 总边界框数
        },
        "visualization_path": 图像保存路径
    })]
)
```

#### RuleImageLabelVisualization 输出结果格式：
```python
ModelRes(
    name="RuleImageLabelVisualization" or "NO_LABEL_DATA",
    type="IMG_LABEL_VISUALIZATION" or "NO_IMG_LABEL_VISUALIZATION",
    error_status=True/False,  # 是否发生错误
    reason=[json.dumps({
        "id": data_id,
        "visualization_status": "success",
        "original_image_path": 原始图像路径,
        "visualization_path": 可视化图像路径,
        "label_stats": {
            "total_labels": 总标注数,
            "top_level_labels": 顶层标注数
        }
    })]
)
```

## 错误处理与扩展建议

### 一、错误处理
常见错误及对应解决方法如下：
- **图像路径无效**：检查 `image` 字段是否正确指向图像文件，确保路径不存在拼写错误、文件未被移动或删除。
- **标注解析失败**：确保 `content` 字段内容为有效的 JSON 字符串或字典格式，可通过 JSON 校验工具验证格式正确性。
- **可视化生成失败**：先检查原始图像文件是否损坏（如无法正常打开），再确认保存可视化图像的目录有足够磁盘空间，避免因空间不足导致保存失败。
- **字体加载失败**：若默认字体路径无效，可更换 `font_path` 参数，使其指向系统中已存在的字体文件（如 Windows 系统的 `C:/Windows/Fonts/simsun.ttc`、Linux 系统的 `/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf`）。


### 二、扩展建议
1. **类别颜色扩展**：可根据业务场景中新增的标注类别，在 `color_map` 字典中补充预设颜色，确保同类标注在不同图像中颜色统一，提升可视化一致性。
2. **大规模数据处理优化**：针对大规模数据集（如万级以上图像），可增加多线程/多进程并行处理逻辑，或集成分布式计算框架（如 Spark），减少整体评估耗时。
3. **标注质量溯源**：结合标注人员 ID 信息，统计不同人员标注数据的重叠率差异，定位标注重叠率异常的人员，针对性开展标注规范培训，提升整体标注质量。


## 参考资料

1. [Dingo 文档](https://deepwiki.com/MigoXLab/dingo) - 完整的 API 文档和更多示例
