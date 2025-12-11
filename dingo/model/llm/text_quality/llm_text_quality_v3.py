import json

from dingo.io.output.eval_detail import EvalDetail, QualityLabel
from dingo.model import Model
from dingo.model.llm.base_openai import BaseOpenAI
from dingo.utils import log
from dingo.utils.exception import ConvertJsonError


@Model.llm_register("LLMTextQualityV3")
class LLMTextQualityV3(BaseOpenAI):
    prompt = """
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

    @classmethod
    def process_response(cls, response: str) -> EvalDetail:
        log.info(response)

        # 清理 markdown 代码块
        if response.startswith("```json"):
            response = response[7:]
        if response.startswith("```"):
            response = response[3:]
        if response.endswith("```"):
            response = response[:-3]

        try:
            response_json = json.loads(response)
        except json.JSONDecodeError:
            raise ConvertJsonError(f"Convert to JSON format failed: {response}")

        # 直接解析，不使用 ResponseScoreReason（因为该类不支持 type/name 字段）
        score = response_json.get("score", 0)
        type_list = response_json.get("type", [])
        name_list = response_json.get("name", [])
        reason_list = response_json.get("reason", [])

        # 确保都是列表
        if not isinstance(type_list, list):
            type_list = [type_list] if type_list else []
        if not isinstance(name_list, list):
            name_list = [name_list] if name_list else []
        if not isinstance(reason_list, list):
            reason_list = [reason_list] if reason_list else []

        result = EvalDetail(metric=cls.__name__)
        if score == 1:
            result.label = [QualityLabel.QUALITY_GOOD]
            result.reason = reason_list if reason_list else [""]
        else:
            # 构建标签：type.name 格式
            labels = []
            for t, n in zip(type_list, name_list):
                labels.append(f"{t}.{n}")
            if not labels:
                labels = [f"QUALITY_BAD.{cls.__name__}"]

            result.status = True
            result.label = labels
            result.reason = reason_list if reason_list else [""]

        return result
