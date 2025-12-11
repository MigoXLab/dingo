import copy
import json
import logging
import os
import random
import time
from pathlib import Path

import numpy as np
import requests
from PIL import Image, ImageDraw, ImageFont

from dingo.config.input_args import EvaluatorRuleArgs
from dingo.io import Data
from dingo.io.output.eval_detail import EvalDetail, QualityLabel
from dingo.model.model import Model
from dingo.model.rule.base import BaseRule


@Model.rule_register("QUALITY_BAD_IMG_EFFECTIVENESS", ["img"])
class RuleImageValid(BaseRule):
    """check whether image is not all white or black"""

    # Metadata for documentation generation
    _metric_info = {
        "category": "Rule-Based IMG Quality Metrics",
        "quality_dimension": "IMG_EFFECTIVENESS",
        "metric_name": "RuleImageValid",
        "description": "Checks whether image is not all white or black, ensuring visual content validity",
        "paper_title": "",
        "paper_url": "",
        "paper_authors": "",
        "evaluation_results": ""
    }

    dynamic_config = EvaluatorRuleArgs()

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        res = EvalDetail(metric=cls.__name__)
        if isinstance(input_data.image[0], str):
            img = Image.open(input_data.image[0])
        else:
            img = input_data.image[0]
        img_new = img.convert("RGB")
        img_np = np.asarray(img_new)
        if np.all(img_np == (255, 255, 255)) or np.all(img_np == (0, 0, 0)):
            res.status = True
            res.label = [f"{cls.metric_type}.{cls.__name__}"]
            res.reason = ["Image is not valid: all white or black"]
        else:
            res.label = [QualityLabel.QUALITY_GOOD]
        return res


@Model.rule_register("QUALITY_BAD_IMG_EFFECTIVENESS", ["img"])
class RuleImageSizeValid(BaseRule):
    """check whether image ratio of width to height is valid"""

    # Metadata for documentation generation
    _metric_info = {
        "category": "Rule-Based IMG Quality Metrics",
        "quality_dimension": "IMG_EFFECTIVENESS",
        "metric_name": "RuleImageSizeValid",
        "description": "Checks whether image ratio of width to height is within valid range",
        "paper_title": "",
        "paper_url": "",
        "paper_authors": "",
        "evaluation_results": ""
    }

    dynamic_config = EvaluatorRuleArgs()

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        res = EvalDetail(metric=cls.__name__)
        if isinstance(input_data.image[0], str):
            img = Image.open(input_data.image[0])
        else:
            img = input_data.image[0]
        width, height = img.size
        aspect_ratio = width / height
        if aspect_ratio > 4 or aspect_ratio < 0.25:
            res.status = True
            res.label = [f"{cls.metric_type}.{cls.__name__}"]
            res.reason = [
                "Image size is not valid, the ratio of width to height: "
                + str(aspect_ratio)
            ]
        else:
            res.label = [QualityLabel.QUALITY_GOOD]
        return res


@Model.rule_register("QUALITY_BAD_IMG_EFFECTIVENESS", ["img"])
class RuleImageQuality(BaseRule):
    """check whether image quality is good."""

    # Metadata for documentation generation
    _metric_info = {
        "category": "Rule-Based IMG Quality Metrics",
        "quality_dimension": "IMG_EFFECTIVENESS",
        "metric_name": "RuleImageQuality",
        "description": "Evaluates image quality using NIMA (Neural Image Assessment) metrics",
        "paper_title": "NIMA: Neural Image Assessment",
        "paper_url": "https://arxiv.org/abs/1709.05424",
        "paper_authors": "Talebi & Milanfar, 2018",
        "evaluation_results": ""
    }

    dynamic_config = EvaluatorRuleArgs(threshold=5.5)

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        import pyiqa
        import torch

        res = EvalDetail(metric=cls.__name__)
        if isinstance(input_data.image[0], str):
            img = Image.open(input_data.image[0])
        else:
            img = input_data.image[0]
        device = (
            torch.device("cuda") if torch.cuda.is_available() else torch.device("cpu")
        )
        iqa_metric = pyiqa.create_metric("nima", device=device)
        score_fr = iqa_metric(img)
        score = score_fr.item()
        if score < cls.dynamic_config.threshold:
            res.status = True
            res.label = [f"{cls.metric_type}.{cls.__name__}"]
            res.reason = ["Image quality is not satisfied, ratio: " + str(score)]
        else:
            res.label = [QualityLabel.QUALITY_GOOD]
        return res


@Model.rule_register("QUALITY_BAD_IMG_SIMILARITY", [])
class RuleImageRepeat(BaseRule):
    """Check for duplicate images using PHash and CNN methods."""

    # Metadata for documentation generation
    _metric_info = {
        "category": "Rule-Based IMG Quality Metrics",
        "quality_dimension": "IMG_SIMILARITY",
        "metric_name": "RuleImageRepeat",
        "description": "Detects duplicate images using PHash and CNN methods to ensure data diversity",
        "paper_title": "ImageNet Classification with Deep Convolutional Neural Networks",
        "paper_url": "https://papers.nips.cc/paper/4824-imagenet-classification-with-deep-convolutional-neural-networks"
                     ".pdf",
        "paper_authors": "Krizhevsky et al., 2012",
        "evaluation_results": ""
    }

    dynamic_config = EvaluatorRuleArgs()

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        from imagededup.methods import CNN, PHash

        res = EvalDetail(metric=cls.__name__)
        image_dir = input_data.content
        if len(os.listdir(image_dir)) == 0:
            raise ZeroDivisionError(
                "The directory is empty, cannot calculate the ratio."
            )
        phasher = PHash()
        cnn_encoder = CNN()
        phash_encodings = phasher.encode_images(image_dir=image_dir)
        duplicates_phash = phasher.find_duplicates(encoding_map=phash_encodings)
        duplicate_images_phash = set()
        for key, values in duplicates_phash.items():
            if values:
                duplicate_images_phash.add(key)
                duplicate_images_phash.update(values)
        duplicates_cnn = cnn_encoder.find_duplicates(
            image_dir=image_dir, min_similarity_threshold=0.97
        )
        common_duplicates = duplicate_images_phash.intersection(
            set(duplicates_cnn.keys())
        )
        if common_duplicates:
            res.status = True
            tmp_reason = [f"{image} -> {duplicates_cnn[image]}" for image in common_duplicates]
            tmp_reason.append({"duplicate_ratio": len(common_duplicates) / len(os.listdir(image_dir))})

            res.label = [f"{cls.metric_type}.{cls.__name__}"]
            res.reason = tmp_reason
        else:
            res.label = [QualityLabel.QUALITY_GOOD]
        return res


@Model.rule_register("QUALITY_BAD_IMG_RELEVANCE", [])
class RuleImageTextSimilarity(BaseRule):
    """Check similarity between image and text content"""

    # Metadata for documentation generation
    _metric_info = {
        "category": "Rule-Based IMG Quality Metrics",
        "quality_dimension": "IMG_RELEVANCE",
        "metric_name": "RuleImageTextSimilarity",
        "description": "Evaluates semantic similarity between image and text content using CLIP model",
        "paper_title": "Learning Transferable Visual Representations with Natural Language Supervision",
        "paper_url": "https://arxiv.org/abs/2103.00020",
        "paper_authors": "Radford et al., 2021",
        "evaluation_results": ""
    }

    dynamic_config = EvaluatorRuleArgs(threshold=0.17)

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        import nltk

        nltk.download("punkt_tab")
        from nltk.tokenize import word_tokenize
        from similarities import ClipSimilarity

        from dingo.model.rule.utils.image_util import download_similar_tool

        res = EvalDetail(metric=cls.__name__)
        if not input_data.image or not input_data.content:
            return res
        if isinstance(input_data.image[0], str):
            img = Image.open(input_data.image[0])
        else:
            img = input_data.image[0]
        tokenized_texts = word_tokenize(input_data.content)
        if cls.dynamic_config.refer_path is None:
            similar_tool_path = download_similar_tool()
        else:
            similar_tool_path = cls.dynamic_config.refer_path[0]
        m = ClipSimilarity(model_name_or_path=similar_tool_path)
        scores = []
        for text in tokenized_texts:
            sim_score = m.similarity([img], [text])
            scores.append(sim_score[0][0])
        average_score = sum(scores) / len(scores)
        if average_score < cls.dynamic_config.threshold:
            res.status = True
            res.label = [f"{cls.metric_type}.{cls.__name__}"]
            res.reason = ["Image quality is not satisfied, ratio: " + str(average_score)]
        else:
            res.label = [QualityLabel.QUALITY_GOOD]
        return res


@Model.rule_register("QUALITY_BAD_IMG_ARTIMUSE", [])
class RuleImageArtimuse(BaseRule):
    # Metadata for documentation generation
    _metric_info = {
        "category": "Rule-Based IMG Quality Metrics",
        "quality_dimension": "IMG_ARTIMUSE",
        "metric_name": "RuleImageArtimuse",
        "description": "Evaluates image quality in the field of aesthetics using artimuse",
        "paper_title": "",
        "paper_url": "",
        "paper_authors": "",
        "evaluation_results": ""
    }

    dynamic_config = EvaluatorRuleArgs(threshold=6, refer_path=['https://artimuse.intern-ai.org.cn/'])

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        try:
            response_create_task = requests.post(
                cls.dynamic_config.refer_path[0] + 'api/v1/task/create_task',
                json={
                    "img_url": input_data.content,
                    "style": 1
                },
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "dingo",
                },
                # timeout=30  # 设置超时时间
            )
            response_create_task_json = response_create_task.json()
            # print(response_create_task_json)
            task_id = response_create_task_json.get('data').get('id')

            time.sleep(5)
            request_time = 0
            while (True):
                request_time += 1
                response_get_status = requests.post(
                    cls.dynamic_config.refer_path[0] + 'api/v1/task/status',
                    json={
                        "id": task_id
                    },
                    headers={
                        "Content-Type": "application/json",
                        "User-Agent": "dingo",
                    },
                    # timeout=30  # 设置超时时间
                )
                response_get_status_json = response_get_status.json()
                # print(response_get_status_json)
                status_data = response_get_status_json.get('data')
                if status_data['phase'] == 'Succeeded':
                    break
                time.sleep(5)

            res = EvalDetail(metric=cls.__name__)
            res.status = True if status_data['score_overall'] < cls.dynamic_config.threshold else False
            tmp = "BadImage" if status_data['score_overall'] < cls.dynamic_config.threshold else "GoodImage"
            if res.status:
                res.label = [f"Artimuse_Succeeded.{tmp}"]
                res.reason = [json.dumps(status_data, ensure_ascii=False)]
            else:
                res.label = [QualityLabel.QUALITY_GOOD]
            return res
        except Exception as e:
            res = EvalDetail(metric=cls.__name__)
            res.status = False
            res.label = ["Artimuse_Fail.Exception"]
            res.reason = [str(e)]
            return res


@Model.rule_register("QUALITY_BAD_IMG_LABEL_OVERLAP", [])
class RuleImageLabelOverlap(BaseRule):
    _metric_info = {
        "category": "Rule-Based IMG Quality Metrics",
        "quality_dimension": "IMG_LABEL_OVERLAP",
        "metric_name": "RuleImageLabelOverlap",
        "description": "Detects overlapping bounding boxes in image annotations, marks full/partial overlap and "
                       "generates visualization images",
        "paper_title": "",
        "paper_url": "",
        "paper_authors": "",
        "evaluation_results": ""
    }

    dynamic_config = EvaluatorRuleArgs(
        refer_path=['../../test/data/overlap_visual_image'],  # 用户保存图片路径
    )

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:

        res = EvalDetail(metric=cls.__name__)

        try:
            # 1. 阈值参数
            iou_partial_threshold = 0.1  # iou小于0.1不属于标注框重叠
            iou_full_threshold = 0.9

            # 2. 解析输入数据
            content = input_data.content
            image_path = input_data.image[0] if (input_data.image and len(input_data.image) > 0) else None

            # 3. 解析标注内容
            if isinstance(content, str):
                try:
                    annotations = json.loads(content)
                except json.JSONDecodeError as e:
                    res = EvalDetail(metric=cls.__name__)
                    res.status = False
                    res.label = ["LabelOverlap_Fail.ParseError"]
                    res.reason = [f"content解析失败：{str(e)}，前50字符：{content[:50]}..."]
                    return res
            elif isinstance(content, dict):
                annotations = content
            else:
                res = EvalDetail(metric=cls.__name__)
                res.status = False
                res.label = ["LabelOverlap_Fail.InvalidContentType"]
                res.reason = [f"content类型错误：需dict/str，实际是{type(content).__name__}"]
                return res

            # 4. 验证数据有效性
            if not annotations:
                res = EvalDetail(metric=cls.__name__)
                res.status = False
                res.label = ["LabelOverlap_Fail.EmptyAnnotations"]
                res.reason = ["annotations为空"]
                return res
            if not image_path or not os.path.exists(image_path):
                res = EvalDetail(metric=cls.__name__)
                res.status = False
                res.label = ["LabelOverlap_Fail.InvalidImagePath"]
                res.reason = [f"图片路径无效：{image_path}"]
                return res

            # 5. 提取边界框并计算重叠
            bboxes = [
                obj for obj in annotations.get('step_1', {}).get('result', [])
                if obj.get('valid', True) and all(k in obj for k in ['x', 'y', 'width', 'height'])
            ]

            has_overlap = False  # 是否符合阈值重叠（部分或完全）
            full_overlap_pairs = []
            partial_overlap_pairs = []

            if bboxes:
                n = len(bboxes)
                for i in range(n):
                    for j in range(i + 1, n):
                        # 计算IOU
                        box1 = bboxes[i]
                        box2 = bboxes[j]
                        x1 = max(box1["x"], box2["x"])
                        y1 = max(box1["y"], box2["y"])
                        x2 = min(box1["x"] + box1["width"], box2["x"] + box2["width"])
                        y2 = min(box1["y"] + box1["height"], box2["y"] + box2["height"])
                        intersection = max(0, x2 - x1) * max(0, y2 - y1)
                        area1 = box1["width"] * box1["height"]
                        area2 = box2["width"] * box2["height"]
                        union = area1 + area2 - intersection
                        iou = intersection / union if union != 0 else 0

                        # 判断是否符合阈值重叠
                        if iou >= iou_full_threshold:
                            full_overlap_pairs.append((i, j))
                            has_overlap = True
                        elif iou >= iou_partial_threshold:
                            partial_overlap_pairs.append((i, j))
                            has_overlap = True

                # 标记重叠边界框
                full_overlap_ids = set(idx for pair in full_overlap_pairs for idx in pair)
                partial_overlap_ids = set(idx for pair in partial_overlap_pairs for idx in pair) - full_overlap_ids
                new_annotations = copy.deepcopy(annotations)
                for idx, box in enumerate(new_annotations["step_1"]["result"]):
                    if idx in full_overlap_ids:
                        box["attribute"] = "full_overlap"
                    elif idx in partial_overlap_ids:
                        box["attribute"] = "partial_overlap"
            else:
                new_annotations = annotations

            # 6. 根据重叠状态设置错误信息
            if has_overlap:
                # 符合阈值重叠：标记为错误状态
                res.status = True
                res.label = ["LabelOverlap_Fail.RuleImageLabelOverlap"]
                res.reason = [f"重叠检测：完全重叠={len(full_overlap_pairs)}，部分重叠={len(partial_overlap_pairs)}"]
            else:
                # 不符合阈值重叠：正常状态
                res.status = False

            # 7. 生成可视化标注框重叠图片
            vis_path = None  # 初始化vis_path变量
            try:
                # 获取基础路径并确保是绝对路径
                base_path = cls.dynamic_config.refer_path[0]

                # 调试信息
                logging.info(f"原始base_path: {base_path}")

                # 处理相对路径
                if not os.path.isabs(base_path):
                    # 获取当前文件的目录作为基准路径
                    current_file_dir = os.path.dirname(os.path.abspath(__file__))
                    base_path = os.path.join(current_file_dir, base_path)
                    logging.info(f"转换后base_path: {base_path}")

                # 规范化路径
                base_path = os.path.normpath(base_path)
                output_dir = Path(base_path)

                # 确保目录存在且有写入权限
                output_dir.mkdir(parents=True, exist_ok=True)

                # 测试目录权限
                test_file = output_dir / "test_permission.txt"
                try:
                    test_file.write_text("test")
                    test_file.unlink()  # 删除测试文件
                    logging.info(f"目录权限检查通过: {output_dir}")
                except Exception as perm_error:
                    logging.error(f"目录无写入权限: {output_dir}, 错误: {perm_error}")
                    # 尝试使用临时目录
                    import tempfile
                    output_dir = Path(tempfile.gettempdir()) / "overlap_visual"
                    output_dir.mkdir(parents=True, exist_ok=True)
                    logging.info(f"切换到临时目录: {output_dir}")

                vis_path = str(output_dir / "overlap.png")

                logging.info(f"最终输出目录: {output_dir}")
                logging.info(f"开始保存图像到: {vis_path}")

                # 生成可视化图像
                img = Image.open(image_path).convert("RGB")
                draw = ImageDraw.Draw(img)

                # 绘制边界框
                for idx, box in enumerate(bboxes):
                    x, y, w, h = box["x"], box["y"], box["width"], box["height"]
                    if idx in full_overlap_ids:
                        color = (255, 0, 0)  # 红色 - 完全重叠
                    elif idx in partial_overlap_ids:
                        color = (255, 255, 0)  # 黄色 - 部分重叠
                    else:
                        color = (0, 255, 0)  # 绿色 - 无重叠

                    draw.rectangle([(x, y), (x + w, y + h)], outline=color, width=3)
                    draw.text((x, max(0, y - 15)), f"Box {idx}", fill=color, font=ImageFont.load_default())

                # 保存图像
                img.save(vis_path)
                logging.info(f"图像保存成功: {vis_path}")

            except Exception as e:
                logging.error(f"可视化生成失败：{str(e)}，详细错误信息:", exc_info=True)
                vis_path = None

            # 8. 整理结果（结果已通过eval_status和eval_details返回）

        except Exception as global_e:
            res = EvalDetail(metric=cls.__name__)
            res.status = False
            res.label = ["LabelOverlap_Fail.GlobalError"]
            res.reason = [f"全局处理错误：{str(global_e)}"]

        return res


@Model.rule_register("QUALITY_BAD_IMG_LABEL_VISUALIZATION", [])
class RuleImageLabelVisualization(BaseRule):
    _metric_info = {
        "category": "Rule-Based IMG Quality Metrics",
        "quality_dimension": "IMG_LABEL_VISUALIZATION",
        "metric_name": "RuleImageLabelVisualization",
        "description": "Generates visualization images with bounding boxes and category labels, helping manual check "
                       "of annotation accuracy",
        "paper_title": "",
        "paper_url": "",
        "paper_authors": "",
        "evaluation_results": ""
    }

    dynamic_config = EvaluatorRuleArgs(
        refer_path=['../../test/data/label_visual_image'],  # 用户保存图片路径
    )

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:

        res = EvalDetail(metric=cls.__name__)

        try:
            # --------------------------
            # 1. 内部工具函数与配置
            # --------------------------
            # label字体大小
            font_size = 50
            # 用户自定义类别-颜色映射
            color_map = {
                'table': (255, 165, 0),  # 橙色
                'figure': (0, 255, 0),  # 绿色
                'text_block': (0, 0, 255),  # 蓝色
                'text_span': (7, 104, 159),  # #07689f
                'equation_inline': (89, 13, 130),  # #590d82
                'equation_ignore': (118, 159, 205)  # #769fcd
            }

            font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

            def poly2bbox(poly):
                """将多边形坐标转换为边界框 [左, 上, 右, 下]"""
                L = poly[0]
                U = poly[1]
                R = poly[2]
                D = poly[5]
                return [min(L, R), min(U, D), max(L, R), max(U, D)]

            def get_random_color():
                """生成随机RGB颜色（用于未定义类别）"""
                return (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))

            def count_total_labels(elements):
                """统计包含子元素的总标注数量"""
                count = 0
                for elem in elements:
                    count += 1
                    if elem.get('line_with_spans'):
                        count += count_total_labels(elem['line_with_spans'])
                return count

            def draw_bboxes(draw_obj, elements, color_map, font_obj):
                """绘制边界框和类别标签，递归处理子元素"""
                for element in elements:
                    # 跳过需忽略的标注（abandon/mask/含图片的table）
                    category = element.get('category_type', '')
                    if (category == 'abandon' or
                            'mask' in category or
                            (category == 'table' and element.get('attribute', {}).get('include_photo'))):
                        continue

                    # 处理边界框坐标
                    poly = element.get('poly', [])
                    if len(poly) < 6:
                        continue
                    bbox = poly2bbox(poly)

                    # 确定颜色（未定义类别自动添加随机色）
                    if category not in color_map:
                        color_map[category] = get_random_color()
                    border_color = color_map[category]

                    # 绘制边界框
                    draw_obj.rectangle(bbox, outline=border_color, width=3)

                    # 绘制类别标签（左上角偏移2px避免贴边）
                    text_pos = (bbox[0] + 2, bbox[1] + 2)
                    draw_obj.text(text_pos, category, fill=border_color, font=font_obj)

                    # 递归处理子元素（如line_with_spans）
                    if element.get('line_with_spans'):
                        draw_bboxes(draw_obj, element['line_with_spans'], color_map, font_obj)

            # --------------------------
            # 2. 解析输入数据
            # --------------------------
            # 提取核心数据
            content = input_data.content  # 标注数据（str或dict）
            image_path = input_data.image[0] if (input_data.image and len(input_data.image) > 0) else None

            # 验证图片路径有效性
            if not image_path or not os.path.exists(image_path):
                res = EvalDetail(metric=cls.__name__)
                res.status = False
                res.label = ["LabelVisualization_Fail.InvalidImagePath"]
                res.reason = [f"图片路径无效/不存在：{image_path}"]
                return res

            # 解析标注内容
            if isinstance(content, str):
                try:
                    annotations = json.loads(content)
                except json.JSONDecodeError as e:
                    res = EvalDetail(metric=cls.__name__)
                    res.status = False
                    res.label = ["LabelVisualization_Fail.ParseError"]
                    res.reason = [f"标注解析失败：{str(e)}，前50字符：{content[:50]}..."]
                    return res
            elif isinstance(content, dict):
                annotations = content
            else:
                res = EvalDetail(metric=cls.__name__)
                res.status = False
                res.label = ["LabelVisualization_Fail.InvalidAnnotationType"]
                res.reason = [f"标注类型错误：需dict/str，实际{type(content).__name__}"]
                return res

            # 提取布局标注（适配"layout_dets"字段）
            layout_dets = annotations.get("layout_dets", [])
            if not layout_dets:
                # 无标注数据时的处理
                res = EvalDetail(metric=cls.__name__)
                res.status = False
                res.label = ["LabelVisualization_Fail.EmptyLayoutData"]
                res.reason = [json.dumps({
                    "message": "无布局标注数据（layout_dets为空）",
                    "visualization_path": None,
                    "label_stats": {"total_labels": 0}
                }, ensure_ascii=False)]
                return res

            # --------------------------
            # 3. 初始化可视化依赖
            # --------------------------
            # 加载字体（失败时降级为默认字体）
            try:
                font = ImageFont.truetype(font_path, font_size)
            except Exception as e:
                logging.warning(
                    f"加载指定字体失败（路径：{font_path}，字号：{font_size}），"
                    f"错误原因：{str(e)}，将使用系统默认字体（可能不支持自定义字号）"
                )
                font = ImageFont.load_default()

            # --------------------------
            # 4. 绘制标注并保存可视化图像
            # --------------------------
            # 打开原始图像
            img = Image.open(image_path).convert("RGB")
            draw = ImageDraw.Draw(img)

            # 调用内部函数绘制标注
            draw_bboxes(draw, layout_dets, color_map, font)

            # 准备输出路径
            try:
                output_dir = Path(cls.dynamic_config.refer_path[0]).resolve()
                output_dir.mkdir(parents=True, exist_ok=True)
                # 生成文件名
                img_basename = Path(image_path).name
                vis_filename = f"visual_{img_basename}"
                vis_path = str(output_dir / vis_filename)
            except Exception as path_error:
                logging.warning(f"输出目录处理失败：{str(path_error)}，将使用临时目录")
                # 回退到临时目录
                import tempfile
                output_dir = Path(tempfile.gettempdir()) / "dingo_visualization"
                output_dir.mkdir(parents=True, exist_ok=True)
                img_basename = Path(image_path).name
                vis_filename = f"visual_{img_basename}"
                vis_path = str(output_dir / vis_filename)

            # 保存图像
            try:
                img.save(vis_path)
            except Exception as e:
                res = EvalDetail(metric=cls.__name__)
                res.status = False
                res.label = ["LabelVisualization_Fail.SaveImageError"]
                res.reason = [f"保存图像失败：{str(e)}"]
                return res

            # --------------------------
            # 5. 整理结果（结果已通过eval_status返回）
            # --------------------------

            res.status = False

        except Exception as global_e:
            # 全局异常处理
            res = EvalDetail(metric=cls.__name__)
            res.status = False
            res.label = ["LabelVisualization_Fail.GlobalError"]
            res.reason = [f"可视化处理全局错误：{str(global_e)}"]

        return res


if __name__ == "__main__":
    data = Data(
        data_id='1',
        content="https://openxlab.oss-cn-shanghai.aliyuncs.com/artimuse/upload/ef39eef6-2b40-4ea3-8285-934684734298-"
                "stsupload-1753254621827-dog.jpg"
    )
    res = RuleImageArtimuse.eval(data)
    print(res)
