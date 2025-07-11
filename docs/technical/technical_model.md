# Dingo: Evaluator层的设计逻辑说明

## 一、概述

`dingo.model.model` 主要负责模型（包括规则、提示词、LLM等）的注册、分组、配置应用和动态加载。它为整个 Dingo 系统提供了统一的模型管理和配置入口，支持自动发现和注册规则、提示词、LLM，并能根据配置文件动态调整模型行为。

---

## 二、主要类与结构

### 1. BaseEvalModel

- 继承自 `pydantic.BaseModel`
- 字段：
  - `name`: str
  - `type`: str
- 用于描述基础的评测模型信息。

### 2. Model

#### 主要职责

- 管理和注册规则（Rule）、提示词（Prompt）、LLM（大语言模型）。
- 支持模型的分组、按 metric_type 分类、按名称索引。
- 支持根据配置文件动态应用模型参数。
- 自动加载和注册 `rule/`、`prompt/`、`llm/` 目录下的所有模型类。

#### 主要类属性

- `module_loaded`: 是否已加载模块，防止重复加载。
- `rule_groups`, `prompt_groups`: 分组管理，结构如 `{group_name: [class, ...]}`。
- `rule_metric_type_map`, `prompt_metric_type_map`: 按 metric_type 分类的映射。
- `rule_name_map`, `prompt_name_map`, `llm_name_map`: 名称到类的映射。

#### 关键方法

##### 注册相关

- `rule_register(metric_type, group)`: 装饰器，用于注册规则类，指定其 metric_type 和分组。
- `llm_register(llm_id)`: 装饰器，用于注册 LLM 类，指定其唯一 ID。
- `prompt_register(metric_type, group)`: 装饰器，用于注册提示词类，指定其 metric_type 和分组。

##### 获取与查询

- `get_group(group_name)`: 获取指定分组下的规则和/或提示词。
- `get_rule_metric_type_map()`: 获取所有规则的 metric_type 映射。
- `get_metric_type_by_rule_name(rule_name)`: 通过规则名获取其 metric_type。
- `get_rule_group(rule_group_name)`: 获取指定规则分组的所有规则类。
- `get_rule_groups()`: 获取所有规则分组。
- `get_rules_by_group(group_name)`: 获取指定分组下所有规则的名称（含 metric_type）。
- `get_rule_by_name(name)`: 通过名称获取规则类。
- `get_llm_name_map()`: 获取所有 LLM 的名称映射。
- `get_llm(llm_name)`: 通过名称获取 LLM 类。
- `print_rule_list()`: 打印所有已注册规则的名称。

##### 配置应用

- `apply_config_rule()`: 应用全局配置中的规则参数到已注册规则。
- `apply_config_llm()`: 应用全局配置中的 LLM 参数到已注册 LLM。
- `apply_config_rule_list(eval_group)`: 根据配置文件中的 rule_list，生成分组。
- `apply_config_prompt_list(eval_group)`: 根据配置文件中的 prompt_list，生成分组。
- `apply_config(custom_config, eval_group)`: 读取配置文件并应用所有相关配置。
- `apply_config_for_spark_driver(custom_config, eval_group)`: 专为 Spark Driver 场景设计的配置应用。

##### 自动加载

- `load_model()`: 自动加载 `rule/`、`prompt/`、`llm/` 目录下的所有 Python 文件，实现自动注册。

---

## 三、使用示例

### 1. 注册规则/LLM/Prompt

```python
@Model.rule_register(metric_type="QUALITY", group=["default"])
class MyRule(BaseRule):
    ...
```

```python
@Model.llm_register(llm_id="gpt3")
class GPT3LLM(BaseLLM):
    ...
```

### 2. 应用配置

```python
Model.apply_config("path/to/config.yaml", eval_group="my_eval_group")
```

### 3. 获取分组信息

```python
group_info = Model.get_group("default")
rules = group_info.get("rule", [])
prompts = group_info.get("prompt", [])
```

---

## 四、设计亮点

- **自动注册**：通过装饰器和自动扫描目录，极大简化了模型的注册流程。
- **灵活分组**：支持规则、提示词的多分组和多类型映射，便于扩展和管理。
- **动态配置**：可通过配置文件动态调整模型参数和分组，适应不同评测场景。
- **统一接口**：所有模型的获取、注册、配置应用均通过统一接口完成，便于维护。

---

## 五、注意事项

- 注册的类必须继承自对应的基类（如 `BaseRule`, `BasePrompt`, `BaseLLM`）。
- 配置文件需符合 `GlobalConfig` 的格式要求。
- 自动加载依赖于目录结构，需保证 `rule/`、`prompt/`、`llm/` 目录下的 Python 文件可被正确导入。

---
