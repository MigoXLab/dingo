import json
import os
import pprint
import shutil
from functools import partial
from pathlib import Path

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


def update_rule_list(rule_type_mapping, rule_type):
    return gr.CheckboxGroup(
        choices=rule_type_mapping.get(rule_type, []),
        value=[],
        label="rule_list"
    )


def update_prompt_list(scene_prompt_mapping, scene):
    """根据选择的场景更新可用的prompt列表，并清空所有勾选"""
    return gr.CheckboxGroup(
        choices=scene_prompt_mapping.get(scene, []),
        value=[],  # 清空所有勾选
        label="prompt_list"
    )


# prompt_list变化时，动态控制model、key、api_url的显示
def toggle_llm_fields(prompt_values):
    visible = bool(prompt_values)
    return (
        gr.update(visible=visible),
        gr.update(visible=visible),
        gr.update(visible=visible)
    )


# 控制column_id、column_prompt、column_content、column_image的显示
def update_column_fields(rule_list, prompt_list):
    rule_type_mapping = get_rule_type_mapping()
    scene_prompt_mapping = get_scene_prompt_mapping()
    data_column_mapping = get_data_column_mapping()
    status_mapping = {
        'id': False,
        'prompt': False,
        'content': False,
        'image': False,
    }

    res = (
        gr.update(visible=status_mapping['id']),
        gr.update(visible=status_mapping['prompt']),
        gr.update(visible=status_mapping['content']),
        gr.update(visible=status_mapping['image'])
    )
    if not rule_list and not prompt_list:
        return res

    key_list = []
    key_list += get_key_by_mapping(rule_type_mapping, rule_list)
    key_list += get_key_by_mapping(scene_prompt_mapping, prompt_list)

    data_column = []
    for key in key_list:
        if not data_column:
            data_column = data_column_mapping[key]
        else:
            new_data_column = data_column_mapping[key]
            if data_column != new_data_column:
                raise gr.Error(f'ConflictError: {key} need data type is different from other.')

    for c in data_column:
        status_mapping[c] = True
    res = (
        gr.update(visible=status_mapping['id']),
        gr.update(visible=status_mapping['prompt']),
        gr.update(visible=status_mapping['content']),
        gr.update(visible=status_mapping['image'])
    )
    return res


def get_rule_type_mapping():
    return {
        'QUALITY_BAD_COMPLETENESS': ['RuleLineEndWithEllipsis', 'RuleLineEndWithTerminal', 'RuleSentenceNumber',
                                     'RuleWordNumber'],
        'QUALITY_BAD_EFFECTIVENESS': ['RuleAbnormalChar', 'RuleAbnormalHtml', 'RuleAlphaWords', 'RuleCharNumber',
                                      'RuleColonEnd', 'RuleContentNull', 'RuleContentShort', 'RuleContentShortMultiLan',
                                      'RuleEnterAndSpace', 'RuleEnterMore', 'RuleEnterRatioMore', 'RuleHtmlEntity',
                                      'RuleHtmlTag', 'RuleInvisibleChar', 'RuleLineJavascriptCount', 'RuleLoremIpsum',
                                      'RuleMeanWordLength', 'RuleSpaceMore', 'RuleSpecialCharacter', 'RuleStopWord',
                                      'RuleSymbolWordRatio', 'RuleOnlyUrl'],
        'QUALITY_BAD_FLUENCY': ['RuleAbnormalNumber', 'RuleCharSplit', 'RuleNoPunc', 'RuleWordSplit', 'RuleWordStuck'],
        'QUALITY_BAD_RELEVANCE': ['RuleHeadWordAr'],
        'QUALITY_BAD_SIMILARITY': ['RuleDocRepeat'],
        'QUALITY_BAD_UNDERSTANDABILITY': ['RuleCapitalWords', 'RuleCurlyBracket', 'RuleLineStartWithBulletpoint',
                                          'RuleUniqueWords'],
        'QUALITY_BAD_IMG_EFFECTIVENESS': ['RuleImageValid', 'RuleImageSizeValid', 'RuleImageQuality'],
        'QUALITY_BAD_IMG_RELEVANCE': ['RuleImageTextSimilarity'],
        'QUALITY_BAD_IMG_SIMILARITY': ['RuleImageRepeat']
    }


def get_scene_prompt_mapping():
    return {
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


def get_key_by_mapping(map_dict: dict, value_list: list):
    key_list = []
    for k,v in map_dict.items():
        if bool(set(v) & set(value_list)):
            key_list.append(k)

    return key_list


def get_data_column_mapping():
    return {
        'LLMTextQualityPromptBase': ['content'],
        'LLMTextQualityModelBase': ['content'],
        'LLMSecurityPolitics': ['content'],
        'LLMSecurityProhibition': ['content'],
        'LLMText3HHarmless': ['content'],
        'LLMText3HHelpful': ['content'],
        'LLMText3HHonest': ['content'],
        'LLMClassifyTopic': ['content'],
        'LLMClassifyQR': ['content'],
        'VLMImageRelevant': ['prompt', 'content'],
        'QUALITY_BAD_COMPLETENESS': ['content'],
        'QUALITY_BAD_EFFECTIVENESS': ['content'],
        'QUALITY_BAD_FLUENCY': ['content'],
        'QUALITY_BAD_RELEVANCE': ['content'],
        'QUALITY_BAD_SIMILARITY': ['content'],
        'QUALITY_BAD_UNDERSTANDABILITY': ['content'],
        'QUALITY_BAD_IMG_EFFECTIVENESS': ['image'],
        'QUALITY_BAD_IMG_RELEVANCE': ['content','image'],
        'QUALITY_BAD_IMG_SIMILARITY': ['content'],
    }


if __name__ == '__main__':
    rule_type_mapping = get_rule_type_mapping()
    rule_type_options = list(rule_type_mapping.keys())

    scene_prompt_mapping = get_scene_prompt_mapping()
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

                    # Add the rule_type dropdown near where scene_list is defined
                    rule_type = gr.Dropdown(
                        choices=rule_type_options,
                        value=rule_type_options[0],
                        label="rule_type",
                        interactive=True
                    )
                    rule_list = gr.CheckboxGroup(
                        choices=rule_type_mapping.get(rule_type_options[0], []),
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
                        choices=scene_prompt_mapping.get(scene_options[0], []),
                        label="prompt_list"
                    )
                    # LLM模型名
                    model = gr.Textbox(
                        placeholder="If want to use llm, please input model, such as: deepseek-chat",
                        label="model",
                        visible=False
                    )
                    # LLM API KEY
                    key = gr.Textbox(
                        placeholder="If want to use llm, please input key, such as: 123456789012345678901234567890xx",
                        label="API KEY",
                        visible=False
                    )
                    # LLM API URL
                    api_url = gr.Textbox(
                        placeholder="If want to use llm, please input api_url, such as: https://api.deepseek.com/v1",
                        label="API URL",
                        visible=False
                    )

                    with gr.Row():
                        # 字段映射说明文本，带示例链接
                        with gr.Column():
                            gr.Markdown("Field Matching: Please input the column name of dataset in the input boxes below ( [examples](https://github.com/MigoXLab/dingo/tree/main/examples) )")

                        column_id = gr.Textbox(
                            value="",
                            placeholder="Column name of id in the input file. If exists multiple levels, use '.' separate",
                            label="column_id",
                            visible=False
                        )
                        column_prompt = gr.Textbox(
                            value="",
                            placeholder="Column name of prompt in the input file. If exists multiple levels, use '.' separate",
                            label="column_prompt",
                            visible=False
                        )
                        column_content = gr.Textbox(
                            value="content",
                            placeholder="Column name of content in the input file. If exists multiple levels, use '.' separate",
                            label="column_content",
                            visible=False
                        )
                        column_image = gr.Textbox(
                            value="",
                            placeholder="Column name of image in the input file. If exists multiple levels, use '.' separate",
                            label="column_image",
                            visible=False
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

        rule_type.change(
            fn=partial(update_rule_list, rule_type_mapping),
            inputs=rule_type,
            outputs=rule_list
        )

        # 场景变化时更新prompt列表
        scene_list.change(
            fn=partial(update_prompt_list, scene_prompt_mapping),
            inputs=scene_list,
            outputs=prompt_list
        )

        prompt_list.change(
            fn=toggle_llm_fields,
            inputs=prompt_list,
            outputs=[model, key, api_url]
        )

        # column字段显示控制
        for comp in [rule_list, prompt_list]:
            comp.change(
                fn=update_column_fields,
                inputs=[rule_list, prompt_list],
                outputs=[column_id, column_prompt, column_content, column_image]
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
