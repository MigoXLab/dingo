# Multi_Lan Dataset

## Dataset Introduction

Multi_Lan Dataset aims to evaluate the ability of Dingo's built-in prompt to mine low-quality data in multi-language pre-training datasets. We extracted a portion of data from the Common Crawl (CC) dataset, which was then annotated by experts in these languages based on seven quality dimensions（[quality_metrics](../../metrics.md)）. If any dimension has problems, the data will be marked as low-quality data.

| Field Name   | Description                                                                                                          |
| ------------ | -------------------------------------------------------------------------------------------------------------------- |
| data_id      | A unique identifier for each data entry, without special significance; users can modify it according to their needs. |
| content      | The text content awaiting quality inspection.                                                                        |
| language     | The language of the content.                                                                                         |
| error_status | Data status: True indicates low-quality data, False indicates high-quality data.                                     |
| type_list    | Types of problems found in low-quality data; this field is an empty list for normal data.                            |
| name_list    | Names of issues found in low-quality data; this field is an empty list for normal data.                              |
| reason_list  | Descriptions of problems found in low-quality data; this field is an empty list for normal data.                     |

### Dataset Link

The dataset is available for different languages through the following links:

| Language   | Dataset Link                                 |
| ---------- | -------------------------------------------- |
| Russian    | https://huggingface.co/datasets/chupei/cc_ru |
| Thai       | https://huggingface.co/datasets/chupei/cc_th |
| Vietnamese | https://huggingface.co/datasets/chupei/cc_vi |
| Hungarian  | https://huggingface.co/datasets/chupei/cc_hu |
| Serbian    | https://huggingface.co/datasets/chupei/cc_sr |

### Dataset Composition

The dataset includes five languages: Russian, Thai, Vietnamese, Hungarian, and Serbian. Below is a summary of each language's data:

| Language   | Number of dataset | Number of High-Quality Data | Number of Low-Quality Data |
| ---------- | ----------------- | --------------------------- | -------------------------- |
| Russian    | 154               | 71                          | 83                         |
| Thai       | 267               | 128                         | 139                        |
| Vietnamese | 214               | 101                         | 113                        |
| Hungarian  | 225               | 99                          | 126                        |
| Serbian    | 144               | 38                          | 76                         |

## Prompt Validation Metrics

### Indicator Description

For prompt validation, we focus on the precision of identifying low-quality data. The metrics are defined as follows:

| Indicator                     | Description                                                                                                       |
| ----------------------------- | ----------------------------------------------------------------------------------------------------------------- |
| TP(True Positive)             | The number of high-quality data points correctly identified as high-quality.                                      |
| FP(False Positive)            | The number of low-quality data points incorrectly identified as high-quality.                                     |
| TN(True Negative)             | The number of low-quality data points correctly identified as low-quality.                                        |
| FN(False Negative)            | The number of high-quality data points incorrectly identified as low-quality.                                     |
| Precision of Low-Quality Data | TN / (TN + FN) , the ratio of low-quality data correctly identified as such among all data marked as low-quality. |

## prompt_text_quality_multilan 设计

When evaluating different languages, the Role should be set to correspond with the language being evaluated. For instance, when evaluating Serbian, the prompt would be as follows:

<pre>
### Role
You are an expert in Serbian language model.
###  Background
The dataset has been compiled from a variety of sources, including social media platforms, news outlets, academic journals, and online forums.
### Goals
Your primary objective is to assess the suitability of this dataset for training a large language model.
### Criteria
ineffectiveness: Verify the effectiveness of the data. Data is considered ineffective if it is primarily composed of carriage returns or spaces. Additionally, data that includes a substantial amount of garbled text, either in Chinese or English, or contains nonsensical content, is also deemed ineffective. A text is labeled invalid if it is empty, consists only of a URL, contains only line breaks, or lacks sufficient length to provide meaningful information.
irrelevance: Determine whether the data contains irrelevant information. Irrelevant information includes citation details, header and footer content, entity markers, non-visible characters, HTML tags, and special symbols. If the text contains a large amount of aggregated data, then this data must be relevant to the topic and separated using high-quality separators, otherwise this aggregated data is irrelevant content.
incompleteness: Check the completeness of the text. Incomplete text may abruptly end with a colon or an ellipsis, or have mismatched parentheses, leading to incomplete meaning.
disunderstandability: Assess the comprehensibility of the text. Ensure that LaTeX formulas and Markdown data are correctly formatted. In addition, the text should ensure correct segmentation and line breaks, and there should be no situations where sentences are unreasonably separated. If there is a list number in the text, the list number must be formatted consistently, correctly, and continuously readable. The text should not contain any tag links that cannot be parsed, nor should it contain a large number of spaces and line breaks that affect reading.
dissimilarity: Examine the text for the presence of duplicate information, including consecutive repeated text and multiple occurrences of special symbols and characters.
disfluency: Examine the text for fluency. The text should not have excessively long English words, large fragments lacking punctuation marks, anti crawling text, or content that is chaotic and does not conform to coherent reading order.
insecurity: Ensure the data does not contain insecure content. Texts should be free from sensitive personal information, and should not include content related to gambling, pornography, political issues, or prohibited information.
### Workflow
1. Thoroughly read and comprehend the text provided by the user.
2. Assign a score to the text. If the text does not meet any negative criteria mentioned above, the score is 1; otherwise, the score is 0.
3. Assign a type to the text. If score is 1, type is none. If score is 0, type is one of the list: ["ineffectiveness", "incompleteness", "disunderstandability", "dissimilarity", "disfluency", "irrelevance", "insecurity"].
4. State the reason for your evaluation.
5. Return the results in JSON format: {"score": x, "type":"xxx", "reason": "xxx"}.
### Warning
Please remember to output only a JSON format data, without any additional content.

</pre>

### Experiment Results

Below are the experimental results showcasing the performance of the prompt across different languages:

| Language   | number | TP  | FP  | TN  | FN  | Precision of Low-Quality Data (%) |
| ---------- | ------ | --- | --- | --- | --- | --------------------------------- |
| Russian    | 154    | 79  | 16  | 55  | 4   | 93.22                             |
| Thai       | 267    | 130 | 30  | 98  | 9   | 91.59                             |
| Vietnamese | 214    | 107 | 32  | 69  | 6   | 92.0                              |
| Hungarian  | 225    | 124 | 30  | 69  | 2   | 97.18                             |
| Serbian    | 114    | 75  | 6   | 32  | 1   | 96.97                             |

## Evaluation

```python
from dingo.io import InputArgs
from dingo.exec import Executor


input_data = {
    "eval_group": "detect_text_quality_th",
    "input_path": "/your/dataset/path",
    "data_format": "jsonl",
    "column_content": "content",
    "save_data": True,
    "save_correct": True,
    "save_raw": True,
    "max_workers": 10,
    "batch_size": 10,
    "custom_config": {
            "prompt_list": ["PromptTextQualityTh"],
            "llm_config":
                {
                    "detect_text_quality_detail":
                        {
                            "key": "EMPTY",
                            "api_url": "your_model_api",
                        }
                }
        }
}
input_args = InputArgs(**input_data)
executor = Executor.exec_map["local"](input_args)
result = executor.execute()
print(result)

```
