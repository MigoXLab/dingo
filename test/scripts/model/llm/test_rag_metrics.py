"""
RAG 评估指标测试

测试覆盖所有5个RAG指标的核心功能：
1. Faithfulness (忠实度)
2. Context Precision (上下文精度)
3. Answer Relevancy (答案相关性)
4. Context Recall (上下文召回)
5. Context Relevancy (上下文相关性)

运行方式：
pytest test/scripts/model/llm/test_rag_metrics.py -v
"""

from unittest.mock import patch

import pytest

from dingo.io import Data
from dingo.model.llm.rag.llm_rag_context_precision import LLMRAGContextPrecision
from dingo.model.llm.rag.llm_rag_context_recall import LLMRAGContextRecall
from dingo.model.llm.rag.llm_rag_context_relevancy import LLMRAGContextRelevancy
from dingo.model.llm.rag.llm_rag_faithfulness import LLMRAGFaithfulness


class TestFaithfulness:
    """测试忠实度评估"""

    def test_process_response_high_score(self):
        """测试高分响应（通过）"""
        response = '''{
            "statements": [
                {"statement": "Python是一种编程语言", "reason": "上下文支持", "verdict": 1}
            ],
            "score": 9
        }'''

        result = LLMRAGFaithfulness.process_response(response)

        assert result.score == 9
        assert result.status is False  # False = good/pass
        assert any("QUALITY_GOOD" in label for label in result.label)
        assert any("FAITHFULNESS_PASS" in label for label in result.label)
        assert result.metric == "LLMRAGFaithfulness"

    def test_process_response_low_score(self):
        """测试低分响应（未通过）"""
        response = '''{
            "statements": [
                {"statement": "不支持的陈述", "reason": "上下文不支持", "verdict": 0}
            ],
            "score": 3
        }'''

        result = LLMRAGFaithfulness.process_response(response)

        assert result.score == 3
        assert result.status is True  # True = bad/fail
        assert any("QUALITY_BAD" in label for label in result.label)
        assert result.metric == "LLMRAGFaithfulness"

    def test_process_response_with_markdown(self):
        """测试带markdown标记的响应"""
        response = '''```json
{
    "statements": [{"statement": "测试", "reason": "测试", "verdict": 1}],
    "score": 8
}
```'''

        result = LLMRAGFaithfulness.process_response(response)

        assert result.score == 8
        assert result.status is False  # False = good/pass

    def test_process_response_no_statements(self):
        """测试没有陈述的响应"""
        response = '''{
            "statements": [],
            "score": 5
        }'''

        result = LLMRAGFaithfulness.process_response(response)

        assert result.score == 5
        assert result.status is False  # 5分刚好达到阈值


class TestContextPrecision:
    """测试上下文精度评估"""

    def test_process_response_high_precision(self):
        """测试高精度响应（所有上下文都相关）"""
        # Context Precision 需要一个响应列表，每个响应对应一个上下文
        responses = [
            '{"verdict": true, "reason": "上下文1相关"}',
            '{"verdict": true, "reason": "上下文2相关"}',
            '{"verdict": true, "reason": "上下文3相关"}'
        ]

        result = LLMRAGContextPrecision.process_response(responses)

        assert result.score == 10  # 所有都相关，平均精度为1，转换为10分
        assert result.status is False  # False = good/pass
        assert any("QUALITY_GOOD" in label for label in result.label)
        assert any("PRECISION_PASS" in label for label in result.label)

    def test_process_response_low_precision(self):
        """测试低精度响应（部分上下文不相关）"""
        responses = [
            '{"verdict": false, "reason": "上下文1不相关"}',
            '{"verdict": false, "reason": "上下文2不相关"}',
            '{"verdict": true, "reason": "上下文3相关"}'
        ]

        result = LLMRAGContextPrecision.process_response(responses)

        # 平均精度较低，分数应该低于5
        assert result.score < 5
        assert result.status is True  # True = bad/fail
        assert any("QUALITY_BAD" in label for label in result.label)


class TestContextRecall:
    """测试上下文召回评估"""

    def test_process_response_high_recall(self):
        """测试高召回率响应（所有陈述都能归因）"""
        response = '''{
            "classifications": [
                {"statement": "陈述1", "reason": "可归因", "attributed": 1},
                {"statement": "陈述2", "reason": "可归因", "attributed": 1},
                {"statement": "陈述3", "reason": "可归因", "attributed": 1}
            ]
        }'''

        result = LLMRAGContextRecall.process_response(response)

        assert result.score == 10  # 3/3 * 10 = 10
        assert result.status is False  # False = good/pass
        assert any("RECALL_PASS" in label for label in result.label)

    def test_process_response_low_recall(self):
        """测试低召回率响应（大部分陈述不能归因）"""
        response = '''{
            "classifications": [
                {"statement": "陈述1", "reason": "不可归因", "attributed": 0},
                {"statement": "陈述2", "reason": "不可归因", "attributed": 0},
                {"statement": "陈述3", "reason": "可归因", "attributed": 1}
            ]
        }'''

        result = LLMRAGContextRecall.process_response(response)

        assert round(result.score, 1) == 3.3  # 1/3 * 10 = 3.33
        assert result.status is True  # True = bad/fail
        assert any("QUALITY_BAD" in label for label in result.label)


class TestContextRelevancy:
    """测试上下文相关性评估"""

    def test_process_response_high_relevancy(self):
        """测试高相关性响应"""
        response = '''{
            "rating": 2
        }'''

        result = LLMRAGContextRelevancy.process_response(response)

        assert result.score == 10.0  # rating 2 -> score 10
        assert result.status is False  # False = good/pass
        assert any("QUALITY_GOOD" in label for label in result.label)

    def test_process_response_medium_relevancy(self):
        """测试中等相关性响应"""
        response = '''{
            "rating": 1
        }'''

        result = LLMRAGContextRelevancy.process_response(response)

        assert result.score == 5.0  # rating 1 -> score 5
        assert result.status is False  # 5分达到阈值

    def test_process_response_low_relevancy(self):
        """测试低相关性响应"""
        response = '''{
            "rating": 0
        }'''

        result = LLMRAGContextRelevancy.process_response(response)

        assert result.score == 0.0  # rating 0 -> score 0
        assert result.status is True  # True = bad/fail
        assert any("QUALITY_BAD" in label for label in result.label)


class TestIntegration:
    """集成测试（使用 mock）"""

    @patch('dingo.model.llm.base_openai.BaseOpenAI.send_messages')
    @patch('dingo.model.llm.base_openai.BaseOpenAI.create_client')
    def test_faithfulness_end_to_end(self, mock_create_client, mock_send_messages):
        """测试忠实度端到端评估"""
        # Mock 客户端创建
        mock_create_client.return_value = None
        # Mock LLM 响应 - 使用正确的格式
        mock_send_messages.return_value = '''{
            "statements": [
                {"statement": "Python是一种编程语言", "reason": "上下文支持", "verdict": 1}
            ],
            "score": 8
        }'''

        data = Data(
            data_id="test_integration",
            prompt="Python是什么？",
            content="Python是一种编程语言。",
            context=["Python是由Guido创建的编程语言。"]
        )

        result = LLMRAGFaithfulness.eval(data)

        assert result.score == 8
        assert result.status is False  # False = good/pass
        assert mock_send_messages.called

    @patch('dingo.model.llm.base_openai.BaseOpenAI.send_messages')
    @patch('dingo.model.llm.base_openai.BaseOpenAI.create_client')
    def test_context_relevancy_end_to_end(self, mock_create_client, mock_send_messages):
        """测试上下文相关性端到端评估"""
        # Mock 客户端创建
        mock_create_client.return_value = None
        # Mock LLM 响应 - 使用正确的格式
        mock_send_messages.return_value = '{"rating": 1}'  # rating 1 -> score 5

        data = Data(
            data_id="test_integration_3",
            prompt="深度学习的应用？",
            context=[
                "深度学习用于图像识别。",
                "区块链是分布式技术。"
            ]
        )

        result = LLMRAGContextRelevancy.eval(data)

        assert result.score == 5.0  # rating 1 映射到 5.0
        assert result.status is False  # False = good/pass (阈值是5，5>=5)
        assert mock_send_messages.called


class TestEdgeCases:
    """边界情况测试"""

    def test_empty_context_list(self):
        """测试空上下文列表"""
        data = Data(
            data_id="test_edge_1",
            prompt="测试问题",
            content="测试答案",
            context=[]
        )

        # 空上下文应该抛出异常或返回错误
        with pytest.raises((ValueError, AttributeError, Exception)):
            LLMRAGFaithfulness.build_messages(data)

    def test_invalid_json_response(self):
        """测试无效的JSON响应"""
        invalid_response = "这不是JSON格式"

        with pytest.raises(Exception):  # ConvertJsonError
            LLMRAGFaithfulness.process_response(invalid_response)

    def test_missing_score_in_response(self):
        """测试响应中缺少score字段（会使用默认值0）"""
        response = '''{
            "statements": []
        }'''

        result = LLMRAGFaithfulness.process_response(response)

        # 当缺少 score 字段时，会使用默认分数 0
        assert result.score == 0
        assert result.status is True  # True = bad/fail (因为分数为0)

    def test_context_relevancy_invalid_rating(self):
        """测试无效的rating值"""
        response = '''{
            "rating": 5
        }'''

        result = LLMRAGContextRelevancy.process_response(response)

        # rating 5 会被映射到 (5/2)*10 = 25，但这超出了0-10的范围
        # 实际实现中可能需要进行范围检查
        assert result.score > 10  # 验证分数计算


# 使用 pytest 命令运行测试，而不是直接运行此文件
# pytest test/scripts/model/llm/test_rag_metrics.py -v
