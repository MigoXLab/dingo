import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from dingo.config.input_args import EvaluatorRuleArgs
from dingo.io.input import Data
from dingo.io.output.eval_detail import EvalDetail, QualityLabel
from dingo.model.model import Model
from dingo.model.rule.base import BaseRule

URL_RE = re.compile(r"^[Hh][Tt][Tt][Pp][Ss]?://[^/$.?#][\s\S]*$")
DOI_RE = re.compile(r"^10\.\d{4,9}/[^\s|]+$", re.IGNORECASE)
DOI_PREFIXES_RE = {"10.0000", "10.0001", "10.5555"}
SPECIAL_CHAR_INVISIBLE_RE = re.compile(
    r"[\u2000-\u200F\u202F\u205F\u3000\uFEFF\u00A0\u2060-\u206F\xa0]"
)
HTML_TAG_LAYOUT_RE = re.compile(
    r"<\s*/?\s*(?:i|b|p|br|sup|sub|em|strong|span|div|u|scp|tt)\b[^>]*>",
    re.IGNORECASE,
)
HTML_TAG_MATH_RE = re.compile(
    r"<\s*/?\s*(?:mml:)?(?:math|mrow|mi|mn|mo|ms|mtext|mspace|msub|msup|msubsup|"
    r"mfrac|msqrt|mroot|mtable|mtr|mtd|mfenced|munderover|munder|mover)\b[^>]*>",
    re.IGNORECASE,
)
HTML_TAG_XML_COMMENT_RE = re.compile(r"<!--[\s\S]*?-->")
HTML_TAG_CDATA_RE = re.compile(r"<!\[CDATA\[[\s\S]*?\]\]>", re.IGNORECASE)
HTML_ENTITY_NAMED_RE = re.compile(r"&[A-Za-z][A-Za-z0-9]+;")
HTML_ENTITY_DECIMAL_RE = re.compile(r"&#[0-9]+;")
HTML_ENTITY_HEX_RE = re.compile(r"&#[xX][0-9A-Fa-f]+;")
SPECIAL_CHAR_REPLACEMENT_RE = re.compile("\uFFFD")
# Keep TAB, LF and CR because multi-line abstracts may legitimately contain them.
SPECIAL_CHAR_CONTROL_RE = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]")
SPECIAL_CHAR_MARKUP_RE = re.compile(
    r"\[(?:!\s*/?\s*(?:i|sub|sup)\s*|!|○![R上下])\]",
    re.IGNORECASE,
)

# Nested reference titles still use the legacy flat taxonomy above. Title and
# abstract each have an independent, field-specific hierarchical taxonomy below.
TITLE_HTML_TAG_FORMATTING_RE = re.compile(
    r"<\s*/?\s*(?:(?:jats|ns\d+|xhtml):)?(?:i|b|strong|em|u|scp|tt)"
    r"(?=[\s/>])[^>]*>",
    re.IGNORECASE,
)
TITLE_HTML_TAG_STRUCTURE_RE = re.compile(
    r"<\s*/?\s*(?:(?:jats|ns\d+|xhtml):)?(?:p|div|span|br)(?=[\s/>])[^>]*>",
    re.IGNORECASE,
)
TITLE_HTML_TAG_LINK_RE = re.compile(
    r"<\s*/?\s*(?:(?:jats|ns\d+|xhtml):)?(?:a|ext-link)(?=[\s/>])[^>]*>",
    re.IGNORECASE,
)
TITLE_HTML_TAG_MEDIA_RE = re.compile(
    r"<\s*/?\s*(?:(?:jats|ns\d+|xhtml):)?(?:img|graphic|inline-graphic)"
    r"(?=[\s/>])[^>]*>",
    re.IGNORECASE,
)
TITLE_HTML_TAG_NAMESPACED_RE = re.compile(
    r"<\s*/?\s*(?:jats|ns\d+|xhtml):[A-Za-z_][\w.-]*(?=[\s/>])[^>]*>",
    re.IGNORECASE,
)
TITLE_HTML_TAG_SUB_SUP_RE = re.compile(
    r"<\s*/?\s*(?:(?:jats|ns\d+|xhtml):)?(?:sub|sup)(?=[\s/>])[^>]*>",
    re.IGNORECASE,
)
TITLE_HTML_TAG_MATH_RE = re.compile(
    r"<\s*/?\s*(?:(?:mml:)?(?:math|mrow|mi|mn|mo|ms|mtext|mspace|msub|msup|"
    r"msubsup|mfrac|msqrt|mroot|mtable|mtr|mtd|mfenced|munderover|munder|mover)|"
    r"(?:(?:jats|ns\d+|xhtml):)?(?:inline-formula|tex))(?=[\s/>])[^>]*>",
    re.IGNORECASE,
)
TITLE_MARKUP_TAG_FORMATTING_RE = re.compile(
    r"\[(?:!\s*/?\s*(?:i|sub|sup)\s*|!)\]",
    re.IGNORECASE,
)
TITLE_MARKUP_TAG_CRAWLER_RE = re.compile(r"\[○![^\]\r\n]+\]", re.IGNORECASE)
TITLE_CHARACTER_RE = re.compile(
    r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F\u00A0\u2000-\u200F\u202A-\u202F"
    r"\u205F\u2066-\u2069\u3000\uE000-\uF8FF\uFEFF\uFFFD]"
)

_TITLE_FORMATTING_TAG_NAMES = {"i", "b", "strong", "em", "u", "scp", "tt"}
_TITLE_STRUCTURE_TAG_NAMES = {"p", "div", "span", "br"}
_TITLE_LINK_TAG_NAMES = {"a", "ext-link"}
_TITLE_MEDIA_TAG_NAMES = {"img", "graphic", "inline-graphic"}
_TITLE_SUB_SUP_TAG_NAMES = {"sub", "sup"}
_TITLE_MATH_TAG_NAMES = {
    "math",
    "mrow",
    "mi",
    "mn",
    "mo",
    "ms",
    "mtext",
    "mspace",
    "msub",
    "msup",
    "msubsup",
    "mfrac",
    "msqrt",
    "mroot",
    "mtable",
    "mtr",
    "mtd",
    "mfenced",
    "munderover",
    "munder",
    "mover",
    "inline-formula",
    "tex",
}
_TITLE_KNOWN_LOCAL_TAG_NAMES = (
    _TITLE_FORMATTING_TAG_NAMES
    | _TITLE_STRUCTURE_TAG_NAMES
    | _TITLE_LINK_TAG_NAMES
    | _TITLE_MEDIA_TAG_NAMES
    | _TITLE_SUB_SUP_TAG_NAMES
    | _TITLE_MATH_TAG_NAMES
)
_TITLE_VOID_TAG_NAMES = {"br", "img", "graphic", "inline-graphic"}
_TITLE_LOCAL_TAG_PATTERN = "|".join(
    sorted((re.escape(name) for name in _TITLE_KNOWN_LOCAL_TAG_NAMES), key=lambda name: (-len(name), name))
)
_TITLE_MATH_TAG_PATTERN = "|".join(
    sorted((re.escape(name) for name in _TITLE_MATH_TAG_NAMES), key=lambda name: (-len(name), name))
)
_TITLE_RECOGNIZED_TAG_NAME_PATTERN = (
    rf"(?:(?:jats|ns\d+|xhtml):[A-Za-z_][\w.-]*|"
    rf"mml:(?:{_TITLE_MATH_TAG_PATTERN})|(?:{_TITLE_LOCAL_TAG_PATTERN}))"
)
TITLE_RECOGNIZED_TAG_START_RE = re.compile(
    rf"<\s*/?\s*{_TITLE_RECOGNIZED_TAG_NAME_PATTERN}(?=[\s/>]|$)",
    re.IGNORECASE,
)
TITLE_RECOGNIZED_COMPLETE_TAG_RE = re.compile(
    rf"<\s*(?P<closing>/?)\s*(?P<name>{_TITLE_RECOGNIZED_TAG_NAME_PATTERN})"
    rf"(?=[\s/>])(?P<attributes>[^>]*)>",
    re.IGNORECASE,
)
TITLE_CLOSING_TAG_WITHOUT_OPEN_BRACKET_RE = re.compile(
    rf"(?<![\w:/<])/\s*{_TITLE_RECOGNIZED_TAG_NAME_PATTERN}\s*>",
    re.IGNORECASE,
)
_TITLE_TAG_PATTERN_CHECKS = (
    (TITLE_HTML_TAG_FORMATTING_RE, "html_tag.formatting", "contains HTML formatting tag"),
    (TITLE_HTML_TAG_STRUCTURE_RE, "html_tag.structure", "contains HTML structure tag"),
    (TITLE_HTML_TAG_LINK_RE, "html_tag.link", "contains HTML/XML link tag"),
    (TITLE_HTML_TAG_MEDIA_RE, "html_tag.media", "contains HTML/XML media tag"),
    (TITLE_HTML_TAG_NAMESPACED_RE, "html_tag.namespaced", "contains namespaced XML tag"),
    (HTML_TAG_XML_COMMENT_RE, "html_tag.xml_comment", "contains XML comment"),
    (HTML_TAG_CDATA_RE, "html_tag.cdata", "contains CDATA section"),
    # Temporarily allow scientific subscript/superscript markup such as H<sub>2</sub>O.
    # (TITLE_HTML_TAG_SUB_SUP_RE, "html_tag.sub_sup", "contains subscript or superscript tag"),
    (TITLE_HTML_TAG_MATH_RE, "html_tag.math", "contains MathML or formula tag"),
)
_TITLE_ENTITY_PATTERN_CHECKS = (
    (HTML_ENTITY_NAMED_RE, "html_entity.named", "contains named HTML entity"),
    (HTML_ENTITY_DECIMAL_RE, "html_entity.decimal", "contains decimal HTML entity"),
    (HTML_ENTITY_HEX_RE, "html_entity.hex", "contains hexadecimal HTML entity"),
)
_TITLE_MARKUP_PATTERN_CHECKS = (
    (TITLE_MARKUP_TAG_FORMATTING_RE, "markup_tag.formatting", "contains bracket formatting token"),
    (TITLE_MARKUP_TAG_CRAWLER_RE, "markup_tag.crawler", "contains crawler markup token"),
)
_TITLE_CHARACTER_CHECKS = (
    ("special_char.replacement", "contains unicode replacement character"),
    ("special_char.control", "contains control character"),
    ("special_char.private_use_area", "contains unicode private-use character"),
    ("invisible_char.zero_width_space", "contains zero-width space"),
    ("invisible_char.bom", "contains BOM character"),
    ("invisible_char.zwnj", "contains ZWNJ character"),
    ("invisible_char.zwj", "contains ZWJ character"),
    ("invisible_char.bidi_control", "contains bidirectional control character"),
    ("space_char.nbsp", "contains non-breaking space"),
    ("space_char.typographic", "contains typographic space"),
)
TITLE_PLACEHOLDER_VALUES = {
    "[untitled]", "untitled", "(no title)", "[no title]", "[no title available]",
    "no title", "unknown", "n/a", "na", "none", "null", "not available",
    "[not available].", "not applicable", "missing", "missing title", "title missing",
    "without title", "tbd", "to be determined", "---", "--", "-", ".",
}
TITLE_ENCODING_ERROR_RE = re.compile(
    r"�|锟斤拷|烫烫烫|屯屯屯|Ã.|Â.|â€™|â€œ|â€|â€“|â€”|â€¦|ï»¿"
)
TITLE_CONFERENCE_RE = re.compile(
    r"^(?:\[\s*)?(?:\d{4}[\s-]+)?ieee\b.*\b"
    r"(?:proceedings|conference|symposium|workshop|congress)\b",
    re.IGNORECASE,
)
TITLE_IDENTIFIER_RE = re.compile(
    r"(?:\d+|(?:doi\s*:\s*)?10\.\d{4,9}/\S+|"
    r"https?://(?:dx\.)?doi\.org/10\.\d{4,9}/\S+|"
    r"(?:https?://|www\.|s3a?://)\S+)",
    re.IGNORECASE,
)
ABSTRACT_PLACEHOLDER_VALUES = {"n/a", "na", "none", "null", "unknown", "-", "--", "."}
ABSTRACT_PLACEHOLDER_RE = re.compile(
    r"^(?:no abstract(?: available)?|abstract (?:is )?(?:not available|unavailable|not provided|"
    r"not supplied|not received|missing)|not available|unavailable)[.!]?$",
    re.IGNORECASE,
)
ABSTRACT_ENCODING_ERROR_RE = re.compile(
    r"�|锟斤拷|烫烫烫|屯屯屯|Ã.|Â.|â€™|â€œ|â€|â€“|â€”|â€¦|ï»¿"
)
ABSTRACT_IDENTIFIER_RE = re.compile(
    r"(?:\d+|(?:doi\s*:\s*)?10\.\d{4,9}/\S+|"
    r"https?://(?:dx\.)?doi\.org/10\.\d{4,9}/\S+|"
    r"(?:https?://|www\.|s3a?://)\S+)",
    re.IGNORECASE,
)

# Abstract tag types are intentionally independent from title tag types. In
# particular, exact ``jats:`` tags are classified only as ``html_tag.jats`` and
# exact ``mml:`` tags are classified only as ``html_tag.math``.
ABSTRACT_HTML_TAG_FORMATTING_RE = re.compile(
    r"<\s*/?\s*(?:i|b|strong|em|u|scp|tt)(?=[\s/>])[^>]*>",
    re.IGNORECASE,
)
ABSTRACT_HTML_TAG_STRUCTURE_RE = re.compile(
    r"<\s*/?\s*(?:p|br|div|span|h[1-6]|pre|blockquote|ul|ol|li|dl|dt|dd|"
    r"table|thead|tbody|tfoot|tr|th|td|caption|section|article|header|footer|"
    r"main|nav|aside|figure|figcaption|hr|details|summary)(?=[\s/>])[^>]*>",
    re.IGNORECASE,
)
ABSTRACT_HTML_TAG_LINK_RE = re.compile(
    r"<\s*/?\s*(?:a|ext-link|xref)(?=[\s/>])[^>]*>",
    re.IGNORECASE,
)
ABSTRACT_HTML_TAG_MEDIA_RE = re.compile(
    r"<\s*/?\s*(?:img|inline-graphic|graphic|iframe|picture|video|audio|"
    r"source|track|object|embed|canvas|svg)(?=[\s/>])[^>]*>",
    re.IGNORECASE,
)
ABSTRACT_HTML_TAG_JATS_RE = re.compile(
    r"<\s*/?\s*jats:[A-Za-z_][\w.-]*(?=[\s/>])[^>]*>",
    re.IGNORECASE,
)
ABSTRACT_HTML_TAG_NAMESPACED_RE = re.compile(
    r"<\s*/?\s*(?!(?:jats|mml):)[A-Za-z_][\w.-]*:[A-Za-z_][\w.-]*"
    r"(?=[\s/>])[^>]*>",
    re.IGNORECASE,
)
ABSTRACT_HTML_TAG_XML_DECLARATION_RE = re.compile(
    r"<\?xml\b[\s\S]*?\?>",
    re.IGNORECASE,
)
ABSTRACT_HTML_TAG_DOCTYPE_RE = re.compile(
    r"<!DOCTYPE\b[\s\S]*?>",
    re.IGNORECASE,
)
ABSTRACT_HTML_TAG_SUB_SUP_RE = re.compile(
    r"<\s*/?\s*(?:sub|sup)(?=[\s/>])[^>]*>",
    re.IGNORECASE,
)
ABSTRACT_HTML_TAG_MATH_RE = re.compile(
    r"<\s*/?\s*(?:mml:[A-Za-z_][\w.-]*|math|mrow|mi|mn|mo|ms|mtext|mspace|"
    r"msub|msup|msubsup|mfrac|msqrt|mroot|mtable|mtr|mtd|mfenced|munderover|"
    r"munder|mover|inline-formula|disp-formula|tex|tex-math)(?=[\s/>])[^>]*>",
    re.IGNORECASE,
)
ABSTRACT_MARKUP_TAG_FORMATTING_RE = re.compile(
    r"\[(?:!\s*/?\s*(?:i|sub|sup)\s*|!)\]",
    re.IGNORECASE,
)
ABSTRACT_MARKUP_TAG_CRAWLER_RE = re.compile(r"\[○![^\]\r\n]+\]", re.IGNORECASE)
ABSTRACT_CRAWLER_ETX_RE = re.compile(r"<<\s*ETX\s*>>|<\s*ETX\s*>", re.IGNORECASE)
ABSTRACT_CRAWLER_NAVIGATION_RE = re.compile(
    r"<\s*previous\s+page\s*\|\s*next\s+page\s*>",
    re.IGNORECASE,
)
ABSTRACT_CRAWLER_TEMPLATE_RE = re.compile(
    r"(?im)^[ \t]*(?:download\s+(?:the\s+)?(?:pdf|full\s+text)|"
    r"view\s+(?:the\s+)?full\s+text|click\s+here\s+to\s+(?:download|view)|"
    r"skip\s+to\s+main\s+content|back\s+to\s+top)[ \t]*[.!]?[ \t]*$"
)
ABSTRACT_CHARACTER_RE = re.compile(
    r"[\x00-\x09\x0B\x0C\x0E-\x1F\x7F\u00A0\u00AD\u2000-\u200F"
    r"\u202A-\u202F\u205F\u2066-\u2069\u3000\uE000-\uF8FF\uFEFF\uFFFD]"
)

_ABSTRACT_FORMATTING_TAG_NAMES = {"i", "b", "strong", "em", "u", "scp", "tt"}
_ABSTRACT_STRUCTURE_TAG_NAMES = {
    "p", "br", "div", "span", "h1", "h2", "h3", "h4", "h5", "h6", "pre",
    "blockquote", "ul", "ol", "li", "dl", "dt", "dd", "table", "thead", "tbody",
    "tfoot", "tr", "th", "td", "caption", "section", "article", "header", "footer",
    "main", "nav", "aside", "figure", "figcaption", "hr", "details", "summary",
}
_ABSTRACT_LINK_TAG_NAMES = {"a", "ext-link", "xref"}
_ABSTRACT_MEDIA_TAG_NAMES = {
    "img", "inline-graphic", "graphic", "iframe", "picture", "video", "audio", "source",
    "track", "object", "embed", "canvas", "svg",
}
_ABSTRACT_SUB_SUP_TAG_NAMES = {"sub", "sup"}
_ABSTRACT_MATH_TAG_NAMES = {
    "math", "mrow", "mi", "mn", "mo", "ms", "mtext", "mspace", "msub", "msup",
    "msubsup", "mfrac", "msqrt", "mroot", "mtable", "mtr", "mtd", "mfenced",
    "munderover", "munder", "mover", "inline-formula", "disp-formula", "tex", "tex-math",
}
_ABSTRACT_KNOWN_LOCAL_TAG_NAMES = (
    _ABSTRACT_FORMATTING_TAG_NAMES
    | _ABSTRACT_STRUCTURE_TAG_NAMES
    | _ABSTRACT_LINK_TAG_NAMES
    | _ABSTRACT_MEDIA_TAG_NAMES
    | _ABSTRACT_SUB_SUP_TAG_NAMES
    | _ABSTRACT_MATH_TAG_NAMES
)
_ABSTRACT_VOID_TAG_NAMES = {
    "area", "base", "br", "col", "embed", "graphic", "hr", "img", "inline-graphic",
    "input", "link", "meta", "param", "source", "track", "wbr",
}
_ABSTRACT_LOCAL_TAG_PATTERN = "|".join(
    sorted(
        (re.escape(name) for name in _ABSTRACT_KNOWN_LOCAL_TAG_NAMES),
        key=lambda name: (-len(name), name),
    )
)
_ABSTRACT_RECOGNIZED_TAG_NAME_PATTERN = (
    rf"(?:[A-Za-z_][\w.-]*:[A-Za-z_][\w.-]*|(?:{_ABSTRACT_LOCAL_TAG_PATTERN}))"
)
ABSTRACT_RECOGNIZED_TAG_START_RE = re.compile(
    rf"<\s*/?\s*{_ABSTRACT_RECOGNIZED_TAG_NAME_PATTERN}(?=[\s/>]|$)",
    re.IGNORECASE,
)
ABSTRACT_RECOGNIZED_COMPLETE_TAG_RE = re.compile(
    rf"<\s*(?P<closing>/?)\s*(?P<name>{_ABSTRACT_RECOGNIZED_TAG_NAME_PATTERN})"
    rf"(?=[\s/>])(?P<attributes>[^>]*)>",
    re.IGNORECASE,
)
ABSTRACT_CLOSING_TAG_WITHOUT_OPEN_BRACKET_RE = re.compile(
    rf"(?<![\w:/<])/\s*{_ABSTRACT_RECOGNIZED_TAG_NAME_PATTERN}\s*>",
    re.IGNORECASE,
)

_ABSTRACT_TAG_PATTERN_CHECKS = (
    (ABSTRACT_HTML_TAG_FORMATTING_RE, "html_tag.formatting", "contains HTML formatting tag"),
    (ABSTRACT_HTML_TAG_STRUCTURE_RE, "html_tag.structure", "contains HTML structure tag"),
    (ABSTRACT_HTML_TAG_LINK_RE, "html_tag.link", "contains HTML/XML link tag"),
    (ABSTRACT_HTML_TAG_MEDIA_RE, "html_tag.media", "contains HTML/XML media tag"),
    (ABSTRACT_HTML_TAG_JATS_RE, "html_tag.jats", "contains JATS tag"),
    (ABSTRACT_HTML_TAG_NAMESPACED_RE, "html_tag.namespaced", "contains namespaced XML tag"),
    (HTML_TAG_XML_COMMENT_RE, "html_tag.xml_comment", "contains XML comment"),
    (HTML_TAG_CDATA_RE, "html_tag.cdata", "contains CDATA section"),
    (
        ABSTRACT_HTML_TAG_XML_DECLARATION_RE,
        "html_tag.xml_declaration",
        "contains XML declaration",
    ),
    (ABSTRACT_HTML_TAG_DOCTYPE_RE, "html_tag.doctype", "contains DOCTYPE declaration"),
    # Temporarily allow scientific subscript/superscript markup such as H<sub>2</sub>O.
    # (ABSTRACT_HTML_TAG_SUB_SUP_RE, "html_tag.sub_sup", "contains subscript or superscript tag"),
    (ABSTRACT_HTML_TAG_MATH_RE, "html_tag.math", "contains MathML or formula tag"),
)
_ABSTRACT_ENTITY_PATTERN_CHECKS = (
    (HTML_ENTITY_NAMED_RE, "html_entity.named", "contains named HTML entity"),
    (HTML_ENTITY_DECIMAL_RE, "html_entity.decimal", "contains decimal HTML entity"),
    (HTML_ENTITY_HEX_RE, "html_entity.hex", "contains hexadecimal HTML entity"),
)
_ABSTRACT_MARKUP_PATTERN_CHECKS = (
    (ABSTRACT_MARKUP_TAG_FORMATTING_RE, "markup_tag.formatting", "contains bracket formatting token"),
    (ABSTRACT_MARKUP_TAG_CRAWLER_RE, "markup_tag.crawler", "contains crawler markup token"),
)
_ABSTRACT_CRAWLER_PATTERN_CHECKS = (
    (ABSTRACT_CRAWLER_ETX_RE, "crawler_residue.etx", "contains visible ETX token"),
    (
        ABSTRACT_CRAWLER_NAVIGATION_RE,
        "crawler_residue.navigation",
        "contains page navigation residue",
    ),
    (
        ABSTRACT_CRAWLER_TEMPLATE_RE,
        "crawler_residue.template",
        "contains page template residue",
    ),
)
_ABSTRACT_CHARACTER_CHECKS = (
    ("special_char.replacement", "contains unicode replacement character"),
    ("special_char.control", "contains control character"),
    ("special_char.private_use_area", "contains unicode private-use character"),
    ("invisible_char.zero_width_space", "contains zero-width space"),
    ("invisible_char.bom", "contains BOM character"),
    ("invisible_char.soft_hyphen", "contains soft hyphen"),
    ("invisible_char.zwnj", "contains ZWNJ character"),
    ("invisible_char.zwj", "contains ZWJ character"),
    ("invisible_char.bidi_control", "contains bidirectional control character"),
    ("space_char.nbsp", "contains non-breaking space"),
    ("space_char.typographic", "contains typographic space"),
    ("space_char.tab", "contains TAB character"),
)
ABSTRACT_CONSECUTIVE_LINE_BREAK_THRESHOLD = 3
ABSTRACT_LINE_BREAK_COUNT_THRESHOLD = 20
ABSTRACT_LINE_BREAK_DENSITY_MIN_COUNT = 5
ABSTRACT_LINE_BREAK_DENSITY_THRESHOLD = 0.05
PAGE_RANGE_RE = re.compile(r"^\d+-\d+$")
ISSN_RE = re.compile(r"^\d{4}-\d{3}[\dX]$")
AUTHOR_SEP_RE = re.compile(r"[|;；]|,,|，，")
ORCID_URL_RE = re.compile(r"^https://orcid\.org/\d{4}-\d{4}-\d{4}-\d{3}[\dX]$")

# These patterns intentionally favor recall: a downstream LLM decides whether a
# candidate really contains multiple people.  Keep the individual evidence names
# stable so sampled results remain easy to diagnose.
AUTHOR_ELLIPSIS_RE = re.compile(
    r"(?:\bet\s+al\.?(?:\s|$)|[\u4e00-\u9fff]\u7b49)$", re.IGNORECASE
)
AUTHOR_CONJUNCTION_RE = re.compile(
    r"(?:\b(?:and(?:\s*/\s*or)?|et|und|y)\b|"
    r"(?<=[^\W\d_])(?:\u548c|\u4e0e|\u53ca)(?=[^\W\d_])|\u3001)",
    re.IGNORECASE,
)
AUTHOR_LIST_SEPARATOR_RE = re.compile(r"[;\uff1b|\n\r\t]|(?<=\s)/(?=\s)")
AUTHOR_CJK_COMMA_NAMES_RE = re.compile(
    r"[\u4e00-\u9fff\u00b7\u2022\u30fb]{2,8}\s*[,\uff0c]\s*"
    r"[\u4e00-\u9fff\u00b7\u2022\u30fb]{2,8}"
)
AUTHOR_WESTERN_COMMA_NAMES_RE = re.compile(
    r"[A-Za-z\u00c0-\u024f][A-Za-z\u00c0-\u024f'\-\u2019.]*"
    r"(?:\s+[A-Za-z\u00c0-\u024f][A-Za-z\u00c0-\u024f'\-\u2019.]*)+"
    r"\s*[,\uff0c]\s*"
    r"[A-Za-z\u00c0-\u024f][A-Za-z\u00c0-\u024f'\-\u2019.]*"
    r"(?:\s+[A-Za-z\u00c0-\u024f][A-Za-z\u00c0-\u024f'\-\u2019.]*)+"
)
AUTHOR_CJK_WHITESPACE_NAMES_RE = re.compile(
    r"^(?:[\u4e00-\u9fff\u00b7\u2022\u30fb]{2,6}\s+){1,}"
    r"[\u4e00-\u9fff\u00b7\u2022\u30fb]{2,6}$"
)

OA_BOOL_VALUES = {"true", "false", "unknown"}
METADATA_TYPE_VALUES = {"paper", "ebook"}
OA_STATUS_VALUES = {"diamond", "gold", "green", "hybrid", "bronze", "closed", ""}
OPEN_OA_STATUS_VALUES = {"diamond", "gold", "green", "hybrid", "bronze"}
LOC_TYPE_VALUES = {"download", "reader", "display", ""}
JSON_LIST_FIELDS = {
    "isbns",
    "author",
    "contributors",
    "locations",
    "access_oa_url",
    "publication_venue_issn",
    "references",
    "related_works",
    "citations",
    "supplementary_material",
}
LICENSE_VALUES = {
    "cc-by",
    "cc-by-nc",
    "cc-by-sa",
    "cc-by-nd",
    "cc-by-nc-sa",
    "cc-by-nc-nd",
    "other-oa",
    "cc0",
    "",
    "public-domain",
    "publisher-specific-oa",
    "publisher-specific",
    "wiley-specific",
    "elsevier-specific",
    "oup-specific",
    "acs-specific",
    "rsc-specific",
    "iop-specific",
    "unspecified-oa",
    "implied-oa",
    "nonexclusive-distrib",
    "gpl-v1",
    "gpl-v2",
    "gpl-v3",
    "mit",
    "ogl-c",
    "pd",
}
ACCESS_LICENSE_VALUES = set(LICENSE_VALUES)
GRADE_CLASS_VALUES = {"k12", "higher-edu", "vocational-edu", "other", ""}
GRADE_VALUES = {"小学", "初中", "高中", ""}
XINGHE_REPOSITORY_MODEL_VERSION_MAP = {
    "mineru": {"1.3.1", "2", "2.5"},
    "llm-web-kit": {"4.1.1"},
}
XINGHE_REPOSITORY_MODEL_NAME_VALUES = set(XINGHE_REPOSITORY_MODEL_VERSION_MAP.keys())
XINGHE_REPOSITORY_MODEL_VERSION_VALUES = {
    version
    for versions in XINGHE_REPOSITORY_MODEL_VERSION_MAP.values()
    for version in versions
}

_DEFAULT_LANGUAGE_VALUES = {"zh", "en", "ja", "de", "fr", "es", "ru", "ko", "ar"}
ASSETS_DIR = Path(__file__).resolve().parent / "assets"


def _load_language_allowed_values() -> set[str]:
    base = ASSETS_DIR / "to_iso-639.json"
    if not base.exists():
        return set(_DEFAULT_LANGUAGE_VALUES)
    try:
        with base.open("r", encoding="utf-8") as f:
            values = json.load(f)
        if isinstance(values, dict):
            return set(str(v) for v in values.values() if isinstance(v, str))
    except (TypeError, ValueError, json.JSONDecodeError):
        return set(_DEFAULT_LANGUAGE_VALUES)
    return set(_DEFAULT_LANGUAGE_VALUES)


def _load_journal_mapping() -> Dict[str, str]:
    csv_path = ASSETS_DIR / "journal_name_mapping_execute_20260512.csv"
    if not csv_path.exists():
        return {}
    # Lazy import to avoid top-level optional dependency / heavier import.
    import csv

    mapping: Dict[str, str] = {}
    with csv_path.open("r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            source_name = row.get("source_journal_name")
            target_name = row.get("target_journal_name")
            if source_name and target_name:
                mapping[source_name] = target_name
    return mapping


LANGUAGE_ALLOWED_VALUES = _load_language_allowed_values()
JOURNAL_NAME_MAPPING = _load_journal_mapping()


def _valid_isbn10(code: str) -> bool:
    if not re.fullmatch(r"\d{9}[\dXx]", code):
        return False
    total = sum((10 - idx) * int(ch) for idx, ch in enumerate(code[:9]))
    check = code[9].upper()
    check_value = 10 if check == "X" else int(check)
    total += check_value
    return total % 11 == 0


def _valid_isbn13(code: str) -> bool:
    if not re.fullmatch(r"\d{13}", code):
        return False
    if not (code.startswith("978") or code.startswith("979")):
        return False
    total = sum(int(ch) * (1 if idx % 2 == 0 else 3) for idx, ch in enumerate(code))
    return total % 10 == 0


def _valid_issn(code: str) -> bool:
    if not ISSN_RE.fullmatch(code):
        return False
    digits = code.replace("-", "")
    total = sum(int(ch) * (8 - idx) for idx, ch in enumerate(digits[:7]))
    calculated = (11 - (total % 11)) % 11
    expected = "X" if calculated == 10 else str(calculated)
    return digits[7].upper() == expected


def _valid_orcid(orcid_url: str) -> bool:
    if not ORCID_URL_RE.fullmatch(orcid_url):
        return False
    digits = orcid_url.rsplit("/", 1)[-1].replace("-", "")
    total = 0
    for digit in digits[:15]:
        total = (total + int(digit)) * 2
    result = (12 - total % 11) % 11
    expected = "X" if result == 10 else str(result)
    return digits[-1] == expected


def _detect_multiple_name_signals(name: str) -> list[str]:
    """Detect signals that one ``author.name`` may contain multiple names.

    This is a high-recall candidate detector rather than a final decision.  It
    returns the matched signal names so downstream diagnostics or an LLM can
    review why the value was tagged.
    """
    evidence: list[str] = []
    normalized = re.sub(r"[ \f\v]+", " ", name.strip())
    if not normalized:
        return evidence

    if AUTHOR_ELLIPSIS_RE.search(normalized):
        evidence.append("author_ellipsis")
    if AUTHOR_CONJUNCTION_RE.search(normalized):
        evidence.append("author_conjunction")
    if AUTHOR_LIST_SEPARATOR_RE.search(normalized):
        evidence.append("explicit_list_separator")

    # Require at least two visible characters on both sides.  This retains
    # "Alice&Bob" and Chinese names while filtering acronym-like R&D / AT&T.
    for match in re.finditer(r"([^\W\d_]+)\s*&\s*([^\W\d_]+)", normalized, re.UNICODE):
        left, right = match.group(1), match.group(2)
        if len(left) >= 2 and len(right) >= 2:
            evidence.append("author_ampersand")
            break

    if AUTHOR_CJK_COMMA_NAMES_RE.search(normalized):
        evidence.append("cjk_comma_names")
    if AUTHOR_WESTERN_COMMA_NAMES_RE.search(normalized):
        evidence.append("western_full_names_comma")

    comma_count = normalized.count(",") + normalized.count("\uff0c")
    if comma_count >= 2:
        evidence.append("ambiguous_multiple_commas")
    if AUTHOR_CJK_WHITESPACE_NAMES_RE.fullmatch(normalized):
        evidence.append("cjk_whitespace_names")

    return list(dict.fromkeys(evidence))


ValidationResult = tuple[bool, list[str], list[str]]


def _ok() -> ValidationResult:
    return False, [], []


def _fail(error_label: str, reason: str) -> ValidationResult:
    return True, [error_label], [reason]


def check_metadata_type(metadata_type: Any) -> ValidationResult:
    if metadata_type is None:
        return _fail("null", "value is null")
    if not isinstance(metadata_type, str):
        return _fail("wrong_type", "value must be a string")
    if metadata_type.strip() == "":
        return _fail("empty", "value must be a non-empty string")
    if metadata_type not in METADATA_TYPE_VALUES:
        return _fail("unsupported_value", f"unsupported value '{metadata_type}'")
    return _ok()


def check_doi(doi: Any, metadata_type: Any) -> ValidationResult:
    if metadata_type not in METADATA_TYPE_VALUES:
        return _ok()
    required = metadata_type == "paper"
    if doi is None:
        return _fail("empty", "value cannot be None when metadata_type='paper'") if required else _ok()
    if not isinstance(doi, str):
        return _fail("wrong_type", "value must be a string")
    doi_trim = doi.strip()
    if doi_trim == "":
        return _fail("empty", "value is empty after trimming") if required else _ok()
    if doi_trim != doi_trim.lower():
        return _fail("not_lowercase", "value must be lowercase")
    if not DOI_RE.fullmatch(doi_trim):
        return _fail("format_invalid", "value does not match DOI format")
    doi_prefix = doi_trim.split("/", 1)[0]
    if doi_prefix in DOI_PREFIXES_RE:
        return _fail(
            "error_prefix",
            f"DOI prefix '{doi_prefix}' is reserved for tests",
        )
    return _ok()


def check_isbns(isbns: Any, metadata_type: Any) -> ValidationResult:
    if metadata_type not in METADATA_TYPE_VALUES:
        return _ok()
    required = metadata_type == "ebook"
    if isbns is None:
        return _fail("empty", "value cannot be None when metadata_type='ebook'") if required else _ok()
    if not (isinstance(isbns, list) and all(isinstance(x, str) for x in isbns)):
        return _fail("wrong_type", "value must be a list of strings")
    if len(isbns) == 0:
        return _fail("empty", "value cannot be empty list when metadata_type='ebook'") if required else _ok()
    for item in isbns:
        if not (_valid_isbn10(item) or _valid_isbn13(item)):
            return _fail("invalid_format", f"invalid ISBN value '{item}'")
    return _ok()


def check_isbn13(isbn13: Any, metadata_type: Any) -> ValidationResult:
    if metadata_type not in METADATA_TYPE_VALUES:
        return _ok()
    required = metadata_type == "ebook"
    if isbn13 is None:
        return _fail("empty", "value cannot be None when metadata_type='ebook'") if required else _ok()
    if not isinstance(isbn13, str):
        return _fail("wrong_type", "value must be a string")
    if isbn13 == "":
        return _fail("empty", "value cannot be empty string when metadata_type='ebook'") if required else _ok()
    if not _valid_isbn13(isbn13):
        return _fail("invalid_format", f"invalid ISBN13 value '{isbn13}'")
    return _ok()


def _check_inner_title(title: Any) -> ValidationResult:
    """Check the inner title in references, related_works, and citations."""
    if title is None:
        return _fail("null", "value is null")
    if not isinstance(title, str):
        return _fail("wrong_type", "value must be a string")
    if title == "":
        return _ok()

    error_labels: List[str] = []
    reasons: List[str] = []
    pattern_checks = [
        (HTML_TAG_LAYOUT_RE, "html_tag_layout", "contains HTML layout tag"),
        (HTML_TAG_MATH_RE, "html_tag_math", "contains MathML tag"),
        (HTML_TAG_XML_COMMENT_RE, "html_tag_xml_comment", "contains XML comment"),
        (HTML_TAG_CDATA_RE, "html_tag_cdata", "contains CDATA section"),
        (HTML_ENTITY_NAMED_RE, "html_entity_named", "contains named HTML entity"),
        (HTML_ENTITY_DECIMAL_RE, "html_entity_decimal", "contains decimal HTML entity"),
        (HTML_ENTITY_HEX_RE, "html_entity_hex", "contains hexadecimal HTML entity"),
        (SPECIAL_CHAR_INVISIBLE_RE, "special_char_invisible", "contains invisible unicode character"),
        (
            SPECIAL_CHAR_REPLACEMENT_RE,
            "special_char_replacement",
            "contains unicode replacement character",
        ),
        (SPECIAL_CHAR_CONTROL_RE, "special_char_control", "contains control character"),
        (SPECIAL_CHAR_MARKUP_RE, "special_char_markup", "contains bracket markup token"),
    ]
    for pattern, error_label, reason in pattern_checks:
        matched_values = list(dict.fromkeys(match.group(0) for match in pattern.finditer(title)))
        if matched_values:
            error_labels.append(error_label)
            reasons.append(f"{reason}: {json.dumps(matched_values, ensure_ascii=True)}")
    return bool(error_labels), error_labels, reasons


def _detect_title_incomplete_tags(value: str) -> list[str]:
    evidence: list[str] = []

    # A recognized tag start without its own closing angle bracket is incomplete.
    # Stop at another opening bracket so a later valid tag cannot close it by accident.
    for match in TITLE_RECOGNIZED_TAG_START_RE.finditer(value):
        closing_bracket = value.find(">", match.end())
        search_end = closing_bracket if closing_bracket >= 0 else len(value)
        next_opening_bracket = value.find("<", match.end(), search_end)
        if closing_bracket < 0 or next_opening_bracket >= 0:
            fragment_end = next_opening_bracket if next_opening_bracket >= 0 else len(value)
            evidence.append(value[match.start():fragment_end])

    # A closing tag missing only its opening angle bracket is also a strong signal.
    # Do not flag permissive forms such as ``< /i>`` which still have an opener.
    for match in TITLE_CLOSING_TAG_WITHOUT_OPEN_BRACKET_RE.finditer(value):
        if not re.search(r"<\s*$", value[:match.start()]):
            evidence.append(match.group(0))

    comment_remainder = HTML_TAG_XML_COMMENT_RE.sub("", value)
    if "<!--" in comment_remainder:
        evidence.append("<!--")
    if "-->" in comment_remainder:
        evidence.append("-->")
    cdata_remainder = HTML_TAG_CDATA_RE.sub("", value)
    if "<![cdata[" in cdata_remainder.lower():
        evidence.append("<![CDATA[")
    if "]]>" in cdata_remainder:
        evidence.append("]]>")

    return list(dict.fromkeys(fragment for fragment in evidence if fragment))


def _detect_title_mismatched_tags(value: str) -> list[str]:
    # Ignore markup-like text inside complete comments and CDATA sections.
    scan_value = HTML_TAG_XML_COMMENT_RE.sub("", value)
    scan_value = HTML_TAG_CDATA_RE.sub("", scan_value)
    stack: list[tuple[str, str]] = []
    evidence: list[str] = []

    for match in TITLE_RECOGNIZED_COMPLETE_TAG_RE.finditer(scan_value):
        raw_tag = match.group(0)
        tag_name = match.group("name").lower()
        local_name = tag_name.rsplit(":", 1)[-1]
        is_closing = bool(match.group("closing"))
        is_self_closing = match.group("attributes").rstrip().endswith("/")

        if local_name in _TITLE_VOID_TAG_NAMES:
            if is_closing:
                evidence.append(raw_tag)
            continue
        if is_closing:
            if stack and stack[-1][0] == tag_name:
                stack.pop()
            else:
                if stack:
                    evidence.append(stack[-1][1])
                evidence.append(raw_tag)
            continue
        if not is_self_closing:
            stack.append((tag_name, raw_tag))

    evidence.extend(raw_tag for _, raw_tag in stack)
    return list(dict.fromkeys(evidence))


def _collect_title_character_matches(value: str) -> dict[str, list[str]]:
    matches: dict[str, list[str]] = {}
    seen: dict[str, set[str]] = {}
    for match in TITLE_CHARACTER_RE.finditer(value):
        char = match.group(0)
        codepoint = ord(char)
        error_label = ""
        if codepoint == 0xFFFD:
            error_label = "special_char.replacement"
        elif codepoint <= 0x08 or codepoint in (0x0B, 0x0C, 0x7F) or 0x0E <= codepoint <= 0x1F:
            error_label = "special_char.control"
        elif 0xE000 <= codepoint <= 0xF8FF:
            error_label = "special_char.private_use_area"
        elif codepoint == 0x200B:
            error_label = "invisible_char.zero_width_space"
        elif codepoint == 0xFEFF:
            error_label = "invisible_char.bom"
        elif codepoint == 0x200C:
            error_label = "invisible_char.zwnj"
        elif codepoint == 0x200D:
            error_label = "invisible_char.zwj"
        elif codepoint in (0x200E, 0x200F) or 0x202A <= codepoint <= 0x202E or 0x2066 <= codepoint <= 0x2069:
            error_label = "invisible_char.bidi_control"
        elif codepoint == 0x00A0:
            error_label = "space_char.nbsp"
        elif 0x2000 <= codepoint <= 0x200A or codepoint in (0x202F, 0x205F, 0x3000):
            error_label = "space_char.typographic"

        if error_label and char not in seen.setdefault(error_label, set()):
            seen[error_label].add(char)
            matches.setdefault(error_label, []).append(char)
    return matches


def _check_pattern_group(
    value: str,
    pattern_checks: tuple[tuple[re.Pattern[str], str, str], ...],
) -> ValidationResult:
    error_labels: List[str] = []
    reasons: List[str] = []
    for pattern, error_label, reason in pattern_checks:
        matched_values = list(
            dict.fromkeys(match.group(0) for match in pattern.finditer(value))
        )
        if matched_values:
            error_labels.append(error_label)
            reasons.append(f"{reason}: {json.dumps(matched_values, ensure_ascii=True)}")
    return bool(error_labels), error_labels, reasons


def _check_title_tag_types(value: str) -> ValidationResult:
    if "<" not in value:
        return _ok()
    return _check_pattern_group(value, _TITLE_TAG_PATTERN_CHECKS)


def _check_title_tag_integrity(value: str) -> ValidationResult:
    if "<" not in value and ">" not in value:
        return _ok()

    error_labels: List[str] = []
    reasons: List[str] = []
    incomplete_tags = _detect_title_incomplete_tags(value)
    if incomplete_tags:
        error_labels.append("html_tag.incomplete")
        reasons.append(
            "contains incomplete HTML/XML tag: "
            f"{json.dumps(incomplete_tags, ensure_ascii=True)}"
        )
    if "<" in value:
        mismatched_tags = _detect_title_mismatched_tags(value)
        if mismatched_tags:
            error_labels.append("html_tag.mismatched")
            reasons.append(
                "contains mismatched HTML/XML tag: "
                f"{json.dumps(mismatched_tags, ensure_ascii=True)}"
            )
    return bool(error_labels), error_labels, reasons


def _check_title_entities(value: str) -> ValidationResult:
    if "&" not in value:
        return _ok()
    return _check_pattern_group(value, _TITLE_ENTITY_PATTERN_CHECKS)


def _check_title_markup_tags(value: str) -> ValidationResult:
    if "[" not in value:
        return _ok()
    return _check_pattern_group(value, _TITLE_MARKUP_PATTERN_CHECKS)


def _check_title_unicode_chars(value: str) -> ValidationResult:
    character_matches = _collect_title_character_matches(value)
    error_labels: List[str] = []
    reasons: List[str] = []
    for error_label, reason in _TITLE_CHARACTER_CHECKS:
        matched_values = character_matches.get(error_label, [])
        if matched_values:
            error_labels.append(error_label)
            reasons.append(f"{reason}: {json.dumps(matched_values, ensure_ascii=True)}")
    return bool(error_labels), error_labels, reasons


def _check_title_non_empty_content(title: str, title_trim: str) -> ValidationResult:
    error_labels: List[str] = []
    reasons: List[str] = []
    title_lower = title_trim.lower()

    if len(title_trim) < 5:
        error_labels.append("too_short")
        reasons.append("trimmed content length is less than 5")
    if len(title_trim) > 1000:
        error_labels.append("too_long")
        reasons.append("trimmed content length is greater than 1000")
    if title_lower in TITLE_PLACEHOLDER_VALUES:
        error_labels.append("likely_placeholder")
        reasons.append("content is a likely title placeholder")
    if TITLE_ENCODING_ERROR_RE.search(title):
        error_labels.append("encoding_error")
        reasons.append("content contains a likely encoding error")
    if TITLE_CONFERENCE_RE.search(title_trim):
        error_labels.append("likely_conference")
        reasons.append("content is likely an IEEE conference title")
    if TITLE_IDENTIFIER_RE.fullmatch(title_trim):
        error_labels.append("likely_identifier")
        reasons.append("content consists only of an identifier or URL")
    return bool(error_labels), error_labels, reasons


def _combine_validation_results(results: list[ValidationResult]) -> ValidationResult:
    invalid = False
    error_labels: List[str] = []
    reasons: List[str] = []
    for result_invalid, result_labels, result_reasons in results:
        invalid = invalid or result_invalid
        error_labels.extend(result_labels)
        reasons.extend(result_reasons)
    return invalid, error_labels, reasons


def check_title(title: Any) -> ValidationResult:
    if title is None:
        return _fail("null", "value is null")
    if not isinstance(title, str):
        return _fail("wrong_type", "value must be a string")

    title_trim = title.strip()
    if title_trim == "":
        # A whitespace-only title may still contain a meaningful whitespace or
        # control-character label, such as NBSP or a typographic space.
        results = [
            _check_title_unicode_chars(title),
            _fail("empty", "value is empty after trimming"),
        ]
    else:
        results = [
            _check_title_tag_types(title),
            _check_title_tag_integrity(title),
            _check_title_entities(title),
            _check_title_markup_tags(title),
            _check_title_unicode_chars(title),
            _check_title_non_empty_content(title, title_trim),
        ]

    return _combine_validation_results(results)


def _detect_abstract_incomplete_tags(value: str) -> list[str]:
    # Complete non-element XML sections are handled by their own labels and must
    # not influence element-boundary checks.
    scan_value = HTML_TAG_XML_COMMENT_RE.sub("", value)
    scan_value = HTML_TAG_CDATA_RE.sub("", scan_value)
    scan_value = ABSTRACT_HTML_TAG_XML_DECLARATION_RE.sub("", scan_value)
    scan_value = ABSTRACT_HTML_TAG_DOCTYPE_RE.sub("", scan_value)
    evidence: list[str] = []

    for match in ABSTRACT_RECOGNIZED_TAG_START_RE.finditer(scan_value):
        closing_bracket = scan_value.find(">", match.end())
        search_end = closing_bracket if closing_bracket >= 0 else len(scan_value)
        next_opening_bracket = scan_value.find("<", match.end(), search_end)
        if closing_bracket < 0 or next_opening_bracket >= 0:
            fragment_end = next_opening_bracket if next_opening_bracket >= 0 else len(scan_value)
            evidence.append(scan_value[match.start():fragment_end])

    for match in ABSTRACT_CLOSING_TAG_WITHOUT_OPEN_BRACKET_RE.finditer(scan_value):
        if not re.search(r"<\s*$", scan_value[:match.start()]):
            evidence.append(match.group(0))

    comment_remainder = HTML_TAG_XML_COMMENT_RE.sub("", value)
    if "<!--" in comment_remainder:
        evidence.append("<!--")
    if "-->" in comment_remainder:
        evidence.append("-->")

    cdata_remainder = HTML_TAG_CDATA_RE.sub("", value)
    if "<![cdata[" in cdata_remainder.lower():
        evidence.append("<![CDATA[")
    if "]]>" in cdata_remainder:
        evidence.append("]]>")

    declaration_remainder = ABSTRACT_HTML_TAG_XML_DECLARATION_RE.sub("", value)
    if re.search(r"<\?xml\b", declaration_remainder, re.IGNORECASE):
        evidence.append("<?xml")
    if "?>" in declaration_remainder:
        evidence.append("?>")

    doctype_remainder = ABSTRACT_HTML_TAG_DOCTYPE_RE.sub("", value)
    if re.search(r"<!DOCTYPE\b", doctype_remainder, re.IGNORECASE):
        evidence.append("<!DOCTYPE")

    return list(dict.fromkeys(fragment for fragment in evidence if fragment))


def _detect_abstract_mismatched_tags(value: str) -> list[str]:
    scan_value = HTML_TAG_XML_COMMENT_RE.sub("", value)
    scan_value = HTML_TAG_CDATA_RE.sub("", scan_value)
    scan_value = ABSTRACT_HTML_TAG_XML_DECLARATION_RE.sub("", scan_value)
    scan_value = ABSTRACT_HTML_TAG_DOCTYPE_RE.sub("", scan_value)
    stack: list[tuple[str, str]] = []
    evidence: list[str] = []

    for match in ABSTRACT_RECOGNIZED_COMPLETE_TAG_RE.finditer(scan_value):
        raw_tag = match.group(0)
        tag_name = match.group("name").lower()
        local_name = tag_name.rsplit(":", 1)[-1]
        is_closing = bool(match.group("closing"))
        is_self_closing = match.group("attributes").rstrip().endswith("/")

        if local_name in _ABSTRACT_VOID_TAG_NAMES:
            if is_closing:
                evidence.append(raw_tag)
            continue
        if is_closing:
            if stack and stack[-1][0] == tag_name:
                stack.pop()
            else:
                if stack:
                    evidence.append(stack[-1][1])
                evidence.append(raw_tag)
            continue
        if not is_self_closing:
            stack.append((tag_name, raw_tag))

    evidence.extend(raw_tag for _, raw_tag in stack)
    return list(dict.fromkeys(evidence))


def _collect_abstract_character_matches(value: str) -> dict[str, list[str]]:
    matches: dict[str, list[str]] = {}
    seen: dict[str, set[str]] = {}
    for match in ABSTRACT_CHARACTER_RE.finditer(value):
        char = match.group(0)
        codepoint = ord(char)
        error_label = ""
        if codepoint == 0xFFFD:
            error_label = "special_char.replacement"
        elif codepoint <= 0x08 or codepoint in (0x0B, 0x0C, 0x7F) or 0x0E <= codepoint <= 0x1F:
            error_label = "special_char.control"
        elif 0xE000 <= codepoint <= 0xF8FF:
            error_label = "special_char.private_use_area"
        elif codepoint == 0x200B:
            error_label = "invisible_char.zero_width_space"
        elif codepoint == 0xFEFF:
            error_label = "invisible_char.bom"
        elif codepoint == 0x00AD:
            error_label = "invisible_char.soft_hyphen"
        elif codepoint == 0x200C:
            error_label = "invisible_char.zwnj"
        elif codepoint == 0x200D:
            error_label = "invisible_char.zwj"
        elif codepoint in (0x200E, 0x200F) or 0x202A <= codepoint <= 0x202E or 0x2066 <= codepoint <= 0x2069:
            error_label = "invisible_char.bidi_control"
        elif codepoint == 0x00A0:
            error_label = "space_char.nbsp"
        elif 0x2000 <= codepoint <= 0x200A or codepoint in (0x202F, 0x205F, 0x3000):
            error_label = "space_char.typographic"
        elif codepoint == 0x09:
            error_label = "space_char.tab"

        if error_label and char not in seen.setdefault(error_label, set()):
            seen[error_label].add(char)
            matches.setdefault(error_label, []).append(char)
    return matches


def _abstract_line_break_stats(value: str) -> tuple[int, int, float]:
    line_breaks = list(re.finditer(r"\r\n|\r|\n", value))
    longest_run = 0
    current_run = 0
    previous_end: int | None = None
    for line_break in line_breaks:
        gap = value[previous_end:line_break.start()] if previous_end is not None else ""
        current_run = current_run + 1 if previous_end is None or not gap.strip(" \t") else 1
        longest_run = max(longest_run, current_run)
        previous_end = line_break.end()
    count = len(line_breaks)
    return count, longest_run, count / max(len(value), 1)


def _check_abstract_tag_types(value: str) -> ValidationResult:
    if "<" not in value:
        return _ok()
    return _check_pattern_group(value, _ABSTRACT_TAG_PATTERN_CHECKS)


def _check_abstract_tag_integrity(value: str) -> ValidationResult:
    if "<" not in value and ">" not in value:
        return _ok()

    error_labels: List[str] = []
    reasons: List[str] = []
    incomplete_tags = _detect_abstract_incomplete_tags(value)
    if incomplete_tags:
        error_labels.append("html_tag.incomplete")
        reasons.append(
            "contains incomplete HTML/XML tag: "
            f"{json.dumps(incomplete_tags, ensure_ascii=True)}"
        )
    if "<" in value:
        mismatched_tags = _detect_abstract_mismatched_tags(value)
        if mismatched_tags:
            error_labels.append("html_tag.mismatched")
            reasons.append(
                "contains mismatched HTML/XML tag: "
                f"{json.dumps(mismatched_tags, ensure_ascii=True)}"
            )
    return bool(error_labels), error_labels, reasons


def _check_abstract_entities(value: str) -> ValidationResult:
    if "&" not in value:
        return _ok()
    return _check_pattern_group(value, _ABSTRACT_ENTITY_PATTERN_CHECKS)


def _check_abstract_markup_tags(value: str) -> ValidationResult:
    if "[" not in value:
        return _ok()
    return _check_pattern_group(value, _ABSTRACT_MARKUP_PATTERN_CHECKS)


def _check_abstract_crawler_residue(value: str) -> ValidationResult:
    return _check_pattern_group(value, _ABSTRACT_CRAWLER_PATTERN_CHECKS)


def _check_abstract_unicode_chars(value: str) -> ValidationResult:
    character_matches = _collect_abstract_character_matches(value)
    error_labels: List[str] = []
    reasons: List[str] = []
    for error_label, reason in _ABSTRACT_CHARACTER_CHECKS:
        matched_values = character_matches.get(error_label, [])
        if matched_values:
            error_labels.append(error_label)
            reasons.append(f"{reason}: {json.dumps(matched_values, ensure_ascii=True)}")

    line_break_count, longest_run, line_break_density = _abstract_line_break_stats(value)
    excessive_line_breaks = (
        longest_run >= ABSTRACT_CONSECUTIVE_LINE_BREAK_THRESHOLD
        or line_break_count > ABSTRACT_LINE_BREAK_COUNT_THRESHOLD
        or (
            line_break_count >= ABSTRACT_LINE_BREAK_DENSITY_MIN_COUNT
            and line_break_density > ABSTRACT_LINE_BREAK_DENSITY_THRESHOLD
        )
    )
    if excessive_line_breaks:
        error_labels.append("space_char.excessive_line_break")
        reasons.append(
            "contains excessive line breaks: "
            f"count={line_break_count}, longest_run={longest_run}, "
            f"density={line_break_density:.4f}"
        )
    return bool(error_labels), error_labels, reasons


def _check_abstract_non_empty_content(
    abstract: str,
    abstract_trim: str,
    title: Any,
) -> ValidationResult:
    error_labels: List[str] = []
    reasons: List[str] = []
    abstract_lower = abstract_trim.lower()

    if len(abstract_trim) < 20:
        error_labels.append("too_short")
        reasons.append("trimmed content length is less than 20")
    if len(abstract_trim) > 6000:
        error_labels.append("too_long")
        reasons.append("trimmed content length is greater than 6000")
    if (
        abstract_lower in ABSTRACT_PLACEHOLDER_VALUES
        or ABSTRACT_PLACEHOLDER_RE.fullmatch(abstract_trim)
    ):
        error_labels.append("likely_placeholder")
        reasons.append("content is a likely abstract placeholder")
    if ABSTRACT_ENCODING_ERROR_RE.search(abstract):
        error_labels.append("encoding_error")
        reasons.append("content contains a likely encoding error")
    if (
        isinstance(title, str)
        and title.strip()
        and abstract_lower == title.strip().lower()
    ):
        error_labels.append("same_title")
        reasons.append("content is identical to title after trimming and lowercasing")
    if ABSTRACT_IDENTIFIER_RE.fullmatch(abstract_trim):
        error_labels.append("likely_identifier")
        reasons.append("content consists only of an identifier or URL")
    return bool(error_labels), error_labels, reasons


def check_abstract(abstract: Any, title: Any = None) -> ValidationResult:
    if abstract is None:
        return _fail("null", "value is null")
    if not isinstance(abstract, str):
        return _fail("wrong_type", "value must be a string")

    abstract_trim = abstract.strip()
    if abstract_trim == "":
        results = [
            _check_abstract_unicode_chars(abstract),
            _fail("empty", "value is empty after trimming"),
        ]
    else:
        results = [
            _check_abstract_tag_types(abstract),
            _check_abstract_tag_integrity(abstract),
            _check_abstract_entities(abstract),
            _check_abstract_markup_tags(abstract),
            _check_abstract_crawler_residue(abstract),
            _check_abstract_unicode_chars(abstract),
            _check_abstract_non_empty_content(abstract, abstract_trim, title),
        ]

    return _combine_validation_results(results)


def check_language(language: Any) -> ValidationResult:
    if language is None:
        return _fail("null", "value is null")
    if not isinstance(language, str):
        return _fail("wrong_type", "value must be a string")
    if language == "":
        return _ok()
    if not LANGUAGE_ALLOWED_VALUES:
        return _ok()
    if language not in LANGUAGE_ALLOWED_VALUES:
        return _fail("unsupported_value", f"unsupported language code '{language}'")
    return _ok()


def check_author(author: Any) -> ValidationResult:
    if author is None:
        return _fail("null", "value is null")
    if not isinstance(author, list):
        return _fail("wrong_type", "value must be a list")
    if len(author) == 0:
        return _fail("empty", "author list is empty")

    normalized_names: List[str] = []
    error_labels: List[str] = []
    reasons: List[str] = []
    for idx, item in enumerate(author):
        if not isinstance(item, dict):
            return _fail("wrong_type", f"item[{idx}] must be an object")
        if set(item.keys()) != {"name", "orcid"}:
            return _fail("invalid_keys", f"item[{idx}] keys must be exactly {{'name','orcid'}}")
        name = item.get("name")
        orcid = item.get("orcid")
        if not isinstance(name, str):
            return _fail("wrong_type", f"item[{idx}].name must be a string")
        if not isinstance(orcid, str):
            return _fail("wrong_type", f"item[{idx}].orcid must be a string")

        name_trim = name.strip()
        if name_trim == "":
            if "empty_name" not in error_labels:
                error_labels.append("empty_name")
                reasons.append(f"item[{idx}].name is empty after trimming")
        else:
            normalized_names.append(re.sub(r"\s+", " ", name_trim).casefold())
            multiple_name_signals = _detect_multiple_name_signals(name_trim)
            if (
                multiple_name_signals
                and "multiple_names" not in error_labels
            ):
                error_labels.append("multiple_names")
                reasons.append(
                    f"item[{idx}].name may contain multiple authors; "
                    f"signals={','.join(multiple_name_signals)}"
                )
            if (
                AUTHOR_SEP_RE.search(name_trim)
                and "invalid_separator" not in error_labels
            ):
                error_labels.append("invalid_separator")
                reasons.append(f"item[{idx}].name contains separator noise")

        orcid_trim = orcid.strip()
        if (
            orcid_trim != ""
            and not _valid_orcid(orcid_trim)
            and "invalid_orcid" not in error_labels
        ):
            error_labels.append("invalid_orcid")
            reasons.append(f"item[{idx}].orcid has invalid format or checksum")

    if len(normalized_names) != len(set(normalized_names)):
        error_labels.insert(1 if "empty_name" in error_labels else 0, "duplicated_name")
        reasons.insert(1 if "empty_name" in error_labels else 0, "author names contain duplicates")

    return bool(error_labels), error_labels, reasons


def check_contributors(contributors: Any) -> ValidationResult:
    if contributors is None:
        return _fail("null", "value is null")
    if not (isinstance(contributors, list) and all(isinstance(x, str) for x in contributors)):
        return _fail("wrong_type", "value must be a list of strings")
    if len(contributors) == 0:
        return _ok()
    for idx, item in enumerate(contributors):
        if AUTHOR_SEP_RE.search(item):
            return _fail("invalid_separator", f"item[{idx}] contains invalid separator")
    return _ok()


def check_locations(locations: Any) -> ValidationResult:
    if locations is None:
        return _fail("null", "value is null")
    if not isinstance(locations, list):
        return _fail("wrong_type", "value must be a list")
    if len(locations) == 0:
        return _ok()
    for idx, item in enumerate(locations):
        if not isinstance(item, dict):
            return _fail("wrong_type", f"item[{idx}] must be an object")
        for key in ("type", "url", "license", "is_oa"):
            if key not in item:
                return _fail("missing_key", f"item[{idx}] missing key '{key}'")
        if item["type"] not in LOC_TYPE_VALUES:
            return _fail("invalid_value", f"item[{idx}].type is invalid")
        if not (isinstance(item["url"], str) and URL_RE.fullmatch(item["url"])):
            return _fail("invalid_url", f"item[{idx}].url is invalid")
        if item["license"] not in LICENSE_VALUES:
            return _fail("invalid_value", f"item[{idx}].license is invalid")
        if item["is_oa"] not in OA_BOOL_VALUES:
            return _fail("invalid_value", f"item[{idx}].is_oa is invalid")
    return _ok()


def check_access_is_oa(
    access_is_oa: Any,
    metadata_type: Any,
    access_oa_status: Any = None,
    access_oa_url: Any = None,
    access_license: Any = None,
) -> ValidationResult:
    if metadata_type not in METADATA_TYPE_VALUES:
        return _ok()
    required = metadata_type == "paper"
    if access_is_oa is None:
        return _fail("empty", "value cannot be None when metadata_type='paper'") if required else _ok()
    if not isinstance(access_is_oa, str):
        return _fail("wrong_type", "value must be a string")
    if access_is_oa == "":
        return _fail("empty", "value cannot be empty string when metadata_type='paper'") if required else _ok()
    if access_is_oa not in OA_BOOL_VALUES:
        return _fail("unsupported_value", f"unsupported value '{access_is_oa}'")

    error_labels: list[str] = []
    reasons: list[str] = []

    # Only apply consistency rules to otherwise valid dependent values. Their
    # own validators report null, type, enum and URL-format errors separately.
    status_is_valid = isinstance(access_oa_status, str) and access_oa_status in OA_STATUS_VALUES
    url_is_string_list = isinstance(access_oa_url, list) and all(
        isinstance(item, str) for item in access_oa_url
    )
    license_is_valid = isinstance(access_license, str) and access_license in ACCESS_LICENSE_VALUES

    if access_is_oa == "true":
        if status_is_valid and access_oa_status not in OPEN_OA_STATUS_VALUES:
            error_labels.append("oa_status_mismatch")
            reasons.append(
                "access_oa_status must be one of diamond, gold, green, hybrid or bronze "
                "when access_is_oa='true'"
            )
        if url_is_string_list and not any(URL_RE.fullmatch(item) for item in access_oa_url):
            error_labels.append("oa_url_mismatch")
            reasons.append("access_oa_url must contain at least one valid URL when access_is_oa='true'")
    else:
        expected_status = "closed" if access_is_oa == "false" else ""
        if status_is_valid and access_oa_status != expected_status:
            error_labels.append("oa_status_mismatch")
            reasons.append(
                f"access_oa_status must be '{expected_status}' when access_is_oa='{access_is_oa}'"
            )
        if url_is_string_list and access_oa_url != []:
            error_labels.append("oa_url_mismatch")
            reasons.append(f"access_oa_url must be empty when access_is_oa='{access_is_oa}'")
        if license_is_valid and access_license != "":
            error_labels.append("license_mismatch")
            reasons.append(f"access_license must be empty when access_is_oa='{access_is_oa}'")

    return bool(error_labels), error_labels, reasons


def check_access_oa_status(access_oa_status: Any) -> ValidationResult:
    if access_oa_status is None:
        return _fail("null", "value is null")
    if not isinstance(access_oa_status, str):
        return _fail("wrong_type", "value must be a string")
    if access_oa_status not in OA_STATUS_VALUES:
        return _fail("unsupported_value", f"unsupported value '{access_oa_status}'")
    return _ok()


def check_access_oa_url(access_oa_url: Any) -> ValidationResult:
    if access_oa_url is None:
        return _fail("null", "value is null")
    if not (isinstance(access_oa_url, list) and all(isinstance(x, str) for x in access_oa_url)):
        return _fail("wrong_type", "value must be a list of strings")
    if len(access_oa_url) == 0:
        return _ok()
    for idx, item in enumerate(access_oa_url):
        if not URL_RE.fullmatch(item):
            return _fail("invalid_url", f"item[{idx}] is not a valid URL")
    return _ok()


def check_access_license(access_license: Any) -> ValidationResult:
    if access_license is None:
        return _fail("null", "value is null")
    if not isinstance(access_license, str):
        return _fail("wrong_type", "value must be a string")
    if access_license == "":
        return _ok()
    if access_license not in ACCESS_LICENSE_VALUES:
        return _fail("unsupported_value", f"unsupported value '{access_license}'")
    return _ok()


def check_publication_published_date(publication_published_date: Any) -> ValidationResult:
    if publication_published_date is None:
        return _fail("null", "value is null")
    if not isinstance(publication_published_date, str):
        return _fail("wrong_type", "value must be a string")
    if publication_published_date == "":
        return _ok()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", publication_published_date):
        return _fail("invalid_format", "value must match YYYY-MM-DD")
    try:
        datetime.strptime(publication_published_date, "%Y-%m-%d")
        return _ok()
    except ValueError:
        return _fail("invalid_date", "value is not a valid calendar date")


def check_publication_published_year(publication_published_year: Any) -> ValidationResult:
    if publication_published_year is None:
        return _ok()
    if not isinstance(publication_published_year, int) or isinstance(publication_published_year, bool):
        return _fail("wrong_type", "value must be an integer")
    if not (0 < publication_published_year < 2100):
        return _fail("out_of_range", "value must be in range (0, 2100)")
    return _ok()


def check_publication_venue_issn(publication_venue_issn: Any) -> ValidationResult:
    if publication_venue_issn is None:
        return _fail("null", "value is null")
    if not (isinstance(publication_venue_issn, list) and all(isinstance(x, str) for x in publication_venue_issn)):
        return _fail("wrong_type", "value must be a list of strings")
    if len(publication_venue_issn) == 0:
        return _ok()
    for idx, item in enumerate(publication_venue_issn):
        if not _valid_issn(item):
            return _fail("invalid_format", f"item[{idx}] is not a valid ISSN")
    return _ok()


def check_publication_venue_biblio_volume(publication_venue_biblio_volume: Any) -> ValidationResult:
    if publication_venue_biblio_volume is None:
        return _fail("null", "value is null")
    if not isinstance(publication_venue_biblio_volume, str):
        return _fail("wrong_type", "value must be a string")
    if publication_venue_biblio_volume == "":
        return _ok()
    try:
        int(publication_venue_biblio_volume)
        return _ok()
    except (TypeError, ValueError):
        return _fail("invalid_format", "value must be parseable as integer")


def check_publication_venue_biblio_issue(publication_venue_biblio_issue: Any) -> ValidationResult:
    if publication_venue_biblio_issue is None:
        return _fail("null", "value is null")
    if not isinstance(publication_venue_biblio_issue, str):
        return _fail("wrong_type", "value must be a string")
    if publication_venue_biblio_issue == "":
        return _ok()
    try:
        int(publication_venue_biblio_issue)
        return _ok()
    except (TypeError, ValueError):
        return _fail("invalid_format", "value must be parseable as integer")


def check_publication_venue_biblio_pages(publication_venue_biblio_pages: Any) -> ValidationResult:
    if publication_venue_biblio_pages is None:
        return _fail("null", "value is null")
    if not isinstance(publication_venue_biblio_pages, str):
        return _fail("wrong_type", "value must be a string")
    if publication_venue_biblio_pages == "":
        return _ok()
    if not PAGE_RANGE_RE.fullmatch(publication_venue_biblio_pages):
        return _fail("invalid_format", "value must match page range format '<start>-<end>'")
    start, end = [int(x.strip()) for x in publication_venue_biblio_pages.split("-")]
    if start <= 0 or end <= 0:
        return _fail("out_of_range", "page numbers must be positive")
    if start > end:
        return _fail("page_order", "start page cannot be greater than end page")
    return _ok()


def check_publication_pages(publication_pages: Any) -> ValidationResult:
    if publication_pages is None:
        return _ok()
    if not isinstance(publication_pages, int) or isinstance(publication_pages, bool):
        return _fail("wrong_type", "value must be an integer")
    if publication_pages <= 0:
        return _fail("out_of_range", "value must be greater than 0")
    return _ok()


def check_publication_venue_name_unified(
    publication_venue_name_unified: Any, publication_venue_name: Any
) -> ValidationResult:
    if publication_venue_name_unified is None:
        return _fail("null", "value is null")
    if not isinstance(publication_venue_name_unified, str):
        return _fail("wrong_type", "value must be a string")
    if publication_venue_name is not None and not isinstance(publication_venue_name, str):
        return _fail("wrong_type", "publication_venue_name must be a string when provided")
    expected_target = None
    if isinstance(publication_venue_name, str) and publication_venue_name != "":
        expected_target = JOURNAL_NAME_MAPPING.get(publication_venue_name, publication_venue_name)
    if publication_venue_name_unified == "":
        return _ok()
    if expected_target is None:
        return _fail("missing_dependency", "cannot validate without publication_venue_name")
    if publication_venue_name_unified != expected_target:
        return _fail("mismatch", f"expected '{expected_target}'")
    return _ok()


def check_grade_class(grade_class: Any) -> ValidationResult:
    if grade_class is None:
        return _fail("null", "value is null")
    if not isinstance(grade_class, str):
        return _fail("wrong_type", "value must be a string")
    if grade_class == "":
        return _ok()
    if grade_class not in GRADE_CLASS_VALUES:
        return _fail("unsupported_value", f"unsupported value '{grade_class}'")
    return _ok()


def check_grade(grade: Any, grade_class: Any) -> ValidationResult:
    if grade is None:
        return _fail("null", "value is null")
    if not isinstance(grade, str):
        return _fail("wrong_type", "value must be a string")
    if grade_class is not None and not isinstance(grade_class, str):
        return _fail("wrong_type", "grade_class must be a string when provided")
    if grade == "":
        return _ok()
    if grade not in GRADE_VALUES:
        return _fail("unsupported_value", f"unsupported value '{grade}'")
    if grade_class != "k12" and grade != "":
        return _fail("grade_mismatch", "grade can be non-empty only when grade_class='k12'")
    return _ok()


def _check_id_type_id_title_items(items: Any) -> ValidationResult:
    if items is None:
        return _fail("null", "value is null")
    if not isinstance(items, list):
        return _fail("wrong_type", "value must be a list")
    if len(items) == 0:
        return _ok()
    required_keys = {"id_type", "id", "title"}
    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            return _fail("wrong_type", f"item[{idx}] must be an object")
        if set(item.keys()) != required_keys:
            return _fail("invalid_keys", f"item[{idx}] keys must be exactly {{'id_type','id','title'}}")
        id_type = item.get("id_type")
        citation_id = item.get("id")
        title = item.get("title")
        if not isinstance(id_type, str) or id_type == "":
            return _fail("empty", f"item[{idx}].id_type must be a non-empty string")
        title_invalid, title_error_labels, title_reasons = _check_inner_title(title)
        if title_invalid:
            return (
                True,
                [f"title_{error_label}" for error_label in title_error_labels],
                [f"item[{idx}].title invalid: {reason}" for reason in title_reasons],
            )
        if id_type == "doi":
            doi_invalid, doi_error_labels, doi_reasons = check_doi(citation_id, "paper")
            if doi_invalid:
                return (
                    True,
                    [f"id_{error_label}" for error_label in doi_error_labels],
                    [f"item[{idx}].id invalid DOI: {reason}" for reason in doi_reasons],
                )
        elif not isinstance(citation_id, str) or citation_id == "":
            return _fail("empty", f"item[{idx}].id must be a non-empty string")
    return _ok()


def check_references(references: Any) -> ValidationResult:
    return _check_id_type_id_title_items(references)


def check_related_works(related_works: Any) -> ValidationResult:
    return _check_id_type_id_title_items(related_works)


def check_citations(citations: Any) -> ValidationResult:
    return _check_id_type_id_title_items(citations)


def check_supplementary_material(supplementary_material: Any) -> ValidationResult:
    if supplementary_material is None:
        return _fail("null", "value is null")
    if not isinstance(supplementary_material, list):
        return _fail("wrong_type", "value must be a list")
    if len(supplementary_material) == 0:
        return _ok()
    required_keys = {
        "supplementary_material_name",
        "supplementary_material_url",
        "supplementary_material_path",
    }
    for idx, item in enumerate(supplementary_material):
        if not isinstance(item, dict):
            return _fail("wrong_type", f"item[{idx}] must be an object")
        if set(item.keys()) != required_keys:
            return _fail(
                "invalid_keys",
                f"item[{idx}] keys must be exactly "
                "{'supplementary_material_name','supplementary_material_url','supplementary_material_path'}"
            )
        for key in required_keys:
            if not isinstance(item.get(key), str):
                return _fail("wrong_type", f"item[{idx}].{key} must be a string")
    return _ok()


def check_cited_by_api_url(cited_by_api_url: Any) -> ValidationResult:
    if cited_by_api_url is None:
        return _fail("null", "value is null")
    if not isinstance(cited_by_api_url, str):
        return _fail("wrong_type", "value must be a string")
    if cited_by_api_url == "":
        return _ok()
    if not URL_RE.fullmatch(cited_by_api_url):
        return _fail("invalid_url", "value is not a valid URL")
    return _ok()


def check_access_xinghe_repository_sha256(
    access_xinghe_repository_sha256: Any, access_xinghe_repository_has_fulltext: Any
) -> ValidationResult:
    if access_xinghe_repository_sha256 is None:
        return _fail("null", "value is null")
    if not isinstance(access_xinghe_repository_has_fulltext, bool):
        return _fail("wrong_type", "access_xinghe_repository_has_fulltext must be boolean")
    has_fulltext = access_xinghe_repository_has_fulltext
    if isinstance(access_xinghe_repository_sha256, str):
        if not has_fulltext:
            return _ok()
        if access_xinghe_repository_sha256 == "":
            return _fail("required", "value is required when has_fulltext=true")
        return _ok()
    if not (
        isinstance(access_xinghe_repository_sha256, list)
        and all(isinstance(x, str) for x in access_xinghe_repository_sha256)
    ):
        return _fail("wrong_type", "value must be a string or list of strings")
    if not has_fulltext:
        return _ok()
    if len(access_xinghe_repository_sha256) == 0:
        return _fail("required", "value is required when has_fulltext=true")
    return _ok()


def check_access_xinghe_repository_origin_path(
    access_xinghe_repository_origin_path: Any, access_xinghe_repository_has_fulltext: Any
) -> ValidationResult:
    if not isinstance(access_xinghe_repository_origin_path, str):
        return _fail("wrong_type", "value must be a string")
    if not isinstance(access_xinghe_repository_has_fulltext, bool):
        return _fail("wrong_type", "access_xinghe_repository_has_fulltext must be boolean")
    if not access_xinghe_repository_has_fulltext:
        return _ok()
    if access_xinghe_repository_origin_path.strip() == "":
        return _fail("required", "value is required when has_fulltext=true")
    return _ok()


def check_access_xinghe_repository_model_name(
    access_xinghe_repository_model_name: Any, access_xinghe_repository_process_status: Any
) -> ValidationResult:
    if not isinstance(access_xinghe_repository_model_name, str):
        return _fail("wrong_type", "value must be a string")
    if access_xinghe_repository_model_name == "":
        if access_xinghe_repository_process_status in (1, "1"):
            return _fail("required", "value is required when process_status=1")
        return _ok()
    if access_xinghe_repository_model_name not in XINGHE_REPOSITORY_MODEL_NAME_VALUES:
        return _fail("unsupported_value", f"unsupported model name '{access_xinghe_repository_model_name}'")
    return _ok()


def check_access_xinghe_repository_model_version(
    access_xinghe_repository_model_version: Any,
    access_xinghe_repository_model_name: Any,
    access_xinghe_repository_process_status: Any,
) -> ValidationResult:
    if not isinstance(access_xinghe_repository_model_version, str):
        return _fail("wrong_type", "value must be a string")
    if access_xinghe_repository_model_version == "":
        if access_xinghe_repository_process_status in (1, "1"):
            return _fail("required", "value is required when process_status=1")
        if (
            isinstance(access_xinghe_repository_model_name, str)
            and access_xinghe_repository_model_name in XINGHE_REPOSITORY_MODEL_NAME_VALUES
            and "" not in XINGHE_REPOSITORY_MODEL_VERSION_MAP[access_xinghe_repository_model_name]
        ):
            return _fail("required", f"value is required for model '{access_xinghe_repository_model_name}'")
        return _ok()
    if access_xinghe_repository_model_version not in XINGHE_REPOSITORY_MODEL_VERSION_VALUES:
        return _fail("unsupported_value", f"unsupported model version '{access_xinghe_repository_model_version}'")
    if (
        isinstance(access_xinghe_repository_model_name, str)
        and access_xinghe_repository_model_name in XINGHE_REPOSITORY_MODEL_NAME_VALUES
    ) and (
        access_xinghe_repository_model_version
        not in XINGHE_REPOSITORY_MODEL_VERSION_MAP[access_xinghe_repository_model_name]
    ):
        return _fail(
            "model_mismatch",
            f"version '{access_xinghe_repository_model_version}' "
            f"is not allowed for model '{access_xinghe_repository_model_name}'"
        )
    return _ok()


def _normalize_json_like_field(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    stripped = value.strip()
    if not stripped:
        return value
    if stripped[0] not in ("[", "{"):
        return value
    try:
        return json.loads(stripped)
    except (TypeError, ValueError, json.JSONDecodeError):
        cleaned = stripped.replace("\r", " ").replace("\n", " ").replace("\t", " ")
        cleaned = "".join(ch if ord(ch) >= 32 else " " for ch in cleaned)
        invalid_escape_re = re.compile(r'\\(?!["\\/bfnrtu])')
        for _ in range(10):
            next_cleaned = invalid_escape_re.sub(r"\\\\", cleaned)
            if next_cleaned == cleaned:
                break
            cleaned = next_cleaned
        try:
            return json.loads(cleaned)
        except (TypeError, ValueError, json.JSONDecodeError):
            return value


def _normalize_bool_field(value: Any) -> Any:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        if value in (0, 1):
            return bool(value)
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in ("1", "true"):
            return True
        if lowered in ("0", "false"):
            return False
    return value


def normalize_record(record: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(record)
    for field in JSON_LIST_FIELDS:
        if field in normalized:
            normalized[field] = _normalize_json_like_field(normalized.get(field))
    normalized["access_xinghe_repository_has_fulltext"] = _normalize_bool_field(
        normalized.get("access_xinghe_repository_has_fulltext")
    )
    return normalized


FIELD_VALIDATORS = {
    "metadata_type": lambda record: check_metadata_type(record.get("metadata_type")),
    "doi": lambda record: check_doi(record.get("doi"), record.get("metadata_type")),
    "isbns": lambda record: check_isbns(record.get("isbns"), record.get("metadata_type")),
    "isbn13": lambda record: check_isbn13(record.get("isbn13"), record.get("metadata_type")),
    "title": lambda record: check_title(record.get("title")),
    "abstract": lambda record: check_abstract(record.get("abstract"), record.get("title")),
    "language": lambda record: check_language(record.get("language")),
    "author": lambda record: check_author(record.get("author")),
    "contributors": lambda record: check_contributors(record.get("contributors")),
    "locations": lambda record: check_locations(record.get("locations")),
    "access_is_oa": lambda record: check_access_is_oa(
        record.get("access_is_oa"),
        record.get("metadata_type"),
        record.get("access_oa_status"),
        record.get("access_oa_url"),
        record.get("access_license"),
    ),
    "access_oa_status": lambda record: check_access_oa_status(record.get("access_oa_status")),
    "access_oa_url": lambda record: check_access_oa_url(record.get("access_oa_url")),
    "access_license": lambda record: check_access_license(record.get("access_license")),
    "publication_published_date": lambda record: check_publication_published_date(
        record.get("publication_published_date")
    ),
    "publication_published_year": lambda record: check_publication_published_year(
        record.get("publication_published_year")
    ),
    "publication_venue_issn": lambda record: check_publication_venue_issn(record.get("publication_venue_issn")),
    "publication_venue_biblio_volume": lambda record: check_publication_venue_biblio_volume(
        record.get("publication_venue_biblio_volume")
    ),
    "publication_venue_biblio_issue": lambda record: check_publication_venue_biblio_issue(
        record.get("publication_venue_biblio_issue")
    ),
    "publication_venue_biblio_pages": lambda record: check_publication_venue_biblio_pages(
        record.get("publication_venue_biblio_pages")
    ),
    "publication_pages": lambda record: check_publication_pages(record.get("publication_pages")),
    "publication_venue_name_unified": lambda record: check_publication_venue_name_unified(
        record.get("publication_venue_name_unified"),
        record.get("publication_venue_name"),
    ),
    "grade_class": lambda record: check_grade_class(record.get("grade_class")),
    "grade": lambda record: check_grade(record.get("grade"), record.get("grade_class")),
    "references": lambda record: check_references(record.get("references")),
    "related_works": lambda record: check_related_works(record.get("related_works")),
    "citations": lambda record: check_citations(record.get("citations")),
    "supplementary_material": lambda record: check_supplementary_material(
        record.get("supplementary_material")
    ),
    "cited_by_api_url": lambda record: check_cited_by_api_url(record.get("cited_by_api_url")),
    "access_xinghe_repository_sha256": lambda record: check_access_xinghe_repository_sha256(
        record.get("access_xinghe_repository_sha256"),
        record.get("access_xinghe_repository_has_fulltext"),
    ),
    "access_xinghe_repository_origin_path": lambda record: check_access_xinghe_repository_origin_path(
        record.get("access_xinghe_repository_origin_path"),
        record.get("access_xinghe_repository_has_fulltext"),
    ),
    "access_xinghe_repository_model_name": lambda record: check_access_xinghe_repository_model_name(
        record.get("access_xinghe_repository_model_name"),
        record.get("access_xinghe_repository_process_status"),
    ),
    "access_xinghe_repository_model_version": lambda record: check_access_xinghe_repository_model_version(
        record.get("access_xinghe_repository_model_version"),
        record.get("access_xinghe_repository_model_name"),
        record.get("access_xinghe_repository_process_status"),
    ),
}


@Model.rule_register("QUALITY_BAD_EFFECTIVENESS", ["xinghe", "quanliang"])
class RuleQuanliangFieldValidation(BaseRule):
    _metric_info = {
        "category": "Rule-Based Metadata Quality Metrics",
        "quality_dimension": "EFFECTIVENESS",
        "metric_name": "RuleQuanliangFieldValidation",
        "description": "Validate Quanliang metadata fields and report invalid fields",
        "paper_title": "",
        "paper_url": "",
        "paper_authors": "",
        "evaluation_results": "",
    }

    _required_fields = []
    dynamic_config = EvaluatorRuleArgs(key_list=list(FIELD_VALIDATORS.keys()))

    def eval(self, input_data: Data) -> EvalDetail:
        res = EvalDetail(metric=self.__class__.__name__)
        normalized = normalize_record(input_data.to_dict())
        selected_fields = self.dynamic_config.key_list or []
        bad_fields: List[str] = []
        reasons: List[str] = []
        for field in selected_fields:
            if field not in FIELD_VALIDATORS:
                bad_fields.append(f"{field}.unsupported_field")
                reasons.append(f"{field}: unsupported field")
                continue
            if field not in normalized:
                bad_fields.append(f"{field}.missing_field")
                reasons.append(f"{field}: missing field")
                continue
            invalid, error_labels, detail_reasons = FIELD_VALIDATORS[field](normalized)
            if invalid:
                bad_fields.extend(f"{field}.{error_label}" for error_label in error_labels)
                reasons.extend(f"{field}: {reason}" for reason in detail_reasons)

        if bad_fields:
            res.status = True
            res.label = bad_fields
            res.reason = reasons
        else:
            res.label = [QualityLabel.QUALITY_GOOD]
        return res
