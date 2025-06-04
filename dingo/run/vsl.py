import argparse
import base64
import json
import os
import platform
import re
import shlex
import shutil
import subprocess
import sys
import time
import webbrowser
from http.server import HTTPServer, SimpleHTTPRequestHandler


def get_folder_structure(root_path):
    structure = []
    for item in os.listdir(root_path):
        item_path = os.path.join(root_path, item)
        if os.path.isdir(item_path):
            category = {'name': item, 'files': []}
            for subitem in os.listdir(item_path):
                if subitem.endswith('.jsonl'):
                    category['files'].append(subitem)
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
                    key = f"{item}/{subitem}"
                    with open(file_path, 'r', encoding='utf-8') as file:
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
    # 生成新的HTML文件名
    timestamp = int(time.time())
    new_html_filename = f"index_{timestamp}.static.html"
    new_html_path = os.path.join(os.path.dirname(html_path), new_html_filename)

    # 复制原始HTML文件
    shutil.copy2(html_path, new_html_path)

    # 读取新的HTML文件内容
    with open(new_html_path, 'r', encoding='utf-8') as file:
        content = file.read()

    json_data = json.dumps(data_source, ensure_ascii=False)
    encoded_data = base64.b64encode(json_data.encode('utf-8')).decode('utf-8')

    script = f"""<script>
    window.dataSource = JSON.parse(decodeURIComponent(escape(atob("{encoded_data}"))));
    </script>
    """

    # 注入数据到新的HTML文件
    head_pattern = re.compile(r'(<head.*?>)', re.IGNORECASE)
    modified_content = head_pattern.sub(r'\1\n' + script, content, count=1)

    with open(new_html_path, 'w', encoding='utf-8') as file:
        file.write(modified_content)

    print(f"Data source injected into {new_html_path}")
    return new_html_filename


def start_http_server(directory, port=8000):
    os.chdir(directory)
    handler = SimpleHTTPRequestHandler
    server = HTTPServer(('', port), handler)
    print(f"Server started on port {port}")
    return server


def process_and_inject(root_path):
    summary_path = os.path.join(root_path, 'summary.json')
    web_static_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'web-static')
    html_path = os.path.join(web_static_dir, 'index.html')

    if not os.path.exists(root_path):
        print(f"Error: The specified input path '{root_path}' does not exist.")
        return False, None

    if not os.path.exists(summary_path):
        print(f"Error: summary.json not found in '{root_path}'.")
        return False, None

    if not os.path.exists(html_path):
        print(f"Error: index.html not found at '{html_path}'.")
        return False, None

    folder_structure = get_folder_structure(root_path)
    summary_data = get_summary_data(summary_path)
    evaluation_details = get_evaluation_details(root_path)
    data_source = create_data_source(root_path, summary_data, folder_structure, evaluation_details)

    data_source['inputPath'] = root_path

    new_html_filename = inject_data_to_html(html_path, data_source)

    print('Data processing and injection completed successfully.')
    print(f"Input path: {root_path}")
    print(f"New HTML file created: {new_html_filename}")

    return True, new_html_filename


def run_visual_app(input_path=None):
    app_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'app')
    os.chdir(app_dir)

    try:
        node_version = subprocess.check_output(['node', '--version']).decode().strip()
        print(f"Node.js version: {node_version}")
    except subprocess.CalledProcessError:
        print('Node.js is not installed. Please install the latest version of Node.js and try again.')
        return False

    try:
        subprocess.run(['npm', 'install'], check=True)

        command = ['npm', 'run', 'dev']
        if input_path:
            command.extend(['--', '--input', input_path])

        print(f"Running command: {' '.join(map(shlex.quote, command))}")
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as e:
        print(f"An error occurred while running npm commands: {e}")
        return False

    return True


def parse_args():
    parser = argparse.ArgumentParser('dingo visualization')
    parser.add_argument('--input', required=True, help='Path to the root folder containing summary.json and subfolders')
    parser.add_argument(
        '--mode',
        choices=['visualization', 'app'],
        default='visualization',
        help='Choose the mode: visualization or app',
    )
    return parser.parse_args()


def open_browser(url):
    system = platform.system().lower()
    try:
        if system == 'darwin':  # macOS
            subprocess.run(['open', url])
        elif system == 'linux':
            subprocess.run(['xdg-open', url])
        else:  # Windows or other systems
            webbrowser.open(url)
    except Exception as e:
        print(f"Failed to open browser automatically: {e}")
        print(f"Please open {url} manually in your browser.")


def main():
    args = parse_args()

    if args.mode == 'app':
        success = run_visual_app(args.input)
    else:  # visualization mode
        success, new_html_filename = process_and_inject(args.input)
        if success:
            web_static_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'web-static')
            port = 8000
            try:
                server = start_http_server(web_static_dir, port)
                url = f"http://localhost:{port}/{new_html_filename}"
                print(f"Visualization is ready at {url}")
                open_browser(url)

                print('HTTP server started. Press Ctrl+C to stop the server.')
                try:
                    server.serve_forever()
                except KeyboardInterrupt:
                    print('\nServer stopped.')
                    server.shutdown()
            except Exception as e:
                print(f"Failed to start server: {e}")
                print(
                    f"You can try opening the file directly in your browser: file://{os.path.abspath(os.path.join(web_static_dir, new_html_filename))}"
                )
                url = f"http://localhost:{port}/{new_html_filename}"
                open_browser(url)
                success = True

    if not success:
        sys.exit(1)


if __name__ == '__main__':
    main()
