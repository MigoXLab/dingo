import json

import gradio as gr
from dingo.exec import Executor
from dingo.io import InputArgs


def dingo_demo(input_path, data_format, column_content, rule_list, prompt_list, key, api_url):
    if not input_path:
        return 'ValueError: input_path can not be empty, please input.'
    if not data_format:
        return 'ValueError: data_format can not be empty, please input.'
    if not column_content:
        return 'ValueError: column_content can not be empty, please input.'
    if not rule_list and not prompt_list:
        return 'ValueError: rule_list and prompt_list can not be empty at the same time.'

    input_data = {
        "input_path": input_path,
        "data_format": data_format,
        "column_content": column_content,
        "custom_config":
            {
                "rule_list": rule_list,
                "prompt_list": prompt_list,
                "llm_config":
                    {
                        "detect_text_quality_detail":
                            {
                                "key": key,
                                "api_url": api_url,
                            }
                    }
            }
    }
    input_args = InputArgs(**input_data)
    executor = Executor.exec_map["local"](input_args)
    result = executor.execute()
    summary = result[0].to_dict()
    return json.dumps(summary, indent=4)


if __name__ == '__main__':
    rule_options = ['RuleAbnormalChar', 'RuleAbnormalHtml', 'RuleContentNull', 'RuleContentShort', 'RuleEnterAndSpace', 'RuleOnlyUrl']
    prompt_options = ['PromptRepeat', 'PromptContentChaos']

    with open("header.html", "r") as file:
        header = file.read()
    with gr.Blocks() as demo:
        gr.HTML(header)
        with gr.Row():
            with gr.Column():
                input_path = gr.Textbox(value='chupei/format-jsonl', placeholder="please input huggingface dataset path", label="input_path")
                data_format = gr.Dropdown(["jsonl", "json", "plaintext", "listjson"], label="data_format")
                column_content = gr.Textbox(value="content", placeholder="please input column name of content in dataset", label="column_content")
                rule_list = gr.CheckboxGroup(choices=rule_options, label="rule_list")
                prompt_list = gr.CheckboxGroup(choices=prompt_options, label="prompt_list")
                key = gr.Textbox(placeholder="If want to use llm, please input the key of it.", label="key")
                api_url = gr.Textbox(placeholder="If want to use llm, please input the api_url of it.", label="api_url")
                with gr.Row():
                    submit_single = gr.Button(value="Submit", interactive=True, variant="primary")
            with gr.Column():
                # 输出组件
                output = gr.Textbox(label="output")

        submit_single.click(
            fn=dingo_demo,
            inputs=[input_path, data_format, column_content, rule_list, prompt_list, key, api_url],
            outputs=output
        )

    # 启动界面
    demo.launch()
