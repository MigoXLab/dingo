# Data Quality Metrics

This document provides comprehensive information about all quality metrics used in Dingo.

**Note**: All metrics are backed by academic sources to ensure objectivity and scientific rigor.

### 3H Assessment Prompts (Honest, Helpful, Harmless)

| Type | Metric | Description | Paper Source | Evaluation Results |
|------|--------|-------------|--------------|-------------------|
| `QUALITY_HARMLESS` | Harmlessness | Checks if responses avoid harmful content, discriminatory language, and dangerous assistance | [Training a Helpful and Harmless Assistant with Reinforcement Learning from Human Feedback](https://arxiv.org/pdf/2204.05862) (Bai et al., 2022) | [📊 See Results](docs/eval/prompt/qa_data_evaluated_by_3h.md) |
| `QUALITY_HELPFUL` | Helpfulness | Assesses if responses address questions directly and follow instructions appropriately | [Training a Helpful and Harmless Assistant with Reinforcement Learning from Human Feedback](https://arxiv.org/pdf/2204.05862) (Bai et al., 2022) | [📊 See Results](docs/eval/prompt/qa_data_evaluated_by_3h.md) |
| `QUALITY_HONEST` | Honesty | Evaluates if responses provide accurate information without fabrication or deception | [Training a Helpful and Harmless Assistant with Reinforcement Learning from Human Feedback](https://arxiv.org/pdf/2204.05862) (Bai et al., 2022) | [📊 See Results](docs/eval/prompt/qa_data_evaluated_by_3h.md) |

### Text Quality Assessment Prompts

| Type | Metric | Description | Paper Source | Evaluation Results |
|------|--------|-------------|--------------|-------------------|
| `TEXT_QUALITY_V4` | Text Quality Assessment V4 | Enhanced text quality evaluation covering completeness (formulas, tables, code), effectiveness (garbled text, spacing), similarity (duplicates), and security (politics, prohibited content) | [WanJuanSiLu: A High-Quality Open-Source Webtext Dataset for Low-Resource Languages](https://arxiv.org/abs/2501.14506) (Yu et al., 2025) | N/A |

### Domain-Specific Assessment Prompts

| Type | Metric | Description | Paper Source | Evaluation Results |
|------|--------|-------------|--------------|-------------------|
| `DATAMAN_ASSESSMENT` | Data Quality & Domain | Evaluates pre-training data quality using the DataMan methodology (14 standards, 15 domains). Assigns a score (0/1), domain type, quality status, and reason. | [DataMan: Data Manager for Pre-training Large Language Models](https://arxiv.org/abs/2502.19363) (Peng et al., 2025) | N/A |

### Classification Prompts

| Type | Metric | Description | Paper Source | Evaluation Results |
|------|--------|-------------|--------------|-------------------|
| `CLASSIFY_QR` | Image Classification | Identifies images as CAPTCHA, QR code, or normal images | Internal Implementation | N/A |
| `CLASSIFY_TOPIC` | Topic Categorization | Classifies text into categories like language processing, writing, code, mathematics, role-play, or knowledge Q&A. Based on BERTopic and INSTAG methodologies | [BERTopic](https://maartengr.github.io/BERTopic/index.html#quick-start) & [INSTAG](https://arxiv.org/pdf/2308.07074) (Grootendorst, 2022; Wei et al., 2023) | [📊 See Results](docs/eval/prompt/text_data_classified_by_topic.md) |

### Image Assessment Prompts

| Type | Metric | Description | Paper Source | Evaluation Results |
|------|--------|-------------|--------------|-------------------|
| `IMAGE_RELEVANT` | Image Relevance | Evaluates if an image matches reference image in terms of face count, feature details, and visual elements | Internal Implementation | N/A |

### Rule-Based Quality Metrics

| Type | Metric | Description | Paper Source | Evaluation Results |
|------|--------|-------------|--------------|-------------------|
| `QUALITY_BAD_EFFECTIVENESS` | RuleAbnormalChar, RuleColonEnd, RuleSpecialCharacter | Detects garbled text and anti-crawling characters by combining special character and invisible character detection; Checks if text abruptly ends with a colon, indicating incomplete content; Checks if data is meaningful and properly formatted by detecting excessive special characters | [RedPajama: an Open Dataset for Training Large Language Models](https://github.com/togethercomputer/RedPajama-Data) (Together Computer, 2023) | N/A |
| `QUALITY_BAD_SIMILARITY` | RuleDocRepeat | Evaluates text for consecutive repeated content and multiple occurrences of special characters | [RedPajama: an Open Dataset for Training Large Language Models](https://github.com/togethercomputer/RedPajama-Data) (Together Computer, 2023) | N/A |
