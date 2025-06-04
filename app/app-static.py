#!/usr/bin/env python

import argparse
import base64
import json
import os
import re


def get_folder_structure(root_path):
    structure = []
    for item in os.listdir(root_path):
        item_path = os.path.join(root_path, item)
        if os.path.isdir(item_path):
            category = {'name': item, 'children': []}
            for subitem in os.listdir(item_path):
                if subitem.endswith('.jsonl'):
                    category['children'].append(
                        {'name': subitem[:-6], 'path': '{0}/{1}'.format(item, subitem)}  # Remove .jsonl extension
                    )
            structure.append(category)
    return structure


def get_summary_data(summary_path):
    with open(summary_path, 'r') as file:
        return json.load(file)


def get_evaluation_details(root_path):
    details = {}
    for item in os.listdir(root_path):
        item_path = os.path.join(root_path, item)
        if os.path.isdir(item_path):
            for subitem in os.listdir(item_path):
                if subitem.endswith('.jsonl'):
                    file_path = os.path.join(item_path, subitem)
                    key = '{0}/{1}'.format(item, subitem[:-6])
                    with open(file_path, 'r') as file:
                        details[key] = [json.loads(line) for line in file]
    return details


def create_data_source(root_path, summary_data, folder_structure, evaluation_details):
    return {
        'inputPath': root_path,
        'data': {
            'summary': summary_data,
            'evaluationFileStructure': folder_structure,
            'evaluationDetailList': evaluation_details,
        },
    }


def inject_data_to_html(html_path, data_source):
    with open(html_path, 'r') as file:
        content = file.read()

    # 使用 json.dumps 并设置 ensure_ascii=False
    json_data = json.dumps(data_source, ensure_ascii=False, indent=2)

    # 对 JSON 数据进行 Base64 编码
    encoded_data = base64.b64encode(json_data.encode('utf-8')).decode('utf-8')

    script = """<script>
window.dataSource = JSON.parse(atob("{0}"));
</script>
""".format(
        encoded_data
    )

    # 定义用于匹配已注入脚本的正则表达式
    injected_script_pattern = re.compile(r'<script>\s*window\.dataSource\s*=.*?</script>', re.DOTALL)

    # 检查并移除已存在的注入脚本
    content = injected_script_pattern.sub('', content)

    # 在 <head> 标签后插入新的脚本
    head_pattern = re.compile(r'(<head.*?>)', re.IGNORECASE)
    modified_content = head_pattern.sub(r'\1\n' + script, content, count=1)

    with open(html_path, 'w') as file:
        file.write(modified_content.encode('utf-8'))

    print('Data source injected into {0}'.format(html_path))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Process folder structure and inject data into HTML.')
    parser.add_argument('--input', required=True, help='Path to the root folder containing summary.json and subfolders')
    args = parser.parse_args()

    root_path = args.input
    summary_path = os.path.join(root_path, 'summary.json')
    html_path = 'out/renderer/index.html'

    if not os.path.exists(root_path):
        print("Error: The specified input path '{0}' does not exist.".format(root_path))
        exit(1)

    if not os.path.exists(summary_path):
        print("Error: summary.json not found in '{0}'.".format(root_path))
        exit(1)

    folder_structure = get_folder_structure(root_path)
    summary_data = get_summary_data(summary_path)
    evaluation_details = get_evaluation_details(root_path)
    data_source = create_data_source(root_path, summary_data, folder_structure, evaluation_details)

    # Ensure inputPath is set in data_source
    data_source['inputPath'] = root_path

    inject_data_to_html(html_path, data_source)

    print('Data processing and injection completed successfully.')
    print('Input path: {0}'.format(root_path))
