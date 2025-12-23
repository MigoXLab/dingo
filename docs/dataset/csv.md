# CSV 数据集读取功能说明

## 功能概述

Dingo 现已支持 CSV 文件的流式读取，提供完整的 CSV 数据处理能力。

## 主要特性

✅ **流式读取** - 使用 Python 标准库 `csv` 包，逐行处理，适合大文件  
✅ **多种格式** - 支持不同的 CSV 方言（excel、excel-tab、unix 等）  
✅ **多种编码** - 支持 UTF-8、GBK、GB2312、Latin1 等编码  
✅ **灵活列名** - 支持带/不带列名的 CSV，自动使用 `column_x` 格式  
✅ **自定义分隔符** - 支持逗号、分号、Tab 等任意分隔符  
✅ **特殊字符处理** - 正确处理引号、逗号、多行内容等特殊情况  

## 配置参数

### DatasetCsvArgs 参数说明

```python
class DatasetCsvArgs(BaseModel):
    has_header: bool = True           # 第一行是否为列名
    encoding: str = 'utf-8'           # 文件编码
    dialect: str = 'excel'            # CSV 格式方言
    delimiter: str | None = None      # 自定义分隔符
    quotechar: str = '"'              # 引号字符
```

### 参数详解

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `has_header` | bool | True | 第一行是否为列名。False 时使用 `column_0`, `column_1` 等 |
| `encoding` | str | 'utf-8' | 文件编码，支持 utf-8、gbk、gb2312、latin1 等 |
| `dialect` | str | 'excel' | CSV 格式：excel（逗号）、excel-tab（Tab）、unix 等 |
| `delimiter` | str\|None | None | 自定义分隔符，优先级高于 dialect |
| `quotechar` | str | '"' | 引号字符 |

## 使用示例

### 1. 标准 CSV（逗号分隔，带列名）

```python
from dingo.config import InputArgs
from dingo.exec import Executor

input_data = {
    "input_path": "data.csv",
    "dataset": {
        "source": "local",
        "format": "csv",
        "csv_config": {
            "has_header": True,
            "encoding": "utf-8",
            "dialect": "excel",
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

### 2. 无列名 CSV

```python
"csv_config": {
    "has_header": False,  # 第一行不是列名
    "encoding": "utf-8",
}
# 数据将使用 column_0, column_1, column_2 等作为列名
```

### 3. Tab 分隔的 CSV

```python
"csv_config": {
    "has_header": True,
    "dialect": "excel-tab",  # Tab 分隔格式
}
```

### 4. 自定义分隔符（分号）

```python
"csv_config": {
    "has_header": True,
    "delimiter": ";",  # 使用分号分隔
}
```

### 5. GBK 编码（中文 Windows）

```python
"csv_config": {
    "has_header": True,
    "encoding": "gbk",  # GBK 编码
}
```

## 运行测试

```bash
# 使用 conda 环境运行测试
conda activate dingo
python test/scripts/dataset/test_csv_dataset.py
```

## 数据格式

CSV 文件的每一行会被转换为 JSON 格式，列名作为 JSON 的键：

**CSV 文件:**
```csv
id,content,label
1,测试数据,good
2,第二条,bad
```

**转换后的 JSON:**
```json
{"id": "1", "content": "测试数据", "label": "good"}
{"id": "2", "content": "第二条", "label": "bad"}
```

**无列名时（has_header=False）:**
```json
{"column_0": "1", "column_1": "测试数据", "column_2": "good"}
{"column_0": "2", "column_1": "第二条", "column_2": "bad"}
```

## 特殊情况处理

### 1. 包含逗号的内容
CSV 标准会自动用引号包裹：
```csv
id,content
1,"包含逗号,的内容"
```

### 2. 包含引号的内容
使用双引号转义：
```csv
id,content
1,"包含""引号""的内容"
```

### 3. 多行内容
CSV 标准支持多行内容：
```csv
id,content
1,"第一行
第二行"
```

### 4. 空值处理
空单元格会转换为空字符串：
```csv
id,content,label
1,,good
```
转换为：
```json
{"id": "1", "content": "", "label": "good"}
```

## 性能特性

### 流式读取
- 使用 `csv.reader` 逐行读取，不会一次性加载整个文件到内存
- 适合处理几 GB 的大型 CSV 文件
- 可以在处理过程中随时中断，不影响性能

### 内存占用
- 只保存当前处理的一行数据
- 对大文件非常友好
- 测试表明可以流畅处理包含数百万行的 CSV 文件

## 常见编码

| 编码 | 使用场景 |
|------|----------|
| utf-8 | 默认编码，支持所有语言 |
| gbk | 中文 Windows 系统常用 |
| gb2312 | 简体中文旧标准 |
| latin1 | 西欧语言 |
| iso-8859-1 | 与 latin1 相同 |
| cp1252 | Windows 西欧编码 |

## 支持的 CSV 方言

| 方言 | 分隔符 | 说明 |
|------|--------|------|
| excel | 逗号 | 标准 Excel CSV 格式 |
| excel-tab | Tab | Excel 的 Tab 分隔格式 |
| unix | 逗号 | Unix 风格的 CSV |

## 技术实现

### 核心文件
1. `dingo/config/input_args.py` - 配置参数定义
2. `dingo/data/datasource/local.py` - CSV 文件读取逻辑
3. `dingo/data/converter/base.py` - CSV 数据转换器

### 实现要点
- 使用 Python 标准库 `csv` 模块
- 支持流式读取，避免内存溢出
- 完整的错误处理和友好的错误提示

## 故障排查

### 编码错误
```
UnicodeDecodeError: 'utf-8' codec can't decode...
```
**解决方案：** 尝试使用 `gbk` 或其他编码

### 分隔符错误
数据列数不匹配或解析错误
**解决方案：** 检查并设置正确的 `delimiter` 参数

### 空文件错误
```
RuntimeError: CSV file is empty
```
**解决方案：** 检查文件是否为空或格式是否正确

## 最佳实践

1. **编码选择**：优先尝试 UTF-8，如果失败再尝试 GBK
2. **大文件处理**：利用流式读取特性，不要尝试一次性加载
3. **数据验证**：在 evaluator 中添加必要的数据验证规则
4. **列名规范**：建议使用带列名的 CSV，便于数据追踪
5. **测试先行**：在处理大批量数据前，先用小样本测试配置


## 相关文档

- [Excel 读取文档](../README_EXCEL.md)
- [数据集配置文档](../../docs/dataset_config.md)
- [评估器配置文档](../../docs/evaluator_config.md)
