import statistics
from typing import Any, Dict

from pydantic import BaseModel, Field


class SummaryModel(BaseModel):
    task_id: str = ''
    task_name: str = ''
    # eval_group: str = ''
    input_path: str = ''
    output_path: str = ''
    create_time: str = ''
    finish_time: str = ''
    score: float = 0.0
    num_good: int = 0
    num_bad: int = 0
    total: int = 0
    type_ratio: Dict[str, Dict[str, int]] = {}

    # 新增：指标分数统计（用于RAG等评估场景）
    # 结构：{field_key: {metric_name: {scores, score_average, ...}}}
    metrics_score_stats: Dict[str, Dict[str, Dict[str, Any]]] = Field(default_factory=dict)

    def add_metric_score(self, field_key: str, metric_name: str, score: float):
        """
        添加指标分数到统计中

        Args:
            field_key: 字段名（如 'user_input,response'）
            metric_name: 指标名称（如 LLMRAGFaithfulness）
            score: 分数值
        """
        metric_stats = self.metrics_score_stats.setdefault(field_key, {}).setdefault(
            metric_name,
            {
                'scores': [],
                'score_average': 0.0,
                'score_count': 0,
                'score_min': None,
                'score_max': None
            }
        )

        metric_stats['scores'].append(score)
        metric_stats['score_count'] += 1

    def calculate_metrics_score_averages(self):
        """
        计算所有字段和指标分数的平均值、最小值、最大值、标准差

        使用 statistics 模块进行统计计算，提高代码可读性和健壮性
        """
        for field_key, metrics in self.metrics_score_stats.items():
            for metric_name, stats in metrics.items():
                scores = stats['scores']
                if scores:
                    # 使用 statistics 模块进行计算
                    mean = statistics.mean(scores)
                    stats['score_average'] = round(mean, 2)
                    stats['score_min'] = round(min(scores), 2)
                    stats['score_max'] = round(max(scores), 2)
                    # 计算标准差
                    if len(scores) > 1:
                        stats['score_std_dev'] = round(statistics.pstdev(scores), 2)
                    # 清理scores列表以减少存储空间（保留统计信息即可）
                    del stats['scores']

    def get_metrics_score_summary(self, field_key: str) -> Dict[str, float]:
        """
        获取指定字段的指标分数汇总（只包含平均值）

        Args:
            field_key: 字段名

        Returns:
            指标名称到平均分数的映射
        """
        if field_key not in self.metrics_score_stats:
            return {}
        return {
            metric_name: stats.get('score_average', 0.0)
            for metric_name, stats in self.metrics_score_stats[field_key].items()
        }

    def get_metrics_score_overall_average(self, field_key: str) -> float:
        """
        计算指定字段所有指标分数的总平均分

        Args:
            field_key: 字段名

        注意：包含所有指标（即使平均分为 0），因为 0 分也是一个重要的评估信号

        Returns:
            总平均分
        """
        if field_key not in self.metrics_score_stats:
            return 0.0

        averages = [
            stats.get('score_average', 0.0)
            for stats in self.metrics_score_stats[field_key].values()
        ]
        return round(sum(averages) / len(averages), 2) if averages else 0.0

    def to_dict(self):
        result = {
            'task_id': self.task_id,
            'task_name': self.task_name,
            # 'eval_group': self.eval_group,
            'input_path': self.input_path,
            'output_path': self.output_path,
            'create_time': self.create_time,
            'finish_time': self.finish_time,
            'score': self.score,
            'num_good': self.num_good,
            'num_bad': self.num_bad,
            'total': self.total,
            'type_ratio': self.type_ratio,
        }

        # 如果有指标分数统计，以层级结构添加到输出中（与 type_ratio 结构一致）
        if self.metrics_score_stats:
            result['metrics_score'] = {
                field_key: {
                    'stats': metrics,
                    'summary': self.get_metrics_score_summary(field_key),
                    'overall_average': self.get_metrics_score_overall_average(field_key)
                }
                for field_key, metrics in self.metrics_score_stats.items()
            }

        return result
