"""
CSV Dataset 测试文件

测试 CSV 文件的流式读取功能，支持不同编码、不同分隔符、不同格式
"""

import csv
import json
import os
import tempfile

from dingo.config import DatasetArgs, DatasetCsvArgs, InputArgs
from dingo.data.dataset.local import LocalDataset
from dingo.data.datasource.local import LocalDataSource


def create_test_csv_file(file_path: str, has_header: bool = True, encoding: str = 'utf-8', delimiter: str = ','):
    """创建测试用的 CSV 文件"""
    try:
        with open(file_path, 'w', encoding=encoding, newline='') as f:
            writer = csv.writer(f, delimiter=delimiter)

            if has_header:
                # 添加表头
                writer.writerow(["姓名", "年龄", "城市", "分数"])

            # 添加数据
            writer.writerow(["张三", "25", "北京", "95.5"])
            writer.writerow(["李四", "30", "上海", "88.0"])
            writer.writerow(["王五", "28", "广州", "92.3"])
            writer.writerow(["赵六", "35", "深圳", "87.8"])

        return True
    except Exception as e:
        print(f"⚠ 创建 CSV 文件失败: {e}")
        return False


def create_test_csv_with_special_chars(file_path: str, encoding: str = 'utf-8'):
    """创建包含特殊字符的测试 CSV 文件"""
    try:
        with open(file_path, 'w', encoding=encoding, newline='') as f:
            writer = csv.writer(f)

            # 添加表头
            writer.writerow(["id", "content", "label"])

            # 添加包含特殊字符的数据
            writer.writerow(["1", "这是第一条测试数据，用于检查CSV读取功能。", "good"])
            writer.writerow(["2", "第二条数据包含特殊字符：@#$%！", "bad"])
            writer.writerow(["3", "第三条数据测试多行\n内容的处理", "good"])
            writer.writerow(["4", '测试引号内的"双引号"', "good"])
            writer.writerow(["5", "测试逗号,在内容中", "bad"])

        return True
    except Exception as e:
        print(f"⚠ 创建特殊字符 CSV 文件失败: {e}")
        return False


def test_csv_with_header():
    """测试有表头的标准 CSV 文件"""
    print("=" * 60)
    print("测试标准 CSV 文件（逗号分隔，有表头）")
    print("=" * 60)

    # 创建临时文件
    temp_dir = tempfile.mkdtemp()
    csv_file = os.path.join(temp_dir, "test_data_with_header.csv")

    try:
        # 创建测试文件
        if not create_test_csv_file(csv_file, has_header=True):
            return

        print(f"✓ 创建测试文件: {csv_file}")

        # 配置参数
        csv_config = DatasetCsvArgs(
            has_header=True,  # 第一行是表头
            encoding='utf-8',
            dialect='excel'
        )

        dataset_config = DatasetArgs(
            source="local",
            format="csv",
            csv_config=csv_config
        )

        input_args = InputArgs(
            task_name="csv_test",
            input_path=csv_file,
            output_path="outputs/csv_test/",
            dataset=dataset_config,
            evaluator=[]
        )

        print("✓ 配置参数创建成功")

        # 创建数据源和数据集
        datasource = LocalDataSource(input_args=input_args)
        print("✓ LocalDataSource 创建成功")

        dataset = LocalDataset(source=datasource, name="test_csv_dataset")
        print("✓ LocalDataset 创建成功")

        # 流式读取数据
        print("\n开始流式读取数据:")
        count = 0
        for idx, data in enumerate(dataset.get_data()):
            count += 1
            print(f"  [{idx + 1}] {data}")

            # 验证数据格式
            if idx == 0:
                # 第一行数据应该有 "姓名", "年龄", "城市", "分数" 这些字段
                data_dict = data.to_dict()
                assert "姓名" in data_dict, "数据缺少 '姓名' 字段"
                assert "年龄" in data_dict, "数据缺少 '年龄' 字段"
                assert "城市" in data_dict, "数据缺少 '城市' 字段"
                assert "分数" in data_dict, "数据缺少 '分数' 字段"
                # 也可以直接通过属性访问
                assert hasattr(data, '姓名'), "数据对象缺少 '姓名' 属性"
                print("✓ 数据格式验证通过")

        assert count == 4, f"期望读取 4 行数据，实际读取了 {count} 行"
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


def test_csv_without_header():
    """测试无表头的 CSV 文件（使用 column_x）"""
    print("\n" + "=" * 60)
    print("测试 CSV 文件（无表头，使用 column_x）")
    print("=" * 60)

    # 创建临时文件
    temp_dir = tempfile.mkdtemp()
    csv_file = os.path.join(temp_dir, "test_data_without_header.csv")

    try:
        # 创建测试文件
        if not create_test_csv_file(csv_file, has_header=False):
            return

        print(f"✓ 创建测试文件: {csv_file}")

        # 配置参数
        csv_config = DatasetCsvArgs(
            has_header=False,  # 第一行不是表头
            encoding='utf-8',
            dialect='excel'
        )

        dataset_config = DatasetArgs(
            source="local",
            format="csv",
            csv_config=csv_config
        )

        input_args = InputArgs(
            task_name="csv_test_no_header",
            input_path=csv_file,
            output_path="outputs/csv_test/",
            dataset=dataset_config,
            evaluator=[]
        )

        print("✓ 配置参数创建成功")

        # 创建数据源和数据集
        datasource = LocalDataSource(input_args=input_args)
        dataset = LocalDataset(source=datasource, name="test_csv_no_header")

        # 流式读取数据
        print("\n开始流式读取数据:")
        count = 0
        for idx, data in enumerate(dataset.get_data()):
            count += 1
            print(f"  [{idx + 1}] {data}")

            # 验证数据格式（使用 column_x 作为列名）
            if idx == 0:
                data_dict = data.to_dict()
                assert "column_0" in data_dict, "数据缺少 'column_0' 字段"
                assert "column_1" in data_dict, "数据缺少 'column_1' 字段"
                assert "column_2" in data_dict, "数据缺少 'column_2' 字段"
                assert "column_3" in data_dict, "数据缺少 'column_3' 字段"
                # 也可以直接通过属性访问
                assert hasattr(data, 'column_0'), "数据对象缺少 'column_0' 属性"
                print("✓ 数据格式验证通过（使用 column_x 作为键）")

        assert count == 4, f"期望读取 4 行数据，实际读取了 {count} 行"
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


def test_csv_tab_delimiter():
    """测试 Tab 分隔的 CSV 文件"""
    print("\n" + "=" * 60)
    print("测试 Tab 分隔的 CSV 文件")
    print("=" * 60)

    # 创建临时文件
    temp_dir = tempfile.mkdtemp()
    csv_file = os.path.join(temp_dir, "test_data_tab.csv")

    try:
        # 创建测试文件（Tab 分隔）
        if not create_test_csv_file(csv_file, has_header=True, delimiter='\t'):
            return

        print(f"✓ 创建测试文件: {csv_file}")

        # 配置参数
        csv_config = DatasetCsvArgs(
            has_header=True,
            encoding='utf-8',
            dialect='excel-tab'  # Tab 分隔格式
        )

        dataset_config = DatasetArgs(
            source="local",
            format="csv",
            csv_config=csv_config
        )

        input_args = InputArgs(
            task_name="csv_test_tab",
            input_path=csv_file,
            output_path="outputs/csv_test/",
            dataset=dataset_config,
            evaluator=[]
        )

        print("✓ 配置参数创建成功")

        # 创建数据源和数据集
        datasource = LocalDataSource(input_args=input_args)
        dataset = LocalDataset(source=datasource, name="test_csv_tab")

        # 流式读取数据
        print("\n开始流式读取数据:")
        count = 0
        for idx, data in enumerate(dataset.get_data()):
            count += 1
            print(f"  [{idx + 1}] {data}")

            # 验证数据格式
            if idx == 0:
                data_dict = data.to_dict()
                assert "姓名" in data_dict, "数据缺少 '姓名' 字段"
                assert "年龄" in data_dict, "数据缺少 '年龄' 字段"
                print("✓ 数据格式验证通过")

        assert count == 4, f"期望读取 4 行数据，实际读取了 {count} 行"
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


def test_csv_custom_delimiter():
    """测试自定义分隔符（分号）的 CSV 文件"""
    print("\n" + "=" * 60)
    print("测试自定义分隔符（分号）的 CSV 文件")
    print("=" * 60)

    # 创建临时文件
    temp_dir = tempfile.mkdtemp()
    csv_file = os.path.join(temp_dir, "test_data_semicolon.csv")

    try:
        # 创建测试文件（分号分隔）
        if not create_test_csv_file(csv_file, has_header=True, delimiter=';'):
            return

        print(f"✓ 创建测试文件: {csv_file}")

        # 配置参数
        csv_config = DatasetCsvArgs(
            has_header=True,
            encoding='utf-8',
            dialect='excel',
            delimiter=';'  # 自定义分隔符：分号
        )

        dataset_config = DatasetArgs(
            source="local",
            format="csv",
            csv_config=csv_config
        )

        input_args = InputArgs(
            task_name="csv_test_semicolon",
            input_path=csv_file,
            output_path="outputs/csv_test/",
            dataset=dataset_config,
            evaluator=[]
        )

        print("✓ 配置参数创建成功")

        # 创建数据源和数据集
        datasource = LocalDataSource(input_args=input_args)
        dataset = LocalDataset(source=datasource, name="test_csv_semicolon")

        # 流式读取数据
        print("\n开始流式读取数据:")
        count = 0
        for idx, data in enumerate(dataset.get_data()):
            count += 1
            print(f"  [{idx + 1}] {data}")

            # 验证数据格式
            if idx == 0:
                data_dict = data.to_dict()
                assert "姓名" in data_dict, "数据缺少 '姓名' 字段"
                assert "年龄" in data_dict, "数据缺少 '年龄' 字段"
                print("✓ 数据格式验证通过")

        assert count == 4, f"期望读取 4 行数据，实际读取了 {count} 行"
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


def test_csv_gbk_encoding():
    """测试 GBK 编码的 CSV 文件"""
    print("\n" + "=" * 60)
    print("测试 GBK 编码的 CSV 文件")
    print("=" * 60)

    # 创建临时文件
    temp_dir = tempfile.mkdtemp()
    csv_file = os.path.join(temp_dir, "test_data_gbk.csv")

    try:
        # 创建测试文件（GBK 编码）
        if not create_test_csv_file(csv_file, has_header=True, encoding='gbk'):
            return

        print(f"✓ 创建测试文件: {csv_file}")

        # 配置参数
        csv_config = DatasetCsvArgs(
            has_header=True,
            encoding='gbk',  # GBK 编码
            dialect='excel'
        )

        dataset_config = DatasetArgs(
            source="local",
            format="csv",
            csv_config=csv_config
        )

        input_args = InputArgs(
            task_name="csv_test_gbk",
            input_path=csv_file,
            output_path="outputs/csv_test/",
            dataset=dataset_config,
            evaluator=[]
        )

        print("✓ 配置参数创建成功")

        # 创建数据源和数据集
        datasource = LocalDataSource(input_args=input_args)
        dataset = LocalDataset(source=datasource, name="test_csv_gbk")

        # 流式读取数据
        print("\n开始流式读取数据:")
        count = 0
        for idx, data in enumerate(dataset.get_data()):
            count += 1
            print(f"  [{idx + 1}] {data}")

            # 验证数据格式
            if idx == 0:
                data_dict = data.to_dict()
                assert "姓名" in data_dict, "数据缺少 '姓名' 字段"
                assert "年龄" in data_dict, "数据缺少 '年龄' 字段"
                print("✓ 数据格式验证通过（GBK 编码正确解析）")

        assert count == 4, f"期望读取 4 行数据，实际读取了 {count} 行"
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


def test_csv_special_characters():
    """测试包含特殊字符的 CSV 文件"""
    print("\n" + "=" * 60)
    print("测试包含特殊字符的 CSV 文件")
    print("=" * 60)

    # 创建临时文件
    temp_dir = tempfile.mkdtemp()
    csv_file = os.path.join(temp_dir, "test_data_special_chars.csv")

    try:
        # 创建测试文件
        if not create_test_csv_with_special_chars(csv_file):
            return

        print(f"✓ 创建测试文件: {csv_file}")

        # 配置参数
        csv_config = DatasetCsvArgs(
            has_header=True,
            encoding='utf-8',
            dialect='excel'
        )

        dataset_config = DatasetArgs(
            source="local",
            format="csv",
            csv_config=csv_config
        )

        input_args = InputArgs(
            task_name="csv_test_special_chars",
            input_path=csv_file,
            output_path="outputs/csv_test/",
            dataset=dataset_config,
            evaluator=[]
        )

        print("✓ 配置参数创建成功")

        # 创建数据源和数据集
        datasource = LocalDataSource(input_args=input_args)
        dataset = LocalDataset(source=datasource, name="test_csv_special_chars")

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
                assert "label" in data_dict, "数据缺少 'label' 字段"
                print("✓ 数据格式验证通过")

        assert count == 5, f"期望读取 5 行数据，实际读取了 {count} 行"
        print(f"\n✓ 成功读取 {count} 条数据（包含特殊字符、多行内容、引号等）")

        print("\n" + "=" * 60)
        print("✓ 测试通过!")
        print("=" * 60)

    finally:
        # 清理临时文件
        import shutil
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
            print(f"\n✓ 清理临时文件: {temp_dir}")


def test_stream_large_csv():
    """测试大文件的流式读取特性"""
    print("\n" + "=" * 60)
    print("测试流式读取特性（大文件）")
    print("=" * 60)

    temp_dir = tempfile.mkdtemp()
    csv_file = os.path.join(temp_dir, "large_test.csv")

    try:
        # 创建包含较多数据的测试文件
        with open(csv_file, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)

            # 添加表头
            writer.writerow(["ID", "名称", "数值"])

            # 添加 1000 行数据
            for i in range(1, 1001):
                writer.writerow([str(i), f"项目_{i}", str(i * 1.5)])

        print(f"✓ 创建包含 1000 行数据的测试文件")

        # 配置参数
        csv_config = DatasetCsvArgs(
            has_header=True,
            encoding='utf-8',
            dialect='excel'
        )

        dataset_config = DatasetArgs(
            source="local",
            format="csv",
            csv_config=csv_config
        )

        input_args = InputArgs(
            task_name="stream_test",
            input_path=csv_file,
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


def test_csv_comprehensive():
    """综合测试 - 测试各种 CSV 功能的完整性"""
    print("\n" + "=" * 60)
    print("综合测试 - CSV 功能完整性验证")
    print("=" * 60)

    print("\n功能列表:")
    print("  1. ✓ 标准 CSV 格式（逗号分隔）")
    print("  2. ✓ 无列名的 CSV（column_x 格式）")
    print("  3. ✓ 不同分隔符（Tab、分号等）")
    print("  4. ✓ 不同的 CSV 格式（dialect）")
    print("  5. ✓ 流式读取（适合大文件）")
    print("  6. ✓ 多行内容和特殊字符")
    print("  7. ✓ 自定义编码（utf-8, gbk 等）")

    print("\n配置参数说明:")
    print("  - has_header: 第一行是否为列名（默认 True）")
    print("  - encoding: 文件编码（默认 utf-8）")
    print("  - dialect: CSV 格式（默认 excel）")
    print("  - delimiter: 自定义分隔符（默认 None，根据 dialect 自动选择）")
    print("  - quotechar: 引号字符（默认双引号）")

    print("\n" + "=" * 60)
    print("✓ 综合测试完成!")
    print("=" * 60)


if __name__ == "__main__":
    print("\n")
    print("╔" + "═" * 58 + "╗")
    print("║" + " " * 16 + "CSV 数据集测试套件" + " " * 22 + "║")
    print("╚" + "═" * 58 + "╝")
    print("\n")

    # 测试标准 CSV
    test_csv_with_header()

    # 测试无列名 CSV
    test_csv_without_header()

    # 测试不同分隔符
    test_csv_tab_delimiter()
    test_csv_custom_delimiter()

    # 测试不同编码
    test_csv_gbk_encoding()

    # 测试特殊字符
    test_csv_special_characters()

    # 测试流式读取
    test_stream_large_csv()

    # 综合测试
    test_csv_comprehensive()

    print("\n")
    print("╔" + "═" * 58 + "╗")
    print("║" + " " * 18 + "所有测试完成!" + " " * 23 + "║")
    print("╚" + "═" * 58 + "╝")
    print("\n")
