# Dataset Redpajama

## Dataset Introduction

This dataset aims to evaluate the accuracy of the built-in prompt words in dingo, therefore, the open-source dataset redpajama is selected, and data is extracted from it to build a test set.

| Field Name   | Description                                                                        |
| ------------ | ---------------------------------------------------------------------------------- |
| data_id      | Data ID, without special meaning, users can modify it according to their own needs |
| content      | Data to be tested                                                                  |
| language     | Language type                                                                      |
| error_status | Data status, True for negative examples, False for positive examples               |
| type_list    | Negative types for negative examples, empty list for positive examples             |
| name_list    | Negative names for negative examples, empty list for positive examples             |
| reason_list  | Negative introductions for negative examples, empty list for positive examples     |

Links:<br>
https://huggingface.co/datasets/chupei/redpajama_good_model<br>
https://huggingface.co/datasets/chupei/redpajama_bad_model

### Dataset Composition

| Type                                    | Count |
| --------------------------------------- | ----- |
| Positive Examples                       | 101   |
| Negative Examples: disfluency           | 4     |
| Negative Examples: dissimilarity        | 3     |
| Negative Examples: disunderstandability | 2     |
| Negative Examples: incompleteness       | 27    |
| Negative Examples: insecurity           | 16    |
| Negative Examples: irrelevance          | 49    |

## Prompt Introduction

The built-in **PromptTextQualityV2** is used as the prompt for this test.<br>
Specific content can be referred to: [Introduction to PromptTextQualityV2](../../../dingo/model/prompt/prompt_text_quality.py)<br>
The built-in prompt collection can be referred to: [Prompt Collection](../../../dingo/model/prompt)

## Evaluation Results

### Concept Introduction

Both positive and negative examples will generate corresponding summary files after evaluation, so the results need to be defined and the concepts clarified.

| Name     | Description                                                                 |
| -------- | --------------------------------------------------------------------------- |
| TP       | True Positive: Number of positive examples evaluated as positive            |
| FP       | False Positive: Number of negative examples evaluated as positive           |
| TN       | True Negative: Number of negative examples evaluated as negative            |
| FN       | False Negative: Number of positive examples evaluated as negative           |
| Accuracy | TP / (TP + FP) Ratio of positive examples among those evaluated as positive |
| Recall   | TP / (TP + FN) Ratio of positive examples correctly evaluated as positive   |
| F1       | (Accuracy + Recall) / 2                                                     |

### Result Display

| Dataset Name | TP  | FP  | TN  | FN  | Accuracy% | Recall% | F1  |
| ------------ | --- | --- | --- | --- | --------- | ------- | --- |
| redpajama    | 95  | 0   | 101 | 6   | 100       | 94      | 97  |

## Evaluation Method

```python
from dingo.io import InputArgs
from dingo.exec import Executor

input_data = {
    "eval_group": "v2",
    "input_path": "chupei/redpajama_good_model",
    "save_data": True,
    "save_correct": True,
    "save_raw": True,
    "max_workers": 10,
    "batch_size": 10,
    "data_format": "jsonl",
    "column_content": "content",
    "custom_config":
        {
            "prompt_list": ["PromptTextQualityV2"],
            "llm_config":
                {
                    "detect_text_quality_detail":
                        {
                            "key": "Your Key",
                            "api_url": "Your Url",
                        }
                }
        }
}
input_args = InputArgs(**input_data)
executor = Executor.exec_map["local"](input_args)
result = executor.execute()
print(result)
```
