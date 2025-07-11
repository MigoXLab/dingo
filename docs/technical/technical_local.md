# Dingo: Executor的Local模式介绍

## 一、模块定位与作用

`dingo.exec.local` 主要实现了本地执行器（LocalExecutor），用于在本地环境下对数据集进行评测任务的自动化批量处理。它负责数据加载、模型配置、评测调度、结果统计与输出，是 Dingo 评测系统的核心执行组件之一。

---

## 二、核心类与结构

### 1. LocalExecutor

#### 继承关系

- 继承自 `ExecProto`，并通过 `@Executor.register("local")` 装饰器注册为 "local" 类型的执行器。

#### 主要属性

- `input_args`: 评测任务的输入参数（InputArgs 实例）。
- `llm`: 当前使用的大语言模型（BaseLLM 实例）。
- `summary`: 评测任务的统计与汇总信息（SummaryModel 实例）。

#### 主要方法

##### 1. 数据加载

- `load_data() -> Generator[Data]`
  - 根据输入参数中的数据集名称，动态加载数据源和数据集，返回数据生成器。

##### 2. 执行主流程

- `execute() -> SummaryModel`
  - 设置日志等级，应用模型配置，创建输出目录。
  - 根据配置选择 LLM，初始化 SummaryModel。
  - 调用 `evaluate()` 进行批量评测。
  - 汇总并写出 summary，返回最终统计结果。

##### 3. 评测主循环

- `evaluate()`
  - 支持多线程和多进程混合并发（规则可选线程/进程，Prompt 固定线程）。
  - 按 batch_size 分批处理数据，调度各分组（rule/prompt）下的评测任务。
  - 聚合每条数据的评测结果，实时更新 summary，并写出单条数据和 summary。

##### 4. 单条数据评测

- `evaluate_single_data(group_type, group, data: Data) -> ResultInfo`
  - 针对 rule 或 prompt 分组，分别调用 `evaluate_rule` 或 `evaluate_prompt`。
  - 聚合每个分组下所有规则/提示词的评测结果，区分好坏类型、名称、原因。

- `evaluate_rule(group: List[BaseRule], d: Data) -> ResultInfo`
  - 依次调用每个规则的 `eval` 方法，分析结果，统计类型、名称、原因。

- `evaluate_prompt(group: List[BasePrompt], d: Data) -> ResultInfo`
  - 依次设置 LLM 的 prompt，调用 LLM 的 `eval` 方法，分析结果。

##### 5. 结果写出与汇总

- `write_single_data(path, input_args, result_info)`
  - 按类型-名称分目录写出每条数据的评测结果（jsonl 格式），支持保存原始数据。

- `write_summary(path, input_args, summary)`
  - 写出当前评测任务的 summary（summary.json）。

- `summarize(summary: SummaryModel) -> SummaryModel`
  - 计算得分、类型/名称分布比例，补充完成时间。

##### 6. 结果查询

- `get_info_list(high_quality: bool) -> list`
  - 读取输出目录下所有结果，按 error_status 区分高/低质量数据。

- `get_bad_info_list()`, `get_good_info_list()`
  - 分别获取低质量/高质量数据列表。

##### 7. 结果合并

- `merge_result_info(existing_list, new_item)`
  - 合并同一 data_id 的评测结果，去重类型、名称、原因。

---

## 三、执行流程（有序步骤）

1. **初始化 LocalExecutor**
   创建 LocalExecutor 实例，传入 InputArgs 参数。

2. **加载数据**
   调用 `load_data` 方法，根据输入参数加载数据集，返回数据生成器。

3. **应用模型配置**
   调用 `Model.apply_config`，根据配置文件和分组名应用评测规则、Prompt、LLM 等配置。

4. **创建输出目录**
   根据当前时间和 UUID 生成唯一输出目录，并在需要时创建。

5. **选择 LLM**
   根据配置文件选择并初始化当前使用的大语言模型（LLM）。

6. **初始化 SummaryModel**
   创建 SummaryModel 实例，用于统计和汇总评测任务信息。

7. **批量评测**
   调用 `evaluate` 方法，按 batch_size 分批调度线程池/进程池，对每批数据进行评测。

8. **对每条数据进行评测（rule/prompt）**
   针对每条数据，分别对 rule 分组和 prompt 分组进行评测，调用相应的评测方法。

9. **聚合结果，写出单条数据**
   聚合每条数据的评测结果，写出到对应的输出文件。

10. **实时更新 summary**
    在评测过程中，实时更新 SummaryModel 的统计信息。

11. **写出 summary.json**
    评测结束后，将 summary 信息写出为 summary.json 文件。

12. **返回 SummaryModel**
    返回最终的 SummaryModel 结果，供后续分析或展示使用。

---

## 四、设计亮点

- **高并发支持**：灵活选择线程池/进程池，兼容本地多核与分布式部署。
- **分组评测**：支持 rule、prompt 分组，便于扩展多种评测维度。
- **动态模型配置**：与 Model 配合，支持按配置文件动态切换评测规则、LLM、Prompt。
- **结果结构化输出**：单条数据与 summary 分别输出，便于后续分析与复现。
- **高/低质量数据筛选**：内置高低质量数据快速检索接口。

---

## 五、注意事项

- 需保证输入参数（InputArgs）和配置文件格式正确。
- 评测规则、Prompt、LLM 需提前注册并实现对应接口。
- 输出目录需有写权限，且不会与历史任务冲突。
- 多进程模式下，需注意环境变量 `LOCAL_DEPLOYMENT_MODE` 的设置。

---

## 六、典型用法

```python
from dingo.io import InputArgs
from dingo.exec.local import LocalExecutor

input_args = InputArgs(
    dataset="my_dataset",
    custom_config="config.yaml",
    eval_group="default",
    output_path="./outputs",
    ...
)
executor = LocalExecutor(input_args)
summary = executor.execute()
print(summary.to_dict())
```

---

## 七、总结

`dingo.exec.local` 是 Dingo 评测系统的本地执行核心，具备高并发、灵活分组、动态配置、结构化输出等特性，适合大规模自动化评测任务。其设计充分考虑了扩展性与易用性，是构建智能评测流水线的重要基础模块。
