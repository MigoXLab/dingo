"""
RAG 评估指标测试

测试覆盖所有5个RAG指标：
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
from dingo.model.llm.rag.llm_rag_answer_relevancy import LLMRAGAnswerRelevancy
from dingo.model.llm.rag.llm_rag_context_precision import LLMRAGContextPrecision
from dingo.model.llm.rag.llm_rag_context_recall import LLMRAGContextRecall
from dingo.model.llm.rag.llm_rag_context_relevancy import LLMRAGContextRelevancy
from dingo.model.llm.rag.llm_rag_faithfulness import LLMRAGFaithfulness


class TestFaithfulness:
    """测试忠实度评估"""

    def test_build_messages_basic(self):
        """测试基本消息构建"""
        data = Data(
            data_id="test_1",
            prompt="Python是什么？",
            content="Python是一种编程语言。",
            context=["Python是由Guido创建的编程语言。"]
        )

        messages = LLMRAGFaithfulness.build_messages(data)

        assert len(messages) == 1
        assert messages[0]["role"] == "user"
        assert "Python是什么？" in messages[0]["content"]
        assert "Python是一种编程语言。" in messages[0]["content"]
        assert "Python是由Guido创建的编程语言。" in messages[0]["content"]

    def test_build_messages_multiple_contexts(self):
        """测试多个上下文"""
        data = Data(
            data_id="test_2",
            prompt="机器学习的应用？",
            content="机器学习用于图像识别和NLP。",
            context=[
                "机器学习在图像识别中应用广泛。",
                "自然语言处理是机器学习的应用。"
            ]
        )

        messages = LLMRAGFaithfulness.build_messages(data)

        assert "上下文1" in messages[0]["content"]
        assert "上下文2" in messages[0]["content"]
        assert "机器学习在图像识别中应用广泛。" in messages[0]["content"]

    def test_build_messages_missing_context_raises_error(self):
        """测试缺少上下文时抛出错误"""
        data = Data(
            data_id="test_3",
            prompt="测试问题",
            content="测试答案"
            # 缺少 context
        )

        with pytest.raises(ValueError, match="需要contexts字段"):
            LLMRAGFaithfulness.build_messages(data)

    def test_process_response_high_score(self):
        """测试高分响应（通过）"""
        response = '{"score": 9, "reason": "答案完全基于上下文，无幻觉。"}'

        result = LLMRAGFaithfulness.process_response(response)

        assert result.score == 9
        assert result.error_status is False
        assert result.type == "QUALITY_GOOD"
        assert result.name == "FAITHFULNESS_PASS"
        assert "9/10" in result.reason[0]

    def test_process_response_low_score(self):
        """测试低分响应（未通过）"""
        response = '{"score": 3, "reason": "答案包含未被上下文支持的陈述。"}'

        result = LLMRAGFaithfulness.process_response(response)

        assert result.score == 3
        assert result.error_status is True
        assert result.type == "QUALITY_BAD_FAITHFULNESS"
        assert result.name == "PromptRAGFaithfulness"
        assert "3/10" in result.reason[0]

    def test_process_response_with_markdown(self):
        """测试带markdown标记的响应"""
        response = '```json\n{"score": 8, "reason": "大部分陈述有支持。"}\n```'

        result = LLMRAGFaithfulness.process_response(response)

        assert result.score == 8
        assert result.error_status is False


class TestContextPrecision:
    """测试上下文精度评估"""

    def test_build_messages_basic(self):
        """测试基本消息构建"""
        data = Data(
            data_id="test_1",
            prompt="深度学习的应用？",
            content="深度学习用于CV和NLP。",
            context=[
                "深度学习在计算机视觉中应用广泛。",
                "NLP是深度学习的重要应用。",
                "区块链是分布式技术。"  # 不相关
            ]
        )

        messages = LLMRAGContextPrecision.build_messages(data)

        assert len(messages) == 1
        assert "深度学习的应用？" in messages[0]["content"]
        assert "深度学习用于CV和NLP。" in messages[0]["content"]
        assert "区块链是分布式技术。" in messages[0]["content"]

    def test_build_messages_missing_answer_raises_error(self):
        """测试缺少答案时抛出错误"""
        data = Data(
            data_id="test_2",
            prompt="测试问题",
            context=["测试上下文"]
            # 缺少 content (answer)
        )

        with pytest.raises(ValueError, match="需要answer字段"):
            LLMRAGContextPrecision.build_messages(data)

    def test_process_response_high_precision(self):
        """测试高精度响应"""
        response = '{"score": 9, "reason": "所有上下文都相关且排序合理。"}'

        result = LLMRAGContextPrecision.process_response(response)

        assert result.score == 9
        assert result.error_status is False
        assert result.type == "QUALITY_GOOD"
        assert "PRECISION_PASS" in result.name

    def test_process_response_low_precision(self):
        """测试低精度响应"""
        response = '{"score": 4, "reason": "大量不相关上下文。"}'

        result = LLMRAGContextPrecision.process_response(response)

        assert result.score == 4
        assert result.error_status is True
        assert result.type == "QUALITY_BAD_CONTEXT_PRECISION"


class TestAnswerRelevancy:
    """测试答案相关性评估"""

    def test_build_messages_basic(self):
        """测试基本消息构建"""
        data = Data(
            data_id="test_1",
            prompt="什么是机器学习？",
            content="机器学习是AI的分支，使计算机能从数据中学习。"
        )

        messages = LLMRAGAnswerRelevancy.build_messages(data)

        assert len(messages) == 1
        assert "什么是机器学习？" in messages[0]["content"]
        assert "机器学习是AI的分支" in messages[0]["content"]

    def test_build_messages_without_context(self):
        """测试不需要上下文（Answer Relevancy 只需问题和答案）"""
        data = Data(
            data_id="test_2",
            prompt="Python的特点？",
            content="Python简洁且易读。"
            # 不需要 context
        )

        messages = LLMRAGAnswerRelevancy.build_messages(data)

        assert len(messages) == 1
        assert "Python的特点？" in messages[0]["content"]

    def test_build_messages_missing_question_raises_error(self):
        """测试缺少问题时抛出错误"""
        data = Data(
            data_id="test_3",
            content="只有答案"
            # 缺少 prompt (question)
        )

        with pytest.raises(ValueError, match="需要question字段"):
            LLMRAGAnswerRelevancy.build_messages(data)

    def test_process_response_high_relevancy(self):
        """测试高相关性响应"""
        response = '{"score": 10, "reason": "答案直接完整回答问题。"}'

        result = LLMRAGAnswerRelevancy.process_response(response)

        assert result.score == 10
        assert result.error_status is False
        assert result.type == "QUALITY_GOOD"

    def test_process_response_low_relevancy(self):
        """测试低相关性响应"""
        response = '{"score": 2, "reason": "答案大量偏题。"}'

        result = LLMRAGAnswerRelevancy.process_response(response)

        assert result.score == 2
        assert result.error_status is True
        assert result.type == "QUALITY_BAD_ANSWER_RELEVANCY"


class TestContextRecall:
    """测试上下文召回评估"""

    def test_build_messages_basic(self):
        """测试基本消息构建"""
        data = Data(
            data_id="test_1",
            prompt="Python的特点？",
            content="Python简洁且有丰富的库。",  # 作为 expected_output
            context=["Python以其简洁的语法著称。"]
        )

        messages = LLMRAGContextRecall.build_messages(data)

        assert len(messages) == 1
        assert "Python的特点？" in messages[0]["content"]
        assert "Python简洁且有丰富的库。" in messages[0]["content"]
        assert "Python以其简洁的语法著称。" in messages[0]["content"]

    def test_build_messages_with_expected_output(self):
        """测试使用 raw_data 中的 expected_output"""
        data = Data(
            data_id="test_2",
            prompt="深度学习的特点？",
            raw_data={
                "expected_output": "深度学习使用多层神经网络。",
                "contexts": ["深度学习使用神经网络。"]
            }
        )

        messages = LLMRAGContextRecall.build_messages(data)

        assert "深度学习使用多层神经网络。" in messages[0]["content"]

    def test_build_messages_missing_expected_output_raises_error(self):
        """测试缺少 expected_output 时抛出错误"""
        data = Data(
            data_id="test_3",
            prompt="测试问题",
            context=["测试上下文"]
            # 缺少 content 或 expected_output
        )

        with pytest.raises(ValueError, match="需要expected_output或answer字段"):
            LLMRAGContextRecall.build_messages(data)

    def test_process_response_high_recall(self):
        """测试高召回率响应"""
        response = '{"score": 9, "reason": "所有关键信息都能从上下文找到。"}'

        result = LLMRAGContextRecall.process_response(response)

        assert result.score == 9
        assert result.error_status is False
        assert "RECALL_PASS" in result.name

    def test_process_response_low_recall(self):
        """测试低召回率响应"""
        response = '{"score": 3, "reason": "大量关键信息缺失。"}'

        result = LLMRAGContextRecall.process_response(response)

        assert result.score == 3
        assert result.error_status is True
        assert result.type == "QUALITY_BAD_CONTEXT_RECALL"


class TestContextRelevancy:
    """测试上下文相关性评估"""

    def test_build_messages_basic(self):
        """测试基本消息构建"""
        data = Data(
            data_id="test_1",
            prompt="机器学习的应用？",
            context=[
                "机器学习用于图像识别。",
                "区块链是分布式技术。"  # 不相关
            ]
        )

        messages = LLMRAGContextRelevancy.build_messages(data)

        assert len(messages) == 1
        assert "机器学习的应用？" in messages[0]["content"]
        assert "机器学习用于图像识别。" in messages[0]["content"]
        assert "区块链是分布式技术。" in messages[0]["content"]

    def test_build_messages_without_answer(self):
        """测试不需要答案（Context Relevancy 只需问题和上下文）"""
        data = Data(
            data_id="test_2",
            prompt="深度学习有哪些应用？",
            context=["深度学习在CV中应用广泛。"]
            # 不需要 content (answer)
        )

        messages = LLMRAGContextRelevancy.build_messages(data)

        assert len(messages) == 1
        assert "深度学习有哪些应用？" in messages[0]["content"]

    def test_build_messages_missing_question_raises_error(self):
        """测试缺少问题时抛出错误"""
        data = Data(
            data_id="test_3",
            context=["只有上下文"]
            # 缺少 prompt (question)
        )

        with pytest.raises(ValueError, match="需要question字段"):
            LLMRAGContextRelevancy.build_messages(data)

    def test_build_messages_missing_contexts_raises_error(self):
        """测试缺少上下文时抛出错误"""
        data = Data(
            data_id="test_4",
            prompt="测试问题"
            # 缺少 context
        )

        with pytest.raises(ValueError, match="需要contexts字段"):
            LLMRAGContextRelevancy.build_messages(data)

    def test_process_response_high_relevancy(self):
        """测试高相关性响应"""
        response = '{"score": 10, "reason": "所有上下文都与问题直接相关。"}'

        result = LLMRAGContextRelevancy.process_response(response)

        assert result.score == 10
        assert result.error_status is False
        assert result.type == "QUALITY_GOOD"

    def test_process_response_low_relevancy(self):
        """测试低相关性响应"""
        response = '{"score": 3, "reason": "大量不相关上下文。"}'

        result = LLMRAGContextRelevancy.process_response(response)

        assert result.score == 3
        assert result.error_status is True
        assert result.type == "QUALITY_BAD_CONTEXT_RELEVANCY"


class TestIntegration:
    """集成测试（使用 mock）"""

    @patch('dingo.model.llm.base_openai.BaseOpenAI.send_messages')
    @patch('dingo.model.llm.base_openai.BaseOpenAI.create_client')
    def test_faithfulness_end_to_end(self, mock_create_client, mock_send_messages):
        """测试忠实度端到端评估"""
        # Mock 客户端创建
        mock_create_client.return_value = None
        # Mock LLM 响应
        mock_send_messages.return_value = '{"score": 8, "reason": "答案基本忠实于上下文。"}'

        data = Data(
            data_id="test_integration",
            prompt="Python是什么？",
            content="Python是一种编程语言。",
            context=["Python是由Guido创建的编程语言。"]
        )

        result = LLMRAGFaithfulness.eval(data)

        assert result.score == 8
        assert result.error_status is False
        assert mock_send_messages.called

    @patch('dingo.model.llm.base_openai.BaseOpenAI.send_messages')
    @patch('dingo.model.llm.base_openai.BaseOpenAI.create_client')
    def test_answer_relevancy_end_to_end(self, mock_create_client, mock_send_messages):
        """测试答案相关性端到端评估"""
        # Mock 客户端创建
        mock_create_client.return_value = None
        # Mock LLM 响应
        mock_send_messages.return_value = '{"score": 9, "reason": "答案直接回答问题。"}'

        data = Data(
            data_id="test_integration_2",
            prompt="什么是机器学习？",
            content="机器学习是AI的一个分支。"
        )

        result = LLMRAGAnswerRelevancy.eval(data)

        assert result.score == 9
        assert result.error_status is False
        assert mock_send_messages.called

    @patch('dingo.model.llm.base_openai.BaseOpenAI.send_messages')
    @patch('dingo.model.llm.base_openai.BaseOpenAI.create_client')
    def test_context_relevancy_end_to_end(self, mock_create_client, mock_send_messages):
        """测试上下文相关性端到端评估"""
        # Mock 客户端创建
        mock_create_client.return_value = None
        # Mock LLM 响应
        mock_send_messages.return_value = '{"score": 6, "reason": "半数上下文相关。"}'

        data = Data(
            data_id="test_integration_3",
            prompt="深度学习的应用？",
            context=[
                "深度学习用于图像识别。",
                "区块链是分布式技术。"
            ]
        )

        result = LLMRAGContextRelevancy.eval(data)

        assert result.score == 6
        assert result.error_status is False  # 默认阈值是5
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

        with pytest.raises(ValueError):
            LLMRAGFaithfulness.build_messages(data)

    def test_single_context(self):
        """测试单个上下文"""
        data = Data(
            data_id="test_edge_2",
            prompt="Python是什么？",
            content="Python是编程语言。",
            context="Python是由Guido创建的。"  # 字符串而非列表
        )

        messages = LLMRAGFaithfulness.build_messages(data)

        assert len(messages) == 1
        assert "Python是由Guido创建的。" in messages[0]["content"]

    def test_very_long_context(self):
        """测试很长的上下文"""
        long_context = "这是一段很长的文本。" * 100

        data = Data(
            data_id="test_edge_3",
            prompt="测试问题",
            content="测试答案",
            context=[long_context]
        )

        messages = LLMRAGFaithfulness.build_messages(data)

        assert len(messages) == 1
        assert long_context in messages[0]["content"]

    def test_chinese_and_english_mixed(self):
        """测试中英文混合"""
        data = Data(
            data_id="test_edge_4",
            prompt="What is 机器学习?",
            content="Machine Learning 是AI的分支。",
            context=["ML is a branch of AI that enables machines to learn."]
        )

        messages = LLMRAGFaithfulness.build_messages(data)

        assert "What is 机器学习?" in messages[0]["content"]
        assert "Machine Learning 是AI的分支。" in messages[0]["content"]

    def test_special_characters(self):
        """测试特殊字符"""
        data = Data(
            data_id="test_edge_5",
            prompt="Python中@装饰器是什么？",
            content="@decorator用于函数增强，使用@符号。",
            context=["装饰器使用@语法糖。"]
        )

        messages = LLMRAGFaithfulness.build_messages(data)

        assert "@装饰器" in messages[0]["content"]
        assert "@decorator" in messages[0]["content"]

    def test_invalid_json_response(self):
        """测试无效的JSON响应"""
        invalid_response = "这不是JSON格式"

        with pytest.raises(Exception):  # ConvertJsonError
            LLMRAGFaithfulness.process_response(invalid_response)

    def test_missing_score_in_response(self):
        """测试响应中缺少score字段"""
        response = '{"reason": "只有理由没有分数"}'

        with pytest.raises(Exception):
            LLMRAGFaithfulness.process_response(response)


# 使用 pytest 命令运行测试，而不是直接运行此文件
# pytest test/scripts/model/llm/test_rag_metrics.py -v
