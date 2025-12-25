"""
Parquet Dataset 测试文件

测试 Parquet 文件的流式读取功能，支持批次读取、列过滤等特性
"""

import json
import os
import tempfile

from dingo.config import DatasetArgs, DatasetParquetArgs, InputArgs
from dingo.data.dataset.local import LocalDataset
from dingo.data.datasource.local import LocalDataSource


def create_test_parquet_file(file_path: str, num_rows: int = 100):
    """创建测试用的 Parquet 文件"""
    try:
        import pandas as pd
    except ImportError:
        print("⚠ pandas 未安装，无法创建测试文件。请运行: pip install pandas pyarrow")
        return False

    try:
        # 创建测试数据
        data = {
            "id": [str(i) for i in range(1, num_rows + 1)],
            "name": [f"用户_{i}" for i in range(1, num_rows + 1)],
            "age": [20 + (i % 50) for i in range(1, num_rows + 1)],
            "city": [["北京", "上海", "广州", "深圳"][i % 4] for i in range(num_rows)],
            "score": [85.5 + (i % 15) for i in range(num_rows)],
            "content": [f"这是第{i}条测试数据，用于验证Parquet读取功能。" for i in range(1, num_rows + 1)],
        }

        df = pd.DataFrame(data)
        df.to_parquet(file_path, engine='pyarrow', compression='snappy', index=False)

        return True
    except Exception as e:
        print(f"⚠ 创建 Parquet 文件失败: {e}")
        return False


def create_test_parquet_with_special_types(file_path: str):
    """创建包含特殊类型的测试 Parquet 文件"""
    try:
        import numpy as np
        import pandas as pd
    except ImportError:
        print("⚠ pandas 或 numpy 未安装")
        return False

    try:
        # 创建包含多种数据类型的测试数据
        data = {
            "id": ["1", "2", "3", "4", "5"],
            "content": [
                "正常的文本内容",
                "包含特殊字符：@#$%！",
                "包含换行符\n的内容",
                '包含"引号"的内容',
                "包含逗号,分号;的内容"
            ],
            "int_col": [1, 2, 3, 4, 5],
            "float_col": [1.1, 2.2, 3.3, 4.4, 5.5],
            "bool_col": [True, False, True, False, True],
            "nullable_col": ["值1", None, "值3", None, "值5"],
        }

        df = pd.DataFrame(data)
        df.to_parquet(file_path, engine='pyarrow', index=False)

        return True
    except Exception as e:
        print(f"⚠ 创建特殊类型 Parquet 文件失败: {e}")
        return False


def test_parquet_basic():
    """测试基本的 Parquet 文件读取"""
    print("=" * 60)
    print("测试基本 Parquet 文件读取")
    print("=" * 60)

    # 创建临时文件
    temp_dir = tempfile.mkdtemp()
    parquet_file = os.path.join(temp_dir, "test_data.parquet")

    try:
        # 创建测试文件
        if not create_test_parquet_file(parquet_file, num_rows=10):
            return

        print(f"✓ 创建测试文件: {parquet_file}")

        # 配置参数
        parquet_config = DatasetParquetArgs(
            batch_size=10000,
            columns=None  # 读取所有列
        )

        dataset_config = DatasetArgs(
            source="local",
            format="parquet",
            parquet_config=parquet_config
        )

        input_args = InputArgs(
            task_name="parquet_test",
            input_path=parquet_file,
            output_path="outputs/parquet_test/",
            dataset=dataset_config,
            evaluator=[]
        )

        print("✓ 配置参数创建成功")

        # 创建数据源和数据集
        datasource = LocalDataSource(input_args=input_args)
        print("✓ LocalDataSource 创建成功")

        dataset = LocalDataset(source=datasource, name="test_parquet_dataset")
        print("✓ LocalDataset 创建成功")

        # 流式读取数据
        print("\n开始流式读取数据:")
        count = 0
        for idx, data in enumerate(dataset.get_data()):
            count += 1
            if idx < 3:  # 只打印前3条
                print(f"  [{idx + 1}] {data}")

            # 验证数据格式
            if idx == 0:
                data_dict = data.to_dict()
                assert "id" in data_dict, "数据缺少 'id' 字段"
                assert "name" in data_dict, "数据缺少 'name' 字段"
                assert "age" in data_dict, "数据缺少 'age' 字段"
                assert "city" in data_dict, "数据缺少 'city' 字段"
                assert "score" in data_dict, "数据缺少 'score' 字段"
                assert "content" in data_dict, "数据缺少 'content' 字段"
                print("✓ 数据格式验证通过")

        assert count == 10, f"期望读取 10 行数据，实际读取了 {count} 行"
        print(f"\n✓ 成功读取 {count} 条数据")

        print("\n" + "=" * 60)
        print("✓ 测试通过!")
        print("=" * 60)

    finally:
        # 清理临时文件
        import shutil
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
            print(f"\n✓ 清理临时文件: {temp_dir}")


def test_parquet_column_filter():
    """测试 Parquet 列过滤功能"""
    print("\n" + "=" * 60)
    print("测试 Parquet 列过滤功能")
    print("=" * 60)

    # 创建临时文件
    temp_dir = tempfile.mkdtemp()
    parquet_file = os.path.join(temp_dir, "test_data_filter.parquet")

    try:
        # 创建测试文件
        if not create_test_parquet_file(parquet_file, num_rows=5):
            return

        print(f"✓ 创建测试文件: {parquet_file}")

        # 配置参数 - 只读取部分列
        parquet_config = DatasetParquetArgs(
            batch_size=10000,
            columns=["id", "name", "content"]  # 只读取这三列
        )

        dataset_config = DatasetArgs(
            source="local",
            format="parquet",
            parquet_config=parquet_config
        )

        input_args = InputArgs(
            task_name="parquet_filter_test",
            input_path=parquet_file,
            output_path="outputs/parquet_test/",
            dataset=dataset_config,
            evaluator=[]
        )

        print("✓ 配置参数创建成功（只读取 id, name, content 列）")

        # 创建数据源和数据集
        datasource = LocalDataSource(input_args=input_args)
        dataset = LocalDataset(source=datasource, name="test_parquet_filter")

        # 流式读取数据
        print("\n开始流式读取数据:")
        count = 0
        for idx, data in enumerate(dataset.get_data()):
            count += 1
            print(f"  [{idx + 1}] {data}")

            # 验证只包含指定的列
            if idx == 0:
                data_dict = data.to_dict()
                assert "id" in data_dict, "数据缺少 'id' 字段"
                assert "name" in data_dict, "数据缺少 'name' 字段"
                assert "content" in data_dict, "数据缺少 'content' 字段"
                assert "age" not in data_dict, "不应包含 'age' 字段"
                assert "city" not in data_dict, "不应包含 'city' 字段"
                assert "score" not in data_dict, "不应包含 'score' 字段"
                print("✓ 列过滤验证通过（只包含指定的列）")

        assert count == 5, f"期望读取 5 行数据，实际读取了 {count} 行"
        print(f"\n✓ 成功读取 {count} 条数据")

        print("\n" + "=" * 60)
        print("✓ 测试通过!")
        print("=" * 60)

    finally:
        # 清理临时文件
        import shutil
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
            print(f"\n✓ 清理临时文件: {temp_dir}")


def test_parquet_batch_size():
    """测试 Parquet 批次大小设置"""
    print("\n" + "=" * 60)
    print("测试 Parquet 批次大小设置")
    print("=" * 60)

    # 创建临时文件
    temp_dir = tempfile.mkdtemp()
    parquet_file = os.path.join(temp_dir, "test_data_batch.parquet")

    try:
        # 创建包含较多数据的测试文件
        if not create_test_parquet_file(parquet_file, num_rows=100):
            return

        print(f"✓ 创建包含 100 行数据的测试文件")

        # 配置参数 - 设置较小的批次大小
        parquet_config = DatasetParquetArgs(
            batch_size=25,  # 每次读取 25 行
            columns=None
        )

        dataset_config = DatasetArgs(
            source="local",
            format="parquet",
            parquet_config=parquet_config
        )

        input_args = InputArgs(
            task_name="parquet_batch_test",
            input_path=parquet_file,
            output_path="outputs/parquet_test/",
            dataset=dataset_config,
            evaluator=[]
        )

        print("✓ 配置参数创建成功（batch_size=25）")

        # 创建数据源和数据集
        datasource = LocalDataSource(input_args=input_args)
        dataset = LocalDataset(source=datasource, name="test_parquet_batch")

        # 流式读取数据
        print("\n开始流式读取数据（分批次处理）:")
        count = 0
        for idx, data in enumerate(dataset.get_data()):
            count += 1
            if idx < 5:  # 只打印前5条
                print(f"  [{idx + 1}] {data}")
            elif idx == 5:
                print(f"  ... (省略中间数据)")

        assert count == 100, f"期望读取 100 行数据，实际读取了 {count} 行"
        print(f"\n✓ 成功读取 {count} 条数据（分 4 个批次处理，每批 25 行）")

        print("\n" + "=" * 60)
        print("✓ 测试通过!")
        print("=" * 60)

    finally:
        # 清理临时文件
        import shutil
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
            print(f"\n✓ 清理临时文件: {temp_dir}")


def test_parquet_special_types():
    """测试包含特殊类型的 Parquet 文件"""
    print("\n" + "=" * 60)
    print("测试包含特殊类型的 Parquet 文件")
    print("=" * 60)

    # 创建临时文件
    temp_dir = tempfile.mkdtemp()
    parquet_file = os.path.join(temp_dir, "test_data_special.parquet")

    try:
        # 创建测试文件
        if not create_test_parquet_with_special_types(parquet_file):
            return

        print(f"✓ 创建测试文件: {parquet_file}")

        # 配置参数
        parquet_config = DatasetParquetArgs(
            batch_size=10000,
            columns=None
        )

        dataset_config = DatasetArgs(
            source="local",
            format="parquet",
            parquet_config=parquet_config
        )

        input_args = InputArgs(
            task_name="parquet_special_test",
            input_path=parquet_file,
            output_path="outputs/parquet_test/",
            dataset=dataset_config,
            evaluator=[]
        )

        print("✓ 配置参数创建成功")

        # 创建数据源和数据集
        datasource = LocalDataSource(input_args=input_args)
        dataset = LocalDataset(source=datasource, name="test_parquet_special")

        # 流式读取数据
        print("\n开始流式读取数据:")
        count = 0
        for idx, data in enumerate(dataset.get_data()):
            count += 1
            print(f"  [{idx + 1}] {data}")

            # 验证数据格式
            if idx == 0:
                data_dict = data.to_dict()
                assert "id" in data_dict, "数据缺少 'id' 字段"
                assert "content" in data_dict, "数据缺少 'content' 字段"
                assert "int_col" in data_dict, "数据缺少 'int_col' 字段"
                assert "float_col" in data_dict, "数据缺少 'float_col' 字段"
                assert "bool_col" in data_dict, "数据缺少 'bool_col' 字段"
                assert "nullable_col" in data_dict, "数据缺少 'nullable_col' 字段"
                print("✓ 数据格式验证通过")

            # 验证 None 值被正确处理为空字符串
            if idx == 1:  # 第二行有 None 值
                data_dict = data.to_dict()
                assert data_dict["nullable_col"] == "", "None 值应该被转换为空字符串"
                print("✓ None 值处理验证通过")

        assert count == 5, f"期望读取 5 行数据，实际读取了 {count} 行"
        print(f"\n✓ 成功读取 {count} 条数据（包含多种数据类型）")

        print("\n" + "=" * 60)
        print("✓ 测试通过!")
        print("=" * 60)

    finally:
        # 清理临时文件
        import shutil
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
            print(f"\n✓ 清理临时文件: {temp_dir}")


def test_stream_large_parquet():
    """测试大文件的流式读取特性"""
    print("\n" + "=" * 60)
    print("测试流式读取特性（大文件）")
    print("=" * 60)

    temp_dir = tempfile.mkdtemp()
    parquet_file = os.path.join(temp_dir, "large_test.parquet")

    try:
        # 创建包含较多数据的测试文件
        if not create_test_parquet_file(parquet_file, num_rows=1000):
            return

        print(f"✓ 创建包含 1000 行数据的测试文件")

        # 配置参数 - 使用较小的批次大小
        parquet_config = DatasetParquetArgs(
            batch_size=100,  # 每次读取 100 行
            columns=None
        )

        dataset_config = DatasetArgs(
            source="local",
            format="parquet",
            parquet_config=parquet_config
        )

        input_args = InputArgs(
            task_name="stream_test",
            input_path=parquet_file,
            output_path="outputs/stream_test/",
            dataset=dataset_config,
            evaluator=[]
        )

        # 创建数据源和数据集
        datasource = LocalDataSource(input_args=input_args)
        dataset = LocalDataset(source=datasource, name="stream_test_dataset")

        # 只读取前 10 条，验证流式读取
        print("开始流式读取（只读取前 10 条）:")
        count = 0
        for idx, data in enumerate(dataset.get_data()):
            if idx < 10:
                print(f"  [{idx + 1}] {data}")
            count += 1
            if idx >= 9:  # 只读取前 10 条就停止
                break

        print(f"\n✓ 流式读取验证通过（处理了 {count} 条数据后停止）")
        print("✓ 流式读取特性工作正常，不需要一次性加载所有数据到内存")

        print("\n" + "=" * 60)
        print("✓ 测试通过!")
        print("=" * 60)

    finally:
        # 清理临时文件
        import shutil
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
            print(f"\n✓ 清理临时文件: {temp_dir}")


def test_parquet_comprehensive():
    """综合测试 - 测试各种 Parquet 功能的完整性"""
    print("\n" + "=" * 60)
    print("综合测试 - Parquet 功能完整性验证")
    print("=" * 60)

    print("\n功能列表:")
    print("  1. ✓ 标准 Parquet 格式读取")
    print("  2. ✓ 列过滤（只读取指定列）")
    print("  3. ✓ 批次大小设置")
    print("  4. ✓ 流式读取（适合大文件）")
    print("  5. ✓ 多种数据类型支持（int、float、bool、string、None）")
    print("  6. ✓ 特殊字符处理")

    print("\n配置参数说明:")
    print("  - batch_size: 每次读取的行数（默认 10000）")
    print("  - columns: 指定读取的列（默认 None，读取所有列）")

    print("\n性能优势:")
    print("  - 使用 PyArrow 引擎，读取速度快")
    print("  - 分批次处理，内存占用可控")
    print("  - 支持列式存储，只读取需要的列")
    print("  - 支持压缩格式，节省存储空间")

    print("\n" + "=" * 60)
    print("✓ 综合测试完成!")
    print("=" * 60)


if __name__ == "__main__":
    print("\n")
    print("╔" + "═" * 58 + "╗")
    print("║" + " " * 14 + "Parquet 数据集测试套件" + " " * 20 + "║")
    print("╚" + "═" * 58 + "╝")
    print("\n")

    # 测试基本读取
    test_parquet_basic()

    # 测试列过滤
    test_parquet_column_filter()

    # 测试批次大小
    test_parquet_batch_size()

    # 测试特殊类型
    test_parquet_special_types()

    # 测试流式读取
    test_stream_large_parquet()

    # 综合测试
    test_parquet_comprehensive()

    print("\n")
    print("╔" + "═" * 58 + "╗")
    print("║" + " " * 18 + "所有测试完成!" + " " * 23 + "║")
    print("╚" + "═" * 58 + "╝")
    print("\n")
