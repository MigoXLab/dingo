from dingo.model.model import Model
from dingo.model.prompt.base import BasePrompt


@Model.prompt_register("IMAGE_RELEVANT", [])
class PromptImageRelevant(BasePrompt):
    content = """
    作为一款专业的图片检测AI工具，请结合第一张图评估第二张图片是否符合标准。请先分析第一张图片，包括背景信息、人脸数量、以及每个人物的脸部和手部特征。
    然后根据以下标准对第二张图片进行评分：\n
    1. 图片中的人脸数量是否与第一张图片一致；\n
    2. 每个人物的脸部和手部是否变形；\n
    3. 如果第一张图片中有国旗标志，则判断第二张图片中的国旗标志颜色和形状是否一致。\n
    只要存在一处不符合，即不通过。评分0表示不通过，1表示通过。\n
    请只输出评分和理由，输出格式为json，模版为{"score": xxx, "reason": "xxx"}。\n
    """
