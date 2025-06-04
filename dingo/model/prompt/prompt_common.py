from dingo.model.model import Model
from dingo.model.prompt.base import BasePrompt


@Model.prompt_register('QUALITY_BAD_SIMILARITY', [])
class PromptRepeat(BasePrompt):
    content = """
    请判断一下文本是否存在重复问题。
    返回一个json，如{"score": 0, "reason": "xxx"}.
    如果存在重复，score是0，否则是1。reason是判断的依据。
    除了json不要有其他内容。
    以下是需要判断的文本：
    """


@Model.prompt_register('QUALITY_BAD_EFFECTIVENESS', [])
class PromptContentChaos(BasePrompt):
    content = """
    请判断一下文本是否存在乱码与反扒文本。
    返回一个json，如{"score": 0, "reason": "xxx"}.
    如果存在问题，score是0，否则是1。reason是判断的依据。
    除了json不要有其他内容。
    以下是需要判断的文本：
    """


@Model.prompt_register('WORD_STICK', [])
class PromptWordStick(BasePrompt):
    content = """
    ### Role
    You are a data quality assessment expert, you can communicate fluently in English, and think from the perspective of Chinese people.
    ### Background
    We use extraction tools to extract PDF files (from academic papers, books, and financial reports) into markdown format, intercept markdown with a fixed length, and need to evaluate the quality of the intercepted content.
    The most desired evaluation is whether the intercepted content meets the quality standards.
    ### Goals
    Your primary goal is to evaluate whether there are any word stuck issues in the text.Word stuck issues can affect the fluency of the corpus used for running LLMs.
    ### workdflow
    1 Problem Definition：Word Stuck Issue is defined as independent words are missing spaces or punctuation between them, causing them to stick together. For example, "aboutafootwideandtwofeetlong" combines the sentence "about a foot wide and two feet long" without a space, which is considered a Word Stuck Issue.
    2 Calculate the total length of the data in characters and denote it as len(b).
    3 Calculate the length of the stuck words(satisfy Word Stuck Issue definition) and denote it as len(a).
    4 Sum up the lengths of all instances of stuck words to get sum(len(a)).
    5 Calculate the ratio as ratio = sum(len(a)) / len(b).
    6 If the ratio is greater than 0.01, then it is considered low-quality data, and output a score of 0; otherwise, it is considered high-quality data, and output a score of 1.
    ### Warning
    Please remember to output only JSON data, without additional content.
    Score: 0 (data meets low-quality standard) or 1 (data  meets high-quality standard).
    Type: If the score is 0, it is the most serious error type; if it is 1, it is "high quality".
    Reason: Return workflow-based reason. Please print the reason if the type is from the following list: ["Word Stuck Issue"].
    Return your answer in JSON format: {"score": 0, "type": "xxx", "reason": "xxx"}.
    Here are the data you need to evaluate:
    """


@Model.prompt_register('CODE_LIST_ISSUE', [])
class PromptUnreadIssue(BasePrompt):
    content = """
    ### Role
    You are a data quality assessment expert with fluent English communication skills, and you have insight into the considerations of Chinese professionals in your field.
    ### Background
    Our process involves using extraction tools to convert PDF files—originating from academic papers, books, financial reports, etc.—into markdown format. Subsequently, we segment this markdown content into chunks of a fixed length for further processing. It's crucial that we evaluate the quality of these segmented contents to ensure they meet our stringent standards.
    ### Objective
    Your main task is to assess whether this dataset is suitable for training a large language model by evaluating the quality of the intercepted markdown content against predefined criteria.
    ### Quality Criteria
    The following criteria define low-quality content:
    Code Block Misrecognition: Code blocks should not be recognized as formulas, tables, or other formats.
    List Recognition Errors: Lists must maintain continuous and correct numbering; any discontinuity or error in sequence is unacceptable.
    ### Evaluation Output
    Your evaluation output must strictly adhere to the JSON format, containing no extraneous information. The JSON object should include:
    Score: 0 if the content fails to meet quality standards due to any of the above issues; 1 if it meets all standards.
    Type: if the score is 0, indicating the most severe type of error present; "High Quality" if the score is 1.
    Problem: Must be one of the predefined problem types: ["Code block missing problem", "List recognition errors"].
    Reason: A concise explanation for the score given, specifically detailing the nature of the issue when applicable.
    Return your answer in JSON format: {"score": 0, "type": "xxx", "reason": "xxx"}.
    Here are the data you need to evaluate:
    """


@Model.prompt_register('UNREAD_ISSUE', [])
class PromptUnreadIssue(BasePrompt):
    content = """
    ### Role
    You are a data quality assessment expert, you can communicate fluently in English, and think from the perspective of Chinese people.
    ### Background
    We use extraction tools to extract PDF files (from academic papers, books, and financial reports) into markdown format, intercept markdown with a fixed length, and need to evaluate the quality of the intercepted content.
    The most desired evaluation is whether the intercepted content meets the quality standards.
    ### Goal
    Your primary Goal is to assess the suitability of this dataset for training a large language model. Unreadable issues can affect the validity of training data for LLMs.
    ### Unreadable issues
    Unreadable issues: It caused by string encoding and decoding methods are inconsistent. Unreadable characters include tow types:
    - Squares (usually placeholders for undefined characters in Unicode): such as "□", "■", "�", etc.
    - Other special symbols: such as "â", "ã", "ä", "å", etc.
    ### Workflow
    1. Calculate the length of the garbled string, denoted as a.
    2. Calculate the total length of the evaluated string, denoted as b.
    3. If the ratio of a/b is greater than 0.01, then it is considered low-quality data.
    ### Quality Standard
    After workflow, you can judge
    1. low-quality：If the ratio of a/b is greater than 0.01, then it is considered low-quality data.
    2. high-quality:If the ratio of a/b is smaller than 0.01，it is considered high-quality data.
    ### Warning
    Please remember to output only JSON data, without additional content.
    Score: 0 (data meets low-quality) or 1 (data meets high-quality).
    Type: If the score is 0, it is the most serious error type; if it is 1, it is "high quality".
    Problem: The problem must be one of the following lists: please be careful not to output anything other than the list type;
    Reason: A brief description of the score. Please print the reason if the type is from the following list: ["Unreadable issue"].
    Return your answer in JSON format: {"score": 0, "type": "xxx", "reason": "xxx"}.
    Here are the data you need to evaluate:
    """
