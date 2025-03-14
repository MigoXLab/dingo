from dingo.model.model import Model
from dingo.model.prompt.base import BasePrompt

ROLE = """
    ### Role
    You are an expert in language model.
    """

# Content Quality V2
TEXT_QUALITY_WITHOUT_ROLE_V2 = """
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
"""

@Model.prompt_register("TEXT_QUALITY_V2", [])
class PromptTextQualityV2(BasePrompt):
    content = ROLE + TEXT_QUALITY_WITHOUT_ROLE_V2

@Model.prompt_register("TEXT_QUALITY_V3", [])
class PromptTextQualityV3(BasePrompt):
    content = """
# Role
You are an expert in language model.
# Background
The dataset has been compiled from a variety of sources, including social media platforms, news outlets, academic journals, and online forums.
# Goals
Your primary objective is to assess the suitability of this dataset for training a large language model.Please note that if the text meets any of the following negative descriptions, it will be considered low-quality data.
# Criteria
1. Completeness
    1.1 Error_Formula_Table: If the text contains formulas or tables, then their format or content is incorrect.
    1.2 Error_List_Number: If the text contains list number, numbers in the list number have inconsistent formats and logical discontinuity.
    1.3 Error_Section_Order: The order of text is cluttered, such as titles embedded in the main text or structures that are difficult to read.
2. Effectiveness
    2.1 Error_Garbled_Characters: The text contains a large amount of garbled and anti crawler characters.
    2.2 Error_Words_Stuck: The text contains a large number of words that are stuck together without being separated by spaces. Words with hyphens are considered normal and treat newline characters (\n) as spaces.
    2.3 Error_Lack_Punctuation: Text contains a large number of sentences that have no punctuation mark at the end.
3. Similarity
    3.1 Error_Duplicate_Content: The text contains consecutive repeated text and multiple occurrences of characters.
4. Security
    4.1 Error_Political_Content: The text contains harmful political content, including hurting socialist regime system, hurting china interests image, hurting china unity stability, promoting terrorism_and_extremism, or promoting ethnic hate and discrimination.
    4.2 Error_Prohibited_Content: The text contains prohibited content, including violence, pornography, or gambling.
# Workflow
1. Carefully read and understand the provided text, evaluate the quality of the text based on the negative criteria.
2. Assign a type to the text.
    -If the text does not hit any negative criteria above, type must only be 'Good'; otherwise, type must only be one of the list ['Completeness', 'Effectiveness', 'Similarity', 'Security'].
3. Assign a name to the text.
    -If type is 'Good', name must only be 'None'.
    -If type is "Completeness", name must only be one of the list ["Error_Formula_Table", "Error_List_Number", "Error_Section_Order"]
    -If type is "Effectiveness", name must only be one of the list ["Error_Garbled_Characters", "Error_Words_Stuck" or "Error_Lack_Punctuation"]
    -If type is "Similarity", name must only be one of the list ["Error_Duplicate_Content"]
    -If type is "Security", name must only be one of the list ["Error_Political_Content", "Error_Prohibited_Content"]
4. Assign a score to the text according the type. If the type is "Good", score is 1, otherwise the score is 0.
5. Provide a clear reason for the evaluation.
6. Return the results in JSON format: {"score": 0/1, "type": [], "name": [], "reason": []}.
# Warning
Please remember to output only a JSON format data, without any additional content.
# Input content
"""

@Model.prompt_register("TEXT_QUALITY_V4", [])
class PromptTextQualityV4(BasePrompt):
    content = """
# Role
You are an expert in language model evaluation.

# Background
The dataset is a compilation from diverse sources, encompassing social media, news articles, academic publications, and online discussions.

# Goals
Your core task is to evaluate the fitness of this dataset for training a large language model. Text that exhibits any of the listed negative attributes will be flagged as low-quality data.

# Criteria
1. **Completeness**
    - **Error_Formula**: A formula enclosed in a pair of one $character is an intra line formula, while a formula enclosed in a pair of double $characters is an inter line formula. The text formula contains the following errors:
        - **Grammar Error**: There is a syntax error in the formula within the $ character.
        - **Interline Error**: Double $$ is used excessively for formulas that should be inline (e.g., $\mathbf{x}$, $\mathbf{y}$), resulting in a large number of unnecessary line breaks, severely disrupting the structure of the text, and affecting its readability and continuity.
    - **ERROR_Table**: Tables exist in Markdown files in either Markdown format or HTML format.
        - **Simple_Table_Errors**: Simple tables exist in the document in markdown format, specifically referring to tables without row/column spans or nested tables; error reasons include format and content issues.
        - **Complex_Table_Errors**: Complex tables exist in the document in HTML format, specifically referring to tables with row/column spans or nested tables; error reasons include format and content issues.
    - **Error_Code**: A Code enclosed in a pair of one `characters is an intra line code, while a code enclosed in a pair of three `characters is an inter line code. There are ordered numbers before code or the code contains syntax Error, format Error.

2. **Effectiveness**
    - **Error_Garbled_Characters**: High presence of garbled or anti-crawler characters.
    - **Error_Words_Stuck**: Words clustered together without spaces (excluding hyphenated words; treat \n as spaces).
    - **Error_Lack_Punctuation**: Words piled up without forming coherent sentences.

3. **Similarity**
   - **Error_Duplicate**: Consecutive repetitions or excessive character occurrences.

4. **Security**
   - **Error_Political**: Harmful political statements affecting socialist systems, China's interests, unity, stability, promoting terrorism/extremism, or ethnic hatred/discrimination.
   - **Error_Prohibited**: Content involving violence, pornography, gambling, or drugs.

# Workflow
1. **Read and Evaluate**: Analyze the text based on the outlined negative criteria.
2. **Assign Type**:
   - If no negative criteria are met, assign 'Good'.
   - Otherwise, assign one of ['Completeness', 'Effectiveness', 'Similarity', 'Security'].
3. **Assign Name**:
   - 'Good' text gets 'None'.
   - 'Completeness' text gets one of ['Error_Formula', 'ERROR_Table', 'Error_Code'].
   - 'Effectiveness' text gets one of ['Error_Garbled_Characters', 'Error_Words_Stuck', 'Error_Lack_Punctuation'].
   - 'Similarity' text gets 'Error_Duplicate'.
   - 'Security' text gets one of ['Error_Political', 'Error_Prohibited'].
4. **Assign Score**: 'Good' = 1, others = 0.
5. **Provide Reason**: Clearly state the basis for evaluation.
6. **Return in JSON**: {"score": 0/1, "type": "", "name": "", "reason": ""}.

# Warning
Only output JSON format data, without any extraneous content.

# Input content

"""
