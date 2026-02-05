"""
单元测试: dingo/model/rule/rule_sciencemetabench.py

测试 ScienceMetaBench 相关规则和功能函数
"""

import json
import os
import shutil
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from dingo.io.input import Data, RequiredField
from dingo.model.rule.rule_sciencemetabench import RuleMetadataSimilarity, calculate_similarity


class TestCalculateSimilarity:
    """测试 calculate_similarity 函数"""

    def test_both_empty(self):
        """测试两个字符串都为空的情况"""
        assert calculate_similarity("", "") == 1.0
        assert calculate_similarity(None, None) == 1.0
        assert calculate_similarity("", None) == 1.0
        assert calculate_similarity(None, "") == 1.0

    def test_one_empty(self):
        """测试一个为空另一个不为空的情况"""
        assert calculate_similarity("", "hello") == 0.0
        assert calculate_similarity("hello", "") == 0.0
        assert calculate_similarity(None, "hello") == 0.0
        assert calculate_similarity("hello", None) == 0.0

    def test_exact_match(self):
        """测试完全匹配的情况"""
        assert calculate_similarity("hello", "hello") == 1.0
        assert calculate_similarity("测试", "测试") == 1.0

    def test_case_insensitive(self):
        """测试忽略大小写"""
        assert calculate_similarity("Hello", "hello") == 1.0
        assert calculate_similarity("WORLD", "world") == 1.0
        assert calculate_similarity("TeSt", "tEsT") == 1.0

    def test_similar_strings(self):
        """测试相似字符串"""
        # 相似度应该大于0但小于1
        sim = calculate_similarity("海底管道砂袋堆叠防护效果数值模拟", "海底管道砂袋堆叠防护效果数值模拟研究")
        assert 0.8 < sim < 1.0

        sim = calculate_similarity("Hello World", "Hello")
        assert 0.5 < sim < 1.0

    def test_completely_different(self):
        """测试完全不同的字符串"""
        sim = calculate_similarity("abc", "xyz")
        assert 0.0 <= sim < 0.5


class TestRuleMetadataSimilarity:
    """测试 RuleMetadataSimilarity 规则"""

    @pytest.fixture
    def test_data_file(self):
        """返回测试数据文件路径"""
        return Path(__file__).parent.parent.parent.parent / "data" / "sciencemetabench" / "paper.jsonl"

    def test_perfect_match(self):
        """测试完全匹配的情况"""
        data = Data()
        data.metadata = {
            "standard": "10.1234/test",
            "produced": "10.1234/test"
        }

        result = RuleMetadataSimilarity.eval(data)

        assert result.metric == "RuleMetadataSimilarity"
        assert result.label == ["QUALITY_GOOD"]
        assert result.score == 1.0

    def test_partial_match(self):
        """测试部分匹配的情况"""
        data = Data()
        data.metadata = {
            "standard": "Test Paper Title",
            "produced": "Test Paper"
        }

        result = RuleMetadataSimilarity.eval(data)

        assert result.metric == "RuleMetadataSimilarity"
        # 相似度应该较高但不是1.0
        assert 0.7 < result.score < 1.0

    def test_below_threshold(self):
        """测试低于阈值的情况"""
        data = Data()
        data.metadata = {
            "standard": "10.1234/test",
            "produced": ""
        }

        result = RuleMetadataSimilarity.eval(data)

        assert result.metric == "RuleMetadataSimilarity"
        assert result.status is True
        assert result.score == 0.0
        assert "QUALITY_BAD_EFFECTIVENESS.RuleMetadataSimilarity" in result.label

    def test_with_real_data(self, test_data_file):
        """使用真实测试数据进行测试"""
        if not test_data_file.exists():
            pytest.skip(f"测试数据文件不存在: {test_data_file}")

        with open(test_data_file, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    json_data = json.loads(line)
                    # 测试 doi 字段
                    if "doi" in json_data and isinstance(json_data["doi"], dict):
                        data = Data()
                        data.metadata = json_data["doi"]

                        result = RuleMetadataSimilarity.eval(data)

                        # 验证结果结构
                        assert result.metric == "RuleMetadataSimilarity"
                        assert result.score is not None
                        assert 0.0 <= result.score <= 1.0

    def test_missing_metadata(self):
        """测试缺少 metadata 字段的情况"""
        data = Data()

        with pytest.raises(ValueError, match="缺少必需字段: metadata"):
            RuleMetadataSimilarity.eval(data)

    def test_invalid_metadata_format(self):
        """测试 metadata 格式错误的情况"""
        data = Data()
        data.metadata = "invalid format"

        with pytest.raises(ValueError, match="数据格式错误"):
            RuleMetadataSimilarity.eval(data)

    def test_custom_threshold(self):
        """测试自定义阈值"""
        data = Data()
        data.metadata = {
            "standard": "Test Paper Title",
            "produced": "Test Paper"
        }

        # 设置自定义阈值
        RuleMetadataSimilarity.dynamic_config.threshold = 0.9

        result = RuleMetadataSimilarity.eval(data)

        assert result.metric == "RuleMetadataSimilarity"
        # 由于相似度约 0.7-0.8，低于 0.9 阈值，应该被标记为质量差
        if result.score < 0.9:
            assert result.status is True

        # 重置为默认值
        RuleMetadataSimilarity.dynamic_config.threshold = 0.6

    def test_custom_key_list(self):
        """测试自定义键名"""
        data = Data()
        data.metadata = {
            "benchmark": "Test Value",
            "product": "Test Value"
        }

        # 设置自定义键名
        RuleMetadataSimilarity.dynamic_config.key_list = ["benchmark", "product"]

        result = RuleMetadataSimilarity.eval(data)

        assert result.metric == "RuleMetadataSimilarity"
        assert result.score == 1.0
        assert result.label == ["QUALITY_GOOD"]

        # 重置为默认值
        RuleMetadataSimilarity.dynamic_config.key_list = ["standard", "produced"]


class TestDeprecatedFunctions:
    """测试已弃用的函数（如果存在）"""

    def test_write_similarity_to_excel_not_implemented(self):
        """测试 write_similarity_to_excel 函数是否存在"""
        # 注意：根据当前代码，write_similarity_to_excel 函数未实现
        # 这个测试用于验证是否需要实现该函数
        try:
            from dingo.model.rule.rule_sciencemetabench import write_similarity_to_excel

            # 如果导入成功，说明函数存在
            assert callable(write_similarity_to_excel)
        except ImportError:
            # 函数不存在，这是预期的
            pytest.skip("write_similarity_to_excel 函数未实现")


class TestWriteSimilarityToExcelPlaceholder:
    """write_similarity_to_excel 测试的占位符"""

    @pytest.fixture
    def temp_output_dir(self):
        """创建临时输出目录"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        # 清理
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def sample_paper_data(self, temp_output_dir):
        """创建示例 paper 数据"""
        data = [
            {
                "sha256": "test001",
                "benchmark": {
                    "doi": "10.1234/test001",
                    "title": "Test Paper 1",
                    "author": "Author 1",
                    "keyword": "keyword1",
                    "abstract": "Abstract 1",
                    "pub_time": "2024"
                },
                "product": {
                    "doi": "10.1234/test001",
                    "title": "Test Paper 1",
                    "author": "Author 1",
                    "keyword": "keyword1",
                    "abstract": "Abstract 1",
                    "pub_time": "2024"
                },
                "dingo_result": {
                    "eval_status": False,
                    "eval_details": {
                        "doi": [
                            {
                                "metric": "RuleMetadataSimilarity",
                                "status": False,
                                "label": ["QUALITY_GOOD"],
                                "score": 1.0,
                                "reason": None
                            }
                        ]
                    }
                }
            },
            {
                "sha256": "test002",
                "benchmark": {
                    "doi": "10.1234/test002",
                    "title": "Test Paper 2",
                    "author": "Author 2",
                    "keyword": "keyword2",
                    "abstract": "Abstract 2",
                    "pub_time": "2024"
                },
                "product": {
                    "doi": "",
                    "title": "Different Title",
                    "author": "Author 2",
                    "keyword": "keyword2",
                    "abstract": "Different Abstract",
                    "pub_time": "2024"
                },
                "dingo_result": {
                    "eval_status": True,
                    "eval_details": {
                        "doi": [
                            {
                                "metric": "RuleMetadataSimilarity",
                                "status": True,
                                "label": ["QUALITY_BAD_EFFECTIVENESS.RuleMetadataSimilarity"],
                                "score": 0.0,
                                "reason": None
                            }
                        ]
                    }
                }
            }
        ]

        # 写入 jsonl 文件
        jsonl_file = Path(temp_output_dir) / "test_result.jsonl"
        with open(jsonl_file, 'w', encoding='utf-8') as f:
            for item in data:
                f.write(json.dumps(item, ensure_ascii=False) + '\n')

        return temp_output_dir

    @pytest.mark.skip(reason="write_similarity_to_excel 函数未在当前版本中实现")
    def test_write_paper_excel(self, sample_paper_data):
        """测试导出 paper 类型的 Excel（功能未实现）"""
        pass

    @pytest.mark.skip(reason="write_similarity_to_excel 函数未在当前版本中实现")
    def test_invalid_type(self, temp_output_dir):
        """测试无效的数据类型（功能未实现）"""
        pass

    @pytest.mark.skip(reason="write_similarity_to_excel 函数未在当前版本中实现")
    def test_nonexistent_directory(self):
        """测试不存在的目录（功能未实现）"""
        pass

    @pytest.mark.skip(reason="write_similarity_to_excel 函数未在当前版本中实现")
    def test_no_jsonl_files(self, temp_output_dir):
        """测试目录中没有 jsonl 文件（功能未实现）"""
        pass

    @pytest.mark.skip(reason="write_similarity_to_excel 函数未在当前版本中实现")
    def test_default_filename(self, sample_paper_data):
        """测试默认文件名生成（功能未实现）"""
        pass

    @pytest.mark.skip(reason="write_similarity_to_excel 函数未在当前版本中实现")
    def test_data_sorting(self, sample_paper_data):
        """测试数据按 sha256 排序（功能未实现）"""
        pass

    @pytest.mark.skip(reason="write_similarity_to_excel 函数未在当前版本中实现")
    def test_all_string_type(self, sample_paper_data):
        """测试所有列都是字符串类型（功能未实现）"""
        pass


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
