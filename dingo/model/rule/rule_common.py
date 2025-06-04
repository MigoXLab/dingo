import re
import string
from typing import List, Tuple

from dingo.config.config import DynamicRuleConfig
from dingo.io import Data
from dingo.model.model import Model
from dingo.model.modelres import ModelRes
from dingo.model.rule.base import BaseRule


@Model.rule_register('QUALITY_BAD_EFFECTIVENESS', ['qa_standard_v1'])
class RuleAbnormalChar(BaseRule):
    # consist of [RuleSpecialCharacter, RuleInvisibleChar]

    @classmethod
    def eval(cls, input_data: Data) -> ModelRes:
        res = ModelRes()
        for r in [RuleSpecialCharacter, RuleInvisibleChar]:
            tmp_res = r.eval(input_data)
            if tmp_res.error_status:
                res.error_status = True
                res.type = cls.metric_type
                res.name = cls.__name__
                res.reason.extend(tmp_res.reason)
        return res


@Model.rule_register('QUALITY_BAD_EFFECTIVENESS', ['qa_standard_v1'])
class RuleAbnormalHtml(BaseRule):
    # consist of [RuleHtmlEntity, RuleHtmlTag]

    @classmethod
    def eval(cls, input_data: Data) -> ModelRes:
        res = ModelRes()
        for r in [RuleHtmlEntity, RuleHtmlTag]:
            tmp_res = r.eval(input_data)
            if tmp_res.error_status:
                res.error_status = True
                res.type = cls.metric_type
                res.name = cls.__name__
                res.reason.extend(tmp_res.reason)
        return res


@Model.rule_register('QUALITY_BAD_FLUENCY', ['pdf_all'])
class RuleAbnormalNumber(BaseRule):
    """Check pdf content abnormal book page or index number."""

    dynamic_config = DynamicRuleConfig(pattern=r'\n{4}\d+\n{4}')

    @classmethod
    def eval(cls, input_data: Data) -> ModelRes:
        res = ModelRes()
        content = input_data.content
        match = re.search(cls.dynamic_config.pattern, content)
        if match:
            res.error_status = True
            res.type = cls.metric_type
            res.name = cls.__name__
            res.reason = [match.group(0).strip('\n')]
        return res


@Model.rule_register('QUALITY_BAD_EFFECTIVENESS', ['pretrain'])
class RuleAlphaWords(BaseRule):
    """Check whether the ratio of words that contain at least one alphabetic
    character > 0.6."""

    dynamic_config = DynamicRuleConfig(threshold=0.6)

    @classmethod
    def eval(cls, input_data: Data) -> ModelRes:
        from nltk.tokenize import word_tokenize

        res = ModelRes()
        content = input_data.content
        words = word_tokenize(content)
        n_words = len(words)
        if n_words == 0:
            return res

        n_alpha_words = sum([any((c.isalpha() for c in w)) for w in words])
        ratio = n_alpha_words / n_words
        if ratio > cls.dynamic_config.threshold:
            pass
        else:
            res.error_status = True
            res.type = cls.metric_type
            res.name = cls.__name__
            res.reason = ['The ratio of words that contain at least one alphabetic character is: ' + str(ratio)]
        return res


@Model.rule_register('QUALITY_BAD_UNDERSTANDABILITY', ['pretrain'])
class RuleCapitalWords(BaseRule):
    """Check whether capital words ratio > 0.2."""

    dynamic_config = DynamicRuleConfig(threshold=0.2)

    @classmethod
    def eval(cls, input_data: Data) -> ModelRes:
        from nltk.tokenize import WordPunctTokenizer

        res = ModelRes()
        content = input_data.content
        words = WordPunctTokenizer().tokenize(content)
        num_words = len(words)
        if num_words == 0:
            return res
        num_caps_words = sum(map(str.isupper, words))
        ratio = num_caps_words / num_words
        if ratio > cls.dynamic_config.threshold and num_words < 200:
            res.error_status = True
            res.type = cls.metric_type
            res.name = cls.__name__
            res.reason = ['ratio: ' + str(ratio)]
        return res


@Model.rule_register('QUALITY_BAD_EFFECTIVENESS', ['pretrain'])
class RuleCharNumber(BaseRule):
    """Check whether the number of char > 100."""

    dynamic_config = DynamicRuleConfig(threshold=100)

    @classmethod
    def eval(cls, input_data: Data) -> ModelRes:
        res = ModelRes()
        text = input_data.content
        text = text.strip()
        text = text.replace(' ', '')
        text = text.replace('\n', '')
        text = text.replace('\t', '')
        num_char = len(text)
        if num_char < cls.dynamic_config.threshold:
            res.error_status = True
            res.type = cls.metric_type
            res.name = cls.__name__
            res.reason = ['The number of char is: ' + str(num_char)]
        return res


@Model.rule_register('QUALITY_BAD_FLUENCY', ['pdf_all'])
class RuleCharSplit(BaseRule):
    """Check pdf content char split."""

    dynamic_config = DynamicRuleConfig(pattern=r'(?:(?:[a-zA-Z]\s){5}[a-zA-Z])', threshold=3)

    @classmethod
    def eval(cls, input_data: Data) -> ModelRes:
        res = ModelRes()
        content = input_data.content
        matches = re.findall(cls.dynamic_config.pattern, content)
        count = len(matches)
        if count >= cls.dynamic_config.threshold:
            res.error_status = True
            res.type = cls.metric_type
            res.name = cls.__name__
            res.reason = matches
        return res


@Model.rule_register(
    'QUALITY_BAD_EFFECTIVENESS', ['default', 'sft', 'pretrain', 'benchmark', 'llm_base', 'text_base_all']
)
class RuleColonEnd(BaseRule):
    """Check whether the last char is ':'."""

    dynamic_config = DynamicRuleConfig()

    @classmethod
    def eval(cls, input_data: Data) -> ModelRes:
        res = ModelRes()
        content = input_data.content
        if len(content) <= 0:
            return res
        if content[-1] == ':':
            res.error_status = True
            res.type = cls.metric_type
            res.name = cls.__name__
            res.reason = [content[-100:]]
        return res


@Model.rule_register(
    'QUALITY_BAD_EFFECTIVENESS',
    [
        'default',
        'sft',
        'pretrain',
        'benchmark',
        'text_base_all',
        'llm_base',
        'multi_lan_ar',
        'multi_lan_ko',
        'multi_lan_ru',
        'multi_lan_th',
        'multi_lan_vi',
        'multi_lan_cs',
        'multi_lan_hu',
        'multi_lan_sr',
        'qa_standard_v1',
        'pdf',
    ],
)
class RuleContentNull(BaseRule):
    """Check whether content is null."""

    dynamic_config = DynamicRuleConfig()

    @classmethod
    def eval(cls, input_data: Data) -> ModelRes:
        res = ModelRes()
        count = len(input_data.content.strip())
        if count == 0:
            res.error_status = True
            res.type = cls.metric_type
            res.name = cls.__name__
            res.reason = ['Content is empty.']
        return res


@Model.rule_register('QUALITY_BAD_EFFECTIVENESS', ['text_base_all', 'qa_standard_v1', 'pdf'])
class RuleContentShort(BaseRule):

    dynamic_config = DynamicRuleConfig(threshold=20)

    @classmethod
    def eval(cls, input_data: Data) -> ModelRes:
        res = ModelRes()
        content = input_data.content.encode('utf-8')
        if len(content) <= cls.dynamic_config.threshold:
            res.error_status = True
            res.type = cls.metric_type
            res.name = cls.__name__
            res.reason = ['Content is too short.']
        return res


@Model.rule_register(
    'QUALITY_BAD_EFFECTIVENESS',
    [
        'multi_lan_ar',
        'multi_lan_ko',
        'multi_lan_ru',
        'multi_lan_th',
        'multi_lan_vi',
        'multi_lan_cs',
        'multi_lan_hu',
        'multi_lan_sr',
    ],
)
class RuleContentShortMultiLan(BaseRule):
    """Check whether content is too short."""

    dynamic_config = DynamicRuleConfig(threshold=20)

    @classmethod
    def eval(cls, input_data: Data) -> ModelRes:
        from nltk.tokenize import WordPunctTokenizer

        res = ModelRes()
        tk = WordPunctTokenizer()
        tokens = tk.tokenize(input_data.content)
        words = [word for word in tokens if word.isalpha()]
        if len(words) < cls.dynamic_config.threshold:
            res.error_status = True
            res.type = cls.metric_type
            res.name = cls.__name__
            res.reason = ['Content is too short.']
        return res


@Model.rule_register('QUALITY_BAD_UNDERSTANDABILITY', [])
class RuleCurlyBracket(BaseRule):
    """Check whether the ratio of the number of {,} and the number of
    characters < 0.025."""

    dynamic_config = DynamicRuleConfig(threshold=0.025)

    @classmethod
    def eval(cls, input_data: Data) -> ModelRes:
        res = ModelRes()
        content = input_data.content
        if len(content) == 0:
            return res

        num = content.count('{') + content.count('}')
        ratio = num / len(content)
        if ratio > cls.dynamic_config.threshold:
            res.error_status = True
            res.type = cls.metric_type
            res.name = cls.__name__
            res.reason = ['The ratio of curly bracket and characters is : ' + str(ratio)]
        return res


@Model.rule_register(
    'QUALITY_BAD_SIMILARITY',
    [
        'default',
        'sft',
        'pretrain',
        'benchmark',
        'text_base_all',
        'llm_base',
        'multi_lan_ar',
        'multi_lan_ko',
        'multi_lan_ru',
        'multi_lan_th',
        'multi_lan_vi',
        'multi_lan_cs',
        'multi_lan_hu',
        'multi_lan_sr',
        'pdf',
    ],
)
class RuleDocRepeat(BaseRule):
    """Check whether content repeats."""

    dynamic_config = DynamicRuleConfig(threshold=80)

    @classmethod
    def eval(cls, input_data: Data) -> ModelRes:
        from dingo.model.rule.utils.util import \
          base_rps_frac_chars_in_dupe_ngrams

        res = ModelRes()
        repeat_score = base_rps_frac_chars_in_dupe_ngrams(6, input_data.content)
        if repeat_score >= cls.dynamic_config.threshold:
            res.error_status = True
            res.type = cls.metric_type
            res.name = cls.__name__
            res.reason = ['Repeatability of text is too high, with ratio： ' + str(repeat_score)]
        return res


@Model.rule_register('QUALITY_BAD_EFFECTIVENESS', ['qa_standard_v1'])
class RuleEnterAndSpace(BaseRule):
    # consist of [RuleEnterMore, RuleEnterRatioMore, RuleSpaceMore]

    @classmethod
    def eval(cls, input_data: Data) -> ModelRes:
        res = ModelRes()
        for r in [RuleEnterMore, RuleEnterRatioMore, RuleSpaceMore]:
            tmp_res = r.eval(input_data)
            if tmp_res.error_status:
                res.error_status = True
                res.type = cls.metric_type
                res.name = cls.__name__
                res.reason.extend(tmp_res.reason)
        return res


@Model.rule_register(
    'QUALITY_BAD_EFFECTIVENESS',
    [
        'text_base_all',
        'llm_base',
        'multi_lan_ar',
        'multi_lan_ko',
        'multi_lan_ru',
        'multi_lan_th',
        'multi_lan_vi',
        'multi_lan_cs',
        'multi_lan_hu',
        'multi_lan_sr',
        'pdf',
    ],
)
class RuleEnterMore(BaseRule):
    """Check whether content has 8 consecutive carriage returns."""

    dynamic_config = DynamicRuleConfig(key_list=[r'\n{8,}', r'\r\n{8,}'])

    @classmethod
    def eval(cls, input_data: Data) -> ModelRes:
        res = ModelRes()
        content = input_data.content
        for p in cls.dynamic_config.key_list:
            SEARCH_REGEX = re.compile(p)
            match = SEARCH_REGEX.search(content)
            if match:
                res.error_status = True
                res.type = cls.metric_type
                res.name = cls.__name__
                res.reason = ['Content has 8 consecutive carriage returns.']
                return res
        return res


@Model.rule_register(
    'QUALITY_BAD_EFFECTIVENESS',
    [
        'text_base_all',
        'llm_base',
        'multi_lan_ar',
        'multi_lan_ko',
        'multi_lan_ru',
        'multi_lan_th',
        'multi_lan_vi',
        'multi_lan_cs',
        'multi_lan_hu',
        'multi_lan_sr',
        'pdf',
    ],
)
class RuleEnterRatioMore(BaseRule):
    """Check whether the number of enter / the number of content > 25%"""

    dynamic_config = DynamicRuleConfig()

    @classmethod
    def eval(cls, input_data: Data) -> ModelRes:
        res = ModelRes()
        content = input_data.content
        if len(content) == 0:
            return res

        ratio = content.count('\n') / len(content)
        if ratio > 0.25:
            res.error_status = True
            res.type = cls.metric_type
            res.name = cls.__name__
            res.reason = ['The number of enter / the number of content > 25%.']
        return res


@Model.rule_register('QUALITY_BAD_RELEVANCE', ['multi_lan_ar'])
class RuleHeadWordAr(BaseRule):
    """Check whether ar content contains irrelevance tail source info."""

    dynamic_config = DynamicRuleConfig()

    @classmethod
    def eval(cls, input_data: Data) -> ModelRes:
        from dingo.model.rule.utils.multi_lan_util import get_xyz_head_word

        res = ModelRes()
        keyword = get_xyz_head_word('ar')
        content_tail = input_data.content[-100:]
        matches = re.findall('|'.join(keyword), content_tail)
        if len(matches) > 0:
            res.error_status = True
            res.type = cls.metric_type
            res.name = cls.__name__
            res.reason = ['Content has irrelevance tail source info.']
        return res


@Model.rule_register('QUALITY_BAD_RELEVANCE', ['multi_lan_cs'])
class RuleHeadWordCs(BaseRule):
    """Check whether cs content contains irrelevance tail source info."""

    dynamic_config = DynamicRuleConfig()

    @classmethod
    def eval(cls, input_data: Data) -> ModelRes:
        from dingo.model.rule.utils.multi_lan_util import get_xyz_head_word

        res = ModelRes()
        keyword = get_xyz_head_word('cs')
        content_tail = input_data.content[-100:]
        matches = re.findall('|'.join(keyword), content_tail)
        if len(matches) > 0:
            res.error_status = True
            res.type = cls.metric_type
            res.name = cls.__name__
            res.reason = ['Content has irrelevance tail source info.']
        return res


@Model.rule_register('QUALITY_BAD_RELEVANCE', ['multi_lan_hu'])
class RuleHeadWordHu(BaseRule):
    """Check whether hu content contains irrelevance tail source info."""

    dynamic_config = DynamicRuleConfig()

    @classmethod
    def eval(cls, input_data: Data) -> ModelRes:
        from dingo.model.rule.utils.multi_lan_util import get_xyz_head_word

        res = ModelRes()
        keyword = get_xyz_head_word('hu')
        content_tail = input_data.content[-100:]
        matches = re.findall('|'.join(keyword), content_tail)
        if len(matches) > 0:
            res.error_status = True
            res.type = cls.metric_type
            res.name = cls.__name__
            res.reason = ['Content has irrelevance tail source info.']
        return res


@Model.rule_register('QUALITY_BAD_RELEVANCE', ['multi_lan_ko'])
class RuleHeadWordKo(BaseRule):
    """Check whether ko content contains irrelevance tail source info."""

    dynamic_config = DynamicRuleConfig()

    @classmethod
    def eval(cls, input_data: Data) -> ModelRes:
        from dingo.model.rule.utils.multi_lan_util import get_xyz_head_word

        res = ModelRes()
        keyword = get_xyz_head_word('ko')
        content_tail = input_data.content[-100:]
        matches = re.findall('|'.join(keyword), content_tail)
        if len(matches) > 0:
            res.error_status = True
            res.type = cls.metric_type
            res.name = cls.__name__
            res.reason = ['Content has irrelevance tail source info.']
        return res


@Model.rule_register('QUALITY_BAD_RELEVANCE', ['multi_lan_ru'])
class RuleHeadWordRu(BaseRule):
    """Check whether ru content contains irrelevance tail source info."""

    dynamic_config = DynamicRuleConfig()

    @classmethod
    def eval(cls, input_data: Data) -> ModelRes:
        from dingo.model.rule.utils.multi_lan_util import get_xyz_head_word

        res = ModelRes()
        keyword = get_xyz_head_word('ru')
        content_tail = input_data.content[-100:]
        matches = re.findall('|'.join(keyword), content_tail)
        if len(matches) > 0:
            res.error_status = True
            res.type = cls.metric_type
            res.name = cls.__name__
            res.reason = ['Content has irrelevance tail source info.']
        return res


@Model.rule_register('QUALITY_BAD_RELEVANCE', ['multi_lan_sr'])
class RuleHeadWordSr(BaseRule):
    """Check whether sr content contains irrelevance tail source info."""

    dynamic_config = DynamicRuleConfig()

    @classmethod
    def eval(cls, input_data: Data) -> ModelRes:
        from dingo.model.rule.utils.multi_lan_util import get_xyz_head_word

        res = ModelRes()
        keyword = get_xyz_head_word('sr')
        content_tail = input_data.content[-100:]
        matches = re.findall('|'.join(keyword), content_tail)
        if len(matches) > 0:
            res.error_status = True
            res.type = cls.metric_type
            res.name = cls.__name__
            res.reason = ['Content has irrelevance tail source info.']
        return res


@Model.rule_register('QUALITY_BAD_RELEVANCE', ['multi_lan_th'])
class RuleHeadWordTh(BaseRule):
    """Check whether th content contains irrelevance tail source info."""

    dynamic_config = DynamicRuleConfig()

    @classmethod
    def eval(cls, input_data: Data) -> ModelRes:
        from dingo.model.rule.utils.multi_lan_util import get_xyz_head_word

        res = ModelRes()
        keyword = get_xyz_head_word('th')
        content_tail = input_data.content[-100:]
        matches = re.findall('|'.join(keyword), content_tail)
        if len(matches) > 0:
            res.error_status = True
            res.type = cls.metric_type
            res.name = cls.__name__
            res.reason = ['Content has irrelevance tail source info.']
        return res


@Model.rule_register('QUALITY_BAD_RELEVANCE', ['multi_lan_vi'])
class RuleHeadWordVi(BaseRule):
    """Check whether vi content contains irrelevance tail source info."""

    dynamic_config = DynamicRuleConfig()

    @classmethod
    def eval(cls, input_data: Data) -> ModelRes:
        from dingo.model.rule.utils.multi_lan_util import get_xyz_head_word

        res = ModelRes()
        keyword = get_xyz_head_word('vi')
        content_tail = input_data.content[-100:]
        matches = re.findall('|'.join(keyword), content_tail)
        if len(matches) > 0:
            res.error_status = True
            res.type = cls.metric_type
            res.name = cls.__name__
            res.reason = ['Content has irrelevance tail source info.']
        return res


@Model.rule_register(
    'QUALITY_BAD_EFFECTIVENESS',
    [
        'default',
        'sft',
        'pretrain',
        'benchmark',
        'text_base_all',
        'multi_lan_ar',
        'multi_lan_ko',
        'multi_lan_ru',
        'multi_lan_th',
        'multi_lan_vi',
        'multi_lan_cs',
        'multi_lan_hu',
        'multi_lan_sr',
        'pdf',
    ],
)
class RuleHtmlEntity(BaseRule):
    """Check whether content has html entity."""

    dynamic_config = DynamicRuleConfig(
        key_list=[
            'nbsp',
            'lt',
            'gt',
            'amp',
            'quot',
            'apos',
            'hellip',
            'ndash',
            'mdash',
            'lsquo',
            'rsquo',
            'ldquo',
            'rdquo',
        ]
    )

    @classmethod
    def eval(cls, input_data: Data) -> ModelRes:
        res = ModelRes()
        content = input_data.content
        if len(content) == 0:
            return res

        entities = cls.dynamic_config.key_list
        full_entities_1 = [f"&{entity}；" for entity in entities]
        full_entities_2 = [f"&{entity};" for entity in entities]
        full_entities_3 = [f"＆{entity};" for entity in entities]
        full_entities_4 = [f"＆{entity}；" for entity in entities]
        full_entities = full_entities_1 + full_entities_2 + full_entities_3 + full_entities_4
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
            res.error_status = True
            res.type = cls.metric_type
            res.name = cls.__name__
            res.reason = [list(set(error_entity))]
        return res


@Model.rule_register(
    'QUALITY_BAD_EFFECTIVENESS',
    [
        'text_base_all',
        'multi_lan_ar',
        'multi_lan_ko',
        'multi_lan_ru',
        'multi_lan_th',
        'multi_lan_vi',
        'multi_lan_cs',
        'multi_lan_hu',
        'multi_lan_sr',
        'pdf',
    ],
)
class RuleHtmlTag(BaseRule):
    """Check whether content has image links or html tags."""

    dynamic_config = DynamicRuleConfig(key_list=['<img', '<p>', '</p>', '<o:p', '</o:p>'])

    @classmethod
    def eval(cls, input_data: Data) -> ModelRes:
        res = ModelRes()
        content = input_data.content
        if len(content) == 0:
            return res

        matches = re.findall('|'.join(cls.dynamic_config.key_list), content)
        num = len(matches)
        if num / len(content) >= 0.01:
            res.error_status = True
            res.type = cls.metric_type
            res.name = cls.__name__
            res.reason = list(set(matches))
        return res


@Model.rule_register('QUALITY_BAD_SECURITY', ['default', 'pretrain', 'benchmark'])
class RuleIDCard(BaseRule):
    """Check if the content contains ID card."""

    dynamic_config = DynamicRuleConfig(
        pattern=r'(身\s{0,10}份|id\s{0,10}number\s{0,10}|identification|identity|\s{0,10}ID\s{0,10}No\s{0,10}|id\s{0,10}card\s{0,10}|NRIC\s{0,10}number\s{0,10}|IC\s{0,10}number\s{0,10}|resident\s{0,10}registration\s{0,10}|I.D.\s{0,10}Number\s{0,10})'
    )

    @classmethod
    def eval(cls, input_data: Data) -> ModelRes:
        from dingo.model.rule.utils.util import Extractor

        res = ModelRes()
        match = re.search(cls.dynamic_config.pattern, input_data.content, re.I)
        if match:
            person_id = Extractor().extract_id_card(input_data.content)
            if len(person_id) != 0:
                res.error_status = True
                res.type = cls.metric_type
                res.name = cls.__name__
                res.reason = [str(person_id)]
        return res


@Model.rule_register(
    'QUALITY_BAD_EFFECTIVENESS',
    [
        'text_base_all',
        'multi_lan_ar',
        'multi_lan_ko',
        'multi_lan_ru',
        'multi_lan_th',
        'multi_lan_vi',
        'multi_lan_cs',
        'multi_lan_hu',
        'multi_lan_sr',
    ],
)
class RuleInvisibleChar(BaseRule):
    """Check whether content has invisible chars."""

    dynamic_config = DynamicRuleConfig(pattern=r'[\u2000-\u200F\u202F\u205F\u3000\uFEFF\u00A0\u2060-\u206F\uFEFF\xa0]')

    @classmethod
    def eval(cls, input_data: Data) -> ModelRes:
        res = ModelRes()
        content = input_data.content
        if len(content) == 0:
            return res

        matches = re.findall(cls.dynamic_config.pattern, content)
        num = len(matches)
        if num / len(content) >= 0.01:
            res.error_status = True
            res.type = cls.metric_type
            res.name = cls.__name__
            res.reason = [repr(s) for s in list(set(matches))]
        return res


@Model.rule_register('QUALITY_BAD_EFFECTIVENESS', ['pdf_all'])
class RuleLatexSpecialChar(BaseRule):
    """Check pdf content latex abnormal char."""

    dynamic_config = DynamicRuleConfig(pattern=r'\$\$(.*?\!\!.*?)\$\$')

    @classmethod
    def eval(cls, input_data: Data) -> ModelRes:
        res = ModelRes()
        content = input_data.content
        match = re.search(cls.dynamic_config.pattern, content)
        if match:
            res.error_status = True
            res.type = cls.metric_type
            res.name = cls.__name__
            res.reason = [match.group(0).strip('\n')]
        return res


@Model.rule_register('QUALITY_BAD_COMPLETENESS', ['pretrain', 'benchmark'])
class RuleLineEndWithEllipsis(BaseRule):
    """Check whether the ratio of line ends with ellipsis < 0.3."""

    dynamic_config = DynamicRuleConfig(threshold=0.3, key_list=['...', '…'])

    @classmethod
    def eval(cls, input_data: Data) -> ModelRes:
        from dingo.model.rule.utils.util import TextSlice, split_paragraphs

        res = ModelRes()
        raw_content = input_data.content
        raw_lines: Tuple[TextSlice] = split_paragraphs(text=raw_content, normalizer=lambda x: x, remove_empty=True)
        num_lines = len(raw_lines)
        if num_lines == 0:
            return res

        num_occurrences = sum([line.text.rstrip().endswith(tuple(cls.dynamic_config.key_list)) for line in raw_lines])
        ratio = num_occurrences / num_lines
        if ratio > cls.dynamic_config.threshold:
            res.error_status = True
            res.type = cls.metric_type
            res.name = cls.__name__
            res.reason = ['The ratio of lines end with ellipsis is: ' + str(ratio)]
        return res


@Model.rule_register('QUALITY_BAD_COMPLETENESS', ['pretrain'])
class RuleLineEndWithTerminal(BaseRule):
    """Check whether the ratio of line ends with terminal punctuation mark >
    0.6."""

    dynamic_config = DynamicRuleConfig(threshold=0.6, key_list=['.', '!', '?', '"', '"'])

    @classmethod
    def eval(cls, input_data: Data) -> ModelRes:
        from dingo.model.rule.utils.util import TextSlice, split_paragraphs

        res = ModelRes()
        raw_content = input_data.content
        raw_lines: Tuple[TextSlice] = split_paragraphs(text=raw_content, normalizer=lambda x: x, remove_empty=True)
        num_lines = len(raw_lines)
        if num_lines == 0:
            return res

        terminal_marks = [
            line.text.rstrip()[-1]
            for line in raw_lines
            if line.text and line.text.rstrip()[-1] not in cls.dynamic_config.key_list
        ]
        num_occurrences = sum([line.text.rstrip().endswith(tuple(cls.dynamic_config.key_list)) for line in raw_lines])
        ratio = num_occurrences / num_lines
        if ratio < cls.dynamic_config.threshold:
            res.error_status = True
            res.type = cls.metric_type
            res.name = cls.__name__
            res.reason = list(set(terminal_marks))
        return res


@Model.rule_register('QUALITY_BAD_UNDERSTANDABILITY', ['sft', 'pretrain', 'benchmark'])
class RuleLineStartWithBulletpoint(BaseRule):
    """Check whether the ratio of line starts with bullet points < 0.9."""

    dynamic_config = DynamicRuleConfig(
        threshold=0.9,
        key_list=[
            '\u2022',  # bullet point
            '\u2023',  # triangular bullet point
            '\u25b6',  # black right pointing triangle
            '\u25c0',  # black left pointing triangle
            '\u25e6',  # white bullet point
            '\u25a0',  # black square
            '\u25a1',  # white square
            '\u25aa',  # black small square
            '\u25ab',  # white small square
            '\u2013',  # en dash
        ],
    )

    @classmethod
    def eval(cls, input_data: Data) -> ModelRes:
        from dingo.model.rule.utils.util import TextSlice, split_paragraphs

        res = ModelRes()
        raw_content = input_data.content
        raw_lines: Tuple[TextSlice] = split_paragraphs(text=raw_content, normalizer=lambda x: x, remove_empty=True)
        num_lines = len(raw_lines)
        if num_lines == 0:
            return res

        num_occurrences = sum([line.text.lstrip().startswith(tuple(cls.dynamic_config.key_list)) for line in raw_lines])
        ratio = num_occurrences / num_lines
        if ratio > cls.dynamic_config.threshold:
            res.error_status = True
            res.type = cls.metric_type
            res.name = cls.__name__
            res.reason = ['The ratio of lines start with bulletpoint is: ' + str(ratio)]
        return res


@Model.rule_register('QUALITY_BAD_EFFECTIVENESS', ['pretrain', 'benchmark'])
class RuleLineJavascriptCount(BaseRule):
    """Check whether line with the word Javascript."""

    dynamic_config = DynamicRuleConfig(threshold=3)

    @classmethod
    def eval(cls, input_data: Data) -> ModelRes:
        from dingo.model.rule.utils.util import (TextSlice, normalize,
                                                 split_paragraphs)

        res = ModelRes()
        raw_content = input_data.content
        normalized_lines: Tuple[TextSlice] = split_paragraphs(text=raw_content, normalizer=normalize, remove_empty=True)
        num_lines = len(normalized_lines)
        if num_lines == 0:
            return res

        num_occurrences = sum(['javascript' in line.text for line in normalized_lines])
        num_not_occur = num_lines - num_occurrences
        if num_not_occur < cls.dynamic_config.threshold and num_lines > 3:
            res.error_status = True
            res.type = cls.metric_type
            res.name = cls.__name__
            res.reason = ['The lines with the word Javascript is: ' + str(num_occurrences)]
        return res


@Model.rule_register('QUALITY_BAD_EFFECTIVENESS', ['pretrain', 'benchmark'])
class RuleLoremIpsum(BaseRule):
    """Check whether the ratio of lorem ipsum < 3e-08."""

    dynamic_config = DynamicRuleConfig(threshold=3e-08)

    @classmethod
    def eval(cls, input_data: Data) -> ModelRes:
        from dingo.model.rule.utils.util import normalize

        res = ModelRes()
        normalized_content = normalize(input_data.content)
        num_normalized_content = len(normalized_content)
        if num_normalized_content == 0:
            return res

        SEARCH_REGEX = re.compile(r'lorem ipsum', re.IGNORECASE)
        num_occurrences = len(SEARCH_REGEX.findall(normalized_content))
        ratio = num_occurrences / num_normalized_content
        if ratio > cls.dynamic_config.threshold:
            res.error_status = True
            res.type = cls.metric_type
            res.name = cls.__name__
            res.reason = ['The ratio of lorem ipsum is: ' + str(ratio)]
        return res


@Model.rule_register('QUALITY_BAD_EFFECTIVENESS', ['pretrain'])
class RuleMeanWordLength(BaseRule):
    """Check whether the mean length of word in [3, 10]"""

    dynamic_config = DynamicRuleConfig(key_list=['3', '10'])

    @classmethod
    def eval(cls, input_data: Data) -> ModelRes:
        from dingo.model.rule.utils.util import normalize

        res = ModelRes()
        normalized_content = normalize(input_data.content)
        normalized_words = tuple(normalized_content.split())
        num_normalized_words = len(normalized_words)
        if num_normalized_words == 0:
            return res

        num_chars = float(sum(map(len, normalized_words)))
        mean_length = num_chars / num_normalized_words
        mean_length = round(mean_length, 2)
        if mean_length >= int(cls.dynamic_config.key_list[0]) and mean_length < int(cls.dynamic_config.key_list[1]):
            pass
        else:
            res.error_status = True
            res.type = cls.metric_type
            res.name = cls.__name__
            res.reason = ['The mean length of word is: ' + str(mean_length)]
        return res


@Model.rule_register(
    'QUALITY_BAD_FLUENCY',
    [
        'default',
        'sft',
        'pretrain',
        'benchmark',
        'text_base_all',
        'llm_base',
        'multi_lan_ar',
        'multi_lan_ko',
        'multi_lan_ru',
        'multi_lan_th',
        'multi_lan_vi',
        'multi_lan_cs',
        'multi_lan_hu',
        'multi_lan_sr',
    ],
)
class RuleNoPunc(BaseRule):
    """Check whether paragraph has no punctuation."""

    dynamic_config = DynamicRuleConfig(threshold=112)

    @classmethod
    def eval(cls, input_data: Data) -> ModelRes:
        res = ModelRes()
        content = input_data.content

        paragraphs = content.split('\n')
        longest_sentence = ''
        max_word_count = 0
        for paragraph in paragraphs:
            if len(paragraph.strip()) == 0:
                continue
            sentences = re.split('[–.!?,;•/|…]', paragraph)
            for sentence in sentences:
                words = sentence.split()
                word_count = len(words)
                if word_count > max_word_count:
                    max_word_count = word_count
                    longest_sentence = sentence.strip()
        if int(max_word_count) > cls.dynamic_config.threshold:
            res.error_status = True
            res.type = cls.metric_type
            res.name = cls.__name__
            res.reason = [longest_sentence]
        return res


@Model.rule_register('QUALITY_BAD_RELEVANCE', [])
class RulePatternSearch(BaseRule):
    """Let user input pattern to search."""

    dynamic_config = DynamicRuleConfig(pattern='your pattern')

    @classmethod
    def eval(cls, input_data: Data) -> ModelRes:
        res = ModelRes()
        matches = re.findall(cls.dynamic_config.pattern, input_data.content)
        if matches:
            res.error_status = True
            res.type = cls.metric_type
            res.name = cls.__name__
            res.reason = matches
        return res


@Model.rule_register('QUALITY_BAD_COMPLETENESS', ['pretrain'])
class RuleSentenceNumber(BaseRule):
    """Check whether the number of sentence in [3, 7500]"""

    dynamic_config = DynamicRuleConfig(key_list=['3', '7500'])

    @classmethod
    def eval(cls, input_data: Data) -> ModelRes:
        res = ModelRes()
        raw_content = input_data.content

        SENT_PATTERN = re.compile(r'\b[^.!?\n]+[.!?]*', flags=re.UNICODE)
        num_sentence = len(SENT_PATTERN.findall(raw_content))
        if num_sentence < int(cls.dynamic_config.key_list[0]) or num_sentence > int(cls.dynamic_config.key_list[1]):
            res.error_status = True
            res.type = cls.metric_type
            res.name = cls.__name__
            res.reason = ['The number of sentence is: ' + str(num_sentence)]
        return res


@Model.rule_register(
    'QUALITY_BAD_EFFECTIVENESS',
    [
        'text_base_all',
        'llm_base',
        'multi_lan_ar',
        'multi_lan_ko',
        'multi_lan_ru',
        'multi_lan_th',
        'multi_lan_vi',
        'multi_lan_cs',
        'multi_lan_hu',
        'multi_lan_sr',
        'pdf',
    ],
)
class RuleSpaceMore(BaseRule):
    """Check whether content has 500 spaces."""

    dynamic_config = DynamicRuleConfig(pattern=' {500,}')

    @classmethod
    def eval(cls, input_data: Data) -> ModelRes:
        res = ModelRes()
        content = input_data.content
        SEARCH_REGEX = re.compile(cls.dynamic_config.pattern)
        match = SEARCH_REGEX.search(content)
        if match:
            res.error_status = True
            res.type = cls.metric_type
            res.name = cls.__name__
            res.reason = ['Content has 500 spaces.']
        return res


@Model.rule_register(
    'QUALITY_BAD_EFFECTIVENESS',
    [
        'default',
        'sft',
        'pretrain',
        'benchmark',
        'text_base_all',
        'llm_base',
        'multi_lan_ar',
        'multi_lan_ko',
        'multi_lan_ru',
        'multi_lan_th',
        'multi_lan_vi',
        'multi_lan_cs',
        'multi_lan_hu',
        'multi_lan_sr',
        'pdf',
    ],
)
class RuleSpecialCharacter(BaseRule):
    """Check whether content has special characters."""

    dynamic_config = DynamicRuleConfig(
        key_list=[
            r'u200e',
            # r"(\\\\;){3,}|(\{\}){3,}|(&nbsp;){3,}",
            r'&#247;|\? :',
            r'[�□]|\{\/U\}',
            r'U\+26[0-F][0-D]|U\+273[3-4]|U\+1F[3-6][0-4][0-F]|U\+1F6[8-F][0-F]',
            r'<\|.*?\|>',
        ]
    )

    @classmethod
    def eval(cls, input_data: Data) -> ModelRes:
        res = ModelRes()
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
            res.error_status = True
            res.type = cls.metric_type
            res.name = cls.__name__
            res.reason = list(set(matches))
        return res


@Model.rule_register('QUALITY_BAD_EFFECTIVENESS', ['pretrain'])
class RuleStopWord(BaseRule):
    """Check whether the ratio of stop word > 0.06."""

    dynamic_config = DynamicRuleConfig(threshold=0.06)

    @classmethod
    def eval(cls, input_data: Data) -> ModelRes:
        from dingo.model.rule.utils.util import get_stop_words
        from nltk.tokenize import WordPunctTokenizer

        res = ModelRes()
        raw_content = input_data.content
        raw_words = list(WordPunctTokenizer().tokenize(raw_content))
        raw_words = [str(w).lower() for w in raw_words]
        num_raw_words = len(raw_words)
        if num_raw_words == 0:
            return res

        STOP_WORDS = get_stop_words('en')
        num_stop_words = len(list(filter(lambda word: word in STOP_WORDS, raw_words)))
        ratio = num_stop_words / num_raw_words
        if ratio < cls.dynamic_config.threshold or num_stop_words < 2:
            res.error_status = True
            res.type = cls.metric_type
            res.name = cls.__name__
            res.reason = ['The ratio of stop words is: ' + str(ratio)]
        return res


@Model.rule_register('QUALITY_BAD_EFFECTIVENESS', ['pretrain', 'benchmark'])
class RuleSymbolWordRatio(BaseRule):
    """Check whether the ratio of symbol and word is > 0.4."""

    dynamic_config = DynamicRuleConfig(threshold=0.4, key_list=['#', '...', '…'])

    @classmethod
    def eval(cls, input_data: Data) -> ModelRes:
        from nltk.tokenize import WordPunctTokenizer

        res = ModelRes()
        raw_content = input_data.content
        raw_words = tuple(WordPunctTokenizer().tokenize(raw_content))
        num_raw_words = len(raw_words)
        if num_raw_words == 0:
            return res

        num_words = num_raw_words
        num_symbols = float(sum(raw_content.count(x) for x in cls.dynamic_config.key_list))

        ratio = num_symbols / num_words
        if ratio > cls.dynamic_config.threshold:
            res.error_status = True
            res.type = cls.metric_type
            res.name = cls.__name__
            res.reason = ['The ratio of symbol / word is: ' + str(ratio)]
        return res


@Model.rule_register('QUALITY_BAD_UNDERSTANDABILITY', ['pretrain'])
class RuleUniqueWords(BaseRule):
    """Check whether the ratio of unique words > 0.1."""

    dynamic_config = DynamicRuleConfig(threshold=0.1)

    @classmethod
    def eval(cls, input_data: Data) -> ModelRes:
        from dingo.model.rule.utils.util import normalize

        res = ModelRes()
        normalized_content = normalize(input_data.content)
        normalized_words = tuple(normalized_content.split())
        num_normalized_words = len(normalized_words)
        if num_normalized_words == 0:
            return res

        num_words = num_normalized_words
        num_unique_words = len(set(normalized_words))
        ratio = num_unique_words / num_words
        if ratio > cls.dynamic_config.threshold:
            pass
        else:
            res.error_status = True
            res.type = cls.metric_type
            res.name = cls.__name__
            res.reason = ['The ratio of unique words is: ' + str(ratio)]
        return res


@Model.rule_register('QUALITY_BAD_SECURITY', [])
class RuleUnsafeWords(BaseRule):
    """Check whether content contains unsafe words."""

    dynamic_config = DynamicRuleConfig(refer_path=[])

    @classmethod
    def eval(cls, input_data: Data) -> ModelRes:
        import ahocorasick
        from dingo.model.rule.utils.util import get_unsafe_words

        res = ModelRes()
        content = input_data.content
        key_list = cls.dynamic_config.key_list
        if key_list is None:
            key_list = get_unsafe_words(cls.dynamic_config.refer_path)

        A = ahocorasick.Automaton()
        for index, key in enumerate(key_list):
            A.add_word(key, (index, key))
        A.make_automaton()
        matches = [(end_index - len(value[1]) + 1, value[1]) for end_index, value in A.iter(content)]
        if matches:
            res.error_status = True
            res.type = cls.metric_type
            res.name = cls.__name__
            res.reason = [value for index, value in matches]
        return res


@Model.rule_register(
    'QUALITY_BAD_EFFECTIVENESS',
    [
        'text_base_all',
        'llm_base',
        'multi_lan_ar',
        'multi_lan_ko',
        'multi_lan_ru',
        'multi_lan_th',
        'multi_lan_vi',
        'multi_lan_cs',
        'multi_lan_hu',
        'multi_lan_sr',
        'qa_standard_v1',
        'pdf',
    ],
)
class RuleOnlyUrl(BaseRule):
    """Check whether content is only an url link."""

    dynamic_config = DynamicRuleConfig(
        pattern=r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
    )

    @classmethod
    def eval(cls, input_data: Data) -> ModelRes:
        res = ModelRes()
        content = input_data.content
        if len(content.strip()) == 0:
            return res
        SEARCH_REGEX = re.compile(cls.dynamic_config.pattern)
        content_without_url = SEARCH_REGEX.sub('', content)
        if len(content_without_url.strip()) == 0:
            res.error_status = True
            res.type = cls.metric_type
            res.name = cls.__name__
            res.reason = ['Content is only an url link.']
        return res


@Model.rule_register('QUALITY_BAD_RELEVANCE', [])
class RuleWatermark(BaseRule):
    """Check whether content has watermarks."""

    dynamic_config = DynamicRuleConfig(key_list=[])

    @classmethod
    def eval(cls, input_data: Data) -> ModelRes:
        res = ModelRes()
        matches = re.findall('|'.join(cls.dynamic_config.key_list), input_data.content)
        if matches:
            res.error_status = True
            res.type = cls.metric_type
            res.name = cls.__name__
            res.reason = matches
        return res


@Model.rule_register('QUALITY_BAD_COMPLETENESS', ['pretrain'])
class RuleWordNumber(BaseRule):
    """Check whether the number of word in [20, 100000]"""

    dynamic_config = DynamicRuleConfig(key_list=['20', '100000'])

    @classmethod
    def eval(cls, input_data: Data) -> ModelRes:
        from dingo.model.rule.utils.util import normalize

        res = ModelRes()
        normalized_content = normalize(input_data.content)
        normalized_words = tuple(normalized_content.split())
        num_normalized_words = len(normalized_words)
        if num_normalized_words >= int(cls.dynamic_config.key_list[0]) and num_normalized_words < int(
            cls.dynamic_config.key_list[1]
        ):
            pass
        else:
            res.error_status = True
            res.type = cls.metric_type
            res.name = cls.__name__
            res.reason = ['The number of word is: ' + str(num_normalized_words)]
        return res


@Model.rule_register('QUALITY_BAD_FLUENCY', ['pdf_all'])
class RuleWordSplit(BaseRule):
    """Check pdf word abnormal split such as "ca- se"."""

    dynamic_config = DynamicRuleConfig(pattern=r'[A-Za-z]+-\s*$')

    @classmethod
    def eval(cls, input_data: Data) -> ModelRes:
        res = ModelRes()
        content = input_data.content
        match = re.findall(cls.dynamic_config.pattern, content)
        if match:
            res.error_status = True
            res.type = cls.metric_type
            res.name = cls.__name__
            res.reason = match
        return res


@Model.rule_register(
    'QUALITY_BAD_FLUENCY',
    [
        'text_base_all',
        'llm_base',
        'multi_lan_ar',
        'multi_lan_ko',
        'multi_lan_ru',
        'multi_lan_th',
        'multi_lan_vi',
        'multi_lan_cs',
        'multi_lan_hu',
        'multi_lan_sr',
    ],
)
class RuleWordStuck(BaseRule):
    """Check whether words are stuck."""

    dynamic_config = DynamicRuleConfig(
        key_list=[
            r'https?://[^\s]+|www.(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+',
            r'\.pdf$',
            r'\w+\.bat',
            r'(\/.*\/.*)',
            r'[01]+|[0-7]+|0x[0-9a-fA-F]+',
        ]
    )

    @classmethod
    def eval(cls, input_data: Data) -> ModelRes:
        import wordninja
        from dingo.model.rule.utils.detect_lang import (decide_language_by_str,
                                                        set_fasttext)
        from dingo.model.rule.utils.util import is_sha256

        res = ModelRes()
        content = input_data.content

        for p in cls.dynamic_config.key_list:
            content = re.sub(p, '', content)
        word_list = [
            word.strip(string.punctuation)
            for word in re.split(r'[⁃>#%-.—,–!?;:\s|_/   =\\@\((.*?)\)\[(.*?)\]]\s*', content)
        ]
        for longest_string in word_list:
            if len(longest_string) > 45 and is_sha256(longest_string) == False:
                lan = decide_language_by_str(longest_string)
                cut = wordninja.split(longest_string)
                if lan == 'en' and len(cut) > 1:
                    res.error_status = True
                    res.type = cls.metric_type
                    res.name = cls.__name__
                    res.reason = [str(longest_string)]
                    return res
        return res


if __name__ == '__main__':
    data = Data(data_id='', prompt='', content='\n \n \n \n hello \n \n ')
    tmp = RuleEnterAndSpace().eval(data)
    print(tmp)
