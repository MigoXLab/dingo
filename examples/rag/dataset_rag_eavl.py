"""
RAGAS论文复现示例

使用dingo标准流程和RAGAS论文中的评测数据集（WikiEval和amnesty_qa）来复现论文结果

论文: RAGAS: Automated Evaluation of Retrieval Augmented Generation
论文链接: https://arxiv.org/abs/2309.15217

数据集:
- WikiEval: https://huggingface.co/datasets/explodinggradients/WikiEval (10个样本，本地路径: test/data/WikiEval_samples_10.jsonl)
  数据字段: question, answer, context_v1, context_v2 (注意: 不是 contexts)
  - question: a question that can be answered from the given Wikipedia page (source).
  - source: The source Wikipedia page from which the question and context are generated.
  - grounded_answer: answer grounded on context_v1
  - ungrounded_answer: answer generated without context_v1
  - poor_answer: answer with poor relevancy compared to grounded_answer and ungrounded_answer
  - context_v1: Ideal context to answer the given question
  - contetx_v2: context that contains redundant information compared to context_v1
"""

import os
from pathlib import Path

from dingo.config import InputArgs
from dingo.exec import Executor

# 配置（从环境变量读取，或直接设置）
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "deepseek-chat")
OPENAI_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_KEY = os.getenv("OPENAI_API_KEY", "YOUR_API_KEY")


def ragas_wikieval_faithfulness():
    """使用WikiEval数据集评估Faithfulness指标"""

    input_data = {
        "input_path": str(Path("test/data/WikiEval_samples_10.jsonl")),
        "dataset": {
            "source": "local",
            "format": "jsonl",
            "field": {
                "prompt": "question",      # 问题字段
                "content": "answer",       # 答案字段
                "context": "context_v1"    # 上下文字段（列表）- WikiEval用context_v1
            }
        },
        "executor": {
            "prompt_list": ["PromptRAGFaithfulness"],  # 使用prompt_list而不是eval_group，避免加载其他评估器
            "result_save": {
                "good": True,
                "bad": True
            }
        },
        "evaluator": {
            "llm_config": {
                "LLMRAGFaithfulness": {
                    "model": OPENAI_MODEL,
                    "key": OPENAI_KEY,
                    "api_url": OPENAI_URL,
                }
            }
        }
    }

    input_args = InputArgs(**input_data)
    executor = Executor.exec_map["local"](input_args)
    result = executor.execute()
    print(result)
    return result


def ragas_wikieval_context_precision():
    """使用WikiEval数据集评估Context Precision指标"""
    input_data = {
        "input_path": str(Path("test/data/WikiEval_samples_10.jsonl")),
        "dataset": {
            "source": "local",
            "format": "jsonl",
            "field": {
                "prompt": "question",
                "content": "answer",
                "context": "context_v1"    # 上下文字段（列表）- WikiEval用context_v1
            }
        },
        "executor": {
            "prompt_list": ["PromptRAGContextPrecision"],
            "result_save": {
                "good": True,
                "bad": True
            }
        },
        "evaluator": {
            "llm_config": {
                "LLMRAGContextPrecision": {
                    "model": OPENAI_MODEL,
                    "key": OPENAI_KEY,
                    "api_url": OPENAI_URL,
                }
            }
        }
    }

    input_args = InputArgs(**input_data)
    executor = Executor.exec_map["local"](input_args)
    result = executor.execute()
    print(result)
    return result


def ragas_wikieval_answer_relevancy():
    """使用WikiEval数据集评估Answer Relevancy指标"""
    input_data = {
        "input_path": str(Path("test/data/WikiEval_samples_10.jsonl")),
        "dataset": {
            "source": "local",
            "format": "jsonl",
            "field": {
                "prompt": "question",
                "content": "answer"
            }
        },
        "executor": {
            "prompt_list": ["PromptRAGAnswerRelevancy"],
            "result_save": {
                "good": True,
                "bad": True
            }
        },
        "evaluator": {
            "llm_config": {
                "LLMRAGAnswerRelevancy": {
                    "model": OPENAI_MODEL,
                    "key": OPENAI_KEY,
                    "api_url": OPENAI_URL,
                }
            }
        }
    }

    input_args = InputArgs(**input_data)
    executor = Executor.exec_map["local"](input_args)
    result = executor.execute()
    print(result)
    return result


def ragas_wikieval_context_recall():
    """使用WikiEval数据集评估Context Recall指标

    注意: Context Recall 需要 expected_output (ground truth answer)
    """
    input_data = {
        "input_path": str(Path("test/data/WikiEval_samples_10.jsonl")),
        "dataset": {
            "source": "local",
            "format": "jsonl",
            "field": {
                "prompt": "question",
                "content": "answer",        # 这里作为 expected_output
                "context": "context_v1"
            }
        },
        "executor": {
            "prompt_list": ["PromptRAGContextRecall"],
            "result_save": {
                "good": True,
                "bad": True
            }
        },
        "evaluator": {
            "llm_config": {
                "LLMRAGContextRecall": {
                    "model": OPENAI_MODEL,
                    "key": OPENAI_KEY,
                    "api_url": OPENAI_URL,
                }
            }
        }
    }

    input_args = InputArgs(**input_data)
    executor = Executor.exec_map["local"](input_args)
    result = executor.execute()
    print(result)
    return result


def ragas_wikieval_context_relevancy():
    """使用WikiEval数据集评估Context Relevancy指标

    注意: Context Relevancy 只需要问题和上下文，不需要答案
    """
    input_data = {
        "input_path": str(Path("test/data/WikiEval_samples_10.jsonl")),
        "dataset": {
            "source": "local",
            "format": "jsonl",
            "field": {
                "prompt": "question",
                "context": "context_v1"    # 只需要问题和上下文
            }
        },
        "executor": {
            "prompt_list": ["PromptRAGContextRelevancy"],
            "result_save": {
                "good": True,
                "bad": True
            }
        },
        "evaluator": {
            "llm_config": {
                "LLMRAGContextRelevancy": {
                    "model": OPENAI_MODEL,
                    "key": OPENAI_KEY,
                    "api_url": OPENAI_URL,
                }
            }
        }
    }

    input_args = InputArgs(**input_data)
    executor = Executor.exec_map["local"](input_args)
    result = executor.execute()
    print(result)
    return result


def ragas_wikieval_all_metrics():
    """使用WikiEval数据集评估所有5个指标"""
    input_data = {
        "input_path": str(Path("test/data/WikiEval_samples_10.jsonl")),
        "dataset": {
            "source": "local",
            "format": "jsonl",
            "field": {
                "prompt": "question",
                "content": "answer",
                "context": "context_v1"    # 上下文字段（列表）- WikiEval用context_v1
            }
        },
        "executor": {
            "prompt_list": [
                "PromptRAGFaithfulness",
                "PromptRAGContextPrecision",
                "PromptRAGAnswerRelevancy",
                "PromptRAGContextRecall",
                "PromptRAGContextRelevancy"
            ],
            "result_save": {
                "good": True,
                "bad": True
            }
        },
        "evaluator": {
            "llm_config": {
                "LLMRAGFaithfulness": {
                    "model": OPENAI_MODEL,
                    "key": OPENAI_KEY,
                    "api_url": OPENAI_URL,
                },
                "LLMRAGContextPrecision": {
                    "model": OPENAI_MODEL,
                    "key": OPENAI_KEY,
                    "api_url": OPENAI_URL,
                },
                "LLMRAGAnswerRelevancy": {
                    "model": OPENAI_MODEL,
                    "key": OPENAI_KEY,
                    "api_url": OPENAI_URL,
                },
                "LLMRAGContextRecall": {
                    "model": OPENAI_MODEL,
                    "key": OPENAI_KEY,
                    "api_url": OPENAI_URL,
                },
                "LLMRAGContextRelevancy": {
                    "model": OPENAI_MODEL,
                    "key": OPENAI_KEY,
                    "api_url": OPENAI_URL,
                }
            }
        }
    }

    input_args = InputArgs(**input_data)
    executor = Executor.exec_map["local"](input_args)
    result = executor.execute()
    print(result)
    return result


if __name__ == "__main__":
    # 单个指标测试
    # ragas_wikieval_faithfulness()
    # ragas_wikieval_context_precision()
    # ragas_wikieval_answer_relevancy()
    ragas_wikieval_context_recall()
    # ragas_wikieval_context_relevancy()

    # 所有指标测试
    # ragas_wikieval_all_metrics()
