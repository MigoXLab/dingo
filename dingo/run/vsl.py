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
            category = {
                "name": item,
                "files": []
            }
            for subitem in os.listdir(item_path):
                if subitem.endswith('.jsonl'):
                    category["files"].append(subitem)
            structure.append(category)
    return structure


def get_summary_data(summary_path):
    with open(summary_path, 'r') as file:
        return json.load(file)


def get_evaluation_details(root_path):
    """
    递归读取所有层级的 jsonl 文件（支持任意深度）
    返回格式: { "相对路径/文件.jsonl": [数据数组] }
    """
    details = {}
    
    def traverse_directory(current_path, relative_path=""):
        """递归遍历目录"""
        try:
            for item in os.listdir(current_path):
                item_path = os.path.join(current_path, item)
                new_relative_path = f"{relative_path}/{item}" if relative_path else item
                
                if os.path.isdir(item_path):
                    # 递归遍历子目录
                    traverse_directory(item_path, new_relative_path)
                elif os.path.isfile(item_path) and item.endswith('.jsonl') and item != 'summary.json':
                    # 读取 jsonl 文件（排除 summary.json）
                    try:
                        with open(item_path, 'r', encoding='utf-8') as file:
                            # 为每行数据添加 _filePath 属性
                            parsed_data = []
                            for line in file:
                                line = line.strip()
                                if line:
                                    try:
                                        data = json.loads(line)
                                        # 添加文件路径信息（与 Electron 应用保持一致）
                                        data['_filePath'] = new_relative_path
                                        parsed_data.append(data)
                                    except json.JSONDecodeError as e:
                                        print(f"Warning: Error parsing line in {item_path}: {e}")
                            details[new_relative_path] = parsed_data
                    except Exception as e:
                        print(f"Warning: Error reading file {item_path}: {e}")
        except Exception as e:
            print(f"Warning: Error reading directory {current_path}: {e}")
    
    traverse_directory(root_path)
    return details


def create_data_source(root_path, summary_data, folder_structure, evaluation_details):
    return {
        "inputPath": root_path,
        "data": {
            "summary": summary_data,
            "evaluationFileStructure": folder_structure,
            "evaluationDetailList": evaluation_details
        }
    }


def inject_data_to_html(html_path, data_source, output_filename=None, add_back_button=False):
    """
    通用的数据注入HTML方法

    Args:
        html_path: 基础HTML模板路径
        data_source: 要注入的数据
        output_filename: 输出文件名，如果为None则自动生成
        add_back_button: 是否添加返回按钮

    Returns:
        生成的HTML文件名
    """
    web_static_dir = os.path.dirname(html_path)

    # 生成输出文件名
    if output_filename is None:
        timestamp = int(time.time())
        output_filename = f"index_{timestamp}.static.html"

    output_path = os.path.join(web_static_dir, output_filename)

    # 复制基础HTML文件
    shutil.copy2(html_path, output_path)

    # 读取HTML内容
    with open(output_path, 'r', encoding='utf-8') as file:
        content = file.read()

    # 准备注入的脚本
    json_data = json.dumps(data_source, ensure_ascii=False)
    encoded_data = base64.b64encode(json_data.encode('utf-8')).decode('utf-8')

    script = f"""<script>
    window.dataSource = JSON.parse(decodeURIComponent(escape(atob("{encoded_data}"))));
    </script>"""

    # 添加返回按钮（如果需要）
    back_button = ""
    if add_back_button:
        back_button = f"""
        <div style="position: fixed; top: 10px; left: 10px; z-index: 1000;">
            <a href="index.html" style="background: #007bff; color: white; padding: 8px 16px; border-radius: 4px; text-decoration: none;">
                ← 返回目录列表
            </a>
        </div>
        """

    # 注入脚本和返回按钮
    head_pattern = re.compile(r'(<head.*?>)', re.IGNORECASE)
    content = head_pattern.sub(r'\1\n' + script, content, count=1)

    if back_button:
        body_pattern = re.compile(r'(<body.*?>)', re.IGNORECASE)
        content = body_pattern.sub(r'\1\n' + back_button, content, count=1)

    # 写入文件
    with open(output_path, 'w', encoding='utf-8') as file:
        file.write(content)

    print(f"✅ Generated: {output_filename}")
    return output_filename


def start_http_server(directory, port=8000):
    os.chdir(directory)
    handler = SimpleHTTPRequestHandler
    server = HTTPServer(("", port), handler)
    print(f"Server started on port {port}")
    return server


def scan_subdirectories(root_path):
    """扫描子目录，查找包含 summary.json 的目录"""
    subdirs = []

    if not os.path.exists(root_path):
        return []

    for item in os.listdir(root_path):
        item_path = os.path.join(root_path, item)
        if os.path.isdir(item_path):
            summary_path = os.path.join(item_path, "summary.json")
            if os.path.exists(summary_path):
                try:
                    with open(summary_path, 'r') as f:
                        summary_data = json.load(f)
                    subdirs.append({
                        "name": item,
                        "path": item_path,
                        "summary": summary_data
                    })
                except Exception as e:
                    print(f"Warning: Could not read summary.json in {item_path}: {e}")

    return sorted(subdirs, key=lambda x: x["name"])


def generate_subdir_html(subdir_path, subdir_name, web_static_dir, base_html_path):
    """为单个子目录生成HTML文件"""
    try:
        # 准备数据
        folder_structure = get_folder_structure(subdir_path)
        summary_data = get_summary_data(os.path.join(subdir_path, "summary.json"))
        evaluation_details = get_evaluation_details(subdir_path)
        data_source = create_data_source(subdir_path, summary_data, folder_structure, evaluation_details)

        # 使用通用方法生成HTML
        subdir_html_filename = f"{subdir_name}.html"
        return inject_data_to_html(
            html_path=base_html_path,
            data_source=data_source,
            output_filename=subdir_html_filename,
            add_back_button=True
        )

    except Exception as e:
        print(f"❌ Error generating HTML for {subdir_name}: {e}")
        return None


def cleanup_old_generated_files(web_static_dir, subdirs):
    """清理旧的生成文件，避免冲突"""
    try:
        # 清理旧的子目录HTML文件
        for subdir in subdirs:
            old_file = os.path.join(web_static_dir, f"{subdir['name']}.html")
            if os.path.exists(old_file):
                os.remove(old_file)

        # 清理旧的目录浏览器文件
        import glob
        old_browser_files = glob.glob(os.path.join(web_static_dir, "directory-browser-*.html"))
        for old_file in old_browser_files:
            try:
                os.remove(old_file)
                print(f"🗑️ Cleaned up old browser file: {os.path.basename(old_file)}")
            except Exception:
                pass

    except Exception as e:
        print(f"Warning: Could not cleanup old files: {e}")


def generate_index_html(root_path, subdirs, web_static_dir, base_html_path):
    """生成主目录页面"""
    # 使用专门的目录浏览器模板
    browser_template_path = os.path.join(web_static_dir, "directory-browser.html")

    if not os.path.exists(browser_template_path):
        print(f"Error: directory-browser.html template not found at '{browser_template_path}'.")
        return None

    # 读取模板文件
    with open(browser_template_path, 'r', encoding='utf-8') as f:
        template_content = f.read()

    # 准备数据
    directory_data = {
        "rootPath": root_path,
        "directories": subdirs
    }

    # 注入数据到模板
    json_data = json.dumps(directory_data, ensure_ascii=False, indent=2)
    encoded_data = base64.b64encode(json_data.encode('utf-8')).decode('utf-8')

    script = f"""<script>
    window.directoryData = JSON.parse(decodeURIComponent(escape(atob("{encoded_data}"))));
    </script>"""

    # 插入数据脚本
    head_pattern = re.compile(r'(<head.*?>)', re.IGNORECASE)
    content = head_pattern.sub(r'\1\n' + script, template_content, count=1)

    # 生成目录浏览器文件，不覆盖原始index.html
    timestamp = int(time.time())
    browser_html_filename = f"directory-browser-{timestamp}.html"
    browser_html_path = os.path.join(web_static_dir, browser_html_filename)

    with open(browser_html_path, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"✅ Generated: {browser_html_filename}")
    return browser_html_filename


def process_and_inject(root_path):
    summary_path = os.path.join(root_path, "summary.json")
    web_static_dir = os.path.join(os.path.dirname(__file__), "..", "..", "web-static")
    html_path = os.path.join(web_static_dir, "index.html")

    if not os.path.exists(root_path):
        print(f"Error: The specified input path '{root_path}' does not exist.")
        return False, None

    if not os.path.exists(html_path):
        print(f"Error: index.html not found at '{html_path}'.")
        return False, None

    if os.path.exists(summary_path):
        # 这是单个评估结果目录（原有逻辑）
        print(f"📊 Processing single evaluation result directory...")
        folder_structure = get_folder_structure(root_path)
        summary_data = get_summary_data(summary_path)
        evaluation_details = get_evaluation_details(root_path)
        data_source = create_data_source(root_path, summary_data, folder_structure, evaluation_details)

        data_source["inputPath"] = root_path

        new_html_filename = inject_data_to_html(html_path, data_source)

        print("Data processing and injection completed successfully.")
        print(f"Input path: {root_path}")
        print(f"New HTML file created: {new_html_filename}")

        return True, new_html_filename

    else:
        # 检查是否为包含多个子目录的根目录
        subdirs = scan_subdirectories(root_path)

        if subdirs:
            # 这是包含多个评估结果的根目录
            print(f"🔄 Found {len(subdirs)} evaluation result directories, generating static HTML files...")

            # 清理旧的生成文件（可选）
            cleanup_old_generated_files(web_static_dir, subdirs)

            # 为每个子目录生成HTML文件
            generated_files = []
            for subdir in subdirs:
                html_file = generate_subdir_html(subdir["path"], subdir["name"], web_static_dir, html_path)
                if html_file:
                    generated_files.append(html_file)

            # 生成主目录页面
            index_file = generate_index_html(root_path, subdirs, web_static_dir, html_path)

            print(f"✅ Generated {len(generated_files)} result pages and 1 index page")
            print(f"📁 Main page: {index_file}")

            return True, index_file
        else:
            print(f"Error: No summary.json found in '{root_path}' and no valid subdirectories found.")
            return False, None


def run_visual_app(input_path=None):
    app_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "app")
    os.chdir(app_dir)

    try:
        node_version = subprocess.check_output(["node", "--version"]).decode().strip()
        print(f"Node.js version: {node_version}")
    except subprocess.CalledProcessError:
        print("Node.js is not installed. Please install the latest version of Node.js and try again.")
        return False

    try:
        subprocess.run(["npm", "install"], check=True)

        command = ["npm", "run", "dev"]
        if input_path:
            command.extend(["--", "--input", input_path])

        print(f"Running command: {' '.join(map(shlex.quote, command))}")
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as e:
        print(f"An error occurred while running npm commands: {e}")
        return False

    return True


def parse_args():
    parser = argparse.ArgumentParser("dingo visualization")
    parser.add_argument("--input", required=True, help="Path to the root folder containing summary.json and subfolders")
    parser.add_argument(
        "--mode",
        choices=[
            "visualization",
            "app"],
        default="visualization",
        help="Choose the mode: visualization or app")
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port for local HTTP server in visualization mode (default: 8000)")
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

    if args.mode == "app":
        success = run_visual_app(args.input)
    else:  # visualization mode
        success, new_html_filename = process_and_inject(args.input)
        if success:
            web_static_dir = os.path.join(os.path.dirname(__file__), "..", "..", "web-static")
            port = args.port
            try:
                server = start_http_server(web_static_dir, port)
                url = f"http://localhost:{port}/{new_html_filename}"
                print(f"Visualization is ready at {url}")
                open_browser(url)

                print("HTTP server started. Press Ctrl+C to stop the server.")
                try:
                    server.serve_forever()
                except KeyboardInterrupt:
                    print("\nServer stopped.")
                    server.shutdown()
            except Exception as e:
                print(f"Failed to start server: {e}")
                print(f"You can try opening the file directly in your browser: file://{os.path.abspath(os.path.join(web_static_dir, new_html_filename))}")
                url = f"http://localhost:{port}/{new_html_filename}"
                open_browser(url)
                success = True

    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
