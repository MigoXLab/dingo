import json
import os
import shutil
import pprint
from pathlib import Path
from functools import partial

import gradio as gr

from dingo.exec import Executor
from dingo.io import InputArgs


def dingo_demo(
        uploaded_file,
        dataset_source, data_format, input_path, max_workers, batch_size,
        column_id, column_prompt, column_content, column_image,
        rule_list, prompt_list, scene_list,
        model, key, api_url
    ):
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

    if max_workers <= 0:
        raise gr.Error('Please input value > 0 in max_workers.')
    if batch_size <= 0:
        raise gr.Error('Please input value > 0 in batch_size.')

    try:
        input_data = {
            "dataset": dataset_source,
            "data_format": data_format,
            "input_path": final_input_path,
            "output_path": "" if dataset_source == 'hugging_face' else os.path.dirname(final_input_path),
            "save_data": True,
            "save_raw": True,

            "max_workers": max_workers,
            "batch_size": batch_size,

            "column_content": column_content,
            "custom_config":{
                "rule_list": rule_list,
                "prompt_list": prompt_list,
                "llm_config": {
                    scene_list: {
                        "model": model,
                        "key": key,
                        "api_url": api_url,
                    }
                }
            }
        }
        if column_id:
            input_data['column_id'] = column_id
        if column_prompt:
            input_data['column_prompt'] = column_prompt
        if column_image:
            input_data['column_image'] = column_image

        # print(input_data)
        # exit(0)

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

def update_prompt_list(scene_prompt_mapping, scene):
    """根据选择的场景更新可用的prompt列表"""
    return gr.CheckboxGroup(
        choices=scene_prompt_mapping.get(scene, []),
        label="prompt_list"
    )

if __name__ == '__main__':
    rule_options = ['RuleAbnormalChar', 'RuleAbnormalHtml', 'RuleContentNull', 'RuleContentShort', 'RuleEnterAndSpace', 'RuleOnlyUrl']
    # prompt_options = ['PromptRepeat', 'PromptContentChaos']
    scene_options = []
    scene_prompt_mapping = {
        # 示例映射关系，你可以根据实际需求修改
        "LLMTextQualityPromptBase": ['PromptRepeat', 'PromptContentChaos'],
        'LLMTextQualityModelBase': ['PromptTextQualityV3', 'PromptTextQualityV4'],
        'LLMSecurityPolitics': ['PromptPolitics'],
        'LLMSecurityProhibition': ['PromptProhibition'],
        'LLMText3HHarmless': ['PromptTextHelpful'],
        'LLMText3HHelpful': ['PromptTextHelpful'],
        'LLMText3HHonest': ['PromptTextHonest'],
        'LLMClassifyTopic': ['PromptClassifyTopic'],
        'LLMClassifyQR': ['PromptClassifyQR'],
        "VLMImageRelevant": ["PromptImageRelevant"],
    }
    scene_options = list(scene_prompt_mapping.keys())

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
                    with gr.Row():
                        max_workers = gr.Number(
                            value=1,
                            # placeholder="",
                            label="max_workers",
                            precision=0
                        )
                        batch_size = gr.Number(
                            value=1,
                            # placeholder="",
                            label="batch_size",
                            precision=0
                        )
                    with gr.Row():
                        column_id = gr.Textbox(
                            value="",
                            # placeholder="please input column name of data id in dataset",
                            label="column_id"
                        )
                        column_prompt = gr.Textbox(
                            value="",
                            # placeholder="please input column name of prompt in dataset",
                            label="column_prompt"
                        )
                        column_content = gr.Textbox(
                            value="content",
                            # placeholder="please input column name of content in dataset",
                            label="column_content"
                        )
                        column_image = gr.Textbox(
                            value="",
                            # placeholder="please input column name of image in dataset",
                            label="column_image"
                        )

                    rule_list = gr.CheckboxGroup(
                        choices=rule_options,
                        value=['RuleAbnormalChar', 'RuleAbnormalHtml'],
                        label="rule_list"
                    )
                    # 添加场景选择下拉框
                    scene_list = gr.Dropdown(
                        choices=scene_options,
                        value=scene_options[0],
                        label="scene_list",
                        interactive=True
                    )
                    prompt_list = gr.CheckboxGroup(
                        choices=scene_prompt_mapping.get(scene_options[0]),
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

        # 场景变化时更新prompt列表
        scene_list.change(
            fn=partial(update_prompt_list, scene_prompt_mapping),
            inputs=scene_list,
            outputs=prompt_list
        )

        submit_single.click(
            fn=dingo_demo,
            inputs=[
                uploaded_file,
                dataset_source, data_format, input_path, max_workers, batch_size,
                column_id, column_prompt, column_content, column_image,
                rule_list, prompt_list, scene_list,
                model, key, api_url
            ],
            outputs=[summary_output, detail_output]  # 修改输出为两个组件
        )

    # 启动界面
    demo.launch()
