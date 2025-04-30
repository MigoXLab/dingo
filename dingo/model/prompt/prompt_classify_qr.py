from dingo.model.model import Model
from dingo.model.prompt.base import BasePrompt


@Model.prompt_register("CLASSIFY_QR", [])
class PromptClassifyQR(BasePrompt):
    content = """
    'Classify the image into one of the following categories: "CAPTCHA", "QR code", or "Normal image". '
    'Return the type as the image category (CAPTCHA or QR code or Normal image) and the reason as the specific type of CAPTCHA or QR code. '
    'Possible CAPTCHA types include: "Text CAPTCHA", "Image CAPTCHA", "Math CAPTCHA", "Slider CAPTCHA", "SMS CAPTCHA", "Voice CAPTCHA". '
    'Return the answer in JSON format: {"name": "xxx", "reason": "xxx" (if applicable)}.'
    'Please remember to output only the JSON format, without any additional content.'

    Here is the image you need to evaluate:
    """
