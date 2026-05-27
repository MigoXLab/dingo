import argparse
import json
import os
import re
import time
from collections import Counter
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from dingo.config.input_args import EvaluatorLLMArgs
from dingo.io.input import Data
from dingo.model import Model

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "deepseek-chat")
OPENAI_URL = os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com/v1")
OPENAI_KEY = os.getenv("OPENAI_API_KEY", "")
EVALUATOR_NAME = "LLMChunkQuality"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Chunk benchmark 脚本：输出 F1 与混淆矩阵。")
    parser.add_argument("--input-jsonl", default="test/data/test_chunk.jsonl", help="输入 JSONL 路径")
    parser.add_argument("--content-field", default="text", help="输入中映射到 content 的字段名")
    parser.add_argument("--label-field", default="error_types", help="输入中标签字段名")
    parser.add_argument("--output-path", default="output/chunk_benchmark_run", help="输出目录")
    parser.add_argument("--model", default=OPENAI_MODEL, help="LLM 模型名")
    parser.add_argument("--api-url", default=OPENAI_URL, help="LLM API 地址")
    parser.add_argument("--api-key", default=OPENAI_KEY, help="LLM API Key")
    parser.add_argument("--request-timeout", type=int, default=60, help="请求超时（秒）")
    return parser.parse_args()


def build_llm_config(args: argparse.Namespace) -> Dict:
    # 与 evaluator 配置对齐，直接传给 EvaluatorLLMArgs
    return {
        "model": args.model,
        "key": args.api_key,
        "api_url": args.api_url,
        "timeout": args.request_timeout,
    }


def read_jsonl(path: Path) -> Iterable[Dict]:
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as e:
                raise ValueError(f"{path} 第 {line_no} 行不是合法 JSON: {e}") from e


def safe_div(a: float, b: float) -> float:
    return 0.0 if b == 0 else a / b


def normalize_error_types(value) -> Optional[List]:
    # 约定：None=无标签样本，[]/非空list=有标签样本
    if value is None:
        return None
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        return [value]
    return [value]


def normalize_error_name(error_name: str) -> str:
    if not error_name:
        return ""
    name = str(error_name).strip()
    if "." in name:
        _, maybe_name = name.split(".", 1)
        name = maybe_name.strip()

    # 兼容历史/基准集中的 snake_case 标签，映射到 prompt 里的标准名称
    legacy_mapping = {
        "start_text_truncation": "Error_Start_Text_Truncation",
        "start_inline_formula_truncation": "Error_Start_Inline_Formula_Truncation",
        "start_interline_formula_truncation": "Error_Start_Interline_Formula_Truncation",
        "start_Interline_Formula_Truncation": "Error_Start_Interline_Formula_Truncation",
        "start_punctuation_truncation": "Error_Start_Punctuation_Truncation",
        "start_text_duplicate": "Error_Start_Text_Duplicate",
    }
    return legacy_mapping.get(name, name)


def build_error_type_to_category_from_prompt(prompt: str) -> Dict[str, str]:
    # 从 llm_rag_chunk_quality 的 prompt 自动抽取错误类型->类别映射
    mapping: Dict[str, str] = {}
    current_category = ""
    for raw_line in prompt.splitlines():
        line = raw_line.strip()
        cat_match = re.match(r"^##\s+\d+\.\s+([A-Za-z][A-Za-z0-9_-]*)", line)
        if cat_match:
            current_category = cat_match.group(1)
            continue
        err_match = re.match(r"^-\s+\*\*(Error_[A-Za-z0-9_]+)\*\*:", line)
        if err_match and current_category:
            mapping[err_match.group(1)] = current_category
    return mapping


def infer_error_category(error_name: str, error_map: Dict[str, str], known_categories: set) -> str:
    if not error_name:
        return ""
    name = str(error_name).strip()
    if name == "Good" or name.startswith("Good."):
        return "Good"
    if "." in name:
        maybe_cat, maybe_name = name.split(".", 1)
        if maybe_cat in known_categories:
            return maybe_cat
        name = maybe_name
    return error_map.get(name, "")


def init_evaluator(llm_config: Dict):
    # Dingo 的 LLM eval 为 classmethod：从注册表拿类并做类级配置
    Model.load_model()
    llm_cls = Model.get_llm_name_map().get(EVALUATOR_NAME)
    if llm_cls is None:
        raise ValueError(f"未找到 evaluator: {EVALUATOR_NAME}")
    Model.set_config_llm(llm_cls, EvaluatorLLMArgs(**llm_config))
    llm_cls.client = None
    return llm_cls


def evaluate_dataset(
    rows: Iterable[Dict],
    llm_model,
    content_field: str,
    label_field: str,
    error_map: Dict[str, str],
) -> Tuple[List[Dict], Dict]:
    # 兼容 Good 类别，且未知类别保持空，不进入统计
    known_categories = set(error_map.values()) | {"Good"}

    tp = fp = fn = tn = 0
    total = labeled_total = errors = 0
    pred_bad_total = pred_good_total = 0
    gt_error_type_counter: Counter = Counter()
    gt_error_category_counter: Counter = Counter()
    pred_error_type_counter: Counter = Counter()
    pred_error_category_counter: Counter = Counter()
    pred_records: List[Dict] = []
    start = time.time()

    # 主循环：逐条推理并累积 benchmark 统计
    for idx, row in enumerate(rows, start=1):
        total += 1
        raw_content = row.get(content_field)
        content = str(raw_content) if raw_content is not None else ""
        error_types = normalize_error_types(row.get(label_field))
        gt_error_names = [normalize_error_name(x) for x in ([] if error_types is None else error_types) if str(x).strip()]
        gt_bad: Optional[int] = None
        if error_types is not None:
            # 仅基于清洗后的有效标签判断是否 bad
            gt_bad = 1 if len(gt_error_names) > 0 else 0

        pred_bad = 1
        score = None
        labels: List[str] = []
        reasons: List[str] = []
        error_message = ""
        has_runtime_error = False
        try:
            # status=True 表示 bad，status=False 表示 good
            result = llm_model.eval(Data(content=content))
            pred_bad = 1 if result.status else 0
            score = result.score
            labels = result.label or []
            reasons = result.reason or []
        except Exception as e:
            errors += 1
            error_message = str(e)
            has_runtime_error = True

        # BaseOpenAI 失败场景通常会返回 QUALITY_BAD.<ExceptionName>
        if any(str(lbl).startswith("QUALITY_BAD.") for lbl in labels):
            has_runtime_error = True

        if error_types is not None and not has_runtime_error:
            labeled_total += 1

        pred_error_names = [normalize_error_name(x) for x in labels if str(x).strip()]
        gt_error_categories = sorted(
            {cat for cat in (infer_error_category(x, error_map, known_categories) for x in gt_error_names) if cat}
        )
        pred_error_categories = sorted(
            {cat for cat in (infer_error_category(x, error_map, known_categories) for x in pred_error_names) if cat}
        )
        if gt_bad == 0 and not gt_error_categories:
            gt_error_categories = ["Good"]
        if pred_bad == 0 and not pred_error_categories:
            pred_error_categories = ["Good"]

        gt_error_type_counter.update(gt_error_names)
        gt_error_category_counter.update(gt_error_categories)
        pred_error_type_counter.update(pred_error_names)
        pred_error_category_counter.update(pred_error_categories)

        if not has_runtime_error:
            if pred_bad == 1:
                pred_bad_total += 1
            else:
                pred_good_total += 1

        if has_runtime_error:
            confusion_tag = "ERROR"
        elif gt_bad is None:
            confusion_tag = "NA"
        elif pred_bad == 1 and gt_bad == 1:
            tp += 1
            confusion_tag = "TP"
        elif pred_bad == 1 and gt_bad == 0:
            fp += 1
            confusion_tag = "FP"
        elif pred_bad == 0 and gt_bad == 1:
            fn += 1
            confusion_tag = "FN"
        else:
            tn += 1
            confusion_tag = "TN"

        pred_records.append(
            {
                "chunk_id": row.get("chunk_id", f"row_{idx}"),
                "doc_id": row.get("doc_id", ""),
                "gt_bad": gt_bad,
                "gt_label": None if gt_bad is None else ("bad" if gt_bad == 1 else "good"),
                "pred_bad": pred_bad,
                "pred_label": "bad" if pred_bad == 1 else "good",
                "confusion_tag": confusion_tag,
                "score": score,
                "labels": labels,
                "reasons": reasons,
                "error": error_message,
                "error_types": [] if error_types is None else error_types,
                "gt_error_categories": gt_error_categories,
                "pred_error_types": pred_error_names,
                "pred_error_categories": pred_error_categories,
                "text": content,
            }
        )

    report = {
        "total": total,
        "labeled_total": labeled_total,
        "unlabeled_total": total - labeled_total,
        "errors": errors,
        "prediction_distribution": {
            "pred_bad": pred_bad_total,
            "pred_good": pred_good_total,
            "pred_bad_ratio": safe_div(pred_bad_total, total),
            "pred_good_ratio": safe_div(pred_good_total, total),
        },
        "gt_error_type_distribution": dict(gt_error_type_counter),
        "gt_error_category_distribution": dict(gt_error_category_counter),
        "pred_error_type_distribution": dict(pred_error_type_counter),
        "pred_error_category_distribution": dict(pred_error_category_counter),
        "elapsed_sec": round(time.time() - start, 2),
    }

    if labeled_total > 0:
        # bad 作为正类进行主指标计算
        precision_bad = safe_div(tp, tp + fp)
        recall_bad = safe_div(tp, tp + fn)
        f1_bad = safe_div(2 * precision_bad * recall_bad, precision_bad + recall_bad)
        precision_good = safe_div(tn, tn + fn)
        recall_good = safe_div(tn, tn + fp)
        f1_good = safe_div(2 * precision_good * recall_good, precision_good + recall_good)
        report.update(
            {
                "confusion_matrix_bad_positive": {"TP": tp, "FP": fp, "FN": fn, "TN": tn},
                "accuracy": safe_div(tp + tn, labeled_total),
                "bad_as_positive": {"precision": precision_bad, "recall": recall_bad, "f1": f1_bad},
                "good_as_positive": {"precision": precision_good, "recall": recall_good, "f1": f1_good},
                "f1": f1_bad,  # 默认暴露 bad-positive F1，便于外部系统直接读取
            }
        )
    else:
        report["note"] = "输入数据不含标签（error_types 缺失），仅输出模型预测结果与分布统计。"

    return pred_records, report


def save_outputs(output_path: Path, input_jsonl: str, pred_records: List[Dict], report: Dict) -> Tuple[Path, Path]:
    # 输出两份文件：逐条预测明细 + 汇总报告
    output_path.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    pred_path = output_path / f"chunk_benchmark_predictions_{ts}.jsonl"
    report_path = output_path / f"chunk_benchmark_report_{ts}.json"

    with pred_path.open("w", encoding="utf-8") as f:
        for row in pred_records:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    report_with_input = {"input_file": input_jsonl, **report}
    report_path.write_text(json.dumps(report_with_input, ensure_ascii=False, indent=2), encoding="utf-8")
    return pred_path, report_path


def main():
    args = parse_args()
    if not args.api_key:
        raise ValueError("OPENAI_API_KEY 为空，请设置环境变量或通过 --api-key 传入。")

    llm_model = init_evaluator(build_llm_config(args))
    # 分类映射与模型 prompt 同步，新增错误类型时无需改 benchmark 脚本
    error_map = build_error_type_to_category_from_prompt(getattr(llm_model, "prompt", "") or "")
    rows = read_jsonl(Path(args.input_jsonl))
    pred_records, report = evaluate_dataset(rows, llm_model, args.content_field, args.label_field, error_map)
    pred_path, report_path = save_outputs(Path(args.output_path), args.input_jsonl, pred_records, report)

    print(f"[Done] predictions_file={pred_path}")
    print(f"[Done] report_file={report_path}")
    print(json.dumps({"input_file": args.input_jsonl, **report}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
