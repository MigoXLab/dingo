# Data Quality Metrics

This document provides comprehensive information about all quality metrics used in Dingo.

**Note**: All metrics are backed by academic sources to ensure objectivity and scientific rigor.

### Text Quality Assessment Metrics

| Type | Metric | Description | Paper Source | Evaluation Results |
|------|--------|-------------|--------------|-------------------|
| `DATAMAN_ASSESSMENT` | DATAMAN | Evaluates pre-training data quality using the DataMan methodology (14 standar... | [DataMan: Data Manager for Pre-training Large Language Models](https://arxiv.org/abs/2502.19363) (Peng et al., 2025) | N/A |
| `QUALITY_BAD_SECURITY` | Politics | Evaluates whether the text contains politics-related content | Internal Implementation | N/A |
| `TEXT_QUALITY_V4` | Pretrain Text Quality Assessment V4 | Enhanced text quality evaluation covering completeness (formulas, tables, cod... | [WanJuanSiLu: A High-Quality Open-Source Webtext Dataset for Low-Resource Languages](https://arxiv.org/abs/2501.14506) (Yu et al., 2025) | [📊 See Results](eval/prompt/redpajama_data_evaluated_by_prompt.md) |

### SFT Data Assessment Metrics

| Type | Metric | Description | Paper Source | Evaluation Results |
|------|--------|-------------|--------------|-------------------|
| `QUALITY_HARMLESS` | Harmlessness | Checks if responses avoid harmful content, discriminatory language, and dange... | [Training a Helpful and Harmless Assistant with Reinforcement Learning from Human Feedback](https://arxiv.org/pdf/2204.05862) (Bai et al., 2022) | [📊 See Results](eval/prompt/qa_data_evaluated_by_3h.md) |
| `QUALITY_HELPFUL` | Helpfulness | Assesses if responses address questions directly and follow instructions appr... | [Training a Helpful and Harmless Assistant with Reinforcement Learning from Human Feedback](https://arxiv.org/pdf/2204.05862) (Bai et al., 2022) | [📊 See Results](eval/prompt/qa_data_evaluated_by_3h.md) |
| `QUALITY_HONEST` | Honesty | Evaluates if responses provide accurate information without fabrication or de... | [Training a Helpful and Harmless Assistant with Reinforcement Learning from Human Feedback](https://arxiv.org/pdf/2204.05862) (Bai et al., 2022) | [📊 See Results](eval/prompt/qa_data_evaluated_by_3h.md) |

### Classification Metrics

| Type | Metric | Description | Paper Source | Evaluation Results |
|------|--------|-------------|--------------|-------------------|
| `CLASSIFY_TOPIC` | Topic Categorization | Classifies text into categories like language processing, writing, code, math... | [BERTopic](https://maartengr.github.io/BERTopic/index.html#quick-start) & [INSTAG](https://arxiv.org/pdf/2308.07074) (Grootendorst, 2022; Wei et al., 2023) | [📊 See Results](eval/prompt/text_data_classified_by_topic.md) |

### Multimodality Assessment Metrics

| Type | Metric | Description | Paper Source | Evaluation Results |
|------|--------|-------------|--------------|-------------------|
| `CLASSIFY_QR` | Image Classification | Identifies images as CAPTCHA, QR code, or normal images | Internal Implementation | N/A |
| `IMAGE_RELEVANT` | Image Relevance | Evaluates if an image matches reference image in terms of face count, feature... | Internal Implementation | N/A |

### Rule-Based TEXT Quality Metrics

| Type | Metric | Description | Paper Source | Evaluation Results |
|------|--------|-------------|--------------|-------------------|
| `QUALITY_BAD_COMPLETENESS` | RuleLineEndWithEllipsis, RuleLineEndWithTerminal, RuleSentenceNumber, RuleWordNumber | Checks whether the ratio of lines ending with ellipsis is below threshold; Ch... | [RedPajama: an Open Dataset for Training Large Language Models](https://github.com/togethercomputer/RedPajama-Data) (Together Computer, 2023) | [📊 See Results](eval/rule/slimpajama_data_evaluated_by_rule.md) |
| `QUALITY_BAD_EFFECTIVENESS` | RuleAbnormalChar, RuleAbnormalHtml, RuleAlphaWords, RuleCharNumber, RuleColonEnd, RuleContentNull, RuleContentShort, RuleContentShortMultiLan, RuleEnterAndSpace, RuleEnterMore, RuleEnterRatioMore, RuleHtmlEntity, RuleHtmlTag, RuleInvisibleChar, RuleLineJavascriptCount, RuleLoremIpsum, RuleMeanWordLength, RuleSpaceMore, RuleSpecialCharacter, RuleStopWord, RuleSymbolWordRatio, RuleOnlyUrl | Detects garbled text and anti-crawling characters by combining special charac... | [RedPajama: an Open Dataset for Training Large Language Models](https://github.com/togethercomputer/RedPajama-Data) (Together Computer, 2023) | [📊 See Results](eval/rule/slimpajama_data_evaluated_by_rule.md) |
| `QUALITY_BAD_FLUENCY` | RuleAbnormalNumber, RuleCharSplit, RuleNoPunc, RuleWordSplit, RuleWordStuck | Checks PDF content for abnormal book page or index numbers that disrupt text ... | [RedPajama: an Open Dataset for Training Large Language Models](https://github.com/togethercomputer/RedPajama-Data) (Together Computer, 2023) | [📊 See Results](eval/rule/slimpajama_data_evaluated_by_rule.md) |
| `QUALITY_BAD_RELEVANCE` | RuleHeadWordAr | Checks whether Arabic content contains irrelevant tail source information | [RedPajama: an Open Dataset for Training Large Language Models](https://github.com/togethercomputer/RedPajama-Data) (Together Computer, 2023) | [📊 See Results](eval/rule/slimpajama_data_evaluated_by_rule.md) |
| `QUALITY_BAD_SIMILARITY` | RuleDocRepeat | Evaluates text for consecutive repeated content and multiple occurrences of s... | [RedPajama: an Open Dataset for Training Large Language Models](https://github.com/togethercomputer/RedPajama-Data) (Together Computer, 2023) | [📊 See Results](eval/rule/slimpajama_data_evaluated_by_rule.md) |
| `QUALITY_BAD_UNDERSTANDABILITY` | RuleCapitalWords, RuleCurlyBracket, RuleLineStartWithBulletpoint, RuleUniqueWords | Checks whether the ratio of capital words is above threshold, indicating poor... | [RedPajama: an Open Dataset for Training Large Language Models](https://github.com/togethercomputer/RedPajama-Data) (Together Computer, 2023) | [📊 See Results](eval/rule/slimpajama_data_evaluated_by_rule.md) |

### Rule-Based IMG Quality Metrics

| Type | Metric | Description | Paper Source | Evaluation Results |
|------|--------|-------------|--------------|-------------------|
| `QUALITY_BAD_IMG_EFFECTIVENESS` | RuleImageValid, RuleImageSizeValid, RuleImageQuality | Checks whether image is not all white or black, ensuring visual content valid... | Internal Implementation | N/A |
| `QUALITY_BAD_IMG_RELEVANCE` | RuleImageTextSimilarity | Evaluates semantic similarity between image and text content using CLIP model | [Learning Transferable Visual Representations with Natural Language Supervision](https://arxiv.org/abs/2103.00020) (Radford et al., 2021) | N/A |
| `QUALITY_BAD_IMG_SIMILARITY` | RuleImageRepeat | Detects duplicate images using PHash and CNN methods to ensure data diversity | [ImageNet Classification with Deep Convolutional Neural Networks](https://papers.nips.cc/paper/4824-imagenet-classification-with-deep-convolutional-neural-networks.pdf) (Krizhevsky et al., 2012) | N/A |

