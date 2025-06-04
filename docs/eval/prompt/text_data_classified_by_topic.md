# Topic Classification

## 任务介绍

### 定义

本功能旨在对输入数据进行主题分类，支持六大主题类别：

| 主题类别         | 英文名称                               |
| ---------------- | -------------------------------------- |
| 语言理解与处理   | Language Understanding and Processing  |
| 写作能力         | Writing Ability                        |
| 代码             | Code                                   |
| 数学与推理       | Mathematics & Reasoning                |
| 任务导向角色扮演 | Task-oriented Role Play                |
| 知识问答         | Knowledge-based Question and Answering |

### 输入与输出

- **输入**：待评测的数据集
- **输出**：
  - 各主题分类的占比统计
  - 每条数据的分类结果

## PromptClassifyTopic设计

<pre>
Assume you are a topic classifier, and your task is to categorize user-provided instructions. There are six options in the list provided. You are required to select one category from the following list: ["Language Understanding and Processing", "Writing Ability", "Code", "Mathematics & Reasoning", "Task-oriented Role Play", "Knowledge-based Question and Answering"].Make sure your answer is within the list provided and do not create any additional answers.

Here are some explanations of the categories you can choose from in the list:
1. Language Understanding and Processing: Tasks that require linguistic understanding or processing of questions, such as word comprehension, proverbs and poetry, Chinese culture, grammatical and syntactic analysis, translation, information extraction, text classification, semantic understanding, grammar checking, sentence restructuring, text summarization, opinion expression, sentiment analysis, and providing suggestions and recommendations.
2. Writing Ability: Some questions that require text writing, such as practical writing (adjusting format, checking grammar, etc.), cultural understanding, creative writing, and professional writing(giving a professional plan, evaluation, report, case, etc.).
3. Code: Tasks focused on code generation or solving programming problems (e.g., code generation, code review, code debugging).
4. Mathematics & Reasoning: Mathematical questions require numerical computations, proving mathematical formulas, solving mathematical problems in application contexts. Reasoning questions often require you to assess the validity of logic, determine which statement is true based on the given assertions and derive conclusions, arrange information according to specific rules, or analyze the logical relationships between sentences.
5. Task-oriented Role Play: Such questions provide a simulated dialogue scenario and explicitly assign you a role to perform specific tasks (e.g., delivering a speech or evaluation, engaging in situational dialogue, providing an explanation).
6. Knowledge-based Question and Answering: Some purely question-and-answer tasks that require specialized subject knowledge or common knowledge, usually involving brief factual answers (e.g., physics, music theory, sports knowledge inquiries, foundational computer science concepts, history, geography, biomedical sciences, factual recall or common sense knowledge).

Guidelines:
1. Any question that begins with phrases such as "Assume you are a xxx," or "You are playing the role of a xxx," must be classified as 'Task-oriented Role Play', regardless of the category to which the latter part of the sentence belongs.

Task requirements:
1. According to the explanations of the categories, select one category from the following list: ["Language Understanding and Processing", "Writing Ability", "Code", "Mathematics & Reasoning", "Task-oriented Role Play", "Knowledge-based Question and Answering"].
2. Return answer in JSON format: {"name":"xxx"}. Please remember to output only the JSON FORMAT, without any additional content.

Below is an instruction:

</pre>

## PromptClassifyTopic验证

### 数据准备

我们使用了AlignBench( https://github.com/THUDM/AlignBench )中的 683 条数据对 PromptClassifyTopic 进行了多轮迭代和测试，最终确定了更具正交性的六大主题类别与描述。

### 主题说明

| 主题类别           | 子类别                                                                                                                                         |
| ------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| **语言理解与处理** | （中文）字词理解，成语&诗歌，语法和句法分析，改写&翻译，NLP任务（如信息抽取, 文本分类等），观点&建议，语法检查，句式修改，文本摘要，情感分析等 |
| **文本写作**       | 实用文体写作，创意文体写作，专业文体写作，其他写作类                                                                                           |
| **代码**           | 代码生成，代码检查，代码调试等                                                                                                                 |
| **数学与推理**     | 初等数学，高等数学，应用数学，公式&原理，数学证明，逻辑推理，逻辑关系推导等                                                                    |
| **角色扮演**       | 游戏娱乐类，（虚拟）恋爱类，功能类，现实名人类，现实生活类                                                                                     |
| **知识问答**       | 专业知识，常识                                                                                                                                 |

### 实验结果

| Model       | Precision | Recall | F1   |
| ----------- | --------- | ------ | ---- |
| Qwen2.5-7B  | 0.77      | 0.75   | 0.75 |
| Qwen2.5-72B | 0.90      | 0.89   | 0.89 |
| GPT-4o      | 0.94      | 0.94   | 0.94 |

## 使用示例

[示例文档](../examples/classify/sdk_topic_classifcation.py)
