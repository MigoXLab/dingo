import re
import string
from typing import Tuple

from dingo.config.input_args import EvaluatorRuleArgs
from dingo.io import Data
from dingo.io.output.eval_detail import EvalDetail, QualityLabel
from dingo.model.model import Model
from dingo.model.rule.base import BaseRule


@Model.rule_register("QUALITY_BAD_EFFECTIVENESS", ["qa_standard_v1"])
class RuleAbnormalChar(BaseRule):
    # consist of [RuleSpecialCharacter, RuleInvisibleChar]
    # Metadata for documentation generation
    _metric_info = {
        "category": "Rule-Based TEXT Quality Metrics",
        "quality_dimension": "EFFECTIVENESS",
        "metric_name": "RuleAbnormalChar",
        "description": "Detects garbled text and anti-crawling characters by combining special character and invisible character detection",
        "paper_title": "RedPajama: an Open Dataset for Training Large Language Models",
        "paper_url": "https://github.com/togethercomputer/RedPajama-Data",
        "paper_authors": "Together Computer, 2023",
        "evaluation_results": "docs/eval/rule/slimpajama_data_evaluated_by_rule.md"
    }

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        res = EvalDetail(metric=cls.__name__)
        for r in [RuleSpecialCharacter, RuleInvisibleChar]:
            tmp_res = r.eval(input_data)
            if tmp_res.status:
                res.status = True
                # res.merge(tmp_res)
                res.label = [f"{cls.metric_type}.{cls.__name__}"]
                if res.reason is None:
                    res.reason = []
                res.reason.extend(tmp_res.reason)
        # Set QUALITY_GOOD when all checks pass
        if not res.status:
            res.label = [QualityLabel.QUALITY_GOOD]
        return res


@Model.rule_register("QUALITY_BAD_EFFECTIVENESS", ["qa_standard_v1"])
class RuleAbnormalHtml(BaseRule):
    # consist of [RuleHtmlEntity, RuleHtmlTag]
    _metric_info = {
        "category": "Rule-Based TEXT Quality Metrics",
        "quality_dimension": "EFFECTIVENESS",
        "metric_name": "RuleAbnormalHtml",
        "description": "Detects abnormal HTML content by combining HTML entity and tag detection",
        "paper_title": "RedPajama: an Open Dataset for Training Large Language Models",
        "paper_url": "https://github.com/togethercomputer/RedPajama-Data",
        "paper_authors": "Together Computer, 2023",
        "evaluation_results": "docs/eval/rule/slimpajama_data_evaluated_by_rule.md"
    }

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        res = EvalDetail(metric=cls.__name__)
        for r in [RuleHtmlEntity, RuleHtmlTag]:
            tmp_res = r.eval(input_data)
            if tmp_res.status:
                res.status = True
                # res.merge(tmp_res)
                res.label = [f"{cls.metric_type}.{cls.__name__}"]
                if res.reason is None:
                    res.reason = []
                res.reason.extend(tmp_res.reason)
        # Set QUALITY_GOOD when all checks pass
        if not res.status:
            res.label = [QualityLabel.QUALITY_GOOD]
        return res


@Model.rule_register("QUALITY_BAD_FLUENCY", ["pdf_all"])
class RuleAbnormalNumber(BaseRule):
    """check pdf content abnormal book page or index number."""
    _metric_info = {
        "category": "Rule-Based TEXT Quality Metrics",
        "quality_dimension": "FLUENCY",
        "metric_name": "RuleAbnormalNumber",
        "description": "Checks PDF content for abnormal book page or index numbers that disrupt text flow",
        "paper_title": "RedPajama: an Open Dataset for Training Large Language Models",
        "paper_url": "https://github.com/togethercomputer/RedPajama-Data",
        "paper_authors": "Together Computer, 2023",
        "evaluation_results": "docs/eval/rule/slimpajama_data_evaluated_by_rule.md"
    }
    dynamic_config = EvaluatorRuleArgs(pattern=r"\n{4}\d+\n{4}")

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        res = EvalDetail(metric=cls.__name__)
        content = input_data.content
        match = re.search(cls.dynamic_config.pattern, content)
        if match:
            res.status = True
            res.label = [f"{cls.metric_type}.{cls.__name__}"]
            res.reason = [match.group(0).strip("\n")]
        else:
            res.label = [QualityLabel.QUALITY_GOOD]
        return res


@Model.rule_register("QUALITY_BAD_EFFECTIVENESS", ["pretrain"])
class RuleAlphaWords(BaseRule):
    """check whether the ratio of words that contain at least one alphabetic character > 0.6"""
    # Metadata for documentation generation
    _metric_info = {
        "category": "Rule-Based TEXT Quality Metrics",
        "quality_dimension": "EFFECTIVENESS",
        "metric_name": "RuleAlphaWords",
        "description": "Checks whether the ratio of words containing at least one alphabetic character is above threshold",
        "paper_title": "RedPajama: an Open Dataset for Training Large Language Models",
        "paper_url": "https://github.com/togethercomputer/RedPajama-Data",
        "paper_authors": "Together Computer, 2023",
        "evaluation_results": "docs/eval/rule/slimpajama_data_evaluated_by_rule.md"
    }
    dynamic_config = EvaluatorRuleArgs(threshold=0.6)

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        from nltk.tokenize import word_tokenize
        res = EvalDetail(metric=cls.__name__)
        content = input_data.content
        words = word_tokenize(content)
        n_words = len(words)
        if n_words == 0:
            return res
        n_alpha_words = sum([any((c.isalpha() for c in w)) for w in words])
        ratio = n_alpha_words / n_words
        if ratio > cls.dynamic_config.threshold:
            res.label = [QualityLabel.QUALITY_GOOD]
        else:
            res.status = True
            res.label = [f"{cls.metric_type}.{cls.__name__}"]
            res.reason = [
                "The ratio of words that contain at least one alphabetic character is: "
                + str(ratio)
            ]
        return res


@Model.rule_register(
    "QUALITY_BAD_EFFECTIVENESS",
    [
        "multi_lan_ar",
        "multi_lan_ko",
        "multi_lan_ru",
        "multi_lan_th",
        "multi_lan_vi",
        "multi_lan_cs",
        "multi_lan_hu",
        "multi_lan_sr",
    ]
)
class RuleAudioDataFormat(BaseRule):
    """check whether the audio data format is right"""

    # Metadata for documentation generation
    _metric_info = {
        "category": "Rule-Based TEXT Quality Metrics",
        "quality_dimension": "EFFECTIVENESS",
        "metric_name": "RuleAudioDataFormat",
        "description": "Check whether the audio data format is right",
        "evaluation_results": ""
    }

    dynamic_config = EvaluatorRuleArgs()

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        res = EvalDetail(metric=cls.__name__)

        raw_data = input_data.raw_data
        key_list = ["id", "audio", "text"]
        if all(key in raw_data for key in key_list):
            res.label = [QualityLabel.QUALITY_GOOD]
        else:
            res.status = True
            res.label = [f"{cls.metric_type}.{cls.__name__}"]
            res.reason = ["Audio Data format error"]
        return res


@Model.rule_register("QUALITY_BAD_UNDERSTANDABILITY", ["pretrain"])
class RuleCapitalWords(BaseRule):
    """check whether capital words ratio > 0.2"""
    # Metadata for documentation generation
    _metric_info = {
        "category": "Rule-Based TEXT Quality Metrics",
        "quality_dimension": "UNDERSTANDABILITY",
        "metric_name": "RuleCapitalWords",
        "description": "Checks whether the ratio of capital words is above threshold, indicating poor readability",
        "paper_title": "RedPajama: an Open Dataset for Training Large Language Models",
        "paper_url": "https://github.com/togethercomputer/RedPajama-Data",
        "paper_authors": "Together Computer, 2023",
        "evaluation_results": "docs/eval/rule/slimpajama_data_evaluated_by_rule.md"
    }

    dynamic_config = EvaluatorRuleArgs(threshold=0.2)

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        from nltk.tokenize import WordPunctTokenizer
        res = EvalDetail(metric=cls.__name__)
        content = input_data.content
        words = WordPunctTokenizer().tokenize(content)
        num_words = len(words)
        if num_words == 0:
            return res
        num_caps_words = sum(map(str.isupper, words))
        ratio = num_caps_words / num_words
        if ratio > cls.dynamic_config.threshold and num_words < 200:
            res.status = True
            res.label = [f"{cls.metric_type}.{cls.__name__}"]
            res.reason = ["ratio: " + str(ratio)]
        else:
            res.label = [QualityLabel.QUALITY_GOOD]
        return res


@Model.rule_register("QUALITY_BAD_EFFECTIVENESS", ["pretrain"])
class RuleCharNumber(BaseRule):
    """check whether the number of char > 100"""
    # Metadata for documentation generation
    _metric_info = {
        "category": "Rule-Based TEXT Quality Metrics",
        "quality_dimension": "EFFECTIVENESS",
        "metric_name": "RuleCharNumber",
        "description": "Checks whether the number of characters is above minimum threshold",
        "paper_title": "RedPajama: an Open Dataset for Training Large Language Models",
        "paper_url": "https://github.com/togethercomputer/RedPajama-Data",
        "paper_authors": "Together Computer, 2023",
        "evaluation_results": "docs/eval/rule/slimpajama_data_evaluated_by_rule.md"
    }
    dynamic_config = EvaluatorRuleArgs(threshold=100)

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        res = EvalDetail(metric=cls.__name__)
        text = input_data.content
        text = text.strip()
        text = text.replace(" ", "")
        text = text.replace("\n", "")
        text = text.replace("\t", "")
        num_char = len(text)
        if num_char < cls.dynamic_config.threshold:
            res.status = True
            res.label = [f"{cls.metric_type}.{cls.__name__}"]
            res.reason = ["The number of char is: " + str(num_char)]
        else:
            res.label = [QualityLabel.QUALITY_GOOD]
        return res


@Model.rule_register("QUALITY_BAD_FLUENCY", ["pdf_all"])
class RuleCharSplit(BaseRule):
    """check pdf content char split."""
    # Metadata for documentation generation
    _metric_info = {
        "category": "Rule-Based TEXT Quality Metrics",
        "quality_dimension": "FLUENCY",
        "metric_name": "RuleCharSplit",
        "description": "Checks PDF content for abnormal character splitting that disrupts readability",
        "paper_title": "RedPajama: an Open Dataset for Training Large Language Models",
        "paper_url": "https://github.com/togethercomputer/RedPajama-Data",
        "paper_authors": "Together Computer, 2023",
        "evaluation_results": "docs/eval/rule/slimpajama_data_evaluated_by_rule.md"
    }
    dynamic_config = EvaluatorRuleArgs(
        pattern=r"(?:(?:[a-zA-Z]\s){5}[a-zA-Z])", threshold=3
    )

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        res = EvalDetail(metric=cls.__name__)
        content = input_data.content
        matches = re.findall(cls.dynamic_config.pattern, content)
        count = len(matches)
        if count >= cls.dynamic_config.threshold:
            res.status = True
            res.label = [f"{cls.metric_type}.{cls.__name__}"]
            res.reason = matches
        else:
            res.label = [QualityLabel.QUALITY_GOOD]
        return res


@Model.rule_register(
    "QUALITY_BAD_EFFECTIVENESS",
    ["default", "sft", "pretrain", "benchmark", "llm_base", "text_base_all"],
)
class RuleColonEnd(BaseRule):
    """check whether the last char is ':'"""
    # Metadata for documentation generation
    _metric_info = {
        "category": "Rule-Based TEXT Quality Metrics",
        "quality_dimension": "EFFECTIVENESS",
        "metric_name": "RuleColonEnd",
        "description": "Checks if text abruptly ends with a colon, indicating incomplete content",
        "paper_title": "RedPajama: an Open Dataset for Training Large Language Models",
        "paper_url": "https://github.com/togethercomputer/RedPajama-Data",
        "paper_authors": "Together Computer, 2023",
        "evaluation_results": "docs/eval/rule/slimpajama_data_evaluated_by_rule.md"
    }
    eval_fileds = ['content']
    dynamic_config = EvaluatorRuleArgs()

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        res = EvalDetail(metric=cls.__name__)
        content = input_data.content
        if len(content) <= 0:
            return res
        if content[-1] == ":":
            # res.eval_status = True
            # res.eval_details = {
            #     "label": [f"{cls.metric_type}.{cls.__name__}"],
            #     "metric": [cls.__name__],
            #     "reason": [content[-100:]]
            # }
            res.status = True
            res.label = [f"{cls.metric_type}.{cls.__name__}"]
            res.reason = [content[-100:]]
        else:
            # res.eval_details = {
            #     "label": [QualityLabel.QUALITY_GOOD]
            # }
            res.label = [QualityLabel.QUALITY_GOOD]
        return res


@Model.rule_register(
    "QUALITY_BAD_EFFECTIVENESS",
    [
        "default",
        "sft",
        "pretrain",
        "benchmark",
        "text_base_all",
        "llm_base",
        "multi_lan_ar",
        "multi_lan_ko",
        "multi_lan_ru",
        "multi_lan_th",
        "multi_lan_vi",
        "multi_lan_cs",
        "multi_lan_hu",
        "multi_lan_sr",
        "qa_standard_v1",
        "pdf",
    ],
)
class RuleContentNull(BaseRule):
    """check whether content is null"""
    # Metadata for documentation generation
    _metric_info = {
        "category": "Rule-Based TEXT Quality Metrics",
        "quality_dimension": "EFFECTIVENESS",
        "metric_name": "RuleContentNull",
        "description": "Checks whether content is empty or null",
        "paper_title": "RedPajama: an Open Dataset for Training Large Language Models",
        "paper_url": "https://github.com/togethercomputer/RedPajama-Data",
        "paper_authors": "Together Computer, 2023",
        "evaluation_results": "docs/eval/rule/slimpajama_data_evaluated_by_rule.md"
    }
    dynamic_config = EvaluatorRuleArgs()

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        res = EvalDetail(metric=cls.__name__)
        count = len(input_data.content.strip())
        if count == 0:
            res.status = True
            res.label = [f"{cls.metric_type}.{cls.__name__}"]
            res.reason = ["Content is empty."]
        else:
            res.label = [QualityLabel.QUALITY_GOOD]
        return res


@Model.rule_register(
    "QUALITY_BAD_EFFECTIVENESS", ["text_base_all", "qa_standard_v1", "pdf"]
)
class RuleContentShort(BaseRule):
    """check whether content is too short"""
    # Metadata for documentation generation
    _metric_info = {
        "category": "Rule-Based TEXT Quality Metrics",
        "quality_dimension": "EFFECTIVENESS",
        "metric_name": "RuleContentShort",
        "description": "Checks whether content is too short to be meaningful",
        "paper_title": "RedPajama: an Open Dataset for Training Large Language Models",
        "paper_url": "https://github.com/togethercomputer/RedPajama-Data",
        "paper_authors": "Together Computer, 2023",
        "evaluation_results": "docs/eval/rule/slimpajama_data_evaluated_by_rule.md"
    }
    dynamic_config = EvaluatorRuleArgs(threshold=20)

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        res = EvalDetail(metric=cls.__name__)
        content = input_data.content.encode("utf-8")
        if len(content) <= cls.dynamic_config.threshold:
            res.status = True
            res.label = [f"{cls.metric_type}.{cls.__name__}"]
            res.reason = ["Content is too short."]
        else:
            res.label = [QualityLabel.QUALITY_GOOD]
        return res


@Model.rule_register(
    "QUALITY_BAD_EFFECTIVENESS",
    [
        "multi_lan_ar",
        "multi_lan_ko",
        "multi_lan_ru",
        "multi_lan_th",
        "multi_lan_vi",
        "multi_lan_cs",
        "multi_lan_hu",
        "multi_lan_sr",
    ],
)
class RuleContentShortMultiLan(BaseRule):
    """check whether content is too short."""
    # Metadata for documentation generation
    _metric_info = {
        "category": "Rule-Based TEXT Quality Metrics",
        "quality_dimension": "EFFECTIVENESS",
        "metric_name": "RuleContentShortMultiLan",
        "description": "Checks whether multi-language content is too short to be meaningful",
        "paper_title": "RedPajama: an Open Dataset for Training Large Language Models",
        "paper_url": "https://github.com/togethercomputer/RedPajama-Data",
        "paper_authors": "Together Computer, 2023",
        "evaluation_results": "docs/eval/rule/slimpajama_data_evaluated_by_rule.md"
    }
    dynamic_config = EvaluatorRuleArgs(threshold=20)

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        from nltk.tokenize import WordPunctTokenizer
        res = EvalDetail(metric=cls.__name__)
        tk = WordPunctTokenizer()
        tokens = tk.tokenize(input_data.content)
        words = [word for word in tokens if word.isalpha()]
        if len(words) < cls.dynamic_config.threshold:
            res.status = True
            res.label = [f"{cls.metric_type}.{cls.__name__}"]
            res.reason = ["Content is too short."]
        else:
            res.label = [QualityLabel.QUALITY_GOOD]
        return res


@Model.rule_register("QUALITY_BAD_UNDERSTANDABILITY", [])
class RuleCurlyBracket(BaseRule):
    """check whether the ratio of the number of {,} and the number of characters < 0.025"""
    # Metadata for documentation generation
    _metric_info = {
        "category": "Rule-Based TEXT Quality Metrics",
        "quality_dimension": "UNDERSTANDABILITY",
        "metric_name": "RuleCurlyBracket",
        "description": "Checks whether the ratio of curly brackets to total characters is below threshold",
        "paper_title": "RedPajama: an Open Dataset for Training Large Language Models",
        "paper_url": "https://github.com/togethercomputer/RedPajama-Data",
        "paper_authors": "Together Computer, 2023",
        "evaluation_results": "docs/eval/rule/slimpajama_data_evaluated_by_rule.md"
    }
    dynamic_config = EvaluatorRuleArgs(threshold=0.025)

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        res = EvalDetail(metric=cls.__name__)
        content = input_data.content
        if len(content) == 0:
            return res
        num = content.count("{") + content.count("}")
        ratio = num / len(content)
        if ratio > cls.dynamic_config.threshold:
            res.status = True
            res.label = [f"{cls.metric_type}.{cls.__name__}"]
            res.reason = [
                "The ratio of curly bracket and characters is : " + str(ratio)
            ]
        else:
            res.label = [QualityLabel.QUALITY_GOOD]
        return res


@Model.rule_register(
    "QUALITY_BAD_SIMILARITY",
    [
        "default",
        "sft",
        "pretrain",
        "benchmark",
        "text_base_all",
        "llm_base",
        "multi_lan_ar",
        "multi_lan_ko",
        "multi_lan_ru",
        "multi_lan_th",
        "multi_lan_vi",
        "multi_lan_cs",
        "multi_lan_hu",
        "multi_lan_sr",
        "pdf",
    ],
)
class RuleDocRepeat(BaseRule):
    """check whether content repeats"""
    # Metadata for documentation generation
    _metric_info = {
        "category": "Rule-Based TEXT Quality Metrics",
        "quality_dimension": "SIMILARITY",
        "metric_name": "RuleDocRepeat",
        "description": "Evaluates text for consecutive repeated content and multiple occurrences of special characters",
        "paper_title": "RedPajama: an Open Dataset for Training Large Language Models",
        "paper_url": "https://github.com/togethercomputer/RedPajama-Data",
        "paper_authors": "Together Computer, 2023",
        "evaluation_results": "docs/eval/rule/slimpajama_data_evaluated_by_rule.md"
    }
    dynamic_config = EvaluatorRuleArgs(threshold=80)

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        from dingo.model.rule.utils.util import base_rps_frac_chars_in_dupe_ngrams

        res = EvalDetail(metric=cls.__name__)
        repeat_score = base_rps_frac_chars_in_dupe_ngrams(6, input_data.content)
        if repeat_score >= cls.dynamic_config.threshold:
            res.status = True
            res.label = [f"{cls.metric_type}.{cls.__name__}"]
            res.reason = [
                "Repeatability of text is too high, with ratio： " + str(repeat_score)
            ]
        else:
            res.label = [QualityLabel.QUALITY_GOOD]
        return res


@Model.rule_register(
    "QUALITY_BAD_SIMILARITY",
    [
        "default",
        "pdf"
    ],
)
class RuleDocFormulaRepeat(BaseRule):
    """check whether Formula repeats"""

    # Metadata for documentation generation
    _metric_info = {
        "category": "Rule-Based TEXT Quality Metrics",
        "quality_dimension": "SIMILARITY",
        "metric_name": "RuleDocFormulaRepeat",
        "description": "Evaluates text for consecutive repeated content and multiple occurrences of special characters",
        "paper_title": "RedPajama: an Open Dataset for Training Large Language Models",
        "paper_url": "https://github.com/togethercomputer/RedPajama-Data",
        "paper_authors": "Together Computer, 2023",
        "evaluation_results": "docs/eval/rule/slimpajama_data_evaluated_by_rule.md"
    }

    dynamic_config = EvaluatorRuleArgs(threshold=20)  # 设置阈值为20

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        res = EvalDetail(metric=cls.__name__)

        # 提取所有公式
        pattern = r'(?:\$\$(.*?)\$\$|\\\((.*?)\\\))'
        matches = re.findall(pattern, input_data.content, re.DOTALL)
        formulas = []
        for match in matches:
            formula = match[0] or match[1]  # 取非空的那个
            formulas.append(formula.strip())
        if not formulas:
            return res
        formula_content = "\n".join(formulas)
        repeat_analysis = cls.analyze_repeats(formula_content)
        # 如果总连续重复长度超过阈值，则标记为错误
        if repeat_analysis['total_repeat_length'] >= cls.dynamic_config.threshold:
            res.status = True
            res.label = [f"{cls.metric_type}.{cls.__name__}"]
            res.reason = [
                f"Formula has too many consecutive repeated characters, "
                f"total repeat length: {repeat_analysis['total_repeat_length']}, "
                f"found {len(repeat_analysis['repeats'])} repeat patterns"
            ]
        else:
            res.label = [QualityLabel.QUALITY_GOOD]

        return res

    @classmethod
    def analyze_repeats(cls, text):
        """
        分析文本中的连续重复模式
        """
        multi_char_pattern = r'(.{2,20}?)\1+'
        multi_char_repeats = list(re.finditer(multi_char_pattern, text))

        # 计算总重复长度
        total_repeat_length = 0
        repeats_info = []

        for match in multi_char_repeats:
            repeat_text = match.group(0)
            pattern = match.group(1)
            repeat_length = len(repeat_text)
            total_repeat_length += repeat_length

            repeats_info.append({
                'text': repeat_text,
                'pattern': pattern,
                'length': repeat_length,
                'type': 'single_char' if len(pattern) == 1 else 'multi_char'
            })
        return {
            'total_repeat_length': total_repeat_length,
            'repeats': repeats_info,
            'multi_char_count': len(multi_char_repeats)
        }


@Model.rule_register("QUALITY_BAD_EFFECTIVENESS", ["qa_standard_v1"])
class RuleEnterAndSpace(BaseRule):
    # consist of [RuleEnterMore, RuleEnterRatioMore, RuleSpaceMore]
    # Metadata for documentation generation
    _metric_info = {
        "category": "Rule-Based TEXT Quality Metrics",
        "quality_dimension": "EFFECTIVENESS",
        "metric_name": "RuleEnterAndSpace",
        "description": "Composite rule checking for excessive carriage returns and spaces",
        "paper_title": "RedPajama: an Open Dataset for Training Large Language Models",
        "paper_url": "https://github.com/togethercomputer/RedPajama-Data",
        "paper_authors": "Together Computer, 2023",
        "evaluation_results": "docs/eval/rule/slimpajama_data_evaluated_by_rule.md"
    }

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        res = EvalDetail(metric=cls.__name__)
        for r in [RuleEnterMore, RuleEnterRatioMore, RuleSpaceMore]:
            tmp_res = r.eval(input_data)
            if tmp_res.status:
                res.status = True
                # res.merge(tmp_res)
                res.label = [f"{cls.metric_type}.{cls.__name__}"]
                if res.reason is None:
                    res.reason = []
                res.reason.extend(tmp_res.reason)
        # Set QUALITY_GOOD when all checks pass
        if not res.status:
            res.label = [QualityLabel.QUALITY_GOOD]
        return res


@Model.rule_register(
    "QUALITY_BAD_EFFECTIVENESS",
    [
        "text_base_all",
        "llm_base",
        "multi_lan_ar",
        "multi_lan_ko",
        "multi_lan_ru",
        "multi_lan_th",
        "multi_lan_vi",
        "multi_lan_cs",
        "multi_lan_hu",
        "multi_lan_sr",
        "pdf",
    ],
)
class RuleEnterMore(BaseRule):
    """check whether content has 8 consecutive carriage returns."""
    # Metadata for documentation generation
    _metric_info = {
        "category": "Rule-Based TEXT Quality Metrics",
        "quality_dimension": "EFFECTIVENESS",
        "metric_name": "RuleEnterMore",
        "description": "Checks whether content has 8 consecutive carriage returns",
        "paper_title": "RedPajama: an Open Dataset for Training Large Language Models",
        "paper_url": "https://github.com/togethercomputer/RedPajama-Data",
        "paper_authors": "Together Computer, 2023",
        "evaluation_results": "docs/eval/rule/slimpajama_data_evaluated_by_rule.md"
    }
    dynamic_config = EvaluatorRuleArgs(key_list=[r"\n{8,}", r"\r\n{8,}"])

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        res = EvalDetail(metric=cls.__name__)
        content = input_data.content
        for p in cls.dynamic_config.key_list:
            SEARCH_REGEX = re.compile(p)
            match = SEARCH_REGEX.search(content)
            if match:
                res.status = True
                res.label = [f"{cls.metric_type}.{cls.__name__}"]
                res.reason = ["Content has 8 consecutive carriage returns."]
                return res
        res.label = [QualityLabel.QUALITY_GOOD]
        return res


@Model.rule_register(
    "QUALITY_BAD_EFFECTIVENESS",
    [
        "text_base_all",
        "llm_base",
        "multi_lan_ar",
        "multi_lan_ko",
        "multi_lan_ru",
        "multi_lan_th",
        "multi_lan_vi",
        "multi_lan_cs",
        "multi_lan_hu",
        "multi_lan_sr",
        "pdf",
    ],
)
class RuleEnterRatioMore(BaseRule):
    """check whether the number of enter / the number of content > 25%"""
    # Metadata for documentation generation
    _metric_info = {
        "category": "Rule-Based TEXT Quality Metrics",
        "quality_dimension": "EFFECTIVENESS",
        "metric_name": "RuleEnterRatioMore",
        "description": "Checks whether the ratio of enter characters to total content is above 25%",
        "paper_title": "RedPajama: an Open Dataset for Training Large Language Models",
        "paper_url": "https://github.com/togethercomputer/RedPajama-Data",
        "paper_authors": "Together Computer, 2023",
        "evaluation_results": "docs/eval/rule/slimpajama_data_evaluated_by_rule.md"
    }
    dynamic_config = EvaluatorRuleArgs()

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        res = EvalDetail(metric=cls.__name__)
        content = input_data.content
        if len(content) == 0:
            return res
        ratio = content.count("\n") / len(content)
        if ratio > 0.25:
            res.status = True
            res.label = [f"{cls.metric_type}.{cls.__name__}"]
            res.reason = ["The number of enter / the number of content > 25%."]
        else:
            res.label = [QualityLabel.QUALITY_GOOD]
        return res


@Model.rule_register("QUALITY_BAD_RELEVANCE", ["multi_lan_ar"])
class RuleHeadWordAr(BaseRule):
    """check whether ar content contains irrelevance tail source info."""
    # Metadata for documentation generation
    _metric_info = {
        "category": "Rule-Based TEXT Quality Metrics",
        "quality_dimension": "RELEVANCE_MULTI_LAN",
        "metric_name": "RuleHeadWordAr",
        "description": "Checks whether Arabic content contains irrelevant tail source information",
        "paper_title": "RedPajama: an Open Dataset for Training Large Language Models",
        "paper_url": "https://github.com/togethercomputer/RedPajama-Data",
        "paper_authors": "Together Computer, 2023",
        "evaluation_results": "docs/eval/rule/slimpajama_data_evaluated_by_rule.md"
    }
    dynamic_config = EvaluatorRuleArgs()

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        from dingo.model.rule.utils.multi_lan_util import get_xyz_head_word
        res = EvalDetail(metric=cls.__name__)
        keyword = get_xyz_head_word("ar")
        content_tail = input_data.content[-100:]
        matches = re.findall("|".join(keyword), content_tail)
        if len(matches) > 0:
            res.status = True
            res.label = [f"{cls.metric_type}.{cls.__name__}"]
            res.reason = ["Content has irrelevance tail source info."]
        else:
            res.label = [QualityLabel.QUALITY_GOOD]
        return res


@Model.rule_register("QUALITY_BAD_RELEVANCE", ["multi_lan_cs"])
class RuleHeadWordCs(BaseRule):
    """check whether cs content contains irrelevance tail source info."""
    # Metadata for documentation generation
    _metric_info = {
        "category": "Rule-Based TEXT Quality Metrics",
        "quality_dimension": "RELEVANCE_MULTI_LAN",
        "metric_name": "RuleHeadWordCs",
        "description": "Checks whether Czech content contains irrelevant tail source information",
        "paper_title": "RedPajama: an Open Dataset for Training Large Language Models",
        "paper_url": "https://github.com/togethercomputer/RedPajama-Data",
        "paper_authors": "Together Computer, 2023",
        "evaluation_results": "docs/eval/rule/slimpajama_data_evaluated_by_rule.md"
    }
    dynamic_config = EvaluatorRuleArgs()

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        from dingo.model.rule.utils.multi_lan_util import get_xyz_head_word
        res = EvalDetail(metric=cls.__name__)
        keyword = get_xyz_head_word("cs")
        content_tail = input_data.content[-100:]
        matches = re.findall("|".join(keyword), content_tail)
        if len(matches) > 0:
            res.status = True
            res.label = [f"{cls.metric_type}.{cls.__name__}"]
            res.reason = ["Content has irrelevance tail source info."]
        else:
            res.label = [QualityLabel.QUALITY_GOOD]
        return res


@Model.rule_register("QUALITY_BAD_RELEVANCE", ["multi_lan_hu"])
class RuleHeadWordHu(BaseRule):
    """check whether hu content contains irrelevance tail source info."""
    # Metadata for documentation generation
    _metric_info = {
        "category": "Rule-Based TEXT Quality Metrics",
        "quality_dimension": "RELEVANCE_MULTI_LAN",
        "metric_name": "RuleHeadWordHu",
        "description": "Checks whether Hungarian content contains irrelevant tail source information",
        "paper_title": "RedPajama: an Open Dataset for Training Large Language Models",
        "paper_url": "https://github.com/togethercomputer/RedPajama-Data",
        "paper_authors": "Together Computer, 2023",
        "evaluation_results": "docs/eval/rule/slimpajama_data_evaluated_by_rule.md"
    }
    dynamic_config = EvaluatorRuleArgs()

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        from dingo.model.rule.utils.multi_lan_util import get_xyz_head_word
        res = EvalDetail(metric=cls.__name__)
        keyword = get_xyz_head_word("hu")
        content_tail = input_data.content[-100:]
        matches = re.findall("|".join(keyword), content_tail)
        if len(matches) > 0:
            res.status = True
            res.label = [f"{cls.metric_type}.{cls.__name__}"]
            res.reason = ["Content has irrelevance tail source info."]
        else:
            res.label = [QualityLabel.QUALITY_GOOD]
        return res


@Model.rule_register("QUALITY_BAD_RELEVANCE", ["multi_lan_ko"])
class RuleHeadWordKo(BaseRule):
    """check whether ko content contains irrelevance tail source info."""
    # Metadata for documentation generation
    _metric_info = {
        "category": "Rule-Based TEXT Quality Metrics",
        "quality_dimension": "RELEVANCE_MULTI_LAN",
        "metric_name": "RuleHeadWordKo",
        "description": "Checks whether Korean content contains irrelevant tail source information",
        "paper_title": "RedPajama: an Open Dataset for Training Large Language Models",
        "paper_url": "https://github.com/togethercomputer/RedPajama-Data",
        "paper_authors": "Together Computer, 2023",
        "evaluation_results": "docs/eval/rule/slimpajama_data_evaluated_by_rule.md"
    }
    dynamic_config = EvaluatorRuleArgs()

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        from dingo.model.rule.utils.multi_lan_util import get_xyz_head_word
        res = EvalDetail(metric=cls.__name__)
        keyword = get_xyz_head_word("ko")
        content_tail = input_data.content[-100:]
        matches = re.findall("|".join(keyword), content_tail)
        if len(matches) > 0:
            res.status = True
            res.label = [f"{cls.metric_type}.{cls.__name__}"]
            res.reason = ["Content has irrelevance tail source info."]
        else:
            res.label = [QualityLabel.QUALITY_GOOD]
        return res


@Model.rule_register("QUALITY_BAD_RELEVANCE", ["multi_lan_ru"])
class RuleHeadWordRu(BaseRule):
    """check whether ru content contains irrelevance tail source info."""
    # Metadata for documentation generation
    _metric_info = {
        "category": "Rule-Based TEXT Quality Metrics",
        "quality_dimension": "RELEVANCE_MULTI_LAN",
        "metric_name": "RuleHeadWordRu",
        "description": "Checks whether Russian content contains irrelevant tail source information",
        "paper_title": "RedPajama: an Open Dataset for Training Large Language Models",
        "paper_url": "https://github.com/togethercomputer/RedPajama-Data",
        "paper_authors": "Together Computer, 2023",
        "evaluation_results": "docs/eval/rule/slimpajama_data_evaluated_by_rule.md"
    }
    dynamic_config = EvaluatorRuleArgs()

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        from dingo.model.rule.utils.multi_lan_util import get_xyz_head_word
        res = EvalDetail(metric=cls.__name__)
        keyword = get_xyz_head_word("ru")
        content_tail = input_data.content[-100:]
        matches = re.findall("|".join(keyword), content_tail)
        if len(matches) > 0:
            res.status = True
            res.label = [f"{cls.metric_type}.{cls.__name__}"]
            res.reason = ["Content has irrelevance tail source info."]
        else:
            res.label = [QualityLabel.QUALITY_GOOD]
        return res


@Model.rule_register("QUALITY_BAD_RELEVANCE", ["multi_lan_sr"])
class RuleHeadWordSr(BaseRule):
    """check whether sr content contains irrelevance tail source info."""
    # Metadata for documentation generation
    _metric_info = {
        "category": "Rule-Based TEXT Quality Metrics",
        "quality_dimension": "RELEVANCE_MULTI_LAN",
        "metric_name": "RuleHeadWordSr",
        "description": "Checks whether Serbian content contains irrelevant tail source information",
        "paper_title": "RedPajama: an Open Dataset for Training Large Language Models",
        "paper_url": "https://github.com/togethercomputer/RedPajama-Data",
        "paper_authors": "Together Computer, 2023",
        "evaluation_results": "docs/eval/rule/slimpajama_data_evaluated_by_rule.md"
    }
    dynamic_config = EvaluatorRuleArgs()

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        from dingo.model.rule.utils.multi_lan_util import get_xyz_head_word
        res = EvalDetail(metric=cls.__name__)
        keyword = get_xyz_head_word("sr")
        content_tail = input_data.content[-100:]
        matches = re.findall("|".join(keyword), content_tail)
        if len(matches) > 0:
            res.status = True
            res.label = [f"{cls.metric_type}.{cls.__name__}"]
            res.reason = ["Content has irrelevance tail source info."]
        else:
            res.label = [QualityLabel.QUALITY_GOOD]
        return res


@Model.rule_register("QUALITY_BAD_RELEVANCE", ["multi_lan_th"])
class RuleHeadWordTh(BaseRule):
    """check whether th content contains irrelevance tail source info."""
    # Metadata for documentation generation
    _metric_info = {
        "category": "Rule-Based TEXT Quality Metrics",
        "quality_dimension": "RELEVANCE_MULTI_LAN",
        "metric_name": "RuleHeadWordAr",
        "description": "Checks whether Arabic content contains irrelevant tail source information",
        "paper_title": "RedPajama: an Open Dataset for Training Large Language Models",
        "paper_url": "https://github.com/togethercomputer/RedPajama-Data",
        "paper_authors": "Together Computer, 2023",
        "evaluation_results": "docs/eval/rule/slimpajama_data_evaluated_by_rule.md"
    }
    dynamic_config = EvaluatorRuleArgs()

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        from dingo.model.rule.utils.multi_lan_util import get_xyz_head_word
        res = EvalDetail(metric=cls.__name__)
        keyword = get_xyz_head_word("th")
        content_tail = input_data.content[-100:]
        matches = re.findall("|".join(keyword), content_tail)
        if len(matches) > 0:
            res.status = True
            res.label = [f"{cls.metric_type}.{cls.__name__}"]
            res.reason = ["Content has irrelevance tail source info."]
        else:
            res.label = [QualityLabel.QUALITY_GOOD]
        return res


@Model.rule_register("QUALITY_BAD_RELEVANCE", ["multi_lan_vi"])
class RuleHeadWordVi(BaseRule):
    """check whether vi content contains irrelevance tail source info."""
    # Metadata for documentation generation
    _metric_info = {
        "category": "Rule-Based TEXT Quality Metrics",
        "quality_dimension": "RELEVANCE_MULTI_LAN",
        "metric_name": "RuleHeadWordVi",
        "description": "Checks whether Vietnamese content contains irrelevant tail source information",
        "paper_title": "RedPajama: an Open Dataset for Training Large Language Models",
        "paper_url": "https://github.com/togethercomputer/RedPajama-Data",
        "paper_authors": "Together Computer, 2023",
        "evaluation_results": "docs/eval/rule/slimpajama_data_evaluated_by_rule.md"
    }
    dynamic_config = EvaluatorRuleArgs()

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        from dingo.model.rule.utils.multi_lan_util import get_xyz_head_word
        res = EvalDetail(metric=cls.__name__)
        keyword = get_xyz_head_word("vi")
        content_tail = input_data.content[-100:]
        matches = re.findall("|".join(keyword), content_tail)
        if len(matches) > 0:
            res.status = True
            res.label = [f"{cls.metric_type}.{cls.__name__}"]
            res.reason = ["Content has irrelevance tail source info."]
        else:
            res.label = [QualityLabel.QUALITY_GOOD]
        return res


@Model.rule_register(
    "QUALITY_BAD_EFFECTIVENESS",
    [
        "default",
        "sft",
        "pretrain",
        "benchmark",
        "text_base_all",
        "multi_lan_ar",
        "multi_lan_ko",
        "multi_lan_ru",
        "multi_lan_th",
        "multi_lan_vi",
        "multi_lan_cs",
        "multi_lan_hu",
        "multi_lan_sr",
        "pdf",
    ],
)
class RuleHtmlEntity(BaseRule):
    """check whether content has html entity"""
    # Metadata for documentation generation
    _metric_info = {
        "category": "Rule-Based TEXT Quality Metrics",
        "quality_dimension": "EFFECTIVENESS",
        "metric_name": "RuleHtmlEntity",
        "description": "Checks whether content contains HTML entities indicating web scraping artifacts",
        "paper_title": "RedPajama: an Open Dataset for Training Large Language Models",
        "paper_url": "https://github.com/togethercomputer/RedPajama-Data",
        "paper_authors": "Together Computer, 2023",
        "evaluation_results": "docs/eval/rule/slimpajama_data_evaluated_by_rule.md"
    }
    dynamic_config = EvaluatorRuleArgs(
        key_list=[
            "nbsp",
            "lt",
            "gt",
            "amp",
            "quot",
            "apos",
            "hellip",
            "ndash",
            "mdash",
            "lsquo",
            "rsquo",
            "ldquo",
            "rdquo",
        ]
    )

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        res = EvalDetail(metric=cls.__name__)
        content = input_data.content
        if len(content) == 0:
            return res
        entities = cls.dynamic_config.key_list
        full_entities_1 = [f"&{entity}；" for entity in entities]
        full_entities_2 = [f"&{entity};" for entity in entities]
        full_entities_3 = [f"＆{entity};" for entity in entities]
        full_entities_4 = [f"＆{entity}；" for entity in entities]
        full_entities = (
            full_entities_1 + full_entities_2 + full_entities_3 + full_entities_4
        )
        # half_entity_1 = [f"{entity}；" for entity in entities]
        half_entity_2 = [f"＆{entity}" for entity in entities]
        half_entity_3 = [f"&{entity}" for entity in entities]
        # half_entity_4 = [f"{entity};" for entity in entities]
        half_entities = half_entity_2 + half_entity_3
        # maked_entities = [f"{entity}" for entity in entities]
        all_entities = full_entities + half_entities
        error_entity = []
        num = 0
        for entity in all_entities:
            if entity in content:
                num += content.count(entity)
                error_entity.append(entity)
        if num / len(content) >= 0.01:
            res.status = True
            res.label = [f"{cls.metric_type}.{cls.__name__}"]
            res.reason = [list(set(error_entity))]
        else:
            res.label = [QualityLabel.QUALITY_GOOD]
        return res


@Model.rule_register(
    "QUALITY_BAD_EFFECTIVENESS",
    [
        "text_base_all",
        "multi_lan_ar",
        "multi_lan_ko",
        "multi_lan_ru",
        "multi_lan_th",
        "multi_lan_vi",
        "multi_lan_cs",
        "multi_lan_hu",
        "multi_lan_sr",
        "pdf",
    ],
)
class RuleHtmlTag(BaseRule):
    """check whether content has image links or html tags."""
    # Metadata for documentation generation
    _metric_info = {
        "category": "Rule-Based TEXT Quality Metrics",
        "quality_dimension": "EFFECTIVENESS",
        "metric_name": "RuleHtmlTag",
        "description": "Checks whether content contains HTML tags or image links indicating web scraping artifacts",
        "paper_title": "RedPajama: an Open Dataset for Training Large Language Models",
        "paper_url": "https://github.com/togethercomputer/RedPajama-Data",
        "paper_authors": "Together Computer, 2023",
        "evaluation_results": "docs/eval/rule/slimpajama_data_evaluated_by_rule.md"
    }
    dynamic_config = EvaluatorRuleArgs(
        key_list=["<img", "<p>", "</p>", "<o:p", "</o:p>"]
    )

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        res = EvalDetail(metric=cls.__name__)
        content = input_data.content
        if len(content) == 0:
            return res
        matches = re.findall("|".join(cls.dynamic_config.key_list), content)
        num = len(matches)
        if num / len(content) >= 0.01:
            res.status = True
            res.label = [f"{cls.metric_type}.{cls.__name__}"]
            res.reason = list(set(matches))
        else:
            res.label = [QualityLabel.QUALITY_GOOD]
        return res


@Model.rule_register("QUALITY_BAD_SECURITY", ["default", "pretrain", "benchmark"])
class RuleIDCard(BaseRule):
    """check if the content contains ID card."""
    # Metadata for documentation generation
    _metric_info = {
        "category": "Rule-Based TEXT Quality Metrics",
        "quality_dimension": "SECURITY",
        "metric_name": "RuleIDCard",
        "description": "Checks whether content contains ID card information",
        "paper_title": "RedPajama: an Open Dataset for Training Large Language Models",
        "paper_url": "https://github.com/togethercomputer/RedPajama-Data",
        "paper_authors": "Together Computer, 2023",
        "evaluation_results": "docs/eval/rule/slimpajama_data_evaluated_by_rule.md"
    }
    dynamic_config = EvaluatorRuleArgs(
        pattern=r"(身\s{0,10}份|id\s{0,10}number\s{0,10}|identification|identity|\s{0,10}ID\s{0,10}No\s{0,10}|id\s{0,10}card\s{0,10}|NRIC\s{0,10}number\s{0,10}|IC\s{0,10}number\s{0,10}|resident\s{0,10}registration\s{0,10}|I.D.\s{0,10}Number\s{0,10})"
    )

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        from dingo.model.rule.utils.util import Extractor
        res = EvalDetail(metric=cls.__name__)
        match = re.search(cls.dynamic_config.pattern, input_data.content, re.I)
        if match:
            person_id = Extractor().extract_id_card(input_data.content)
            if len(person_id) != 0:
                res.status = True
                res.label = [f"{cls.metric_type}.{cls.__name__}"]
                res.reason = [str(person_id)]
                return res
        res.label = [QualityLabel.QUALITY_GOOD]
        return res


@Model.rule_register(
    "QUALITY_BAD_EFFECTIVENESS",
    [
        "text_base_all",
        "multi_lan_ar",
        "multi_lan_ko",
        "multi_lan_ru",
        "multi_lan_th",
        "multi_lan_vi",
        "multi_lan_cs",
        "multi_lan_hu",
        "multi_lan_sr",
    ],
)
class RuleInvisibleChar(BaseRule):
    """check whether content has invisible chars."""
    # Metadata for documentation generation
    _metric_info = {
        "category": "Rule-Based TEXT Quality Metrics",
        "quality_dimension": "EFFECTIVENESS",
        "metric_name": "RuleInvisibleChar",
        "description": "Checks whether content contains invisible characters that may cause display issues",
        "paper_title": "RedPajama: an Open Dataset for Training Large Language Models",
        "paper_url": "https://github.com/togethercomputer/RedPajama-Data",
        "paper_authors": "Together Computer, 2023",
        "evaluation_results": "docs/eval/rule/slimpajama_data_evaluated_by_rule.md"
    }
    dynamic_config = EvaluatorRuleArgs(
        pattern=r"[\u2000-\u200F\u202F\u205F\u3000\uFEFF\u00A0\u2060-\u206F\uFEFF\xa0]"
    )

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        res = EvalDetail(metric=cls.__name__)
        content = input_data.content
        if len(content) == 0:
            return res
        matches = re.findall(cls.dynamic_config.pattern, content)
        num = len(matches)
        if num / len(content) >= 0.01:
            res.status = True
            res.label = [f"{cls.metric_type}.{cls.__name__}"]
            res.reason = [repr(s) for s in list(set(matches))]
        else:
            res.label = [QualityLabel.QUALITY_GOOD]
        return res


@Model.rule_register(
    "QUALITY_BAD_EFFECTIVENESS",
    [
        "multi_lan_ar",
        "multi_lan_ko",
        "multi_lan_ru",
        "multi_lan_th",
        "multi_lan_vi",
        "multi_lan_cs",
        "multi_lan_hu",
        "multi_lan_sr",
    ]
)
class RuleImageDataFormat(BaseRule):
    """check whether the nlp data format is right"""

    # Metadata for documentation generation
    _metric_info = {
        "category": "Rule-Based TEXT Quality Metrics",
        "quality_dimension": "EFFECTIVENESS",
        "metric_name": "RuleImageDataFormat",
        "description": "Check whether the image data format is right",
        "evaluation_results": ""
    }

    dynamic_config = EvaluatorRuleArgs()

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        res = EvalDetail(metric=cls.__name__)

        raw_data = input_data.raw_data
        key_list = ["img_id", "image"]
        if all(key in raw_data for key in key_list):
            res.label = [QualityLabel.QUALITY_GOOD]
        else:
            res.status = True
            res.label = [f"{cls.metric_type}.{cls.__name__}"]
            res.reason = ["Image Data format error"]
        return res


@Model.rule_register("QUALITY_BAD_EFFECTIVENESS", ["pdf_all"])
class RuleLatexSpecialChar(BaseRule):
    """check pdf content latex abnormal char."""
    # Metadata for documentation generation
    _metric_info = {
        "category": "Rule-Based TEXT Quality Metrics",
        "quality_dimension": "EFFECTIVENESS",
        "metric_name": "RuleLatexSpecialChar",
        "description": "Checks whether pdf content contains latex special characters",
        "paper_title": "RedPajama: an Open Dataset for Training Large Language Models",
        "paper_url": "https://github.com/togethercomputer/RedPajama-Data",
        "paper_authors": "Together Computer, 2023",
        "evaluation_results": "docs/eval/rule/slimpajama_data_evaluated_by_rule.md"
    }
    dynamic_config = EvaluatorRuleArgs(pattern=r"\$\$(.*?\!\!.*?)\$\$")

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        res = EvalDetail(metric=cls.__name__)
        content = input_data.content
        match = re.search(cls.dynamic_config.pattern, content)
        if match:
            res.status = True
            res.label = [f"{cls.metric_type}.{cls.__name__}"]
            res.reason = [match.group(0).strip("\n")]
        else:
            res.label = [QualityLabel.QUALITY_GOOD]
        return res


@Model.rule_register("QUALITY_BAD_COMPLETENESS", ["pretrain", "benchmark"])
class RuleLineEndWithEllipsis(BaseRule):
    """check whether the ratio of line ends with ellipsis < 0.3"""
    # Metadata for documentation generation
    _metric_info = {
        "category": "Rule-Based TEXT Quality Metrics",
        "quality_dimension": "COMPLETENESS",
        "metric_name": "RuleLineEndWithEllipsis",
        "description": "Checks whether the ratio of lines ending with ellipsis is below threshold",
        "paper_title": "RedPajama: an Open Dataset for Training Large Language Models",
        "paper_url": "https://github.com/togethercomputer/RedPajama-Data",
        "paper_authors": "Together Computer, 2023",
        "evaluation_results": "docs/eval/rule/slimpajama_data_evaluated_by_rule.md"
    }
    dynamic_config = EvaluatorRuleArgs(threshold=0.3, key_list=["...", "…"])

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        from dingo.model.rule.utils.util import TextSlice, split_paragraphs
        res = EvalDetail(metric=cls.__name__)
        raw_content = input_data.content
        raw_lines: Tuple[TextSlice] = split_paragraphs(
            text=raw_content, normalizer=lambda x: x, remove_empty=True
        )
        num_lines = len(raw_lines)
        if num_lines == 0:
            return res
        num_occurrences = sum(
            [
                line.text.rstrip().endswith(tuple(cls.dynamic_config.key_list))
                for line in raw_lines
            ]
        )
        ratio = num_occurrences / num_lines
        if ratio > cls.dynamic_config.threshold:
            res.status = True
            res.label = [f"{cls.metric_type}.{cls.__name__}"]
            res.reason = ["The ratio of lines end with ellipsis is: " + str(ratio)]
        else:
            res.label = [QualityLabel.QUALITY_GOOD]
        return res


@Model.rule_register("QUALITY_BAD_COMPLETENESS", ["pretrain"])
class RuleLineEndWithTerminal(BaseRule):
    """check whether the ratio of line ends with terminal punctuation mark > 0.6"""
    # Metadata for documentation generation
    _metric_info = {
        "category": "Rule-Based TEXT Quality Metrics",
        "quality_dimension": "COMPLETENESS",
        "metric_name": "RuleLineEndWithTerminal",
        "description": "Checks whether the ratio of lines ending with terminal punctuation is above threshold",
        "paper_title": "RedPajama: an Open Dataset for Training Large Language Models",
        "paper_url": "https://github.com/togethercomputer/RedPajama-Data",
        "paper_authors": "Together Computer, 2023",
        "evaluation_results": "docs/eval/rule/slimpajama_data_evaluated_by_rule.md"
    }
    dynamic_config = EvaluatorRuleArgs(
        threshold=0.6, key_list=[".", "!", "?", '"', '"']
    )

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        from dingo.model.rule.utils.util import TextSlice, split_paragraphs
        res = EvalDetail(metric=cls.__name__)
        raw_content = input_data.content
        raw_lines: Tuple[TextSlice] = split_paragraphs(
            text=raw_content, normalizer=lambda x: x, remove_empty=True
        )
        num_lines = len(raw_lines)
        if num_lines == 0:
            return res
        terminal_marks = [
            line.text.rstrip()[-1]
            for line in raw_lines
            if line.text and line.text.rstrip()[-1] not in cls.dynamic_config.key_list
        ]
        num_occurrences = sum(
            [
                line.text.rstrip().endswith(tuple(cls.dynamic_config.key_list))
                for line in raw_lines
            ]
        )
        ratio = num_occurrences / num_lines
        if ratio < cls.dynamic_config.threshold:
            res.status = True
            res.label = [f"{cls.metric_type}.{cls.__name__}"]
            res.reason = list(set(terminal_marks))
        else:
            res.label = [QualityLabel.QUALITY_GOOD]
        return res


@Model.rule_register("QUALITY_BAD_UNDERSTANDABILITY", ["sft", "pretrain", "benchmark"])
class RuleLineStartWithBulletpoint(BaseRule):
    """check whether the ratio of line starts with bullet points < 0.9"""
    # Metadata for documentation generation
    _metric_info = {
        "category": "Rule-Based TEXT Quality Metrics",
        "quality_dimension": "UNDERSTANDABILITY",
        "metric_name": "RuleLineStartWithBulletpoint",
        "description": "Checks whether the ratio of lines starting with bullet points is below threshold",
        "paper_title": "RedPajama: an Open Dataset for Training Large Language Models",
        "paper_url": "https://github.com/togethercomputer/RedPajama-Data",
        "paper_authors": "Together Computer, 2023",
        "evaluation_results": "docs/eval/rule/slimpajama_data_evaluated_by_rule.md"
    }
    dynamic_config = EvaluatorRuleArgs(
        threshold=0.9,
        key_list=[
            "\u2022",  # bullet point
            "\u2023",  # triangular bullet point
            "\u25B6",  # black right pointing triangle
            "\u25C0",  # black left pointing triangle
            "\u25E6",  # white bullet point
            "\u25A0",  # black square
            "\u25A1",  # white square
            "\u25AA",  # black small square
            "\u25AB",  # white small square
            "\u2013",  # en dash
        ],
    )

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        from dingo.model.rule.utils.util import TextSlice, split_paragraphs
        res = EvalDetail(metric=cls.__name__)
        raw_content = input_data.content
        raw_lines: Tuple[TextSlice] = split_paragraphs(
            text=raw_content, normalizer=lambda x: x, remove_empty=True
        )
        num_lines = len(raw_lines)
        if num_lines == 0:
            return res
        num_occurrences = sum(
            [
                line.text.lstrip().startswith(tuple(cls.dynamic_config.key_list))
                for line in raw_lines
            ]
        )
        ratio = num_occurrences / num_lines
        if ratio > cls.dynamic_config.threshold:
            res.status = True
            res.label = [f"{cls.metric_type}.{cls.__name__}"]
            res.reason = ["The ratio of lines start with bulletpoint is: " + str(ratio)]
        else:
            res.label = [QualityLabel.QUALITY_GOOD]
        return res


@Model.rule_register("QUALITY_BAD_EFFECTIVENESS", ["pretrain", "benchmark"])
class RuleLineJavascriptCount(BaseRule):
    """check whether line with the word Javascript."""
    # Metadata for documentation generation
    _metric_info = {
        "category": "Rule-Based TEXT Quality Metrics",
        "quality_dimension": "EFFECTIVENESS",
        "metric_name": "RuleJavascriptCount",
        "description": "Checks whether content contains excessive Javascript-related text",
        "paper_title": "RedPajama: an Open Dataset for Training Large Language Models",
        "paper_url": "https://github.com/togethercomputer/RedPajama-Data",
        "paper_authors": "Together Computer, 2023",
        "evaluation_results": "docs/eval/rule/slimpajama_data_evaluated_by_rule.md"
    }
    dynamic_config = EvaluatorRuleArgs(threshold=3)

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        from dingo.model.rule.utils.util import TextSlice, normalize, split_paragraphs
        res = EvalDetail(metric=cls.__name__)
        raw_content = input_data.content
        normalized_lines: Tuple[TextSlice] = split_paragraphs(
            text=raw_content, normalizer=normalize, remove_empty=True
        )
        num_lines = len(normalized_lines)
        if num_lines == 0:
            return res
        num_occurrences = sum(["javascript" in line.text for line in normalized_lines])
        num_not_occur = num_lines - num_occurrences
        if num_not_occur < cls.dynamic_config.threshold and num_lines > 3:
            res.status = True
            res.label = [f"{cls.metric_type}.{cls.__name__}"]
            res.reason = [
                "The lines with the word Javascript is: " + str(num_occurrences)
            ]
        else:
            res.label = [QualityLabel.QUALITY_GOOD]
        return res


@Model.rule_register("QUALITY_BAD_EFFECTIVENESS", ["pretrain", "benchmark"])
class RuleLoremIpsum(BaseRule):
    """check whether the ratio of lorem ipsum < 3e-08"""
    # Metadata for documentation generation
    _metric_info = {
        "category": "Rule-Based TEXT Quality Metrics",
        "quality_dimension": "EFFECTIVENESS",
        "metric_name": "RuleLoremIpsum",
        "description": "Checks whether content contains lorem ipsum placeholder text",
        "paper_title": "RedPajama: an Open Dataset for Training Large Language Models",
        "paper_url": "https://github.com/togethercomputer/RedPajama-Data",
        "paper_authors": "Together Computer, 2023",
        "evaluation_results": "docs/eval/rule/slimpajama_data_evaluated_by_rule.md"
    }
    dynamic_config = EvaluatorRuleArgs(threshold=3e-08)

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        from dingo.model.rule.utils.util import normalize
        res = EvalDetail(metric=cls.__name__)
        normalized_content = normalize(input_data.content)
        num_normalized_content = len(normalized_content)
        if num_normalized_content == 0:
            return res
        SEARCH_REGEX = re.compile(r"lorem ipsum", re.IGNORECASE)
        num_occurrences = len(SEARCH_REGEX.findall(normalized_content))
        ratio = num_occurrences / num_normalized_content
        if ratio > cls.dynamic_config.threshold:
            res.status = True
            res.label = [f"{cls.metric_type}.{cls.__name__}"]
            res.reason = ["The ratio of lorem ipsum is: " + str(ratio)]
        else:
            res.label = [QualityLabel.QUALITY_GOOD]
        return res


@Model.rule_register("QUALITY_BAD_EFFECTIVENESS", ["pretrain"])
class RuleMeanWordLength(BaseRule):
    """check whether the mean length of word in [3, 10]"""
    # Metadata for documentation generation
    _metric_info = {
        "category": "Rule-Based TEXT Quality Metrics",
        "quality_dimension": "EFFECTIVENESS",
        "metric_name": "RuleMeanWordLength",
        "description": "Checks whether the mean length of words is within acceptable range",
        "paper_title": "RedPajama: an Open Dataset for Training Large Language Models",
        "paper_url": "https://github.com/togethercomputer/RedPajama-Data",
        "paper_authors": "Together Computer, 2023",
        "evaluation_results": "docs/eval/rule/slimpajama_data_evaluated_by_rule.md"
    }
    dynamic_config = EvaluatorRuleArgs(key_list=["3", "10"])

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        from dingo.model.rule.utils.util import normalize
        res = EvalDetail(metric=cls.__name__)
        normalized_content = normalize(input_data.content)
        normalized_words = tuple(normalized_content.split())
        num_normalized_words = len(normalized_words)
        if num_normalized_words == 0:
            return res
        num_chars = float(sum(map(len, normalized_words)))
        mean_length = num_chars / num_normalized_words
        mean_length = round(mean_length, 2)
        if mean_length >= int(cls.dynamic_config.key_list[0]) and mean_length < int(cls.dynamic_config.key_list[1]):
            res.label = [QualityLabel.QUALITY_GOOD]
        else:
            res.status = True
            res.label = [f"{cls.metric_type}.{cls.__name__}"]
            res.reason = ["The mean length of word is: " + str(mean_length)]
        return res


@Model.rule_register(
    "QUALITY_BAD_EFFECTIVENESS",
    [
        "multi_lan_ar",
        "multi_lan_ko",
        "multi_lan_ru",
        "multi_lan_th",
        "multi_lan_vi",
        "multi_lan_cs",
        "multi_lan_hu",
        "multi_lan_sr",
    ]
)
class RuleNlpDataFormat(BaseRule):
    """check whether the nlp data format is right"""

    # Metadata for documentation generation
    _metric_info = {
        "category": "Rule-Based TEXT Quality Metrics",
        "quality_dimension": "EFFECTIVENESS",
        "metric_name": "RuleNlpDataFormat",
        "description": "Check whether the nlp data format is right",
        "evaluation_results": ""
    }

    dynamic_config = EvaluatorRuleArgs()

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        res = EvalDetail(metric=cls.__name__)

        raw_data = input_data.raw_data
        key_list = ["track_id", "content"]
        if all(key in raw_data for key in key_list):
            res.label = [QualityLabel.QUALITY_GOOD]
        else:
            res.status = True
            res.label = [f"{cls.metric_type}.{cls.__name__}"]
            res.reason = ["NLP Data format error"]
        return res


@Model.rule_register(
    "QUALITY_BAD_FLUENCY",
    [
        "default",
        "sft",
        "pretrain",
        "benchmark",
        "text_base_all",
        "llm_base",
        "multi_lan_ar",
        "multi_lan_ko",
        "multi_lan_ru",
        "multi_lan_th",
        "multi_lan_vi",
        "multi_lan_cs",
        "multi_lan_hu",
        "multi_lan_sr",
    ],
)
class RuleNoPunc(BaseRule):
    """check whether paragraph has no punctuation."""
    # Metadata for documentation generation
    _metric_info = {
        "category": "Rule-Based TEXT Quality Metrics",
        "quality_dimension": "FLUENCY",
        "metric_name": "RuleNoPunc",
        "description": "Checks whether paragraphs lack punctuation marks, indicating poor text quality",
        "paper_title": "RedPajama: an Open Dataset for Training Large Language Models",
        "paper_url": "https://github.com/togethercomputer/RedPajama-Data",
        "paper_authors": "Together Computer, 2023",
        "evaluation_results": "docs/eval/rule/slimpajama_data_evaluated_by_rule.md"
    }

    dynamic_config = EvaluatorRuleArgs(threshold=112)

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        res = EvalDetail(metric=cls.__name__)
        content = input_data.content
        paragraphs = content.split("\n")
        longest_sentence = ""
        max_word_count = 0
        for paragraph in paragraphs:
            if len(paragraph.strip()) == 0:
                continue
            sentences = re.split("[–.!?,;•/|…]", paragraph)
            for sentence in sentences:
                words = sentence.split()
                word_count = len(words)
                if word_count > max_word_count:
                    max_word_count = word_count
                    longest_sentence = sentence.strip()
        if int(max_word_count) > cls.dynamic_config.threshold:
            res.status = True
            res.label = [f"{cls.metric_type}.{cls.__name__}"]
            res.reason = [longest_sentence]
        else:
            res.label = [QualityLabel.QUALITY_GOOD]
        return res


@Model.rule_register("QUALITY_BAD_RELEVANCE", [])
class RulePatternSearch(BaseRule):
    """let user input pattern to search"""
    # Metadata for documentation generation
    _metric_info = {
        "category": "Rule-Based TEXT Quality Metrics",
        "quality_dimension": "RELEVANCE",
        "metric_name": "RulePatternSearch",
        "description": "Checks whether content contains specific pattern",
        "paper_title": "RedPajama: an Open Dataset for Training Large Language Models",
        "paper_url": "https://github.com/togethercomputer/RedPajama-Data",
        "paper_authors": "Together Computer, 2023",
        "evaluation_results": "docs/eval/rule/slimpajama_data_evaluated_by_rule.md"
    }
    dynamic_config = EvaluatorRuleArgs(pattern="your pattern")

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        res = EvalDetail(metric=cls.__name__)
        matches = re.findall(cls.dynamic_config.pattern, input_data.content)
        if matches:
            res.status = True
            res.label = [f"{cls.metric_type}.{cls.__name__}"]
            res.reason = matches
        else:
            res.label = [QualityLabel.QUALITY_GOOD]
        return res


@Model.rule_register("QUALITY_BAD_COMPLETENESS", ["pretrain"])
class RuleSentenceNumber(BaseRule):
    """check whether the number of sentence in [3, 7500]"""
    # Metadata for documentation generation
    _metric_info = {
        "category": "Rule-Based TEXT Quality Metrics",
        "quality_dimension": "COMPLETENESS",
        "metric_name": "RuleSentenceNumber",
        "description": "Checks whether the number of sentences is within acceptable range",
        "paper_title": "RedPajama: an Open Dataset for Training Large Language Models",
        "paper_url": "https://github.com/togethercomputer/RedPajama-Data",
        "paper_authors": "Together Computer, 2023",
        "evaluation_results": "docs/eval/rule/slimpajama_data_evaluated_by_rule.md"
    }
    dynamic_config = EvaluatorRuleArgs(key_list=["3", "7500"])

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        res = EvalDetail(metric=cls.__name__)
        raw_content = input_data.content
        SENT_PATTERN = re.compile(r"\b[^.!?\n]+[.!?]*", flags=re.UNICODE)
        num_sentence = len(SENT_PATTERN.findall(raw_content))
        if num_sentence < int(cls.dynamic_config.key_list[0]) or num_sentence > int(
            cls.dynamic_config.key_list[1]
        ):
            res.status = True
            res.label = [f"{cls.metric_type}.{cls.__name__}"]
            res.reason = ["The number of sentence is: " + str(num_sentence)]
        else:
            res.label = [QualityLabel.QUALITY_GOOD]
        return res


@Model.rule_register(
    "QUALITY_BAD_EFFECTIVENESS",
    [
        "multi_lan_ar",
        "multi_lan_ko",
        "multi_lan_ru",
        "multi_lan_th",
        "multi_lan_vi",
        "multi_lan_cs",
        "multi_lan_hu",
        "multi_lan_sr",
    ]
)
class RuleSftDataFormat(BaseRule):
    """check whether the nlp data format is right"""

    # Metadata for documentation generation
    _metric_info = {
        "category": "Rule-Based TEXT Quality Metrics",
        "quality_dimension": "EFFECTIVENESS",
        "metric_name": "RuleSftDataFormat",
        "description": "Check whether the sft data format is right",
        "evaluation_results": ""
    }

    dynamic_config = EvaluatorRuleArgs()

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        res = EvalDetail(metric=cls.__name__)

        raw_data = input_data.raw_data
        key_list = ["track_id", "type", "prompt", "completion"]
        if all(key in raw_data for key in key_list):
            res.label = [QualityLabel.QUALITY_GOOD]
        else:
            res.status = True
            res.label = [f"{cls.metric_type}.{cls.__name__}"]
            res.reason = ["SFT Data format error"]
        return res


@Model.rule_register(
    "QUALITY_BAD_EFFECTIVENESS",
    [
        "text_base_all",
        "llm_base",
        "multi_lan_ar",
        "multi_lan_ko",
        "multi_lan_ru",
        "multi_lan_th",
        "multi_lan_vi",
        "multi_lan_cs",
        "multi_lan_hu",
        "multi_lan_sr",
        "pdf",
    ],
)
class RuleSpaceMore(BaseRule):
    """check whether content has 500 spaces."""
    # Metadata for documentation generation
    _metric_info = {
        "category": "Rule-Based TEXT Quality Metrics",
        "quality_dimension": "EFFECTIVENESS",
        "metric_name": "RuleSpaceMore",
        "description": "Checks whether content contains excessive consecutive spaces",
        "paper_title": "RedPajama: an Open Dataset for Training Large Language Models",
        "paper_url": "https://github.com/togethercomputer/RedPajama-Data",
        "paper_authors": "Together Computer, 2023",
        "evaluation_results": "docs/eval/rule/slimpajama_data_evaluated_by_rule.md"
    }
    dynamic_config = EvaluatorRuleArgs(pattern=" {500,}")

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        res = EvalDetail(metric=cls.__name__)
        content = input_data.content
        SEARCH_REGEX = re.compile(cls.dynamic_config.pattern)
        match = SEARCH_REGEX.search(content)
        if match:
            res.status = True
            res.label = [f"{cls.metric_type}.{cls.__name__}"]
            res.reason = ["Content has 500 spaces."]
        else:
            res.label = [QualityLabel.QUALITY_GOOD]
        return res


@Model.rule_register(
    "QUALITY_BAD_EFFECTIVENESS",
    [
        "default",
        "sft",
        "pretrain",
        "benchmark",
        "text_base_all",
        "llm_base",
        "multi_lan_ar",
        "multi_lan_ko",
        "multi_lan_ru",
        "multi_lan_th",
        "multi_lan_vi",
        "multi_lan_cs",
        "multi_lan_hu",
        "multi_lan_sr",
        "pdf",
    ],
)
class RuleSpecialCharacter(BaseRule):
    """check whether content has special characters."""
    # Metadata for documentation generation
    _metric_info = {
        "category": "Rule-Based TEXT Quality Metrics",
        "quality_dimension": "EFFECTIVENESS",
        "metric_name": "RuleSpecialCharacter",
        "description": "Checks if data is meaningful and properly formatted by detecting excessive special characters",
        "paper_title": "RedPajama: an Open Dataset for Training Large Language Models",
        "paper_url": "https://github.com/togethercomputer/RedPajama-Data",
        "paper_authors": "Together Computer, 2023",
        "evaluation_results": "docs/eval/rule/slimpajama_data_evaluated_by_rule.md"
    }
    dynamic_config = EvaluatorRuleArgs(
        key_list=[
            r"u200e",
            # r"(\\\\;){3,}|(\{\}){3,}|(&nbsp;){3,}",
            r"&#247;|\? :",
            r"[�□]|\{\/U\}",
            r"U\+26[0-F][0-D]|U\+273[3-4]|U\+1F[3-6][0-4][0-F]|U\+1F6[8-F][0-F]",
            r"<\|.*?\|>",
        ]
    )

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        res = EvalDetail(metric=cls.__name__)
        content = input_data.content
        if len(content) == 0:
            return res
        matches = []
        num = 0
        for p in cls.dynamic_config.key_list:
            m = re.findall(p, content)
            num += len(m)
            matches = matches + m
        if num / len(content) >= 0.01:
            # res.eval_status = True
            # res.eval_details = {
            #     "label": [f"{cls.metric_type}.{cls.__name__}"],
            #     "metric": [cls.__name__],
            #     "reason": list(set(matches))
            # }
            res.status = True
            res.label = [f"{cls.metric_type}.{cls.__name__}"]
            res.reason = list(set(matches))
        else:
            # res.eval_details = {
            #     "label": [QualityLabel.QUALITY_GOOD]
            # }
            res.label = [QualityLabel.QUALITY_GOOD]
        return res


@Model.rule_register("QUALITY_BAD_EFFECTIVENESS", ["pretrain"])
class RuleStopWord(BaseRule):
    """check whether the ratio of stop word > 0.06"""
    # Metadata for documentation generation
    _metric_info = {
        "category": "Rule-Based TEXT Quality Metrics",
        "quality_dimension": "EFFECTIVENESS",
        "metric_name": "RuleStopWord",
        "description": "Checks whether the ratio of stop words is above threshold",
        "paper_title": "RedPajama: an Open Dataset for Training Large Language Models",
        "paper_url": "https://github.com/togethercomputer/RedPajama-Data",
        "paper_authors": "Together Computer, 2023",
        "evaluation_results": "docs/eval/rule/slimpajama_data_evaluated_by_rule.md"
    }
    dynamic_config = EvaluatorRuleArgs(threshold=0.06)

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        from nltk.tokenize import WordPunctTokenizer

        from dingo.model.rule.utils.util import get_stop_words
        res = EvalDetail(metric=cls.__name__)
        raw_content = input_data.content
        raw_words = list(WordPunctTokenizer().tokenize(raw_content))
        raw_words = [str(w).lower() for w in raw_words]
        num_raw_words = len(raw_words)
        if num_raw_words == 0:
            return res
        STOP_WORDS = get_stop_words("en")
        num_stop_words = len(list(filter(lambda word: word in STOP_WORDS, raw_words)))
        ratio = num_stop_words / num_raw_words
        if ratio < cls.dynamic_config.threshold or num_stop_words < 2:
            res.status = True
            res.label = [f"{cls.metric_type}.{cls.__name__}"]
            res.reason = ["The ratio of stop words is: " + str(ratio)]
        else:
            res.label = [QualityLabel.QUALITY_GOOD]
        return res


@Model.rule_register("QUALITY_BAD_EFFECTIVENESS", ["pretrain", "benchmark"])
class RuleSymbolWordRatio(BaseRule):
    """check whether the ratio of symbol and word is > 0.4"""
    # Metadata for documentation generation
    _metric_info = {
        "category": "Rule-Based TEXT Quality Metrics",
        "quality_dimension": "UNDERSTANDABILITY",
        "metric_name": "RuleSymbolWordRatio",
        "description": "Checks whether the ratio of symbols to words is above threshold",
        "paper_title": "RedPajama: an Open Dataset for Training Large Language Models",
        "paper_url": "https://github.com/togethercomputer/RedPajama-Data",
        "paper_authors": "Together Computer, 2023",
        "evaluation_results": "docs/eval/rule/slimpajama_data_evaluated_by_rule.md"
    }
    dynamic_config = EvaluatorRuleArgs(threshold=0.4, key_list=["#", "...", "…"])

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        from nltk.tokenize import WordPunctTokenizer
        res = EvalDetail(metric=cls.__name__)
        raw_content = input_data.content
        raw_words = tuple(WordPunctTokenizer().tokenize(raw_content))
        num_raw_words = len(raw_words)
        if num_raw_words == 0:
            return res
        num_words = num_raw_words
        num_symbols = float(
            sum(raw_content.count(x) for x in cls.dynamic_config.key_list)
        )
        ratio = num_symbols / num_words
        if ratio > cls.dynamic_config.threshold:
            res.status = True
            res.label = [f"{cls.metric_type}.{cls.__name__}"]
            res.reason = ["The ratio of symbol / word is: " + str(ratio)]
        else:
            res.label = [QualityLabel.QUALITY_GOOD]
        return res


@Model.rule_register("QUALITY_BAD_UNDERSTANDABILITY", ["pretrain"])
class RuleUniqueWords(BaseRule):
    """check whether the ratio of unique words > 0.1"""
    # Metadata for documentation generation
    _metric_info = {
        "category": "Rule-Based TEXT Quality Metrics",
        "quality_dimension": "UNDERSTANDABILITY",
        "metric_name": "RuleUniqueWordsRatio",
        "description": "Checks whether the ratio of unique words is above threshold",
        "paper_title": "RedPajama: an Open Dataset for Training Large Language Models",
        "paper_url": "https://github.com/togethercomputer/RedPajama-Data",
        "paper_authors": "Together Computer, 2023",
        "evaluation_results": "docs/eval/rule/slimpajama_data_evaluated_by_rule.md"
    }
    dynamic_config = EvaluatorRuleArgs(threshold=0.1)

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        from dingo.model.rule.utils.util import normalize
        res = EvalDetail(metric=cls.__name__)
        normalized_content = normalize(input_data.content)
        normalized_words = tuple(normalized_content.split())
        num_normalized_words = len(normalized_words)
        if num_normalized_words == 0:
            return res
        num_words = num_normalized_words
        num_unique_words = len(set(normalized_words))
        ratio = num_unique_words / num_words
        if ratio > cls.dynamic_config.threshold:
            res.label = [QualityLabel.QUALITY_GOOD]
        else:
            res.status = True
            res.label = [f"{cls.metric_type}.{cls.__name__}"]
            res.reason = ["The ratio of unique words is: " + str(ratio)]
        return res


@Model.rule_register("QUALITY_BAD_SECURITY", [])
class RuleUnsafeWords(BaseRule):
    """check whether content contains unsafe words."""
    # Metadata for documentation generation
    _metric_info = {
        "category": "Rule-Based TEXT Quality Metrics",
        "quality_dimension": "SECURITY",
        "metric_name": "RuleUnsafeWords",
        "description": "Checks whether content contains unsafe words",
        "paper_title": "RedPajama: an Open Dataset for Training Large Language Models",
        "paper_url": "https://github.com/togethercomputer/RedPajama-Data",
        "paper_authors": "Together Computer, 2023",
        "evaluation_results": "docs/eval/rule/slimpajama_data_evaluated_by_rule.md"
    }
    dynamic_config = EvaluatorRuleArgs(refer_path=[])

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:

        import ahocorasick

        from dingo.model.rule.utils.util import get_unsafe_words

        res = EvalDetail(metric=cls.__name__)
        content = input_data.content
        key_list = cls.dynamic_config.key_list
        if key_list is None:
            key_list = get_unsafe_words(cls.dynamic_config.refer_path)

        A = ahocorasick.Automaton()
        for index, key in enumerate(key_list):
            A.add_word(key, (index, key))
        A.make_automaton()

        matches = []
        for end_index, (index, keyword) in A.iter(content):
            start_index = end_index - len(keyword) + 1

            # 检查单词边界
            if cls._is_whole_word(content, start_index, end_index):
                matches.append((start_index, keyword))

        if matches:
            res.status = True
            res.label = [f"{cls.metric_type}.{cls.__name__}"]
            res.reason = [value for index, value in matches]
        else:
            res.label = [QualityLabel.QUALITY_GOOD]
        return res

    @classmethod
    def _is_whole_word(cls, text: str, start: int, end: int) -> bool:
        """检查匹配是否是一个完整的单词"""
        # 检查左侧边界
        if start > 0 and text[start - 1].isalnum():
            return False

        # 检查右侧边界
        if end < len(text) - 1 and text[end + 1].isalnum():
            return False

        return True


@Model.rule_register(
    "QUALITY_BAD_EFFECTIVENESS",
    [
        "multi_lan_ar",
        "multi_lan_ko",
        "multi_lan_ru",
        "multi_lan_th",
        "multi_lan_vi",
        "multi_lan_cs",
        "multi_lan_hu",
        "multi_lan_sr",
    ]
)
class RuleVedioDataFormat(BaseRule):
    """check whether the vedio data format is right"""
    # Metadata for documentation generation
    _metric_info = {
        "category": "Rule-Based TEXT Quality Metrics",
        "quality_dimension": "EFFECTIVENESS",
        "metric_name": "RuleVedioDataFormat",
        "description": "Check whether the vedio data format is right",
        "evaluation_results": ""
    }
    dynamic_config = EvaluatorRuleArgs()

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        res = EvalDetail(metric=cls.__name__)
        raw_data = input_data.raw_data
        key_list = ["id", "video", "text"]
        if all(key in raw_data for key in key_list):
            res.label = [QualityLabel.QUALITY_GOOD]
        else:
            res.status = True
            res.label = [f"{cls.metric_type}.{cls.__name__}"]
            res.reason = ["Vedio Data format error"]
        return res


@Model.rule_register(
    "QUALITY_BAD_EFFECTIVENESS",
    [
        "text_base_all",
        "llm_base",
        "multi_lan_ar",
        "multi_lan_ko",
        "multi_lan_ru",
        "multi_lan_th",
        "multi_lan_vi",
        "multi_lan_cs",
        "multi_lan_hu",
        "multi_lan_sr",
        "qa_standard_v1",
        "pdf",
    ],
)
class RuleOnlyUrl(BaseRule):
    """check whether content is only an url link."""
    # Metadata for documentation generation
    _metric_info = {
        "category": "Rule-Based TEXT Quality Metrics",
        "quality_dimension": "EFFECTIVENESS",
        "metric_name": "RuleOnlyUrl",
        "description": "Checks whether content consists only of URLs without meaningful text",
        "paper_title": "RedPajama: an Open Dataset for Training Large Language Models",
        "paper_url": "https://github.com/togethercomputer/RedPajama-Data",
        "paper_authors": "Together Computer, 2023",
        "evaluation_results": "docs/eval/rule/slimpajama_data_evaluated_by_rule.md"
    }
    dynamic_config = EvaluatorRuleArgs(
        pattern=r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"
    )

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        res = EvalDetail(metric=cls.__name__)
        content = input_data.content
        if len(content.strip()) == 0:
            return res
        SEARCH_REGEX = re.compile(cls.dynamic_config.pattern)
        content_without_url = SEARCH_REGEX.sub("", content)
        if len(content_without_url.strip()) == 0:
            res.status = True
            res.label = [f"{cls.metric_type}.{cls.__name__}"]
            res.reason = ["Content is only an url link."]
        else:
            res.label = [QualityLabel.QUALITY_GOOD]
        return res


@Model.rule_register("QUALITY_BAD_RELEVANCE", [])
class RuleWatermark(BaseRule):
    """check whether content has watermarks."""
    # Metadata for documentation generation
    _metric_info = {
        "category": "Rule-Based TEXT Quality Metrics",
        "quality_dimension": "RELEVANCE",
        "metric_name": "RuleWatermark",
        "description": "Checks whether content has watermarks",
        "paper_title": "RedPajama: an Open Dataset for Training Large Language Models",
        "paper_url": "https://github.com/togethercomputer/RedPajama-Data",
        "paper_authors": "Together Computer, 2023",
        "evaluation_results": "docs/eval/rule/slimpajama_data_evaluated_by_rule.md"
    }
    dynamic_config = EvaluatorRuleArgs(key_list=[])

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        res = EvalDetail(metric=cls.__name__)
        matches = re.findall("|".join(cls.dynamic_config.key_list), input_data.content)
        if matches:
            res.status = True
            res.label = [f"{cls.metric_type}.{cls.__name__}"]
            res.reason = matches
        else:
            res.label = [QualityLabel.QUALITY_GOOD]
        return res


@Model.rule_register("QUALITY_BAD_COMPLETENESS", ["pretrain"])
class RuleWordNumber(BaseRule):
    """check whether the number of word in [20, 100000]"""
    # Metadata for documentation generation
    _metric_info = {
        "category": "Rule-Based TEXT Quality Metrics",
        "quality_dimension": "COMPLETENESS",
        "metric_name": "RuleWordNumber",
        "description": "Checks whether the number of words is within acceptable range",
        "paper_title": "RedPajama: an Open Dataset for Training Large Language Models",
        "paper_url": "https://github.com/togethercomputer/RedPajama-Data",
        "paper_authors": "Together Computer, 2023",
        "evaluation_results": "docs/eval/rule/slimpajama_data_evaluated_by_rule.md"
    }
    dynamic_config = EvaluatorRuleArgs(key_list=["20", "100000"])

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        from dingo.model.rule.utils.util import normalize
        res = EvalDetail(metric=cls.__name__)
        normalized_content = normalize(input_data.content)
        normalized_words = tuple(normalized_content.split())
        num_normalized_words = len(normalized_words)
        if num_normalized_words >= int(
            cls.dynamic_config.key_list[0]
        ) and num_normalized_words < int(cls.dynamic_config.key_list[1]):
            res.label = [QualityLabel.QUALITY_GOOD]
        else:
            res.status = True
            res.label = [f"{cls.metric_type}.{cls.__name__}"]
            res.reason = ["The number of word is: " + str(num_normalized_words)]
        return res


@Model.rule_register("QUALITY_BAD_FLUENCY", ["pdf_all"])
class RuleWordSplit(BaseRule):
    """check pdf word abnormal split such as "ca- se"."""
    # Metadata for documentation generation
    _metric_info = {
        "category": "Rule-Based TEXT Quality Metrics",
        "quality_dimension": "FLUENCY",
        "metric_name": "RuleWordSplit",
        "description": "Checks for abnormal word splits in PDF content that disrupt readability",
        "paper_title": "RedPajama: an Open Dataset for Training Large Language Models",
        "paper_url": "https://github.com/togethercomputer/RedPajama-Data",
        "paper_authors": "Together Computer, 2023",
        "evaluation_results": "docs/eval/rule/slimpajama_data_evaluated_by_rule.md"
    }
    dynamic_config = EvaluatorRuleArgs(pattern=r"[A-Za-z]+-\s*$")

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        res = EvalDetail(metric=cls.__name__)
        content = input_data.content
        match = re.findall(cls.dynamic_config.pattern, content)
        if match:
            res.status = True
            res.label = [f"{cls.metric_type}.{cls.__name__}"]
            res.reason = match
        else:
            res.label = [QualityLabel.QUALITY_GOOD]
        return res


@Model.rule_register(
    "QUALITY_BAD_FLUENCY",
    [
        "text_base_all",
        "llm_base",
        "multi_lan_ar",
        "multi_lan_ko",
        "multi_lan_ru",
        "multi_lan_th",
        "multi_lan_vi",
        "multi_lan_cs",
        "multi_lan_hu",
        "multi_lan_sr",
    ],
)
class RuleWordStuck(BaseRule):
    """check whether words are stuck."""
    # Metadata for documentation generation
    _metric_info = {
        "category": "Rule-Based TEXT Quality Metrics",
        "quality_dimension": "FLUENCY",
        "metric_name": "RuleWordStuck",
        "description": "Checks whether words are stuck together without proper spacing",
        "paper_title": "RedPajama: an Open Dataset for Training Large Language Models",
        "paper_url": "https://github.com/togethercomputer/RedPajama-Data",
        "paper_authors": "Together Computer, 2023",
        "evaluation_results": "docs/eval/rule/slimpajama_data_evaluated_by_rule.md"
    }
    dynamic_config = EvaluatorRuleArgs(
        key_list=[
            r"https?://[^\s]+|www.(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+",
            r"\.pdf$",
            r"\w+\.bat",
            r"(\/.*\/.*)",
            r"[01]+|[0-7]+|0x[0-9a-fA-F]+",
        ]
    )

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        import wordninja

        from dingo.model.rule.utils.detect_lang import decide_language_by_str
        from dingo.model.rule.utils.util import is_sha256
        res = EvalDetail(metric=cls.__name__)
        content = input_data.content
        for p in cls.dynamic_config.key_list:
            content = re.sub(p, "", content)
        word_list = [
            word.strip(string.punctuation)
            for word in re.split(
                r"[⁃>#%-.—,–!?;:\s|_/   =\\@\((.*?)\)\[(.*?)\]]\s*", content
            )
        ]
        for longest_string in word_list:
            if len(longest_string) > 45 and not is_sha256(longest_string):
                lan = decide_language_by_str(longest_string)
                cut = wordninja.split(longest_string)
                if lan == "en" and len(cut) > 1:
                    res.status = True
                    res.label = [f"{cls.metric_type}.{cls.__name__}"]
                    res.reason = [str(longest_string)]
                    return res
        res.label = [QualityLabel.QUALITY_GOOD]
        return res


@Model.rule_register("QUALITY_BAD_SECURITY", ["default", "pretrain", "benchmark"])
class RulePIIDetection(BaseRule):
    """检测文本中的个人身份信息（PII）- 基于 NIST SP 800-122 和中国《个人信息保护法》"""

    # Metadata for documentation generation
    _metric_info = {
        "category": "Rule-Based TEXT Quality Metrics",
        "quality_dimension": "SECURITY",
        "metric_name": "RulePIIDetection",
        "description": "Detects Personal Identifiable Information (PII) including ID cards, phone numbers, emails, and credit cards",
        "standard": "NIST SP 800-122, China Personal Information Protection Law",
        "reference_url": "https://nvlpubs.nist.gov/nistpubs/Legacy/SP/nistspecialpublication800-122.pdf",
        "evaluation_results": ""
    }

    # PII 检测模式配置（按严重程度排序）
    PII_PATTERNS = {
        # 1. 中国身份证号（18位）- 高风险
        "cn_id_card": {
            "pattern": r"\b[1-9]\d{5}(18|19|20)\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])\d{3}[0-9Xx]\b",
            "description": "Chinese ID Card",
            "description_zh": "中国身份证号",
            "severity": "high"
        },

        # 2. 信用卡号（13-19位，支持分隔符）- 高风险
        "credit_card": {
            "pattern": r"\b\d{4}(?:[-\s]?\d{4}){2}[-\s]?\d{1,7}\b",
            "description": "Credit Card Number",
            "description_zh": "信用卡号",
            "severity": "high",
            "validator": "_validate_luhn"
        },

        # 3. 中国手机号（11位）- 中风险
        "cn_phone": {
            "pattern": r"\b1[3-9]\d{9}\b",
            "description": "Chinese Mobile Phone",
            "description_zh": "中国手机号",
            "severity": "medium"
        },

        # 4. 电子邮件 - 中风险
        "email": {
            "pattern": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
            "description": "Email Address",
            "description_zh": "电子邮件",
            "severity": "medium"
        },

        # 5. 美国社会安全号（SSN）- 高风险
        "ssn": {
            "pattern": r"\b\d{3}-\d{2}-\d{4}\b",
            "description": "US Social Security Number",
            "description_zh": "美国社会安全号",
            "severity": "high"
        },

        # 6. 中国护照号（E/G/P开头+8位数字）- 高风险
        "cn_passport": {
            "pattern": r"\b[EGP]\d{8}\b",
            "description": "Chinese Passport Number",
            "description_zh": "中国护照号",
            "severity": "high"
        },

        # 7. IP 地址（IPv4）- 低风险
        "ip_address": {
            "pattern": r"\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b",
            "description": "IP Address",
            "description_zh": "IP地址",
            "severity": "low",
            "validator": "_validate_ip"
        }
    }

    @classmethod
    def _validate_luhn(cls, number: str) -> bool:
        """Luhn 算法验证信用卡号"""
        # 移除空格和连字符
        digits = [int(d) for d in number if d.isdigit()]

        if len(digits) < 13 or len(digits) > 19:
            return False

        checksum = 0
        reverse_digits = digits[::-1]

        for i, digit in enumerate(reverse_digits):
            if i % 2 == 1:
                digit *= 2
                if digit > 9:
                    digit -= 9
            checksum += digit

        return checksum % 10 == 0

    @classmethod
    def _validate_ip(cls, ip: str) -> bool:
        """验证 IP 地址合法性"""
        parts = ip.split('.')
        if len(parts) != 4:
            return False

        try:
            for part in parts:
                num = int(part)
                if num < 0 or num > 255:
                    return False
            return True
        except ValueError:
            return False

    @classmethod
    def _mask_email(cls, value: str) -> str:
        """邮箱脱敏：保留用户名首字母和域名"""
        if "@" in value:
            username, domain = value.split("@", 1)
            if len(username) <= 2:
                masked_username = "*" * len(username)
            else:
                masked_username = username[0] + "*" * (len(username) - 1)
            return f"{masked_username}@{domain}"
        return cls._mask_default(value)

    @classmethod
    def _mask_cn_phone(cls, value: str) -> str:
        """手机号脱敏：保留前3位和后4位"""
        if len(value) == 11:
            return value[:3] + "****" + value[-4:]
        return cls._mask_default(value)

    @classmethod
    def _mask_cn_id_card(cls, value: str) -> str:
        """身份证脱敏：保留前6位和后4位"""
        if len(value) == 18:
            return value[:6] + "********" + value[-4:]
        return cls._mask_default(value)

    @classmethod
    def _mask_credit_card(cls, value: str) -> str:
        """信用卡脱敏：只保留后4位"""
        digits = ''.join(c for c in value if c.isdigit())
        if len(digits) >= 4:
            return "*" * (len(digits) - 4) + digits[-4:]
        return "*" * len(digits)

    @classmethod
    def _mask_ip_address(cls, value: str) -> str:
        """IP地址脱敏：保留第一段和最后一段"""
        parts = value.split('.')
        if len(parts) == 4:
            return f"{parts[0]}.***.***.{parts[3]}"
        return cls._mask_default(value)

    @classmethod
    def _mask_default(cls, value: str) -> str:
        """默认脱敏策略：保留前3位和后4位"""
        if len(value) <= 7:
            return "*" * len(value)
        return value[:3] + "*" * (len(value) - 7) + value[-4:]

    @classmethod
    def _mask_pii(cls, value: str, pii_type: str) -> str:
        """
        脱敏处理：根据不同类型的 PII 采用不同的脱敏策略

        Args:
            value: 原始 PII 值
            pii_type: PII 类型

        Returns:
            脱敏后的值
        """
        # 使用字典分发策略
        strategies = {
            "email": cls._mask_email,
            "cn_phone": cls._mask_cn_phone,
            "cn_id_card": cls._mask_cn_id_card,
            "credit_card": cls._mask_credit_card,
            "ip_address": cls._mask_ip_address,
        }

        mask_func = strategies.get(pii_type, cls._mask_default)
        return mask_func(value)

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        res = EvalDetail(metric=cls.__name__)
        content = input_data.content

        detected_pii = []

        # 遍历所有 PII 模式进行检测
        for pii_type, config in cls.PII_PATTERNS.items():
            pattern = config["pattern"]
            matches = re.findall(pattern, content)

            for match in matches:
                # 如果有自定义验证器，进行额外验证
                if "validator" in config:
                    validator_method = getattr(cls, config["validator"], None)
                    if validator_method and not validator_method(match):
                        continue  # 验证失败，跳过

                # 脱敏处理
                masked_value = cls._mask_pii(match, pii_type)

                detected_pii.append({
                    "type": pii_type,
                    "value": masked_value,
                    "description": config.get("description_zh", config["description"]),
                    "severity": config["severity"]
                })

        # 如果检测到 PII，标记为 QUALITY_BAD
        if detected_pii:
            res.status = True
            res.label = [f"{cls.metric_type}.{cls.__name__}"]

            # 使用 defaultdict 按严重程度分组（一次遍历）
            from collections import defaultdict
            pii_by_severity = defaultdict(list)
            for item in detected_pii:
                pii_by_severity[item["severity"]].append(item)

            # 构建详细原因
            reasons = []
            severity_labels = {"high": "High Risk PII", "medium": "Medium Risk PII", "low": "Low Risk PII"}

            for severity in ["high", "medium", "low"]:
                if severity in pii_by_severity:
                    items = ', '.join([
                        "{desc}({val})".format(desc=item["description"], val=item["value"])
                        for item in pii_by_severity[severity]
                    ])
                    reasons.append(f"{severity_labels[severity]}: {items}")

            res.reason = reasons
        else:
            res.label = [QualityLabel.QUALITY_GOOD]

        return res


if __name__ == "__main__":
    data = Data(data_id="", prompt="", content="\n \n \n \n hello \n \n ")
    tmp = RuleEnterAndSpace().eval(data)
