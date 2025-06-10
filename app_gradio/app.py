import json
import os
import shutil
from pathlib import Path

import gradio as gr
from dingo.exec import Executor
from dingo.io import InputArgs


def dingo_demo(dataset_source, input_path, uploaded_file, data_format, column_content, rule_list, prompt_list, model,
               key, api_url):
    if not data_format:
        raise gr.Error('ValueError: data_format can not be empty, please input.')
    if not column_content:
        raise gr.Error('ValueError: column_content can not be empty, please input.')
    if not rule_list and not prompt_list:
        raise gr.Error('ValueError: rule_list and prompt_list can not be empty at the same time.')

    # Handle input path based on dataset source
    if dataset_source == "hugging_face":
        if not input_path:
            raise gr.Error('ValueError: input_path can not be empty for hugging_face dataset, please input.')
        final_input_path = input_path
    else:  # local
        if not uploaded_file:
            raise gr.Error('Please upload a file for local dataset.')

        file_base_name = os.path.basename(uploaded_file.name)
        if not str(file_base_name).endswith(('.jsonl', '.json', '.txt')):
            raise gr.Error('File format must be \'.jsonl\', \'.json\' or \'.txt\'')

        final_input_path = uploaded_file.name

    try:
        input_data = {
            "dataset": dataset_source,
            "input_path": final_input_path,
            "output_path": "" if dataset_source == 'hugging_face' else os.path.dirname(final_input_path),
            "save_data": True,
            "save_raw": True,
            "data_format": data_format,
            "column_content": column_content,
            "custom_config":{
                "rule_list": rule_list,
                "prompt_list": prompt_list,
                "llm_config":
                    {
                        "LLMTextQualityPromptBase":
                            {
                                "model": model,
                                "key": key,
                                "api_url": api_url,
                            }
                    }
            }
        }
        input_args = InputArgs(**input_data)
        executor = Executor.exec_map["local"](input_args)
        summary = executor.execute().to_dict()
        detail = executor.get_bad_info_list()
        new_detail = []
        for item in detail:
            new_detail.append(item)
        if summary['output_path']:
            shutil.rmtree(summary['output_path'])

        # 返回两个值：概要信息和详细信息
        return json.dumps(summary, indent=4), new_detail
    except Exception as e:
        raise gr.Error(str(e))


def update_input_components(dataset_source):
    # 根据数据源的不同，返回不同的输入组件
    if dataset_source == "hugging_face":
        # 如果数据源是huggingface，返回一个可见的文本框和一个不可见的文件组件
        return [
            gr.Textbox(visible=True),
            gr.File(visible=False),
        ]
    else:  # local
        # 如果数据源是本地，返回一个不可见的文本框和一个可见的文件组件
        return [
            gr.Textbox(visible=False),
            gr.File(visible=True),
        ]


if __name__ == '__main__':
    rule_options = ['RuleAbnormalChar', 'RuleAbnormalHtml', 'RuleContentNull', 'RuleContentShort', 'RuleEnterAndSpace', 'RuleOnlyUrl']
    prompt_options = ['PromptRepeat', 'PromptContentChaos']

    current_dir = Path(__file__).parent
    with open(os.path.join(current_dir, 'header.html'), "r") as file:
        header = file.read()
    with gr.Blocks() as demo:
        gr.HTML(header)
        with gr.Row():
            with gr.Column():
                with gr.Column():
                    dataset_source = gr.Dropdown(
                        choices=["hugging_face", "local"],
                        value="hugging_face",
                        label="dataset [source]"
                    )
                    input_path = gr.Textbox(
                        value='chupei/format-jsonl',
                        placeholder="please input hugging_face dataset path",
                        label="input_path",
                        visible=True
                    )
                    uploaded_file = gr.File(
                        label="upload file",
                        visible=False
                    )

                    data_format = gr.Dropdown(
                        ["jsonl", "json", "plaintext", "listjson"],
                        label="data_format"
                    )
                    column_content = gr.Textbox(
                        value="content",
                        placeholder="please input column name of content in dataset",
                        label="column_content"
                    )

                    rule_list = gr.CheckboxGroup(
                        choices=rule_options,
                        value=['RuleAbnormalChar', 'RuleAbnormalHtml'],
                        label="rule_list"
                    )
                    prompt_list = gr.CheckboxGroup(
                        choices=prompt_options,
                        label="prompt_list"
                    )
                    model = gr.Textbox(
                        placeholder="If want to use llm, please input model, such as: deepseek-chat",
                        label="model"
                    )
                    key = gr.Textbox(
                        placeholder="If want to use llm, please input key, such as: 123456789012345678901234567890xx",
                        label="API KEY"
                    )
                    api_url = gr.Textbox(
                        placeholder="If want to use llm, please input api_url, such as: https://api.deepseek.com/v1",
                        label="API URL"
                    )

                with gr.Row():
                    submit_single = gr.Button(value="Submit", interactive=True, variant="primary")

            with gr.Column():
                # 修改输出组件部分，使用Tabs
                with gr.Tabs():
                    with gr.Tab("Result Summary"):
                        summary_output = gr.Textbox(label="summary", max_lines=50)
                    with gr.Tab("Result Detail"):
                        detail_output = gr.JSON(label="detail", max_height=800)  # 使用JSON组件来更好地展示结构化数据

        dataset_source.change(
            fn=update_input_components,
            inputs=dataset_source,
            outputs=[input_path, uploaded_file]
        )

        submit_single.click(
            fn=dingo_demo,
            inputs=[dataset_source, input_path, uploaded_file, data_format, column_content, rule_list, prompt_list,
                    model, key, api_url],
            outputs=[summary_output, detail_output]  # 修改输出为两个组件
        )

    # 启动界面
    demo.launch()
