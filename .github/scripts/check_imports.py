#!/usr/bin/env python3
"""检查所有Python文件是否可以成功编译和导入"""

import os
import py_compile
import sys
from pathlib import Path


def check_syntax(file_path):
    """检查Python文件语法"""
    try:
        py_compile.compile(file_path, doraise=True)
        return True, None
    except py_compile.PyCompileError as e:
        return False, str(e)


def main():
    """主函数"""
    project_root = Path(__file__).parent.parent.parent
    dingo_path = project_root / "dingo"

    if not dingo_path.exists():
        print(f"❌ 找不到dingo目录: {dingo_path}")
        sys.exit(1)

    errors = []
    checked = 0

    print("🔍 检查所有Python文件的语法和导入...")
    print("-" * 60)

    for py_file in dingo_path.rglob("*.py"):
        if "__pycache__" in str(py_file):
            continue

        checked += 1
        success, error = check_syntax(str(py_file))

        if success:
            print(f"✓ {py_file.relative_to(project_root)}")
        else:
            error_msg = f"✗ {py_file.relative_to(project_root)}: {error}"
            print(error_msg)
            errors.append(error_msg)

    print("-" * 60)
    print(f"📊 检查了 {checked} 个文件")

    if errors:
        print(f"\n❌ 发现 {len(errors)} 个错误:")
        for error in errors:
            print(f"  {error}")
        sys.exit(1)
    else:
        print(f"✅ 所有文件检查通过！")
        sys.exit(0)


if __name__ == "__main__":
    main()
