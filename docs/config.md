# Config

`Dingo` 为不同模块设置了各自的配置，让用户可以更加自由地使用项目完成自身的质检需求。

## Cli Config

用户在命令行输入指令启动项目时会使用到的参数，本质是为了实例化`InputArgs`类：

| Parameter                 | Type |             Default              | Required | Description                                                                                  |
|---------------------------|------|:--------------------------------:|:--------:|----------------------------------------------------------------------------------------------|
| --task_name / -n          | str  |             "dingo"              |    No    | task name.                                                                                   |
| --eval_group / -e         | str  |                ""                |   Yes    | Eval models, can be specified multiple times like '-e default' or '-e pretrain'              |
| --input_path / -i         | str  | "test/data/test_local_json.json" |   Yes    | file or directory path to check.                                                             |
| --output_path             | str  |            "outputs/"            |    No    | output path of result.                                                                       |
| --save_data               | bool |              False               |    No    | whether save results into files.                                                             |
| --save_correct            | bool |              False               |    No    | whether save correct data.                                                                   |
| --save_raw                | bool |              False               |    No    | whether save raw data.                                                                       |
| --start_index             | int  |                0                 |    No    | the number of data start to check.                                                           |
| --end_index               | int  |                -1                |    No    | the number of data end to check. if it's negative, include the data from start_index to end. |
| --max_workers             | int  |                1                 |    No    | the number of max workers to concurrent check.                                               |
| --batch_size              | int  |                1                 |    No    | the number of max data for concurrent check.                                                 |
| --dataset                 | str  |          "hugging_face"          |   Yes    | dataset type, in ['hugging_face', 'local']                                                   |
| --data_format             | str  |              "json"              |   Yes    | data format, such as: ['json', 'jsonl', 'plaintext', 'listjson'].                            |
| --huggingface_split       | str  |                ""                |    No    | Huggingface split, default is 'train'                                                        |
| --huggingface_config_name | str  |               None               |    No    | Huggingface config name                                                                      |
| --column_id               | str  |                ""                | Depends  | Column name of id in the input file. If exists multiple levels, use '.' separate             |
| --column_prompt           | str  |                ""                | Depends  | Column name of prompt in the input file. If exists multiple levels, use '.' separate         |
| --column_content          | str  |                ""                |   Yes    | Column name of content in the input file. If exists multiple levels, use '.' separate        |
| --column_image            | str  |                ""                | Depends  | Column name of image in the input file. If exists multiple levels, use '.' separate          |
| --custom_config           | str  |               None               | Depends  | Custom config file path                                                                      |
| --log_level               | str  |            "WARNING"             |    No    | printing level of logs, in ['DEBUG', 'INFO', 'WARNING', 'ERROR']                             |

 ## SDK Config

用户通过SDK方式启动项目时会使用到的参数，即`InputArgs`类：

| Parameter               | Type                  |             Default              | Required | Description                                                                                  |
|-------------------------|-----------------------|:--------------------------------:|:--------:|----------------------------------------------------------------------------------------------|
| task_name               | str                   |             "dingo"              |    No    | task name .                                                                                  |
| eval_group              | str                   |                ""                |   Yes    | eval model.                                                                                  |
| input_path              | str                   | "test/data/test_local_json.json" |   Yes    | file or directory path to check.                                                             |
| output_path             | str                   |            "outputs/"            |    No    | output path of result.                                                                       |
| save_data               | bool                  |              False               |    No    | whether save results into files.                                                             |
| save_correct            | bool                  |              False               |    No    | whether save correct data.                                                                   |
| save_raw                | bool                  |              False               |    No    | whether save raw data.                                                                       |
| start_index             | int                   |                0                 |    No    | the number of data start to check.                                                           |
| end_index               | int                   |                -1                |    No    | the number of data end to check. if it's negative, include the data from start_index to end. |
| max_workers             | int                   |                1                 |    No    | the number of max workers to concurrent check.                                               |
| batch_size              | int                   |                1                 |    No    | the number of max data for concurrent check.                                                 |
| dataset                 | str                   |          "hugging_face"          |   Yes    | dataset type, in ['hugging_face', 'local']                                                   |
| data_format             | str                   |              "json"              |   Yes    | data format, such as: ['json', 'jsonl', 'plaintext', 'listjson'].                            |
| huggingface_split       | str                   |                ""                |    No    | Huggingface split                                                                            |
| huggingface_config_name | Optional[str]         |               None               |    No    | Huggingface config name                                                                      |
| column_id               | str                   |                ""                | Depends  | Column name of id in the input file. If exists multiple levels, use '.' separate             |
| column_prompt           | str                   |                ""                | Depends  | Column name of prompt in the input file. If exists multiple levels, use '.' separate         |
| column_content          | str                   |                ""                |   Yes    | Column name of content in the input file. If exists multiple levels, use '.' separate        |
| column_image            | str                   |                ""                | Depends  | Column name of image in the input file. If exists multiple levels, use '.' separate          |
| custom_config           | Optional[str \| dict] |               None               | Depends  | custom config, file path or dict                                                             |
| log_level               | str                   |            "WARNING"             |    No    | printing level of logs, in ['DEBUG', 'INFO', 'WARNING', 'ERROR']                             |

## Custom Config

`Dingo` 通过启发式规则、第三方质量检测工具或服务以及大型模型，使用户能够个性化他们的数据质量检查方法。这些能力可以通过配置来实现。
进一步来说，就是使用上述配置项中提到的 `custom_config` 的参数，该参数指向配置文件路径或字典。如果所指向的是文件，那么文件中仅包含一个json格式
的数据，例如： [config_template.json](../test/config/config_template.json)

| Parameter       | Type | Description                                              |
|-----------------|------|----------------------------------------------------------|
| rule_list       | list | choose these functions as a group to check data quality. |
| prompt_list     | list | choose these prompts as a group to check data quality.   |
| rule_config     | dict | parameters related to rules and key is rule name.        |
| llm_config      | dict | parameters related to llm and key is llm name.           |
| multi_turn_mode | str  | choose parse mode for multi-turn dialogue.               |

`rule_list` 和 `prompt_list` 参数与上述提到的 `eval_group` 配合使用。
如果 `eval_group` 已经内置，那 `rule_list` 和 `prompt_list` 则报错提示。
如果 `eval_group` 没有内置，那么项目则根据 `rule_list` 和 `prompt_list` 罗列的规则与prompt进行质检。
具体的使用方法，可以参考：[sdk_custom_rule.py](../examples/custom/sdk_custom_rule.py)、[sdk_custom_llm.py](../examples/custom/sdk_custom_llm.py)

### rule_config

启发式规则是数据处理和质量检查的常用方法，`Dingo` 已经实施了一系列启发式规则，并将其分为规则组，如 `pretrain` 和 `sft`。
在配置文件的模板中，与启发式规则配置相关的项是 `rule_config` ，它的key是具体的规则名称。
通过 `rule_config` 用户可以在不去修改源代码的情况下，动态的设置规则中的阈值、模式、关键词列表与引用路径。

| Parameter          | Type     | Description                                                |
|--------------------|----------|------------------------------------------------------------|
| threshold          | float    | rule uses the number to decide.                            |
| pattern            | string   | rule uses the character string to match.                   |
| key_list           | list     | rule uses these keys to match.                             |
| refer_path         | list     | rule loads the file content or small models.               |

### llm_config

`Dingo` 在进行大模型质检时，一些必要的配置是无法避免的，比如密钥、链接等。但是考虑到隐私与安全问题，用户需要自行设置且对他人保密。、
所以上述的 `llm_config` 参数就显得十分必要，它的key是项目注册的大语言模型，如 `openai`。

| Parameter  | Type | Description                                         |
|------------|------|-----------------------------------------------------|
| model      | list | llm uses which model.                               |
| key        | list | llm uses the key to verify identity.                |
| api_url    | list | llm uses the url to access the model.               |
| parameters | dict | llm uses the parameters to tune LLM configurations. |

#### parameters

`temperature` 数字类型，可选。默认为 1。要使用的采样温度(temperature)，介于 0 和 2 之间。
我们通常建议只修改此参数或 top_p 一个参数而不是两个同时修改。

`top_p` 数字类型，可选。默认为 1。
我们通常建议只修改此参数或 temperature 一个参数而不是两个同时修改。

`max_tokens` 整数类型，可选。默认为 4000。要生成的最大令牌数。

`presence_penalty` 数字类型，可选。默认为 0。介于 -2.0 和 2.0 之间的数字。

`frequency_penalty` 数字类型，可选。默认为 0。范围在 -2.0 到 2.0 之间的数字。

更多参数细节可参考OpenAI API官方文档。

### multi_turn_mode

`Dingo` 支持多轮对话数据质检，如MT-Bench、MT-Bench++和MT-Bench101，其中包含多轮对话质检的解析模式。

| Parameter | Type |                Description                |
|-----------|------|-------------------------------------------|
| all       | str  | concat all turns in multi-turn dialogues. |

具体的使用方法，可以参考：
[sdk_mtbench101_rule_all.py](../examples/multi_turn_dialogues/sdk_mtbench101_rule_all.py)、[sdk_mtbench101_llm.py](../examples/multi_turn_dialogues/sdk_mtbench101_llm.py)、
[sdk_mtbench_rule_all.py](../examples/multi_turn_dialogues/sdk_mtbench_rule_all.py)、[sdk_mtbench_llm.py](../examples/multi_turn_dialogues/sdk_mtbench_llm.py)。
