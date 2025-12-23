# Excel 数据集读取功能说明

## 功能概述

Dingo 现已支持 Excel 文件的流式读取，同时支持 `.xlsx` 和 `.xls` 两种格式，提供完整的 Excel 数据处理能力。

## 主要特性

✅ **流式读取** - 使用只读模式加载工作簿，逐行处理，适合大文件  
✅ **多种格式** - 同时支持 `.xlsx`（使用 openpyxl）和 `.xls`（使用 xlrd）格式  
✅ **多工作表** - 支持通过索引或名称选择指定工作表  
✅ **灵活列名** - 支持带/不带列名的 Excel，自动使用数字索引格式  
✅ **自动类型** - 自动处理数字、文本、日期等多种数据类型  
✅ **空值处理** - 正确处理空单元格、空行等特殊情况  

## 配置参数

### DatasetExcelArgs 参数说明

```python
class DatasetExcelArgs(BaseModel):
    sheet_name: str | int = 0        # 工作表索引或名称
    has_header: bool = True          # 第一行是否为列名
```

### 参数详解

| 参数 | 类型 | 默认值 | 说明 |
|------|-----|--------|------|
| `sheet_name` | str|int | 0 | 工作表选择。整数表示索引（从0开始），字符串表示工作表名称 |
| `has_header` | bool | True | 第一行是否为列名。False 时使用 `0`, `1`, `2` 等数字作为列名 |

## 使用示例

### 1. 标准 Excel（带列名，第一个工作表）

```python
from dingo.config import InputArgs
from dingo.exec import Executor

input_data = {
    "input_path": "data.xlsx",
    "dataset": {
        "source": "local",
        "format": "excel",
        "excel_config": {
            "sheet_name": 0,
            "has_header": True,
        }
    },
    "evaluator": [
        {
            "fields": {"id":"id", "content": "content"},
            "evals": [
                {"name": "RuleColonEnd"}
            ]
        }
    ]
}

input_args = InputArgs(**input_data)
executor = Executor.exec_map["local"](input_args)
result = executor.execute()
```

### 2. 无列名 Excel

```python
"excel_config": {
    "sheet_name": 0,
    "has_header": False,  # 第一行不是列名
}
# 数据将使用 0, 1, 2, 3 等作为列名
```

### 3. 通过索引选择工作表

```python
"excel_config": {
    "sheet_name": 1,  # 读取第二个工作表（索引从0开始）
    "has_header": True,
}
```

### 4. 通过名称选择工作表

```python
"excel_config": {
    "sheet_name": "销售数据",  # 使用工作表名称
    "has_header": True,
}
```

### 5. 读取 .xls 格式文件

```python
input_data = {
    "input_path": "data.xls",  # 旧版 Excel 格式
    "dataset": {
        "source": "local",
        "format": "excel",
        "excel_config": {
            "sheet_name": 0,
            "has_header": True,
        }
    },
    # ... 其他配置
}
```

## 运行测试

```bash
# 使用 conda 环境运行测试
conda activate dingo
python test/scripts/dataset/test_excel_dataset.py
```

## 数据格式

Excel 文件的每一行会被转换为 JSON 格式，列名作为 JSON 的键：

**Excel 文件:**

| 参数 | 类型 | 默认值 |
|------|-----|--------|
| 1  | 测试数据 | good  |
| 2  | 第二条   | bad   |

**转换后的 JSON:**
```json
{"id": 1, "content": "测试数据", "label": "good"}
{"id": 2, "content": "第二条", "label": "bad"}
```

**无列名时（has_header=False）:**
```json
{"0": 1, "1": "测试数据", "2": "good"}
{"0": 2, "1": "第二条", "2": "bad"}
```

## 特殊情况处理

### 1. 多个工作表

Excel 文件可以包含多个工作表，使用 `sheet_name` 参数选择：

```python
# 方式1: 通过索引选择
"sheet_name": 0  # 第一个工作表
"sheet_name": 1  # 第二个工作表

# 方式2: 通过名称选择
"sheet_name": "Sheet1"
"sheet_name": "销售数据"
```

### 2. 空值处理

空单元格会转换为空字符串：

| id | content | label |
|----|---------|-------|
| 1  |         | good  |

转换为：
```json
{"id": 1, "content": "", "label": "good"}
```

### 3. 空行跳过

完全空的行会被自动跳过，不会出现在输出中。

### 4. 数据类型自动转换

Excel 的各种数据类型会自动转换：
- **数字**: 保持为数字类型（整数或浮点数）
- **文本**: 保持为字符串
- **日期**: 转换为 Python datetime 对象的字符串表示
- **公式**: 读取计算后的值（使用 `data_only=True`）

### 5. 列名缺失或重复

如果标题行中有空单元格，会自动使用 `Column_x` 格式：

| name | | age |
|------|---|-----|
| 张三 | 25 | 北京 |

转换为：
```json
{"name": "张三", "Column_1": "25", "age": "北京"}
```

## 性能特性

### 流式读取
- 使用 `openpyxl` 的只读模式（`read_only=True`）和 `xlrd` 的按需加载（`on_demand=True`）
- 逐行处理，不会一次性加载整个文件到内存
- 适合处理几十 MB 到几百 MB 的大型 Excel 文件
- 可以在处理过程中随时中断，不影响性能

### 内存占用
- 只保存当前处理的一行数据
- 对大文件非常友好
- 相比一次性加载整个工作簿，内存占用大幅降低


## 依赖库

### .xlsx 格式 (推荐)
```bash
pip install openpyxl
```

### .xls 格式（旧版 Excel）
```bash
pip install xlrd
```

### 完整安装
```bash
# 同时支持两种格式
pip install openpyxl xlrd
```

## 支持的 Excel 格式

| 格式 | 依赖库 | 说明 |
|------|--------|------|
| .xlsx | openpyxl | Excel 2007+ 标准格式，推荐使用 |
| .xls | xlrd | Excel 97-2003 旧格式 |

## 技术实现

### 核心文件
1. `dingo/config/input_args.py` - 配置参数定义
2. `dingo/data/datasource/local.py` - Excel 文件读取逻辑
   - `_load_excel_file_xlsx()` - 处理 .xlsx 格式
   - `_load_excel_file_xls()` - 处理 .xls 格式
3. `dingo/data/converter/base.py` - Excel 数据转换器

## 故障排查

### 缺少依赖库
```
RuntimeError: openpyxl is missing. Please install it using: pip install openpyxl
```
**解决方案：** 
```bash
pip install openpyxl  # 用于 .xlsx 文件
pip install xlrd      # 用于 .xls 文件
```

### 工作表不存在
```
RuntimeError: Sheet "数据表" not found in Excel file. Available sheets: ['Sheet1', 'Sheet2']
```
**解决方案：** 检查工作表名称是否正确，或使用数字索引（从0开始）

### 工作表索引越界
```
RuntimeError: Sheet index 3 out of range. Total sheets: 2
```
**解决方案：** 检查工作表索引是否正确，记住索引从 0 开始

### 空文件错误
```
RuntimeError: Excel file "data.xlsx" is empty
```
**解决方案：** 检查文件是否为空或第一个工作表是否包含数据

### 文件格式错误
```
RuntimeError: Failed to read .xlsx file "data.xlsx": ...
```
**解决方案：** 
1. 确认文件是有效的 Excel 文件
2. 尝试在 Excel 中打开并另存为新文件
3. 检查文件是否损坏


## 相关文档
- [数据集配置文档](../config.md)
- [评估器配置文档](../rules.md)

## 示例代码

完整的示例代码可以在以下位置找到：
- `examples/dataset/excel.py` - 基本使用示例
- `test/scripts/dataset/test_excel_dataset.py` - 完整测试用例

