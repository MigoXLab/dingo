# Dingo 多字段质检在 SQL 数据库中的应用

## 一、项目背景

### 1.1 应用场景
星河图书馆作为一个大型图书管理系统，其数据库中存储了海量的图书元数据信息，如 ISBN、书名、作者、出版信息等。这些数据的质量直接影响到图书检索、推荐、统计分析等业务功能的准确性。


下面将以2个在实际业务中出现的问题为例做分析：
- **ISBN 格式问题**：ISBN 作为图书的唯一标识符，可能存在格式不规范、校验位错误等问题
- **书名质量问题**：书名字段可能包含异常字符、空值、乱码等，影响用户体验和系统稳定性


### 1.2 解决方案
采用 Dingo 数据质量评估框架，实现对 SQL 数据库中多个字段的并行质检，确保数据质量符合业务要求。

## 二、技术方案

### 2.1 系统架构
见 `dingo` 架构图

### 2.2 核心配置

#### 2.2.1 数据源配置
```python
"dataset": {
    "source": "sql",
    "format": "jsonl",
    "sql_config": {
        'dialect': 'mysql',
        'driver': 'pymysql',
        'username': '***',
        'password': '***',
        'host': '***',
        'port': '***',
        'database': '***',
        'connect_args': '?charset=utf8mb4'
    }
}
```

**配置说明**：
- 采用 MySQL 协议连接数据库
- 使用 UTF-8 字符集，确保中文等多字节字符正确处理
- 通过 PyMySQL 驱动实现 Python 与数据库的交互

#### 2.2.2 多字段评估配置
```python
"evaluator": [
    {
        "fields": {"content": "isbn"},
        "evals": [
            {"name": "RuleIsbn"}
        ]
    },
    {
        "fields": {"content": "title"},
        "evals": [
            {"name": "RuleAbnormalChar"},
            {"name": "RuleContentNull"},
        ]
    }
]
```

**评估策略**：
1. **ISBN 字段评估**
   - 使用 `RuleIsbn` 规则
   - 验证 ISBN-10 和 ISBN-13 格式
   - 检查校验位的正确性

2. **Title 字段评估**
   - 使用 `RuleAbnormalChar` 规则检查异常字符
   - 使用 `RuleContentNull` 规则检查空值
   - 多规则并行检查，提高检测覆盖率

### 2.3 技术特点

#### 2.3.1 多字段并行处理
Dingo 支持在单次任务中同时对多个字段进行质检，每个字段可以配置独立的规则集，实现了：
- **并行执行**：不同字段的检查可以并行处理，提高效率
- **独立结果**：每个字段独立输出检查结果，便于问题定位
- **灵活配置**：可以根据业务需求为不同字段配置不同的质检规则

#### 2.3.2 规则组合
每个字段可以应用多个质检规则，实现多维度的质量评估：
```python
"evals": [
    {"name": "RuleAbnormalChar"},  # 检查异常字符
    {"name": "RuleContentNull"},   # 检查空值
]
```

#### 2.3.3 结果分层存储
```
outputs/20251126_161212_9c822000/
├── summary.json          # 总体评估结果
├── isbn/                 # ISBN 字段结果
│   └── QUALITY_GOOD.jsonl
└── title/                # Title 字段结果
    └── QUALITY_GOOD.jsonl
```

## 三、测试实施

### 3.1 测试数据
- **数据表**：`***(星河表)`
- **数据来源**：星河图书馆数据库
- **测试条件**：`where isbn is not null and isbn != ''`
- **数据量**：10 条记录

### 3.2 测试执行
```python
from dingo.config import InputArgs
from dingo.exec import Executor

# 构建配置
input_args = InputArgs(**input_data)

# 执行质检
executor = Executor.exec_map["local"](input_args)
result = executor.execute()
```

### 3.3 测试结果

#### 3.3.1 总体结果
```json
{
    "task_id": "9c82232a-ca9f-11f0-b738-7c10c9512fac",
    "task_name": "dingo",
    "create_time": "20251126_161212",
    "finish_time": "20251126_161212",
    "score": 100.0,
    "num_good": 10,
    "num_bad": 0,
    "total": 10
}
```

**结果分析**：
- ✅ 所有 10 条测试数据全部通过质检
- ✅ 综合得分 100 分
- ✅ 无质量问题数据（num_bad = 0）

#### 3.3.2 字段级结果
```json
"type_ratio": {
    "isbn": {
        "QUALITY_GOOD": 1.0
    },
    "title": {
        "QUALITY_GOOD": 1.0
    }
}
```

**字段分析**：
- **ISBN 字段**：100% 通过率，所有 ISBN 格式规范
- **Title 字段**：100% 通过率，无异常字符和空值

#### 3.3.3 数据样本
检查通过的数据示例：

**样本 1**：
- **ISBN**: 9787508685397
- **Title**: 5分钟商学院•管理篇
- **Author**: 刘润
- **Publisher**: 中信出版社

**样本 2**：
- **ISBN**: 9781591842217
- **Title**: The Knack
- **Author**: Norm Brodsky
- **Publisher**: PORTFOLIO

**样本 3**：
- **ISBN**: 9787561346037
- **Title**: 滚雪球2
- **Author**: 福特
- **Publisher**: 陕西师范大学出版社

## 四、技术优势

### 4.1 灵活的数据源支持
Dingo 支持多种数据源，包括：
- ✅ SQL 数据库（MySQL、PostgreSQL、StarRocks、Doris 等）
- ✅ 本地文件（JSONL、CSV 等）
- ✅ S3 对象存储
- ✅ Hugging Face 数据集

### 4.2 多维度质量评估
- **多字段并行**：一次任务可同时评估多个字段
- **多规则组合**：每个字段可应用多个质检规则
- **规则可扩展**：支持自定义规则，满足特定业务需求

### 4.3 高效的执行机制
- **本地执行**：支持单机快速处理
- **分布式执行**：支持 Spark 等分布式框架处理大规模数据
- **流式处理**：支持数据流式读取和处理，降低内存占用

### 4.4 完善的结果输出
```
outputs/
└── 20251126_161212_9c822000/
    ├── summary.json                    # 总体统计
    ├── isbn/
    │   ├── QUALITY_GOOD.jsonl         # 合格数据
    │   └── QUALITY_BAD.jsonl          # 不合格数据（如有）
    └── title/
        ├── QUALITY_GOOD.jsonl
        └── QUALITY_BAD.jsonl
```

**输出特点**：
- 按字段分目录存储
- 按质量等级分文件存储
- 完整保留原始数据和评估详情
- 提供 JSON 格式便于后续分析

## 五、应用场景

### 5.1 数据质量监控
- **定期检查**：定时任务自动执行质检，监控数据质量趋势
- **实时告警**：质量指标低于阈值时触发告警
- **质量报表**：生成数据质量周报、月报

### 5.2 数据清洗
- **问题定位**：快速找出不合格数据
- **分类处理**：按问题类型分别处理
- **清洗验证**：清洗后再次执行质检验证效果

### 5.3 数据迁移验证
- **迁移前检查**：确保源数据质量
- **迁移后验证**：确保数据完整性和准确性
- **对比分析**：迁移前后质量对比

### 5.4 业务数据审核
- **入库前审核**：新数据入库前进行质量检查
- **业务规则验证**：确保数据符合业务规则
- **合规性检查**：确保数据符合行业标准

## 六、参考资料

### 6.1 相关文档
- [Dingo SQL 数据源配置文档](../dataset/sql.md)
- [Dingo 规则列表](../rules.md)
- [Dingo 配置指南](../config.md)

### 6.2 示例代码
- [完整测试代码](../../examples/dataset/sql_xinghe.py)
- [SQL 数据源示例](../../examples/dataset/sql.py)
