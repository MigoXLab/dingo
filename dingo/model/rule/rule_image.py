import os
from typing import List

import numpy as np
from dingo.config.config import DynamicRuleConfig
from dingo.io import Data
from dingo.model.model import Model
from dingo.model.modelres import ModelRes
from dingo.model.rule.base import BaseRule
from PIL import Image


@Model.rule_register('QUALITY_BAD_EFFECTIVENESS', ['img'])
class RuleImageValid(BaseRule):
    """Check whether image is not all white or black."""

    dynamic_config = DynamicRuleConfig()

    @classmethod
    def eval(cls, input_data: Data) -> ModelRes:
        res = ModelRes()
        if isinstance(input_data.image[0], str):
            img = Image.open(input_data.image[0])
        else:
            img = input_data.image[0]
        img_new = img.convert('RGB')
        img_np = np.asarray(img_new)
        if np.all(img_np == (255, 255, 255)) or np.all(img_np == (0, 0, 0)):
            res.error_status = True
            res.type = cls.metric_type
            res.name = cls.__name__
            res.reason = ['Image is not valid: all white or black']
        return res


@Model.rule_register('QUALITY_BAD_EFFECTIVENESS', ['img'])
class RuleImageSizeValid(BaseRule):
    """Check whether image ratio of width to height is valid."""

    dynamic_config = DynamicRuleConfig()

    @classmethod
    def eval(cls, input_data: Data) -> ModelRes:
        res = ModelRes()
        if isinstance(input_data.image[0], str):
            img = Image.open(input_data.image[0])
        else:
            img = input_data.image[0]
        width, height = img.size
        aspect_ratio = width / height
        if aspect_ratio > 4 or aspect_ratio < 0.25:
            res.error_status = True
            res.type = cls.metric_type
            res.name = cls.__name__
            res.reason = ['Image size is not valid, the ratio of width to height: ' + str(aspect_ratio)]
        return res


@Model.rule_register('QUALITY_BAD_EFFECTIVENESS', ['img'])
class RuleImageQuality(BaseRule):
    """Check whether image quality is good."""

    dynamic_config = DynamicRuleConfig(threshold=5.5)

    @classmethod
    def eval(cls, input_data: Data) -> ModelRes:
        import pyiqa
        import torch

        res = ModelRes()
        if isinstance(input_data.image[0], str):
            img = Image.open(input_data.image[0])
        else:
            img = input_data.image[0]
        device = torch.device('cuda') if torch.cuda.is_available() else torch.device('cpu')
        iqa_metric = pyiqa.create_metric('nima', device=device)
        score_fr = iqa_metric(img)
        score = score_fr.item()
        if score < cls.dynamic_config.threshold:
            res.error_status = True
            res.type = cls.metric_type
            res.name = cls.__name__
            res.reason = ['Image quality is not satisfied, ratio: ' + str(score)]
        return res


@Model.rule_register('QUALITY_BAD_EFFECTIVENESS', [])
class RuleImageRepeat(BaseRule):
    """Check for duplicate images using PHash and CNN methods."""

    dynamic_config = DynamicRuleConfig()

    @classmethod
    def eval(cls, input_data: Data) -> ModelRes:
        from imagededup.methods import CNN, PHash

        res = ModelRes()
        image_dir = input_data.content
        if len(os.listdir(image_dir)) == 0:
            raise ZeroDivisionError('The directory is empty, cannot calculate the ratio.')
        phasher = PHash()
        cnn_encoder = CNN()
        phash_encodings = phasher.encode_images(image_dir=image_dir)
        duplicates_phash = phasher.find_duplicates(encoding_map=phash_encodings)
        duplicate_images_phash = set()
        for key, values in duplicates_phash.items():
            if values:
                duplicate_images_phash.add(key)
                duplicate_images_phash.update(values)
        duplicates_cnn = cnn_encoder.find_duplicates(image_dir=image_dir, min_similarity_threshold=0.97)
        common_duplicates = duplicate_images_phash.intersection(set(duplicates_cnn.keys()))
        if common_duplicates:
            res.error_status = True
            res.type = cls.metric_type
            res.name = cls.__name__
            res.reason = [f"{image} -> {duplicates_cnn[image]}" for image in common_duplicates]
            res.reason.append({'duplicate_ratio': len(common_duplicates) / len(os.listdir(image_dir))})
        return res


@Model.rule_register('QUALITY_BAD_EFFECTIVENESS', [])
class RuleImageTextSimilarity(BaseRule):

    dynamic_config = DynamicRuleConfig(threshold=0.17)

    @classmethod
    def eval(cls, input_data: Data) -> ModelRes:
        import nltk

        nltk.download('punkt_tab')
        from dingo.model.rule.utils.image_util import download_similar_tool
        from nltk.tokenize import word_tokenize
        from similarities import ClipSimilarity

        res = ModelRes()
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
            res.error_status = True
            res.type = cls.metric_type
            res.name = cls.__name__
            res.reason = ['Image quality is not satisfied, ratio: ' + str(average_score)]
        return res


if __name__ == '__main__':
    data = Data(data_id='', prompt='', content='')
    tmp = RuleImageRepeat().eval(data)
    print(tmp)
