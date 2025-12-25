import re

from dingo.config.input_args import EvaluatorRuleArgs
from dingo.io import Data
from dingo.io.output.eval_detail import EvalDetail, QualityLabel
from dingo.model.model import Model
from dingo.model.rule.base import BaseRule

# ========== Privacy Issues ==========


@Model.rule_register("RESUME_QUALITY_BAD_PRIVACY", ["default", "resume"])
class RuleResumeIDCard(BaseRule):
    """Check if the resume contains Chinese ID card number."""

    _metric_info = {
        "category": "Rule-Based RESUME Quality Metrics",
        "quality_dimension": "PRIVACY_SECURITY",
        "metric_name": "RuleResumeIDCard",
        "description": "Detects 18-digit Chinese ID card numbers in resume content",
        "severity": "critical",
        "paper_title": "N/A",
        "paper_url": "",
        "paper_authors": "Dingo Team",
        "evaluation_results": ""
    }

    dynamic_config = EvaluatorRuleArgs(pattern=r'\b\d{17}[\dXx]\b')

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        res = EvalDetail(metric=cls.__name__)
        content = input_data.content
        match = re.search(cls.dynamic_config.pattern, content)
        if match:
            res.status = True
            res.label = [f"{cls.metric_type}.{cls.__name__}"]
            res.reason = ["Found ID card number: " + match.group(0)[:6] + "****" + match.group(0)[-4:]]
        else:
            res.label = [QualityLabel.QUALITY_GOOD]
        return res


@Model.rule_register("RESUME_QUALITY_BAD_PRIVACY", ["default", "resume"])
class RuleResumeDetailedAddress(BaseRule):
    """Check if the resume contains detailed address information."""

    _metric_info = {
        "category": "Rule-Based RESUME Quality Metrics",
        "quality_dimension": "PRIVACY_SECURITY",
        "metric_name": "RuleResumeDetailedAddress",
        "description": "Detects detailed address patterns that may leak privacy",
        "severity": "high",
        "paper_title": "N/A",
        "paper_url": "",
        "paper_authors": "Dingo Team",
        "evaluation_results": ""
    }

    dynamic_config = EvaluatorRuleArgs(pattern=r'(省|市|区|县|镇|街道|路|号|室|栋|单元|楼).{0,20}(省|市|区|县|镇|街道|路|号|室|栋|单元|楼)')

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        res = EvalDetail(metric=cls.__name__)
        content = input_data.content
        match = re.search(cls.dynamic_config.pattern, content)
        if match:
            res.status = True
            res.label = [f"{cls.metric_type}.{cls.__name__}"]
            res.reason = ["Found detailed address: " + match.group(0)]
        else:
            res.label = [QualityLabel.QUALITY_GOOD]
        return res


# ========== Contact Information Issues ==========


@Model.rule_register("RESUME_QUALITY_BAD_CONTACT", ["default", "resume"])
class RuleResumeEmailMissing(BaseRule):
    """Check if the resume is missing email address."""

    _metric_info = {
        "category": "Rule-Based RESUME Quality Metrics",
        "quality_dimension": "CONTENT_COMPLETENESS",
        "metric_name": "RuleResumeEmailMissing",
        "description": "Checks if resume contains a valid email address",
        "severity": "high",
        "paper_title": "N/A",
        "paper_url": "",
        "paper_authors": "Dingo Team",
        "evaluation_results": ""
    }

    dynamic_config = EvaluatorRuleArgs(pattern=r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        res = EvalDetail(metric=cls.__name__)
        content = input_data.content
        match = re.search(cls.dynamic_config.pattern, content)
        if not match:
            res.status = True
            res.label = [f"{cls.metric_type}.{cls.__name__}"]
            res.reason = ["Email address not found in resume"]
        else:
            res.label = [QualityLabel.QUALITY_GOOD]
        return res


@Model.rule_register("RESUME_QUALITY_BAD_CONTACT", ["default", "resume"])
class RuleResumePhoneMissing(BaseRule):
    """Check if the resume is missing phone number."""

    _metric_info = {
        "category": "Rule-Based RESUME Quality Metrics",
        "quality_dimension": "CONTENT_COMPLETENESS",
        "metric_name": "RuleResumePhoneMissing",
        "description": "Checks if resume contains a valid phone number",
        "severity": "high",
        "paper_title": "N/A",
        "paper_url": "",
        "paper_authors": "Dingo Team",
        "evaluation_results": ""
    }

    dynamic_config = EvaluatorRuleArgs(pattern=r'(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3,4}[-.\s]?\d{4}')

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        res = EvalDetail(metric=cls.__name__)
        content = input_data.content
        match = re.search(cls.dynamic_config.pattern, content)
        if not match:
            res.status = True
            res.label = [f"{cls.metric_type}.{cls.__name__}"]
            res.reason = ["Phone number not found in resume"]
        else:
            res.label = [QualityLabel.QUALITY_GOOD]
        return res


@Model.rule_register("RESUME_QUALITY_BAD_CONTACT", ["default", "resume"])
class RuleResumePhoneFormat(BaseRule):
    """Check if phone number format is invalid."""

    _metric_info = {
        "category": "Rule-Based RESUME Quality Metrics",
        "quality_dimension": "CONTENT_COMPLETENESS",
        "metric_name": "RuleResumePhoneFormat",
        "description": "Validates phone number format in resume",
        "severity": "medium",
        "paper_title": "N/A",
        "paper_url": "",
        "paper_authors": "Dingo Team",
        "evaluation_results": ""
    }

    dynamic_config = EvaluatorRuleArgs(pattern=r'\b\d{11}\b')

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        res = EvalDetail(metric=cls.__name__)
        content = input_data.content
        matches = re.findall(cls.dynamic_config.pattern, content)
        invalid_phones = [m for m in matches if not m.startswith(('13', '14', '15', '16', '17', '18', '19'))]
        if invalid_phones:
            res.status = True
            res.label = [f"{cls.metric_type}.{cls.__name__}"]
            res.reason = ["Invalid phone format: " + ", ".join(invalid_phones)]
        else:
            res.label = [QualityLabel.QUALITY_GOOD]
        return res


# ========== Format Issues ==========


@Model.rule_register("RESUME_QUALITY_BAD_FORMAT", ["default", "resume"])
class RuleResumeExcessiveWhitespace(BaseRule):
    """Check if resume contains excessive whitespace."""

    _metric_info = {
        "category": "Rule-Based RESUME Quality Metrics",
        "quality_dimension": "FORMAT_QUALITY",
        "metric_name": "RuleResumeExcessiveWhitespace",
        "description": "Detects excessive consecutive spaces in resume",
        "severity": "low",
        "paper_title": "N/A",
        "paper_url": "",
        "paper_authors": "Dingo Team",
        "evaluation_results": ""
    }

    dynamic_config = EvaluatorRuleArgs(pattern=r' {3,}', threshold=3)

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        res = EvalDetail(metric=cls.__name__)
        content = input_data.content
        matches = re.findall(cls.dynamic_config.pattern, content)
        if len(matches) >= cls.dynamic_config.threshold:
            res.status = True
            res.label = [f"{cls.metric_type}.{cls.__name__}"]
            res.reason = ["Found " + str(len(matches)) + " instances of excessive whitespace"]
        else:
            res.label = [QualityLabel.QUALITY_GOOD]
        return res


@Model.rule_register("RESUME_QUALITY_BAD_FORMAT", ["default", "resume"])
class RuleResumeMarkdown(BaseRule):
    """Check if resume has Markdown syntax errors."""

    _metric_info = {
        "category": "Rule-Based RESUME Quality Metrics",
        "quality_dimension": "FORMAT_QUALITY",
        "metric_name": "RuleResumeMarkdown",
        "description": "Detects common Markdown syntax errors in resume",
        "severity": "low",
        "paper_title": "N/A",
        "paper_url": "",
        "paper_authors": "Dingo Team",
        "evaluation_results": ""
    }

    dynamic_config = EvaluatorRuleArgs(pattern=r'(#{7,}|(\*{3,})|(\_{3,}))')

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        res = EvalDetail(metric=cls.__name__)
        content = input_data.content
        match = re.search(cls.dynamic_config.pattern, content)
        if match:
            res.status = True
            res.label = [f"{cls.metric_type}.{cls.__name__}"]
            res.reason = ["Markdown syntax error: " + match.group(0)]
        else:
            res.label = [QualityLabel.QUALITY_GOOD]
        return res


# ========== Structure Issues ==========


@Model.rule_register("RESUME_QUALITY_BAD_STRUCTURE", ["default", "resume"])
class RuleResumeNameMissing(BaseRule):
    """Check if resume is missing name in the first section."""

    _metric_info = {
        "category": "Rule-Based RESUME Quality Metrics",
        "quality_dimension": "STRUCTURE_CLARITY",
        "metric_name": "RuleResumeNameMissing",
        "description": "Checks if resume contains a name in the first 200 characters",
        "severity": "critical",
        "paper_title": "N/A",
        "paper_url": "",
        "paper_authors": "Dingo Team",
        "evaluation_results": ""
    }

    dynamic_config = EvaluatorRuleArgs()

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        res = EvalDetail(metric=cls.__name__)
        content = input_data.content
        first_section = content[:200]
        # Check if first section contains Chinese name pattern or heading
        if not re.search(r'(^#\s*.+|^.{2,4}$)', first_section, re.MULTILINE):
            res.status = True
            res.label = [f"{cls.metric_type}.{cls.__name__}"]
            res.reason = ["Name or heading not found in the first section"]
        else:
            res.label = [QualityLabel.QUALITY_GOOD]
        return res


@Model.rule_register("RESUME_QUALITY_BAD_STRUCTURE", ["default", "resume"])
class RuleResumeSectionMissing(BaseRule):
    """Check if resume is missing required sections."""

    _metric_info = {
        "category": "Rule-Based RESUME Quality Metrics",
        "quality_dimension": "STRUCTURE_CLARITY",
        "metric_name": "RuleResumeSectionMissing",
        "description": "Checks if resume contains required sections like education or experience",
        "severity": "medium",
        "paper_title": "N/A",
        "paper_url": "",
        "paper_authors": "Dingo Team",
        "evaluation_results": ""
    }

    dynamic_config = EvaluatorRuleArgs(pattern=r'(教育|学历|工作|经历|experience|education)', threshold=1)

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        res = EvalDetail(metric=cls.__name__)
        content = input_data.content.lower()
        matches = re.findall(cls.dynamic_config.pattern, content, re.IGNORECASE)
        if len(matches) < cls.dynamic_config.threshold:
            res.status = True
            res.label = [f"{cls.metric_type}.{cls.__name__}"]
            res.reason = ["Required sections (education/experience) not found"]
        else:
            res.label = [QualityLabel.QUALITY_GOOD]
        return res


# ========== Professionalism Issues ==========


@Model.rule_register("RESUME_QUALITY_BAD_PROFESSIONALISM", ["default", "resume"])
class RuleResumeEmoji(BaseRule):
    """Check if resume contains emoji characters."""

    _metric_info = {
        "category": "Rule-Based RESUME Quality Metrics",
        "quality_dimension": "PROFESSIONALISM",
        "metric_name": "RuleResumeEmoji",
        "description": "Detects emoji usage in resume which reduces professionalism",
        "severity": "medium",
        "paper_title": "N/A",
        "paper_url": "",
        "paper_authors": "Dingo Team",
        "evaluation_results": ""
    }

    dynamic_config = EvaluatorRuleArgs(pattern=r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF]')

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        res = EvalDetail(metric=cls.__name__)
        content = input_data.content
        matches = re.findall(cls.dynamic_config.pattern, content)
        if matches:
            res.status = True
            res.label = [f"{cls.metric_type}.{cls.__name__}"]
            res.reason = ["Found " + str(len(matches)) + " emoji characters"]
        else:
            res.label = [QualityLabel.QUALITY_GOOD]
        return res


@Model.rule_register("RESUME_QUALITY_BAD_PROFESSIONALISM", ["default", "resume"])
class RuleResumeInformal(BaseRule):
    """Check if resume contains informal language."""

    _metric_info = {
        "category": "Rule-Based RESUME Quality Metrics",
        "quality_dimension": "PROFESSIONALISM",
        "metric_name": "RuleResumeInformal",
        "description": "Detects informal or colloquial expressions in resume",
        "severity": "low",
        "paper_title": "N/A",
        "paper_url": "",
        "paper_authors": "Dingo Team",
        "evaluation_results": ""
    }

    dynamic_config = EvaluatorRuleArgs(pattern=r'(搞定|牛逼|厉害|哈哈|嘿嘿|呵呵|啊|呀|吧|哦)')

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        res = EvalDetail(metric=cls.__name__)
        content = input_data.content
        matches = re.findall(cls.dynamic_config.pattern, content)
        if matches:
            res.status = True
            res.label = [f"{cls.metric_type}.{cls.__name__}"]
            res.reason = ["Found informal language: " + ", ".join(set(matches))]
        else:
            res.label = [QualityLabel.QUALITY_GOOD]
        return res


# ========== Date Issues ==========


@Model.rule_register("RESUME_QUALITY_BAD_DATE", ["default", "resume"])
class RuleResumeDateFormat(BaseRule):
    """Check if resume has inconsistent date formats."""

    _metric_info = {
        "category": "Rule-Based RESUME Quality Metrics",
        "quality_dimension": "PROFESSIONALISM",
        "metric_name": "RuleResumeDateFormat",
        "description": "Detects inconsistent date format usage in resume",
        "severity": "medium",
        "paper_title": "N/A",
        "paper_url": "",
        "paper_authors": "Dingo Team",
        "evaluation_results": ""
    }

    dynamic_config = EvaluatorRuleArgs(pattern=r'\d{4}[-./年]\d{1,2}')

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        res = EvalDetail(metric=cls.__name__)
        content = input_data.content
        matches = re.findall(cls.dynamic_config.pattern, content)
        if matches:
            separators = set([re.search(r'[-./年]', m).group(0) for m in matches])
            if len(separators) > 1:
                res.eval_status = True
                res.eval_details = {
                    "label": [f"{cls.metric_type}.{cls.__name__}"],
                    "metric": [cls.__name__],
                    "reason": ["Inconsistent date formats found: " + ", ".join(matches[:3])]
                }
            else:
                res.eval_details = {
                    "label": [QualityLabel.QUALITY_GOOD]
                }
        else:
            res.label = [QualityLabel.QUALITY_GOOD]
        return res


# ========== Completeness Issues ==========


@Model.rule_register("RESUME_QUALITY_BAD_COMPLETENESS", ["default", "resume"])
class RuleResumeEducationMissing(BaseRule):
    """Check if resume is missing education section."""

    _metric_info = {
        "category": "Rule-Based RESUME Quality Metrics",
        "quality_dimension": "CONTENT_COMPLETENESS",
        "metric_name": "RuleResumeEducationMissing",
        "description": "Checks if resume contains education background information",
        "severity": "high",
        "paper_title": "N/A",
        "paper_url": "",
        "paper_authors": "Dingo Team",
        "evaluation_results": ""
    }

    dynamic_config = EvaluatorRuleArgs(pattern=r'(教育|学历|education|university|college|bachelor|master|phd)')

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        res = EvalDetail(metric=cls.__name__)
        content = input_data.content.lower()
        match = re.search(cls.dynamic_config.pattern, content, re.IGNORECASE)
        if not match:
            res.status = True
            res.label = [f"{cls.metric_type}.{cls.__name__}"]
            res.reason = ["Education section not found in resume"]
        else:
            res.label = [QualityLabel.QUALITY_GOOD]
        return res


@Model.rule_register("RESUME_QUALITY_BAD_COMPLETENESS", ["default", "resume"])
class RuleResumeExperienceMissing(BaseRule):
    """Check if resume is missing work experience section."""

    _metric_info = {
        "category": "Rule-Based RESUME Quality Metrics",
        "quality_dimension": "CONTENT_COMPLETENESS",
        "metric_name": "RuleResumeExperienceMissing",
        "description": "Checks if resume contains work experience information",
        "severity": "medium",
        "paper_title": "N/A",
        "paper_url": "",
        "paper_authors": "Dingo Team",
        "evaluation_results": ""
    }

    dynamic_config = EvaluatorRuleArgs(pattern=r'(工作|经历|experience|employment|position|职位)')

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        res = EvalDetail(metric=cls.__name__)
        content = input_data.content.lower()
        match = re.search(cls.dynamic_config.pattern, content, re.IGNORECASE)
        if not match:
            res.status = True
            res.label = [f"{cls.metric_type}.{cls.__name__}"]
            res.reason = ["Work experience section not found in resume"]
        else:
            res.label = [QualityLabel.QUALITY_GOOD]
        return res
