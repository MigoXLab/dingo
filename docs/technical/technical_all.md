# Dingo: 小白也能理解的技术文档

## 一、安装

### 基础安装
1. 使用conda准备 dingo 运行环境:
```shell
conda create --name dingo python=3.10 -y

conda activate dingo
```

2. 安装 dingo:
- pip安装:
```shell
pip install dingo_python
```

- 如果希望使用 dingo 的最新功能，也可以从源代码构建它：
```shell
git clone git@github.com:MigoXLab/dingo.git dingo
cd dingo
pip install -e .
```

### 进阶安装
如果想要体验全部的 dingo 功能，那么需要安装所有的可选依赖:
```shell
pip install -r requirements/contribute.txt
pip install -r requirements/docs.txt
pip install -r requirements/optional.txt
pip install -r requirements/web.txt
```

## 二、快速开始

### 概览
在 dingo 中启动一个评估任务可以通过以下2种方式：命令行、代码。

**命令行启动**
```shell
python -m dingo.run.cli
   --input_path data.txt
   --dataset local
   --data_format plaintext
   -e sft
   --save_data
```

**代码启动**
```python
from dingo.exec import Executor
from dingo.io import InputArgs

input_data = {
    "input_path": "data.txt",
    "dataset": "local",
    "data_format": "plaintext",
    "eval_group": "sft",
    "save_data": True
}
input_args = InputArgs(**input_data)
executor = Executor.exec_map["local"](input_args)
result = executor.execute()
print(result)
```

### 评估结果
评估完成后，评估结果将打印如下字段:
+ task_id
+ task_name
+ input_path
+ output_path
+ create_time
+ finish_time
+ score
+ num_good
+ num_bad
+ type_ratio
+ name_ratio

所有运行输出将定向到 outputs 目录，结构如下：
```
outputs/
├── 20250609_101837_50b5c0be
├── 20250609_111057_5d250cf6            # 每个任务一个文件夹
│   ├── QUALITY_BAD_COMPLETENESS        # 评估阶段的一级类型
│   │   ├── RuleSentenceNumber.jsonl    # 评估阶段的二级类型
│   │   └── RuleWordNumber.jsonl
│   ├── QUALITY_BAD_EFFECTIVENESS
│   │   ├── RuleColonEnd.jsonl
│   │   └── RuleEnterAndSpace.jsonl
│   └── summary.json                    # 单个任务的汇总结果
├── ...
```

## 三、教程

### 整体概括
本项目的架构可以分为以下3个模块：Data、Evaluator、Executor
+ Data: 负责数据的加载与格式转化
+ Evaluator: 负责评估的执行
+ Executor: 负责任务的分配与调度

![Architecture of dingo](assets/architeture.png)

### 基础配置
dingo 启动方式具有2种，因此配置方式也分为以下2种情况:
1. [命令行配置列表](config.md#cli-config)
2. [代码配置列表](config.md#sdk-config)

**命令行启动**
在命令行环境中，所有配置均以 参数键值对 的形式指定，遵从标准 CLI 语法规则，通过 --参数名 参数值 的方式传递每个配置项。

```shell
python -m dingo.run.cli
   --input_path data.txt
   --dataset local
   --data_format plaintext
   -e sft
   --save_data True
```

**代码启动**
在代码环境中，配置都是 Python 格式的，遵从基本的 Python 语法，通过定义变量的形式指定每个配置项。

```python
from dingo.io import InputArgs

input_data = {
    "input_path": "data.txt",
    "dataset": "local",
    "data_format": "plaintext",
    "eval_group": "sft",
    "save_data": True
}
input_args = InputArgs(**input_data)
```

### 加载数据
如果想要 dingo 顺利读入数据，那么需要在配置时设置以下参数:
- input_path
- dataset
- data_format

数据读入后，进入格式转化阶段，此时执行字段的映射，因此需要在配置时设置以下参数:
- column_id
- column_prompt
- column_content

最终数据以 [Data](../dingo/io/input/Data.py) 类对象的形式在项目中流转。
如果用户在配置时将参数 save_raw 设置为True，那么 Data 类对象的 raw_data 有值否则为空字典。

### 设置并发
dingo 默认状态下没有开启并发，如果有大规模评估任务需要开启并发，那么应该在配置时设置以下参数:
+ max_workers
+ batch_size

以上2个参数应当搭配使用，如果max_workers设置为10但是batch_size设置为1，那么评估的效率不会得到较大提升。

建议batch_size大于等于max_workers。

### 结果保存
评估任务完成后会在当前目录下创建 outputs 文件夹并且不保存原始数据格式，除非用户在配置时设置了以下参数:
+ save_data
+ save_raw
+ save_correct
+ output_path

上文中评估阶段的二级类型jsonl文件中的每条结果数据收到配置参数 save_raw 的影响。

如果 save_raw 设置为True，那么将执行 [ResultInfo](../dingo/io/output/ResultInfo.py) 类的 to_dict_raw 函数，否则将执行 to_dict 函数。

### 启动前端页面
dingo 评估任务结束后，如果保存了评估结果，那么就可以通过一下方式启动前端页面展示结果:
```shell
python -m dingo.run.vsl --input outputs/20250609_101837_50b5c0be
```

## 四、规则
dingo 内置了不同类型的评估规则，详情见: [规则列表](rules.md)。
每条评估规则都有自己的 metric_type 和所属的 group。

每条数据经过规则评估，会产生一个 [ModelRes](../dingo/model/modelres.py) 类对象作为结果，一般来说规则的 metric_type 作为 type 而规则名作为 name。

用户可以通过配置 eval_group 参数来调用该 group 内的所有规则执行评估任务。 如果用户需要组合一批评估规则用来评估，那么请参考下文的 **自定义配置** 。

## 五、提示词
dingo 提示词与规则类似，都有 metric_type 和 group ，并且他们的作用也相同。
但是提示词需要与场景配合才能执行评估任务，详情见:

- [提示词列表](../dingo/model/prompt)

## 六、场景
dingo 的场景负责将数据打包发送给模型，并接收模型返回的结果，然后进行解析，处理成统一的 ModelRes 类对象。

- [场景列表](../dingo/model/llm)

请注意，不同场景对于评估结果 ModelRes 类对象的构建思路也不同，其 type 和 name 的意义也因此不同。

## 七、进阶教程

### 自定义配置
上文的 **教程-基础配置** 篇章中介绍了项目配置的方式与参数列表，但是并没有涉及到自定义，现在让我们来详细了解 **自定义配置** 。

自定义配置离不开参数 [custom_config](config.md#custom-config) , 这个参数包括能够自定义的所有内容，如下所示：
- rule_list
- prompt_list
- rule_config
- llm_config
- multi_turn_mode

### 自定义规则
dingo 内置的规则向用户开放了接口，允许用户根据不同的评估任务进行动态配置。

规则的自定义通过上文 custom_config 参数中的 [rule_config](config.md#rule_config) 实现，可以设置的值包括:
+ threshold
+ pattern
+ key_list
+ refer_path

### 自定义场景
dingo 在使用提示词进行评估任务的时候，必须同时使用场景，执行数据的打包发送与接收处理。

场景的自定义同样是通过上文 custom_config 参数实现，不同的是需要参数 [llm_config](config.md#llm_config) ，可以设置的值包括:
+ model
+ key
+ api_url
+ parameters

需要注意的是参数 [parameters](config.md#parameters) ，这个参数会对模型的推理产生影响，可以设置的值包括:
+ temperature
+ top_p
+ max_tokens
+ presence_penalty
+ frequency_penalty

更多参数细节可参考OpenAI API官方文档。

### 新增数据格式转化
上文的 **教程-基础配置** 篇章中介绍了项目配置的参数列表，其中 data_format 表示数据的格式，同时也代表了一种数据转化的方式。

dingo 内置的数据转化方式有4种，即 data_format 的4个可取的值: json, jsonl, plaintext, listjson.

其对应的转化逻辑见: [数据格式转化列表](../dingo/data/converter/base.py)

模板如下:

```python
@BaseConverter.register("jsonl")
class JsonLineConverter(BaseConverter):
    """Json line file converter."""

    data_id = 0

    def __init__(self):
        super().__init__()

    @classmethod
    def convertor(cls, input_args: InputArgs) -> Callable:
        def _convert(raw: Union[str, Dict]):
            j = raw
            if isinstance(raw, str):
                j = json.loads(raw)
            cls.data_id += 1
            return Data(
                **{
                    "data_id": (
                        cls.find_levels_data(j, input_args.column_id)
                        if input_args.column_id != ""
                        else str(cls.data_id)
                    ),
                    "prompt": (
                        cls.find_levels_data(j, input_args.column_prompt)
                        if input_args.column_prompt != ""
                        else ""
                    ),
                    "content": (
                        cls.find_levels_data(j, input_args.column_content)
                        if input_args.column_content != ""
                        else ""
                    ),
                    "raw_data": j,
                }
            )

        return _convert
```

可以见到，Converter类需要注册一个名称，也就是为 data_format 新增一个可取值，不妨设为 myjsonl

```python
@BaseConverter.register("myjsonl")
```

然后就是实现 convertor 类函数，特别需要注意函数接收变量与返回值的类型。

```python
@classmethod
def convertor(cls, input_args: InputArgs) -> Callable:
```

最后，需要填充 [Data](../dingo/io/input/Data.py) 类，这是项目中数据的基本形态，也是待评估的数据形态。

## 新增规则
上文的 **规则** 篇章介绍了 [规则列表](rules.md) ，其在项目中的位置为 [规则代码列表](../dingo/model/rule) 。

当dingo内置的规则无法满足用户的评估任务，用户需要添加新的评估规则时，可以参考一下模板:

```python
@Model.rule_register(
    "QUALITY_BAD_EFFECTIVENESS",
    ["default", "sft", "pretrain", "benchmark", "llm_base", "text_base_all"],
)
class RuleColonEnd(BaseRule):
    """check whether the last char is ':'"""

    dynamic_config = DynamicRuleConfig()

    @classmethod
    def eval(cls, input_data: Data) -> ModelRes:
        res = ModelRes()
        content = input_data.content
        if len(content) <= cls.dynamic_config.threshold:
            return res
        if content[-1] == ":":
            res.error_status = True
            res.type = cls.metric_type
            res.name = cls.__name__
            res.reason = [content[-100:]]
        return res
```

首先，所有的规则都是 [BaseRule](../dingo/model/rule/base.py) 类的实现，都具有以下3个类属性:

+ metric_type: 函数 rule_register 执行时赋值
+ group: 函数 rule_register 执行时赋值
+ dynamic_config: 开放的自定义接口

其次，所有的规则都需要执行注册操作，即 Model.rule_register 函数，并指明 metric_type 与 group。

```python
@Model.rule_register(
    "QUALITY_BAD_EFFECTIVENESS",
    ["default", "sft", "pretrain", "benchmark", "llm_base", "text_base_all"],
)
```

然后，定义类属性 dynamic_config ，否则用户无法对规则进行自定义操作

```python
dynamic_config = DynamicRuleConfig()
```

最后，实现 eval 类函数，需要注意接收变量与返回值的类型

```python
@classmethod
def eval(cls, input_data: Data) -> ModelRes:
```

### 新增提示词

上文的 **提示词** 篇章中已经介绍了 [提示词列表](../dingo/model/prompt) ，如果用户在评估过程中产生了新的评估任务，需要涉及自己的提示词。

那么将新的提示词添加到项目的方式可以参考一下方式:

```python
@Model.prompt_register("QUALITY_BAD_SIMILARITY", [])
class PromptRepeat(BasePrompt):
    content = """
    请判断一下文本是否存在重复问题。
    返回一个json，如{"score": 0, "reason": "xxx"}.
    如果存在重复，score是0，否则是1。reason是判断的依据。
    除了json不要有其他内容。
    以下是需要判断的文本：
    """
```

从上面的模板中可以看到，新增的提示词必须继承 [BasePrompt](../dingo/model/prompt/base.py) 类。

```python
class PromptRepeat(BasePrompt):
```

然后，与新增规则相似，都执行注册操作，并指明 metric_type 与 group 。

注意， group 可以是空列表，表名该提示词不属于任何的 group ，并且无法通过 group 来调用。

```python
@Model.prompt_register("QUALITY_BAD_SIMILARITY", [])
```

最后，填写新的提示词。

```python
content = """
    请判断一下文本是否存在重复问题。
    返回一个json，如{"score": 0, "reason": "xxx"}.
    如果存在重复，score是0，否则是1。reason是判断的依据。
    除了json不要有其他内容。
    以下是需要判断的文本：
    """
```

### 新增场景
上文的 **场景** 篇章介绍了场景的职责，即: 打包发送数据、接收解析数据

那么，新增一个场景就需要实现以上2个功能，详情见下方模板:

```python
class BaseOpenAI(BaseLLM):
    prompt = None
    client = None
    dynamic_config = DynamicLLMConfig()

    @classmethod
    def set_prompt(cls, prompt: BasePrompt):
        pass

    @classmethod
    def create_client(cls):
        pass

    @classmethod
    def build_messages(cls, input_data: Data) -> List:
        pass

    @classmethod
    def send_messages(cls, messages: List):
        pass

    @classmethod
    def process_response(cls, response: str) -> ModelRes:
        pass

    @classmethod
    def eval(cls, input_data: Data) -> ModelRes:
        if cls.client is None:
            cls.create_client()

        messages = cls.build_messages(input_data)

        attempts = 0
        except_msg = ""
        except_name = Exception.__class__.__name__
        while attempts < 3:
            try:
                response = cls.send_messages(messages)
                return cls.process_response(response)
            except (ValidationError, ExceedMaxTokens, ConvertJsonError) as e:
                except_msg = str(e)
                except_name = e.__class__.__name__
                break
            except Exception as e:
                attempts += 1
                time.sleep(1)
                except_msg = str(e)
                except_name = e.__class__.__name__

        return ModelRes(
            error_status=True, type="QUALITY_BAD", name=except_name, reason=[except_msg]
        )
```

第一步，场景必须继承 [BaseLLM](../dingo/model/llm/base.py) 或者其子类

```python
class BaseOpenAI(BaseLLM):
```

第二步，设置场景的模型类属性:

```python
    prompt = None
    client = None
    dynamic_config = DynamicLLMConfig()
```

第四步，实现 set_prompt 类函数，用于设置场景提示词:

```python
@classmethod
def set_prompt(cls, prompt: BasePrompt):
```

第五步，实现 create_client 类函数，创建模型 client ，用于收发数据。

```python
@classmethod
def create_client(cls):
```

第六步，实现 build_messages 类函数，打包数据，用于发送。

```python
@classmethod
def build_messages(cls, input_data: Data) -> List:
```

第七步，实现 send_messages 类函数，发送打包完成的数据，并且接收模型返回的数据。

```python
@classmethod
def send_messages(cls, messages: List):
```

第八步，实现 process_response 类函数，解析模型返回的数据

```python
@classmethod
def process_response(cls, response: str) -> ModelRes:
```

第九步，实现 eval 类函数，统筹执行以上实现的类函数，并将解析后的数据转化为 [ModelRes](../dingo/model/modelres.py) 类型。

```python
@classmethod
def eval(cls, input_data: Data) -> ModelRes:
```
