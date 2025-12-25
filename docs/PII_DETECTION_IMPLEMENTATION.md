# PII 检测规则实现文档

## 📊 实现概览

已在 `dingo/model/rule/rule_common.py` 中实现 PII（个人身份信息）检测规则 `RulePIIDetection`。

---

## ✅ 实现完成情况

| 项目 | 状态 | 说明 |
|------|------|------|
| **规则实现** | ✅ 完成 | `RulePIIDetection` 类 |
| **标准依据** | ✅ 完成 | NIST SP 800-122 + 中国《个人信息保护法》|
| **脱敏处理** | ✅ 完成 | 自动脱敏检测到的 PII |
| **严重等级** | ✅ 完成 | high/medium/low 三级分类 |

---

## 🎯 支持的 PII 类型

### 1. **高风险 PII** 🔴

| PII 类型 | 正则模式 | 额外验证 | 示例 |
|---------|---------|---------|------|
| **中国身份证号** | 18位格式验证 | ❌ | 110101199001011234 |
| **信用卡号** | 13-19位，支持分隔符 | ✅ Luhn算法 | 4532 1488 0343 6464 |
| **美国SSN** | XXX-XX-XXXX格式 | ❌ | 123-45-6789 |
| **中国护照号** | E/G/P开头+8位数字 | ❌ | E12345678 |

### 2. **中风险 PII** 🟡

| PII 类型 | 正则模式 | 额外验证 | 示例 |
|---------|---------|---------|------|
| **中国手机号** | 1[3-9]开头11位 | ❌ | 13812345678 |
| **电子邮件** | 标准邮箱格式 | ❌ | user@example.com |

### 3. **低风险 PII** 🟢

| PII 类型 | 正则模式 | 额外验证 | 示例 |
|---------|---------|---------|------|
| **IP地址** | IPv4格式 | ✅ 范围验证 | 192.168.1.100 |

---

## 🛡️ 脱敏策略

### 脱敏规则

```python
# 身份证号：保留前6位和后4位
110101199001011234 → 110101********1234

# 手机号：保留前3位和后4位
13812345678 → 138****5678

# 邮箱：保留用户名首字母和域名
user@example.com → u***@example.com

# 信用卡：只保留后4位
4532148803436464 → ************6464

# IP地址：保留第一段和最后一段
192.168.1.100 → 192.***.***.100
```

---

## 🔍 验证算法

### 1. **Luhn 算法（信用卡验证）**

用于验证信用卡号的合法性，防止误报。

```python
def _validate_luhn(cls, number: str) -> bool:
    """Luhn 算法验证信用卡号"""
    digits = [int(d) for d in number if d.isdigit()]

    if len(digits) < 13 or len(digits) > 19:
        return False

    checksum = 0
    reverse_digits = digits[::-1]

    for i, digit in enumerate(reverse_digits):
        if i % 2 == 1:
            digit *= 2
            if digit > 9:
                digit -= 9
        checksum += digit

    return checksum % 10 == 0
```

**优势**:
- ✅ 过滤掉无效的卡号组合
- ✅ 减少误报率
- ✅ 支持带空格和连字符的格式

### 2. **IP 地址验证**

验证 IP 地址每段数字是否在 0-255 范围内。

```python
def _validate_ip(cls, ip: str) -> bool:
    """验证 IP 地址合法性"""
    parts = ip.split('.')
    if len(parts) != 4:
        return False

    try:
        for part in parts:
            num = int(part)
            if num < 0 or num > 255:
                return False
        return True
    except ValueError:
        return False
```

---

## 📝 使用示例

### 基础使用

```python
from dingo.io import Data
from dingo.model.rule.rule_common import RulePIIDetection

# 创建测试数据
data = Data(
    data_id="1",
    content="张三，身份证 110101199001011234，手机 13812345678"
)

# 执行检测
result = RulePIIDetection.eval(data)

# 查看结果
print(f"检测状态: {result.status}")  # True（检测到PII）
print(f"标签: {result.label}")  # ['QUALITY_BAD_SECURITY.RulePIIDetection']
print(f"原因: {result.reason}")
# ['High Risk PII: 中国身份证号(110101********1234)',
#  'Medium Risk PII: 中国手机号(138****5678)']
```

### 集成到评测流程

```python
from dingo.config import InputArgs
from dingo.exec import Executor

input_data = {
    "task_name": "pii_detection",
    "input_path": "data.jsonl",
    "output_path": "outputs/",
    "evaluator": [
        {
            "fields": {
                "content": "text"
            },
            "evals": [
                {
                    "name": "RulePIIDetection"
                }
            ]
        }
    ]
}

input_args = InputArgs(**input_data)
executor = Executor.exec_map["local"](input_args)
summary = executor.execute()
```

---

## 📚 标准依据

### 1. **NIST SP 800-122** ⭐
**美国国家标准与技术研究院 - PII 保护指南**

- **文档**: https://nvlpubs.nist.gov/nistpubs/Legacy/SP/nistspecialpublication800-122.pdf
- **适用**: 通用PII识别和分类
- **分类**: 直接标识符、间接标识符、敏感PII


### 2. **GDPR（参考）**
- **文档**: https://gdpr-info.eu/art-4-gdpr/
- **适用**: 欧盟业务
- **特点**: 最严格的数据保护标准

---

## 📊 输出格式

### EvalDetail 结构

```python
EvalDetail(
    metric="RulePIIDetection",
    status=True,  # True表示检测到PII
    label=["QUALITY_BAD_SECURITY.RulePIIDetection"],
    reason=[
        "High Risk PII: 中国身份证号(110101********1234), 信用卡号(************6464)",
        "Medium Risk PII: 中国手机号(138****5678), 电子邮件(u***@example.com)",
        "Low Risk PII: IP地址(192.***.***.100)"
    ]
)
```



## 📖 相关文档

- [NIST SP 800-122: Guide to Protecting PII](https://nvlpubs.nist.gov/nistpubs/Legacy/SP/nistspecialpublication800-122.pdf)
- [GDPR Article 4](https://gdpr-info.eu/art-4-gdpr/)
- [Microsoft Presidio](https://github.com/microsoft/presidio)
