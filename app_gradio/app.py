import json
import os
import pprint
import shutil
from functools import partial
from pathlib import Path

import gradio as gr

from dingo.config import InputArgs
from dingo.exec import Executor
from dingo.model import Model


def dingo_demo(
        uploaded_file,
        dataset_source, data_format, input_path, max_workers, batch_size,
        fields_data,
        rule_list, llm_list,
        # rule_config_data,
        llm_config_data
):
    if not data_format:
        raise gr.Error('ValueError: data_format can not be empty, please input.')

    if not rule_list and not llm_list:
        raise gr.Error('ValueError: rule_list and llm_list can not be empty at the same time.')

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
        # Parse fields from dataframe
        fields = {}
        if fields_data is not None and len(fields_data) > 0:
            for row in fields_data.values.tolist():
                if len(row) >= 2 and row[0] and row[1]:  # Both key and value are not empty
                    fields[row[0]] = row[1]

        # Parse rule configs from dataframe
        rule_configs = {}
        # if rule_config_data is not None and len(rule_config_data) > 0:
        #     for row in rule_config_data.values.tolist():
        #         if len(row) >= 6 and row[0]:  # Rule name exists
        #             rule_name = row[0]
        #             config = {}
        #
        #             # threshold
        #             if row[1] is not None and str(row[1]).strip():
        #                 try:
        #                     config['threshold'] = float(row[1])
        #                 except:
        #                     pass
        #
        #             # pattern
        #             if row[2] and str(row[2]).strip():
        #                 config['pattern'] = str(row[2])
        #
        #             # key_list
        #             if row[3] and str(row[3]).strip():
        #                 try:
        #                     val = str(row[3])
        #                     config['key_list'] = json.loads(val) if val.startswith('[') else [k.strip() for k in val.split(',') if k.strip()]
        #                 except:
        #                     config['key_list'] = [k.strip() for k in str(row[3]).split(',') if k.strip()]
        #
        #             # refer_path
        #             if row[4] and str(row[4]).strip():
        #                 try:
        #                     val = str(row[4])
        #                     config['refer_path'] = json.loads(val) if val.startswith('[') else [p.strip() for p in val.split(',') if p.strip()]
        #                 except:
        #                     config['refer_path'] = [p.strip() for p in str(row[4]).split(',') if p.strip()]
        #
        #             # parameters
        #             if row[5] and str(row[5]).strip():
        #                 try:
        #                     config['parameters'] = json.loads(str(row[5]))
        #                 except:
        #                     pass
        #
        #             if config:
        #                 rule_configs[rule_name] = config

        # Parse llm configs from dataframe
        llm_configs = {}
        if llm_config_data is not None and len(llm_config_data) > 0:
            for row in llm_config_data.values.tolist():
                if len(row) >= 5 and row[0]:  # LLM name exists
                    llm_name = row[0]
                    config = {}

                    # model
                    if row[1] and str(row[1]).strip():
                        config['model'] = str(row[1])

                    # key
                    if row[2] and str(row[2]).strip():
                        config['key'] = str(row[2])

                    # api_url
                    if row[3] and str(row[3]).strip():
                        config['api_url'] = str(row[3])

                    # parameters
                    if row[4] and str(row[4]).strip():
                        try:
                            config['parameters'] = json.loads(str(row[4]))
                        except Exception:
                            pass

                    if config:
                        llm_configs[llm_name] = config

        # Build evals array
        evals = []

        # Add rule evaluators and their configurations
        for rule in rule_list:
            eval_item = {"name": rule}
            if rule in rule_configs:
                eval_item["config"] = rule_configs[rule]
            evals.append(eval_item)

        # Add LLM evaluators and their configurations
        for llm in llm_list:
            eval_item = {"name": llm}
            if llm in llm_configs:
                eval_item["config"] = llm_configs[llm]
            evals.append(eval_item)

        input_data = {
            "input_path": final_input_path,
            "output_path": "" if dataset_source == 'hugging_face' else os.path.dirname(final_input_path),
            "dataset": {
                "source": dataset_source,
                "format": data_format,
            },
            "executor": {
                "result_save": {
                    "bad": True,
                    "good": True
                },
                "max_workers": max_workers,
                "batch_size": batch_size,
            },
            "evaluator": [
                {
                    "fields": fields,
                    "evals": evals
                }
            ]
        }

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

        # Return summary and detail information
        return json.dumps(summary, indent=4), new_detail
    except Exception as e:
        raise gr.Error(str(e))


def update_input_components(dataset_source):
    # Return different input components based on data source
    if dataset_source == "hugging_face":
        # If data source is huggingface, return a visible textbox and an invisible file component
        return [
            gr.Textbox(visible=True),
            gr.File(visible=False),
        ]
    else:  # local
        # If data source is local, return an invisible textbox and a visible file component
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


# Generate configuration dataframes based on selected evaluators
# def generate_rule_config_dataframe(rule_list):
#     """Generate rule configuration dataframe based on selected rules"""
#     if not rule_list:
#         return gr.update(value=[], visible=False)
#
#     # Create rows for each rule
#     rows = []
#     for rule in rule_list:
#         rows.append([rule, None, "", "", "", ""])
#
#     return gr.update(value=rows, visible=True)


def generate_llm_config_dataframe(llm_list):
    """Generate LLM configuration dataframe based on selected LLMs"""
    if not llm_list:
        return gr.update(value=[], visible=False)

    # Create rows for each LLM
    rows = []
    for llm in llm_list:
        rows.append([llm, "deepseek-chat", "your-api-key", "https://api.deepseek.com/v1", ""])

    return gr.update(value=rows, visible=True)


def suggest_fields_dataframe(rule_list, llm_list):
    """Suggest required field mappings based on selected evaluators"""
    suggested_fields = set()

    # Fields required by rule evaluators
    rule_type_mapping = get_rule_type_mapping()
    data_column_mapping = get_data_column_mapping()

    for rule in rule_list:
        # Find which type this rule belongs to
        for rule_type, rules in rule_type_mapping.items():
            if rule in rules:
                if rule_type in data_column_mapping:
                    suggested_fields.update(data_column_mapping[rule_type])
                break

    # Fields required by LLM evaluators
    llm_column_mapping = get_llm_column_mapping()
    for llm in llm_list:
        if llm in llm_column_mapping:
            suggested_fields.update(llm_column_mapping[llm])

    # Generate suggested fields rows
    rows = []
    for field in sorted(suggested_fields):
        rows.append([field, field])

    return gr.update(value=rows if rows else [["content", "content"]])


def get_rule_type_mapping():
    origin_map = Model.get_rule_metric_type_map()
    process_map = {'Rule-Based TEXT Quality Metrics': []}  # can adjust the order
    for k, v in origin_map.items():
        if k in ['QUALITY_BAD_COMPLETENESS', 'QUALITY_BAD_EFFECTIVENESS', 'QUALITY_BAD_FLUENCY',
                 'QUALITY_BAD_RELEVANCE',
                 'QUALITY_BAD_SIMILARITY', 'QUALITY_BAD_UNDERSTANDABILITY']:
            k = 'Rule-Based TEXT Quality Metrics'
        for r in v:
            if k not in process_map:
                process_map[k] = []
            process_map[k].append(r.__name__)
    # print(process_map)

    return process_map


def get_llm_list():
    """Get LLM list from Model.llm_name_map"""
    llm_name_map = Model.get_llm_name_map()
    return list(llm_name_map.keys())


def get_llm_column_mapping():
    """Get column mapping required by each LLM"""
    # Define columns required by each LLM based on actual needs
    # Can be dynamically obtained from Model information, using default configuration for now
    llm_list = get_llm_list()
    mapping = {}
    for llm_name in llm_list:
        # Specify different field requirements based on specific LLM type
        if 'VLM' in llm_name or 'Image' in llm_name:
            mapping[llm_name] = ['content', 'image']
        elif 'Relevant' in llm_name:
            mapping[llm_name] = ['prompt', 'content']
        else:
            mapping[llm_name] = ['content']
    return mapping


def get_data_column_mapping():
    return {
        # Rule mapping
        'Rule-Based TEXT Quality Metrics': ['content'],
        'QUALITY_BAD_SECURITY': ['content'],
        'QUALITY_BAD_IMG_EFFECTIVENESS': ['image'],
        'QUALITY_BAD_IMG_RELEVANCE': ['content', 'image'],
        'QUALITY_BAD_IMG_SIMILARITY': ['content'],
    }


if __name__ == '__main__':
    rule_type_mapping = get_rule_type_mapping()
    rule_type_options = list(rule_type_mapping.keys())

    llm_options = get_llm_list()

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
                        ["jsonl", "json", "plaintext", "listjson","image"],
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
                        label="Rule Type",
                        interactive=True
                    )
                    rule_list = gr.CheckboxGroup(
                        choices=rule_type_mapping.get(rule_type_options[0], []),
                        label="Rule List"
                    )
                    # LLM evaluator list
                    llm_list = gr.CheckboxGroup(
                        choices=llm_options,
                        label="LLM List"
                    )

                    gr.Markdown("### EvalPipline Configuration")
                    gr.Markdown("Configure field mappings and evaluator parameters based on selected evaluators ([Examples](https://github.com/MigoXLab/dingo/tree/main/examples))")

                    # Field mapping configuration
                    gr.Markdown("**EvalPipline.fields** - Field Mapping")
                    fields_dataframe = gr.Dataframe(
                        value=[["content", "content"]],
                        headers=["Field Key", "Dataset Column"],
                        datatype=["str", "str"],
                        col_count=(2, "fixed"),
                        row_count=(1, "dynamic"),
                        label="Field Mappings (add/remove rows as needed)",
                        interactive=True
                    )

                    # Rule configuration
                    # gr.Markdown("**Rule Config** - EvalPiplineConfig.config for Rules")
                    # rule_config_dataframe = gr.Dataframe(
                    #     value=[],
                    #     headers=["Rule Name", "threshold", "pattern", "key_list", "refer_path", "parameters"],
                    #     datatype=["str", "number", "str", "str", "str", "str"],
                    #     col_count=(6, "fixed"),
                    #     row_count=(0, "dynamic"),
                    #     label="Rule Configurations (auto-generated based on rule_list selection)",
                    #     interactive=True,
                    #     visible=False
                    # )

                    # LLM configuration
                    gr.Markdown("**LLM Config** - EvalPiplineConfig.config for LLMs")
                    llm_config_dataframe = gr.Dataframe(
                        value=[],
                        headers=["LLM Name", "model", "key", "api_url", "parameters"],
                        datatype=["str", "str", "str", "str", "str"],
                        col_count=(5, "fixed"),
                        row_count=(0, "dynamic"),
                        label="LLM Configurations (auto-generated based on llm_list selection)",
                        interactive=True,
                        visible=False
                    )

                with gr.Row():
                    submit_single = gr.Button(value="Submit", interactive=True, variant="primary")

            with gr.Column():
                # Output component section, using Tabs
                with gr.Tabs():
                    with gr.Tab("Result Summary"):
                        summary_output = gr.JSON(label="Summary", max_height=800)
                    with gr.Tab("Result Detail"):
                        detail_output = gr.JSON(label="Detail", max_height=800)  # Use JSON component for better structured data display

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

        # Auto-generate configuration dataframes when rule_list changes
        # rule_list.change(
        #     fn=generate_rule_config_dataframe,
        #     inputs=rule_list,
        #     outputs=rule_config_dataframe
        # )

        # Auto-generate configuration dataframes when llm_list changes
        llm_list.change(
            fn=generate_llm_config_dataframe,
            inputs=llm_list,
            outputs=llm_config_dataframe
        )

        # Suggest field mappings when evaluators change
        for comp in [rule_list, llm_list]:
            comp.change(
                fn=suggest_fields_dataframe,
                inputs=[rule_list, llm_list],
                outputs=fields_dataframe
            )

        submit_single.click(
            fn=dingo_demo,
            inputs=[
                uploaded_file,
                dataset_source, data_format, input_path, max_workers, batch_size,
                fields_dataframe,
                rule_list, llm_list,
                # rule_config_dataframe,
                llm_config_dataframe
            ],
            outputs=[summary_output, detail_output]
        )

    # Launch interface
    demo.launch(share=True)
