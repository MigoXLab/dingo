# Dingo: Evaluator层的设计逻辑说明

## 一、概述

`dingo.model.model` 主要负责模型（包括规则、提示词、LLM等）的注册、分组、配置应用和动态加载。它为整个 Dingo 系统提供了统一的模型管理和配置入口，支持自动发现和注册规则、提示词、LLM，并能根据配置文件动态调整模型行为。

### 1.1 核心功能

- **模型注册管理**：提供统一的装饰器接口，支持规则、提示词、LLM的自动注册
- **分组与分类**：支持按功能分组和按metric_type分类的多维度组织方式
- **动态配置**：支持通过配置文件动态调整模型参数和行为
- **自动发现**：自动扫描目录结构，发现并加载所有可用的模型类
- **统一接口**：提供一致的API接口，简化模型的使用和管理

### 1.2 架构设计

```
┌─────────────────────────────────────────────────────────┐
│                    Model Manager                        │
├─────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐      │
│  │   Rules     │  │   Prompts   │  │    LLMs     │      │
│  │ Management  │  │ Management  │  │ Management  │      │
│  └─────────────┘  └─────────────┘  └─────────────┘      │
├─────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐      │
│  │   Groups    │  │ Metric Type │  │ Name Maps   │      │
│  │ Management  │  │   Mapping   │  │ Management  │      │
│  └─────────────┘  └─────────────┘  └─────────────┘      │
├─────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐      │
│  │   Config    │  │   Auto      │  │   Dynamic   │      │
│  │ Application │  │ Discovery   │  │   Loading   │      │
│  └─────────────┘  └─────────────┘  └─────────────┘      │
└─────────────────────────────────────────────────────────┘
```

---

## 二、主要类与结构

### 2.1 BaseEvalModel

#### 类定义
```python
class BaseEvalModel(BaseModel):
    name: str
    type: str
```

#### 功能说明
- 继承自 `pydantic.BaseModel`，提供数据验证和序列化功能
- 用于描述基础的评测模型信息
- 作为所有评测模型的基础数据结构

#### 使用场景
- 配置文件中的模型定义
- API接口的数据传输
- 模型元数据的存储

### 2.2 Model

#### 2.2.1 主要职责

- **模型生命周期管理**：负责模型的全生命周期，从注册到使用到配置
- **分组与分类管理**：支持多维度的模型组织方式
- **配置动态应用**：支持运行时动态调整模型参数
- **自动发现机制**：自动扫描和加载可用的模型类

#### 2.2.2 核心类属性

```python
class Model:
    # 模块加载状态管理
    module_loaded = False
    
    # 分组管理
    rule_groups = {}      # {group_name: [rule_classes]}
    prompt_groups = {}    # {group_name: [prompt_classes]}
    
    # 按metric_type分类
    rule_metric_type_map = {}    # {metric_type: [rule_classes]}
    prompt_metric_type_map = {}  # {metric_type: [prompt_classes]}
    
    # 名称映射
    rule_name_map = {}    # {rule_name: rule_class}
    prompt_name_map = {}  # {prompt_name: prompt_class}
    llm_name_map = {}     # {llm_name: llm_class}
```

#### 2.2.3 数据流图

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Model Files   │───▶│   Auto Loader   │───▶│   Name Maps     │
│   (rule/,       │    │                 │    │                 │
│    prompt/,     │    │                 │    │                 │
│    llm/)        │    │                 │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │                        │
                                ▼                        ▼
                       ┌─────────────────┐    ┌─────────────────┐
                       │   Groups        │    │   Metric Type   │
                       │   Management    │    │   Mapping       │
                       └─────────────────┘    └─────────────────┘
                                │                        │
                                ▼                        ▼
                       ┌─────────────────┐    ┌─────────────────┐
                       │   Config        │    │   Runtime       │
                       │   Application   │    │   Usage         │
                       └─────────────────┘    └─────────────────┘
```

---

## 三、核心方法详解

### 3.1 注册相关方法

#### 3.1.1 rule_register

```python
@classmethod
def rule_register(cls, metric_type: str, group: List[str]) -> Callable:
```

**功能**：注册规则类的装饰器

**参数说明**：
- `metric_type`: 规则所属的评测类型（如"QUALITY", "SAFETY"等）
- `group`: 规则所属的分组列表

**使用示例**：
```python
@Model.rule_register(metric_type="QUALITY", group=["default", "strict"])
class ContentQualityRule(BaseRule):
    def eval(self, data: Data) -> ModelRes:
        # 实现评测逻辑
        pass
```

**内部流程**：
1. 将规则类添加到指定的分组中
2. 将规则类添加到metric_type映射中
3. 将规则类添加到名称映射中
4. 为规则类设置group和metric_type属性

#### 3.1.2 llm_register

```python
@classmethod
def llm_register(cls, llm_id: str) -> Callable:
```

**功能**：注册LLM类的装饰器

**参数说明**：
- `llm_id`: LLM的唯一标识符

**使用示例**：
```python
@Model.llm_register(llm_id="gpt-3.5-turbo")
class GPT35TurboLLM(BaseLLM):
    def eval(self, data: Data) -> ModelRes:
        # 实现LLM评测逻辑
        pass
```

#### 3.1.3 prompt_register

```python
@classmethod
def prompt_register(cls, metric_type: str, group: List[str]) -> Callable:
```

**功能**：注册提示词类的装饰器

**参数说明**：
- `metric_type`: 提示词所属的评测类型
- `group`: 提示词所属的分组列表

### 3.2 查询与获取方法

#### 3.2.1 分组查询

```python
@classmethod
def get_group(cls, group_name) -> Dict[str, List]:
```

**功能**：获取指定分组下的所有模型

**返回值**：
```python
{
    'rule': [rule_classes],
    'prompt': [prompt_classes]
}
```

**使用示例**：
```python
group_info = Model.get_group("default")
rules = group_info.get("rule", [])
prompts = group_info.get("prompt", [])
```

#### 3.2.2 按类型查询

```python
@classmethod
def get_rule_metric_type_map(cls) -> Dict[str, List[Callable]]:
```

**功能**：获取所有规则的metric_type映射

**返回值**：
```python
{
    'QUALITY': [rule_class1, rule_class2],
    'SAFETY': [rule_class3, rule_class4]
}
```

#### 3.2.3 按名称查询

```python
@classmethod
def get_rule_by_name(cls, name: str) -> Callable:
```

**功能**：通过名称获取规则类

**使用示例**：
```python
rule_class = Model.get_rule_by_name("ContentQualityRule")
```

### 3.3 配置应用方法

#### 3.3.1 apply_config_rule

```python
@classmethod
def apply_config_rule(cls):
```

**功能**：应用全局配置中的规则参数

**处理流程**：
1. 检查GlobalConfig中是否有rule_config
2. 遍历每个规则配置
3. 获取规则的dynamic_config
4. 根据配置文件更新配置参数

**配置示例**：
```yaml
rule_config:
  ContentQualityRule:
    - ["threshold", 0.8]
    - ["max_length", 1000]
```

#### 3.3.2 apply_config_llm

```python
@classmethod
def apply_config_llm(cls):
```

**功能**：应用全局配置中的LLM参数

**处理流程**：
1. 检查GlobalConfig中是否有llm_config
2. 遍历每个LLM配置
3. 获取LLM的dynamic_config
4. 根据配置文件更新配置参数

#### 3.3.3 apply_config

```python
@classmethod
def apply_config(cls, custom_config: Optional[str | dict], eval_group: str = ''):
```

**功能**：完整的配置应用流程

**处理流程**：
1. 读取配置文件
2. 应用规则配置
3. 应用LLM配置
4. 应用规则列表配置
4. 应用提示词列表配置

### 3.4 自动加载方法

#### 3.4.1 load_model

```python
@classmethod
def load_model(cls):
```

**功能**：自动加载所有模型文件

**处理流程**：
1. 检查是否已加载，避免重复加载
2. 扫描rule/目录下的所有.py文件
3. 扫描prompt/目录下的所有.py文件
4. 扫描llm/目录下的所有.py文件
4. 使用importlib动态导入模块
6. 处理导入异常，记录日志

**目录结构要求**：
```
dingo/model/
├── rule/
│   ├── __init__.py
│   ├── quality_rule.py
│   └── safety_rule.py
├── prompt/
│   ├── __init__.py
│   ├── qa_prompt.py
│   └── summary_prompt.py
└── llm/
    ├── __init__.py
    ├── gpt_llm.py
    └── claude_llm.py
```

---

## 四、扩展性设计

### 4.1 插件化架构

Model类采用插件化设计，支持：

1. **动态注册**：运行时动态注册新的模型
2. **热插拔**：支持模型的动态加载和卸载
3. **版本管理**：支持模型版本的管理和切换

### 4.2 自定义扩展

#### 4.2.1 自定义规则

```python
@Model.rule_register(metric_type="CUSTOM", group=["custom"])
class CustomRule(BaseRule):
    def __init__(self):
        super().__init__()
        self.custom_param = "default"
    
    def eval(self, data: Data) -> ModelRes:
        # 自定义评测逻辑
        result = self.custom_evaluation(data)
        return ModelRes(
            type="CUSTOM",
            name="CustomRule",
            error_status=result.is_error,
            reason=result.reasons
        )
```

#### 4.2.2 自定义LLM

```python
@Model.llm_register(llm_id="custom-llm")
class CustomLLM(BaseLLM):
    def __init__(self):
        super().__init__()
        self.api_key = None
        self.endpoint = None
    
    def set_prompt(self, prompt: BasePrompt):
        self.current_prompt = prompt
    
    def eval(self, data: Data) -> ModelRes:
        # 自定义LLM调用逻辑
        response = self.call_custom_api(data)
        return self.parse_response(response)
```

### 4.3 配置扩展

支持多种配置格式：

1. **JSON配置**：
```json
{
  "rule_config": {
    "CustomRule": [
      ["custom_param", "value"]
    ]
  }
}
```

2. **Python配置**：
```python
config = {
    "rule_config": {
        "CustomRule": [
            ["custom_param", "value"]
        ]
    }
}
Model.apply_config(config, eval_group="custom")
```

---

## 五、注意事项与限制

### 5.1 使用限制

1. **继承要求**：所有注册的类必须继承自对应的基类
   - 规则类：继承自`BaseRule`
   - 提示词类：继承自`BasePrompt`
   - LLM类：继承自`BaseLLM`

2. **命名要求**：
   - 类名必须唯一
   - LLM的llm_id必须唯一
   - 分组名不能重复

3. **目录结构要求**：
   - 必须存在`rule/`、`prompt/`、`llm/`目录
   - Python文件必须以`.py`结尾
   - 不能包含`__init__.py`文件

### 5.2 配置限制

1. **配置文件格式**：必须符合`GlobalConfig`的格式要求
2. **参数类型**：配置参数必须与模型期望的类型匹配
3. **依赖关系**：配置的模型必须已经注册

### 5.3 性能考虑

1. **内存使用**：大量模型注册可能占用较多内存
2. **加载时间**：首次加载可能需要较长时间
3. **并发安全**：多线程环境下需要注意线程安全

### 5.4 错误处理

1. **导入错误**：模块导入失败时会记录日志但不会中断程序
2. **配置错误**：配置参数错误时会抛出异常
3. **注册错误**：重复注册时会覆盖之前的注册
