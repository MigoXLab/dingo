#!/usr/bin/env python3
"""
自动生成 Metrics 文档的脚本
按照 3H Assessment Prompts 表格的格式生成文档
"""

import sys
from pathlib import Path
from typing import Any, Dict, List

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dingo.model.model import Model  # noqa: E402


def scan_prompt_classes() -> List[Dict[str, Any]]:
    """扫描所有 prompt 类，提取 _metric_info 信息"""
    # 先加载模型
    Model.load_model()

    metrics_info = []

    # 直接从 prompt_metric_type_map 中获取信息
    for metric_type, prompt_classes in Model.prompt_metric_type_map.items():
        for prompt_class in prompt_classes:
            if hasattr(prompt_class, '_metric_info'):
                info = prompt_class._metric_info.copy()
                info['prompt_type'] = metric_type
                info['class_name'] = prompt_class.__name__
                info['type'] = 'prompt'
                metrics_info.append(info)

    return metrics_info


def scan_rule_classes() -> List[Dict[str, Any]]:
    """扫描所有 rule 类，提取 _metric_info 信息"""
    # 先加载模型
    Model.load_model()

    metrics_info = []

    # 直接从 rule_metric_type_map 中获取信息
    for metric_type, rule_classes in Model.rule_metric_type_map.items():
        for rule_class in rule_classes:
            if hasattr(rule_class, '_metric_info'):
                info = rule_class._metric_info.copy()
                info['rule_type'] = metric_type
                info['class_name'] = rule_class.__name__
                info['type'] = 'rule'

                # 如果 _metric_info 中没有设置 category，则根据类型设置默认值
                if 'category' not in info or not info['category']:
                    info['category'] = 'Rule-Based Quality Metrics'

                metrics_info.append(info)

    return metrics_info


def truncate_description(description: str, max_length: int = 80) -> str:
    """截断description到指定长度"""
    if len(description) <= max_length:
        return description
    return description[:max_length - 3] + "..."


def generate_table_section(title: str, metrics: List[Dict[str, Any]]) -> str:
    """生成表格部分"""
    if not metrics:
        return ""

    # 表格头部
    table = f"### {title}\n\n"
    table += "| Type | Metric | Description | Paper Source | Evaluation Results |\n"
    table += "|------|--------|-------------|--------------|-------------------|\n"

    # 对于rule类，按type分组合并；对于prompt类，保持原有逻辑
    if title.startswith("Rule-Based") and "Quality Metrics" in title:
        # 按type分组
        type_groups = {}
        for metric in metrics:
            if metric.get('type') == 'rule':
                rule_type = metric.get('rule_type', '')
                if rule_type not in type_groups:
                    type_groups[rule_type] = []
                type_groups[rule_type].append(metric)

        # 为每个type生成一行
        for rule_type in sorted(type_groups.keys()):
            group_metrics = type_groups[rule_type]
            type_name = f"`{rule_type}`"

            # 合并同一type的metric名称
            metric_names = [m['class_name'] for m in group_metrics]
            combined_metrics = ", ".join(metric_names)

            # 合并描述（取第一个作为代表，或者合并所有描述）
            descriptions = [m['description'] for m in group_metrics]
            combined_description = "; ".join(descriptions)
            combined_description = truncate_description(combined_description)

            # 取第一个metric的论文信息（因为都是相同的）
            first_metric = group_metrics[0]

            # 处理论文来源
            if first_metric.get('paper_url') and first_metric.get('paper_title'):
                paper_urls = [url.strip() for url in first_metric['paper_url'].split(',')]
                paper_titles = [title.strip() for title in first_metric['paper_title'].split('&')]

                # 如果有多个URL和标题，为每个创建单独的链接
                if len(paper_urls) > 1 and len(paper_titles) > 1:
                    links = []
                    for i, (title, url) in enumerate(zip(paper_titles, paper_urls)):
                        links.append(f"[{title}]({url})")
                    paper_source = " & ".join(links)
                else:
                    paper_source = f"[{first_metric['paper_title']}](" \
                        f"{first_metric['paper_url']})"

                if first_metric.get('paper_authors'):
                    paper_source += f" ({first_metric['paper_authors']})"
            else:
                paper_source = "Internal Implementation"

            # 处理评测结果
            if first_metric.get('evaluation_results'):
                # 修正相对路径：从 docs/metrics.md 到 docs/eval/prompt/xxx.md
                eval_path = first_metric['evaluation_results']
                if eval_path.startswith('docs/'):
                    eval_path = eval_path[5:]  # 去掉 'docs/' 前缀
                eval_results = f"[📊 See Results]({eval_path})"
            else:
                eval_results = "N/A"

            table += f"| {type_name} | {combined_metrics} | " \
                f"{combined_description} | {paper_source} | {eval_results} |\n"
    else:
        # 对于prompt类，保持原有逻辑
        sort_key = lambda x: x.get('prompt_type', x.get('rule_type', ''))  # noqa: E731
        for metric in sorted(metrics, key=sort_key):
            # 处理type列
            if metric.get('type') == 'prompt':
                type_name = f"`{metric['prompt_type']}`"
            elif metric.get('type') == 'rule':
                type_name = f"`{metric['rule_type']}`"
            else:
                type_name = "N/A"

            # 对于rule类，使用类名作为metric名称；对于prompt类，使用描述名称
            if metric.get('type') == 'rule':
                metric_name = metric['class_name']
            else:
                metric_name = metric['metric_name']
            description = truncate_description(metric['description'])

            # 处理论文来源
            if metric.get('paper_url') and metric.get('paper_title'):
                paper_urls = [url.strip() for url in metric['paper_url'].split(',')]
                paper_titles = [title.strip() for title in metric['paper_title'].split('&')]

                # 如果有多个URL和标题，为每个创建单独的链接
                if len(paper_urls) > 1 and len(paper_titles) > 1:
                    links = []
                    for i, (title, url) in enumerate(zip(paper_titles, paper_urls)):
                        links.append(f"[{title}]({url})")
                    paper_source = " & ".join(links)
                else:
                    paper_source = f"[{metric['paper_title']}](" \
                        f"{metric['paper_url']})"

                if metric.get('paper_authors'):
                    paper_source += f" ({metric['paper_authors']})"
            else:
                paper_source = "Internal Implementation"

            # 处理评测结果
            if metric.get('evaluation_results'):
                # 修正相对路径：从 docs/metrics.md 到 docs/eval/prompt/xxx.md
                eval_path = metric['evaluation_results']
                if eval_path.startswith('docs/'):
                    eval_path = eval_path[5:]  # 去掉 'docs/' 前缀
                eval_results = f"[📊 See Results]({eval_path})"
            else:
                eval_results = "N/A"

            table += f"| {type_name} | {metric_name} | {description} | " \
                f"{paper_source} | {eval_results} |\n"

    table += "\n"
    return table


def generate_metrics_documentation() -> str:
    """生成完整的 metrics 文档"""
    # 扫描所有类
    prompt_metrics = scan_prompt_classes()
    rule_metrics = scan_rule_classes()

    # 合并所有metrics
    all_metrics = prompt_metrics + rule_metrics

    # 按类别分组
    categories = {}
    for metric in all_metrics:
        category = metric.get('category', 'other')
        if category not in categories:
            categories[category] = []
        categories[category].append(metric)

    # 生成文档
    doc = "# Data Quality Metrics\n\n"
    doc += "This document provides comprehensive information about " \
           "all quality metrics used in Dingo.\n\n"
    doc += "**Note**: All metrics are backed by academic sources to " \
           "ensure objectivity and scientific rigor.\n\n"

    # 按预定义顺序生成各个类别
    category_order = ["Text Quality Assessment Metrics", "SFT Data Assessment Metrics",
                      "Classification Metrics", "Multimodality Assessment Metrics",
                      "Rule-Based TEXT Quality Metrics", "Rule-Based IMG Quality Metrics",
                      "other"]
    for category in category_order:
        if category in categories:
            doc += generate_table_section(category, categories[category])

    return doc


def main():
    """主函数"""
    try:
        documentation = generate_metrics_documentation()

        # 写入文档文件
        output_file = project_root / "docs" / "metrics.md"
        output_file.parent.mkdir(exist_ok=True)

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(documentation)

        print(f"✅ Metrics documentation generated successfully: {output_file}")

        # 打印统计信息
        prompt_metrics = scan_prompt_classes()
        rule_metrics = scan_rule_classes()
        all_metrics = prompt_metrics + rule_metrics

        print(f"📊 Total metrics found: {len(all_metrics)}")
        print(f"   - Prompt-based: {len(prompt_metrics)}")
        print(f"   - Rule-based: {len(rule_metrics)}")

        categories = {}
        for metric in all_metrics:
            category = metric.get('category', 'other')
            categories[category] = categories.get(category, 0) + 1

        print("📈 Metrics by category:")
        for category, count in sorted(categories.items()):
            print(f"   - {category}: {count}")

    except Exception as e:
        print(f"❌ Error generating documentation: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
