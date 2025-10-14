import gzip
import os
import tempfile
import unittest
from pathlib import Path

from dingo.data.datasource.local import load_local_file


class TestLocalFileHandling(unittest.TestCase):

    def setUp(self):
        """设置测试环境"""
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        """清理测试环境"""
        import shutil
        shutil.rmtree(self.test_dir)

    def test_load_utf8_text_file(self):
        """测试加载普通UTF-8文本文件"""
        test_content = "Hello World\n测试中文\n"
        test_file = os.path.join(self.test_dir, "test.txt")

        with open(test_file, "w", encoding="utf-8") as f:
            f.write(test_content)

        # 测试按行读取
        lines = list(load_local_file(test_file, by_line=True))
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0], "Hello World\n")
        self.assertEqual(lines[1], "测试中文\n")

        # 测试整体读取
        content = list(load_local_file(test_file, by_line=False))
        self.assertEqual(len(content), 1)
        self.assertEqual(content[0], test_content)

    def test_load_gzip_file(self):
        """测试加载.gz压缩文件"""
        test_content = "Compressed content\n压缩内容\n"
        test_file = os.path.join(self.test_dir, "test.jsonl.gz")

        with gzip.open(test_file, "wt", encoding="utf-8") as f:
            f.write(test_content)

        # 测试按行读取
        lines = list(load_local_file(test_file, by_line=True))
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0], "Compressed content\n")
        self.assertEqual(lines[1], "压缩内容\n")

        # 测试整体读取
        content = list(load_local_file(test_file, by_line=False))
        self.assertEqual(len(content), 1)
        self.assertEqual(content[0], test_content)

    def test_load_binary_file_error(self):
        """测试加载二进制文件应该报错"""
        test_file = os.path.join(self.test_dir, "test.bin")

        # 创建一个包含二进制数据的文件
        with open(test_file, "wb") as f:
            f.write(b"\x00\x01\x02\x03\xFF\xFE\xFD")

        with self.assertRaises(RuntimeError) as context:
            list(load_local_file(test_file))

        self.assertIn("Unsupported file format or encoding", str(context.exception))
        self.assertIn("UTF-8 text files", str(context.exception))

    def test_load_invalid_gzip_file_error(self):
        """测试加载无效的.gz文件应该报错"""
        test_file = os.path.join(self.test_dir, "fake.gz")

        # 创建一个伪造的.gz文件（实际上不是gzip格式）
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("This is not a gzip file")

        with self.assertRaises(RuntimeError) as context:
            list(load_local_file(test_file))

        self.assertIn("Failed to read gzipped file", str(context.exception))
        self.assertIn("valid gzip-compressed text file", str(context.exception))

    def test_load_non_utf8_file_error(self):
        """测试加载非UTF-8编码文件应该报错"""
        test_file = os.path.join(self.test_dir, "test_gbk.txt")

        # 创建一个GBK编码的文件
        with open(test_file, "w", encoding="gbk") as f:
            f.write("这是GBK编码的文件")

        with self.assertRaises(RuntimeError) as context:
            list(load_local_file(test_file))

        self.assertIn("Unsupported file format or encoding", str(context.exception))
        self.assertIn("UTF-8 text files", str(context.exception))

    def test_load_empty_file(self):
        """测试加载空文件"""
        test_file = os.path.join(self.test_dir, "empty.txt")

        with open(test_file, "w", encoding="utf-8"):
            pass  # 创建空文件

        lines = list(load_local_file(test_file, by_line=True))
        self.assertEqual(len(lines), 0)

        content = list(load_local_file(test_file, by_line=False))
        self.assertEqual(len(content), 1)
        self.assertEqual(content[0], "")

    def test_load_directory(self):
        """测试加载目录中的多个文件"""
        # 创建多个测试文件
        file1 = os.path.join(self.test_dir, "file1.txt")
        file2 = os.path.join(self.test_dir, "file2.jsonl")

        with open(file1, "w", encoding="utf-8") as f:
            f.write("Content 1\n")

        with open(file2, "w", encoding="utf-8") as f:
            f.write("Content 2\n")

        lines = list(load_local_file(self.test_dir, by_line=True))
        # 应该读取到两行内容（每个文件一行）
        self.assertEqual(len(lines), 2)
        self.assertIn("Content 1\n", lines)
        self.assertIn("Content 2\n", lines)

    def test_load_nonexistent_file(self):
        """测试加载不存在的文件应该报错"""
        nonexistent_file = os.path.join(self.test_dir, "nonexistent.txt")

        with self.assertRaises(RuntimeError) as context:
            list(load_local_file(nonexistent_file))

        self.assertIn("is not a valid path", str(context.exception))


if __name__ == "__main__":
    unittest.main()
