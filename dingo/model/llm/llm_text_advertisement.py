import json

from dingo.io.input import RequiredField
from dingo.io.output.eval_detail import EvalDetail, QualityLabel
from dingo.model import Model
from dingo.model.llm.base_openai import BaseOpenAI
from dingo.model.response.response_class import ResponseScoreTypeNameReason
from dingo.utils import log
from dingo.utils.exception import ConvertJsonError


@Model.llm_register("LLMTextAdvertisement")
class LLMTextAdvertisement(BaseOpenAI):
    """Flag only severe hard-sell ads and traffic diversion in UGC."""

    _metric_info = {
        "category": "Pretrain Text Quality Assessment Metrics",
        "metric_name": "LLMTextAdvertisement",
        "description": "Flags only severe hard-sell ads and traffic diversion. Soft product mentions and hashtag-heavy notes pass.",
        "paper_title": "",
        "paper_url": "",
        "paper_authors": "Internal Implementation",
        "evaluation_results": "",
        "examples": "examples/ugc/eval_ad_and_media_url.py",
    }
    _required_fields = [RequiredField.CONTENT]
    prompt = """
# Role
You are checking Xiaohongshu-style UGC. Most notes mention products, venues, or brands. That is normal. Flag only severe advertising.

# Decision rule
Default to Good. Flag Advertisement only when conversion is the explicit, dominant purpose and a strong call-to-action is present. If you are unsure, return Good.

# Flag only when at least one is explicit and central:
- Hard sell with urgency or a buy path: limited stock, countdown, dump price, 抄底价, 打骨折, coupon code, 小黄车, 点击链接, 下方链接, 闭眼囤, 赶紧冲, plus a clear ask to purchase now
- Direct off-platform conversion: 私信下单, 加微信/QQ, scan a QR code, join a sales group, or send readers to Taobao/Douyin shop/landing pages to complete a deal
- Pure commercial listing with no personal narrative: wholesale/OEM recruitment, priced real-estate listing with an agency, factory sourcing, or a wall of shopping SKU tags and nothing else

# Do NOT flag:
- Daily vlog, outfit, travel, parenting, or food notes that mention a brand
- Soft 种草: selling points, "好用/回购/安利", or a product tutorial without a buy/contact CTA
- Hashtags, [话题], timestamps, or brand tags on an otherwise ordinary note
- Venue/store visits, wedding-site recaps, camera-gear diaries, or restaurant shares
- Comparing options or warning people not to buy the wrong item
- "私信咨询" or "评论区扣字" when it is only a mild invite and the body is still a real experience, not a sales script
- One product being the topic of a personal review

# Output
Return only JSON: {"score": 0 or 1, "type": "...", "name": "...", "reason": "..."}
- score 1 = not a severe ad: type "Good", name "None"
- score 0 = severe ad: type "Effectiveness", name "Advertisement"
Cite a short span. No extra text.

# Input
"""

    @classmethod
    def build_messages(cls, input_data):
        title = getattr(input_data, "prompt", None) or ""
        body = input_data.content or ""
        payload = f"Title:\n{title}\n\nContent:\n{body}"
        return [{"role": "user", "content": cls.prompt + payload}]

    @classmethod
    def process_response(cls, response: str) -> EvalDetail:
        log.info(response)
        text = response.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end > start:
            text = text[start:end + 1]
        try:
            response_json = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ConvertJsonError(f"Convert to JSON format failed: {response}") from exc

        parsed = ResponseScoreTypeNameReason(**response_json)
        result = EvalDetail(metric=cls.__name__)
        if parsed.score == 1:
            result.label = [QualityLabel.QUALITY_GOOD]
            result.reason = [parsed.reason]
            return result

        result.status = True
        result.score = 0
        result.label = ["Effectiveness.Advertisement"]
        result.reason = [parsed.reason]
        return result
