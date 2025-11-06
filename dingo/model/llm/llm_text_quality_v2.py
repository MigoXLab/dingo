from dingo.model import Model
from dingo.model.llm.base_openai import BaseOpenAI


@Model.llm_register("LLMTextQualityV2")
class LLMTextQualityV2(BaseOpenAI):
    prompt = """
### Role
You are an expert in language model.
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
