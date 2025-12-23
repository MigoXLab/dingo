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


def scan_llm_classes() -> List[Dict[str, Any]]:
    """扫描所有 LLM 类，提取 _metric_info 信息"""
    # 先加载模型
    Model.load_model()

    metrics_info = []

    # 从 llm_name_map 中获取所有 LLM 类
    for llm_name, llm_class in Model.llm_name_map.items():
        if hasattr(llm_class, '_metric_info'):
            info = llm_class._metric_info.copy()
            info['llm_name'] = llm_name
            info['class_name'] = llm_class.__name__
            info['type'] = 'llm'
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


def truncate_description(description: str, max_length: int = 120) -> str:
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
    table += "| Type | Metric | Description | Paper Source | Evaluation Results | Examples |\n"
    table += "|------|--------|-------------|--------------|-------------------|----------|\n"

    # 对于rule类，按type分组合并；对于llm类，保持原有逻辑
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

            # 处理示例链接
            if first_metric.get('examples'):
                # 修正相对路径
                example_path = first_metric['examples']
                if example_path.startswith('docs/'):
                    example_path = example_path[5:]
                elif example_path.startswith('examples/'):
                    example_path = f"../{example_path}"
                examples = f"[📝 View Example]({example_path})"
            else:
                examples = "N/A"

            table += f"| {type_name} | {combined_metrics} | " \
                f"{combined_description} | {paper_source} | {eval_results} | {examples} |\n"
    else:
        # 对于llm类，按类名排序；对于其他类型保持原有逻辑
        sort_key = lambda x: x.get('class_name', '')  # noqa: E731
        for metric in sorted(metrics, key=sort_key):
            # 处理type列
            if metric.get('type') == 'llm':
                type_name = f"`{metric.get('llm_name', 'LLM')}`"
            elif metric.get('type') == 'rule':
                type_name = f"`{metric['rule_type']}`"
            else:
                type_name = "N/A"

            # 使用类名作为metric名称
            metric_name = metric['class_name']
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

            # 处理示例链接
            if metric.get('examples'):
                # 修正相对路径
                example_path = metric['examples']
                if example_path.startswith('docs/'):
                    example_path = example_path[5:]
                elif example_path.startswith('examples/'):
                    example_path = f"../{example_path}"
                examples = f"[📝 View Example]({example_path})"
            else:
                examples = "N/A"

            table += f"| {type_name} | {metric_name} | {description} | " \
                f"{paper_source} | {eval_results} | {examples} |\n"

    table += "\n"
    return table


def generate_metrics_documentation() -> str:
    """生成完整的 metrics 文档"""
    # 扫描所有类
    llm_metrics = scan_llm_classes()
    rule_metrics = scan_rule_classes()

    # 合并所有metrics
    all_metrics = llm_metrics + rule_metrics

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
    category_order = [
        "RAG Evaluation Metrics",
        "Pretrain Text Quality Assessment Metrics",
        "SFT Data Assessment Metrics",
        "Classification Metrics",
        "Multimodality Assessment Metrics",
        "Rule-Based TEXT Quality Metrics",
        "Rule-Based IMG Quality Metrics"
    ]

    processed_categories = set()

    # 首先处理预定义类别
    for category in category_order:
        if category in categories:
            doc += generate_table_section(category, categories[category])
            processed_categories.add(category)

    # 处理未预定义的类别 - 归入"other"或单独显示
    unprocessed_categories = set(categories.keys()) - processed_categories - {"other"}

    if unprocessed_categories:
        # 如果有未预定义的类别，先显示它们
        for category in sorted(unprocessed_categories):
            doc += generate_table_section(category, categories[category])
            processed_categories.add(category)

    # 最后处理显式的"other"类别（如果存在）
    if "other" in categories:
        doc += generate_table_section("Other Metrics", categories["other"])

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
        llm_metrics = scan_llm_classes()
        rule_metrics = scan_rule_classes()
        all_metrics = llm_metrics + rule_metrics

        print(f"📊 Total metrics found: {len(all_metrics)}")
        print(f"   - LLM-based: {len(llm_metrics)}")
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
