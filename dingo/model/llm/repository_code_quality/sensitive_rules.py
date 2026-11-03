"""Rule-first sensitive-data detection for repository source code.

The public candidate dictionaries intentionally contain no matched value.  Strongly
validated identifiers and credentials can be reported directly; ambiguous items are
sent to the contextual LLM reviewer with a scrubbed line hint only.
"""

from __future__ import annotations
import ipaddress
import json
import re
from collections import defaultdict
from datetime import datetime
from typing import Any, Callable

_PLACEHOLDER = re.compile(
    r"(?i)^(?:your[_-]?.*|example|sample|dummy|test(?:ing)?|changeme|password|secret|"
    r"token|none|null|<.*>|\$\{.*\}|\{\{.*\}\}|x{4,}|\*{4,})$"
)
_EXAMPLE_EMAIL_DOMAIN = re.compile(r"(?i)^(?:example\.(?:com|org|net)|test\.com|localhost|invalid)$")
_INFRA_CONTEXT = re.compile(
    r"(?i)\b(?:endpoint|database|db|prod(?:uction)?|vpn|cluster|kubernetes|redis|mysql|"
    r"postgres|mongo(?:db)?|jenkins|gitlab|nexus|harbor|grafana|vault|server|host)\b"
)
_IP_CONTEXT = re.compile(r"(?i)\b(?:ip(?:v[46])?|address|client|remote|source|destination|host|server)\b")
_PHONE_CONTEXT = re.compile(r"(?i)\b(?:phone|mobile|telephone|tel|contact|手机号|电话)\b")
_PERSON_CONTEXT = re.compile(r"(?i)\b(?:full[_ -]?name|person[_ -]?name|customer[_ -]?name|姓名|联系人)\b")
_BANK_CONTEXT = re.compile(r"(?i)\b(?:bank[_ -]?account|account[_ -]?(?:no|number)|iban|账户|账号)\b")
_ROUTING_CONTEXT = re.compile(r"(?i)\b(?:aba|routing(?:[_ -]?(?:no|number))?)\b")
_TFN_CONTEXT = re.compile(r"(?i)\b(?:tfn|tax[_ -]?(?:id|number)|australia|澳大利亚税号)\b")
_IMEI_CONTEXT = re.compile(r"(?i)\bimei\b")
_CVV_CONTEXT = re.compile(r"(?i)\b(?:cvv2?|cvc2?|card[_ -]?security[_ -]?code|安全码)\b")
_CARD_CONTEXT = re.compile(r"(?i)\b(?:credit[_ -]?card|card(?:[_ -]?(?:no|number))?|pan|银行卡|卡号)\b")
_SSN_CONTEXT = re.compile(r"(?i)\b(?:ssn|social[_ -]?security)\b")
_EIN_CONTEXT = re.compile(r"(?i)\b(?:ein|employer[_ -]?identification|tax[_ -]?(?:id|number))\b")
_COOKIE_CONTEXT = re.compile(r"(?i)\b(?:set-cookie|cookie|session(?:id)?|csrf)\b")
_INTERNAL_DOMAIN = re.compile(r"\b[a-z0-9.-]+\.(?:corp|internal|intranet|lan|localdomain)\b", re.I)
_IMPORT_LINE = re.compile(r"^\s*(?:import|package|from|use|require|include|namespace|xmlns)\b", re.I)
_NAME_LABEL = re.compile(
    r"(?i)^(?:(?:full|person|customer|client|user|contact|patient|student|candidate|employee|first|"
    r"last|middle|display|account|member|guest|vendor|buyer|seller|owner|applicant|recipient|sender|"
    r"party|individual)[ _-]?)+names?$"
)
_ROLE_EMAIL_LOCAL = re.compile(
    r"(?i)^(?:info|information|support|help|helpdesk|admin|administrator|webmaster|postmaster|"
    r"hostmaster|abuse|noreply|no-reply|donotreply|do-not-reply|contact|contacts|sales|marketing|"
    r"office|hello|feedback|mail|email|team|legal|privacy|newsletter|news|jobs?|careers?|press|"
    r"service|services|root|null|none|test|testing|example|user|users|everyone|all|license|"
    r"licensing|bugs?|ops|noc|notifications?|subscribe|unsubscribe|git|github|web|www|ftp|lists?|"
    r"listserv|billing|invoices?|orders?|donations?|donate|general|nobody|daemon|security|"
    r"enquir(?:y|ies)|inquiries|reception|dev(?:elopment)?|devs?|devops)(?:[._+-].*)?$"
)
_EMAIL_TLD_BLOCKLIST = {
    "png", "jpg", "jpeg", "gif", "svg", "webp", "ico", "bmp", "tif", "tiff", "css", "js", "jsx", "ts",
    "tsx", "html", "htm", "json", "xml", "yaml", "yml", "md", "txt", "pdf", "zip", "gz", "tar", "mp3",
    "mp4", "woff", "woff2", "ttf", "eot", "log", "csv", "sql", "sh", "py", "java", "class", "min",
}
_STRONG_AUTHOR_MARKER = re.compile(
    r"(?i)(?:\bcopyright\b|©|\(c\)|[@\\]authors?\b|[\"']authors?[\"']|\bauthors?\s*[:=]|"
    r"\bmaintainers?\s*[:=])"
)
_WEAK_AUTHOR_MARKER = re.compile(
    r"(?i)\b(?:authors?|maintainers?|created by|written by|maintained by|modified by|updated by)\b"
)
_COMMENT_LINE = re.compile(r"^\s*(?://+|#+|\*+|/\*+|;+|--+|<!--|%+|\\|\{#)")
_PROFESSION_CONTEXT = re.compile(
    r"(?i)\b(?:researcher|professor|lecturer|speaker|engineer|developer|designer|architect|scientist|"
    r"consultant|analyst|attorney|lawyer|physician|doctor|nurse|founder|cofounder|ceo|cto|cfo|coo|president|"
    r"chairman|chairwoman|director|manager|author|writer|editor|translator|illustrator|photographer|artist|"
    r"musician|journalist|student|teacher|accountant|librarian)\b"
)
_HTML_TAG = re.compile(r"</?[A-Za-z][^>]{0,300}>")
_CODE_PUNCTUATION = re.compile(r"[;{}()\[\]<>]|=>|::|\|\||&&|[!=<>]=|[-+*/%&|^]=|\\")
_ATTRIBUTION_WORDS = re.compile(
    r"(?i)\b(?:copyright|authors?|maintainers?|created|written|maintained|modified|updated|by|from|of|c)\b"
)
_ORG_SUFFIX = re.compile(
    r"(?i)^\s*[,.;]?\s*(?:llc|ltd|limited|inc|incorporated|gmbh|pty|pte|pvt|llp|plc|corp|corporation|"
    r"co|ag|bv|nv|ab|oy|sa|s\.a\.|ltda|institut\w*|institute|university|foundation|company|group)\b"
)
_AUTHOR_PREFIX = re.compile(r"(?i)(?:\d{4}|by|copyright|authors?|created|written|maintained|modified|updated|from|of|c)$")
_TEST_CARD_NUMBERS = (
    "4242424242424242", "5555555555554444", "2223000048400010", "4012888888881881",
    "378282246310005", "371449635398431", "6011111111111117", "3530111333300000",
    "4000056655665556", "5200828282828210", "5105105105105100", "4111111111111111",
)
_MAX_CANDIDATES = 500
_MAX_EVIDENCE_ITEMS = 20
_ORG_NAME = re.compile(
    r"(?i)\b(?:inc|llc|ltd|limited|corp|corporation|company|foundation|fund|team|authors?|"
    r"contributors?|reserved|rights|university|universit\w*|institut\w*|institutes?|labs?|"
    r"laboratory|gmbh|plc|group|project|software|solutions?|services?|systems?|technologies|"
    r"technology|holdings?|enterprises?|association|society|center|centre|council|committee|"
    r"department|ministry|studio|studios?|media|holders?|partners?|bank|schools?|college|"
    r"academy|agency|network|community|consortium|corporations?|industries|works|business|"
    r"machines|pty|pte|pvt|llp|press|publishing|publications?|research|engineering|consulting|"
    r"logistics|motors|electric|electrical|electronics|communications|healthcare|insurance|pharma|"
    r"robotics|sciences?|acad\w*|journal|proceedings|transactions|letters|bulletin|magazine|"
    r"national|federal|review|"
    r"rentals?|sales|parts|supplies|equipment|machinery|trading|wholesale|retail|stores?|shops?|"
    r"markets?|outlets?|associates|contractors?|builders?|construction|distributors?|products?|goods|"
    r"furniture|appliances?|forklifts?|trucks?|casino|betting|lottery|gaming|entertainment|productions?|"
    r"publishers?|printing|advertising|marketing|transport(?:ation)?|airlines?|hotels?|resorts?|"
    r"restaurants?|catering|foods?|beverages?|clinic|hospital|pharmacy|properties|realty|estates|"
    r"ventures|capital|investments?|securities|assets?|banking|mortgage|loans|accounting|payroll|"
    r"staffing|recruiting|cleaning|roofing|plumbing|solar|mining|chemicals|plastics|metals|steel|"
    r"timber|textiles|apparel|fashion|jewelry|cosmetics|pharmaceuticals|biotech|hardware|hosting|"
    r"travel|tours|tourism|promotions?)\b"
)
_COLLECTIVE_ORG = re.compile(
    r"(?i)\b(?:group|team|llc|ltd|limited|inc|incorporated|corp|corporation|company|foundation|"
    r"association|society|committee|department|ministry|institute|institut\w*|university|universit\w*|"
    r"college|schools?|labs?|laboratory|studios?|agency|council|cent(?:er|re)|consortium|partners?|"
    r"holdings?|enterprises?|technologies|systems?|solutions?|services?|software|projects?)\b"
)
_CONN_STRING = re.compile(r"(?i)\b(?:jdbc:|data\s+source\s*=|initial\s+catalog\s*=|connection\s*string|server\s*=)")
_VERSION_CONTEXT = re.compile(r"(?i)version|release|revision|build|\btag\b|\$id:|\$header:|,v\s+\d|\bv\d+\.\d+")
_OPENVPN_STATIC_KEY = re.compile(r"-----BEGIN OpenVPN Static key(?: V\d)?-----")
_URL_CREDENTIAL_PARAM = re.compile(
    r"(?i)[?&;][\w.-]*(?:api[_-]?key|apikey|key|token|access[_-]?token|auth[_-]?token|password|passwd|pwd|"
    r"secret|signature|sig)=(?P<value>[A-Za-z0-9_./+~=-]{6,})"
)
_DOCUMENTATION_NETWORKS = (
    ipaddress.ip_network("192.0.2.0/24"),
    ipaddress.ip_network("198.51.100.0/24"),
    ipaddress.ip_network("203.0.113.0/24"),
)
_PUBLIC_RESOLVERS = {"8.8.8.8", "8.8.4.4", "1.1.1.1", "1.0.0.1", "9.9.9.9", "208.67.222.222", "208.67.220.220"}
_NAME_STOPWORDS = {
    "all", "and", "any", "as", "at", "author", "authors", "be", "by", "code", "contract", "copyright",
    "documentation", "each", "for", "from", "granted", "hereby", "in", "is", "it", "license", "licensed",
    "not", "of", "on", "open", "or", "other", "others", "permission", "private", "project", "public",
    "redistribution", "reserved", "rights", "same", "see", "software", "source", "team", "terms", "that",
    "the", "this", "to", "under", "use", "used", "version", "warranty", "we", "with", "without",
    "written", "you", "your", "legal", "notice", "statement", "agreement", "policy", "disclaimer",
    "trademark", "trademarks", "page", "site", "website", "web", "guide", "manual", "tutorial",
    "chapter", "section", "figure", "table", "appendix", "note", "notes", "warning", "tip", "drive",
    "geek", "developer", "developers", "subject", "sentence", "document", "documents", "file", "files",
    "when", "where", "what", "which", "while", "whom", "whose", "why", "how", "then", "than", "there",
    "here", "these", "those", "after", "before", "during", "until", "unless", "although", "however",
    "therefore", "moreover", "also", "both", "many", "most", "some", "several", "because", "since",
    "once", "every", "into", "onto", "over", "between", "among", "through", "about", "above", "below",
    "upon", "within", "such", "very", "only", "just", "even", "still", "again", "does", "did", "been",
    "being", "are", "was", "were", "has", "have", "had", "should", "would", "could", "shall", "might",
    "please", "thanks", "welcome", "hello", "maybe", "perhaps", "actually", "really", "usually",
    "currently", "previously", "recently", "finally", "additionally",
}
_NAME_PARTICLES = {
    "al", "bin", "da", "de", "del", "della", "der", "di", "dos", "du", "el", "ibn", "la", "le", "mac",
    "mc", "st", "ten", "ter", "van", "von",
}

_CN_PROVINCES = {
    "11", "12", "13", "14", "15", "21", "22", "23", "31", "32", "33", "34", "35", "36", "37",
    "41", "42", "43", "44", "45", "46", "50", "51", "52", "53", "54", "61", "62", "63", "64", "65",
    "71", "81", "82",
}
_CN_ID_WEIGHTS = (7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2)
_CN_ID_CHECK = "10X98765432"


def _digits(value: str) -> str:
    return re.sub(r"\D", "", value)


def _luhn(value: str, minimum: int, maximum: int) -> bool:
    digits = _digits(value)
    if not minimum <= len(digits) <= maximum or len(set(digits)) < 3:
        return False
    total = 0
    for index, char in enumerate(reversed(digits)):
        digit = int(char)
        if index % 2:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0


def _valid_cn_id(value: str) -> bool:
    value = value.upper()
    if not re.fullmatch(r"[1-9]\d{16}[0-9X]", value) or value[:2] not in _CN_PROVINCES:
        return False
    try:
        datetime.strptime(value[6:14], "%Y%m%d")
    except ValueError:
        return False
    if value[14:17] == "000":
        return False
    checksum = sum(int(char) * weight for char, weight in zip(value[:17], _CN_ID_WEIGHTS))
    return value[-1] == _CN_ID_CHECK[checksum % 11]


def _valid_ssn(value: str) -> bool:
    area, group, serial = (int(part) for part in value.split("-"))
    return not (area == 0 or area == 666 or area >= 900 or group == 0 or serial == 0)


def _valid_iban(value: str) -> bool:
    compact = re.sub(r"\s", "", value).upper()
    if not re.fullmatch(r"[A-Z]{2}\d{2}[A-Z0-9]{11,30}", compact):
        return False
    rearranged = compact[4:] + compact[:4]
    numeric = "".join(str(ord(char) - 55) if char.isalpha() else char for char in rearranged)
    remainder = 0
    for char in numeric:
        remainder = (remainder * 10 + int(char)) % 97
    return remainder == 1


def _valid_tfn(value: str) -> bool:
    digits = _digits(value)
    if len(set(digits)) <= 2:
        return False
    if len(digits) == 9:
        weights = (1, 4, 3, 7, 5, 8, 6, 9, 10)
        return sum(int(a) * b for a, b in zip(digits, weights)) % 11 == 0
    if len(digits) == 11:
        if digits[0] == "0":
            return False
        adjusted = str(int(digits[0]) - 1) + digits[1:]
        weights = (10, 1, 3, 5, 7, 9, 11, 13, 15, 17, 19)
        return sum(int(a) * b for a, b in zip(adjusted, weights)) % 89 == 0
    return False


def _valid_aba(value: str) -> bool:
    digits = _digits(value)
    if len(digits) != 9 or len(set(digits)) < 3:
        return False
    return sum(int(char) * (3, 7, 1)[index % 3] for index, char in enumerate(digits)) % 10 == 0


def _valid_italian_tax_id(value: str) -> bool:
    value = value.upper()
    pattern = r"[A-Z]{6}[0-9LMNPQRSTUV]{2}[ABCDEHLMPRST][0-9LMNPQRSTUV]{2}[A-Z][0-9LMNPQRSTUV]{3}[A-Z]"
    if not re.fullmatch(pattern, value):
        return False
    odd = {
        **dict(zip("0123456789", (1, 0, 5, 7, 9, 13, 15, 17, 19, 21))),
        **dict(zip(
            "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
            (1, 0, 5, 7, 9, 13, 15, 17, 19, 21, 2, 4, 18, 20, 11, 3, 6, 8, 12, 14, 16, 10, 22, 25, 24, 23),
        )),
    }
    even = {char: index for index, char in enumerate("0123456789")}
    even.update({char: index for index, char in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ")})
    checksum = sum(odd[char] if index % 2 == 0 else even[char] for index, char in enumerate(value[:15]))
    return value[-1] == chr(ord("A") + checksum % 26)


def _not_placeholder(value: str) -> bool:
    stripped = value.strip().strip("'\"")
    return bool(stripped) and not _PLACEHOLDER.fullmatch(stripped)


_CREDENTIAL_NOISE = re.compile(
    r"(?i)\b(?:process|env|environ|getenv|system|config|settings|self|this|ctx|context|require|"
    r"import|function|return|new|null|undefined|true|false)\b"
)
_EMAIL_PATTERN = re.compile(r"\b([A-Za-z0-9.!#$%&'*+=?^_`{|}~-]+)@([A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+)\b")


def _credential_literal(value: str) -> str:
    """Normalize an assignment value; return an empty string when it is not a literal."""
    stripped = value.strip().strip("'\"").rstrip(",;")
    if len(stripped) < 6 or re.search(r"[\[\]{}()<>]", stripped):
        return ""
    if stripped[0] in "$%&!~^|/.-+*" or "?" in stripped:
        return ""
    if _CREDENTIAL_NOISE.search(stripped):
        return ""
    if "://" in stripped:
        return ""
    if re.fullmatch(r"\d+(?:\.\d+)*", stripped) or re.fullmatch(r"[0-9a-fA-F]{1,15}", stripped):
        return ""
    if re.fullmatch(r"(?:[A-Za-z_][A-Za-z0-9_]*\.)+[A-Za-z_][A-Za-z0-9_]*", stripped):
        return ""
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", stripped) and not any(char.isdigit() for char in stripped):
        return ""
    if re.fullmatch(
        r"(?i)(?:change[_-]?me|example|sample|demo|test|testing|dummy|placeholder|todo|"
        r"foo|bar|baz|xxx+|your[_-]?\w*|<.*>)(?:[_-]\w+)*",
        stripped,
    ):
        return ""
    return stripped


def _quoted_credential_value(value: str) -> bool:
    """Validate a quoted credential literal; reject identifiers, type names and concatenations."""
    stripped = value.strip()
    if len(stripped) < 6 or re.search(r"[\[\]{}<>]", stripped):
        return False
    if stripped.startswith("+") or " + " in stripped or stripped.endswith(" +"):
        return False
    if _CREDENTIAL_NOISE.search(stripped):
        return False
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", stripped) and not any(char.isdigit() for char in stripped):
        return False
    return not re.fullmatch(
        r"(?i)(?:change[_-]?me|example|sample|demo|test|testing|dummy|placeholder|todo|"
        r"foo|bar|baz|xxx+|your[_-]?\w*|<.*>)(?:[_-]\w+)*",
        stripped,
    )


def _strong_unquoted_credential(value: str) -> bool:
    """High-confidence literal: mixed classes or a long key-shaped token."""
    stripped = _credential_literal(value)
    if not stripped:
        return False
    if re.fullmatch(r"[0-9a-fA-F]{16,}", stripped):
        return True
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", stripped):
        return False
    return bool(re.search(r"\d", stripped)) or bool(re.search(r"[-_@:/+=~%]", stripped))


def _weak_unquoted_credential(value: str) -> bool:
    """Identifier-shaped literal: keep as a contextual candidate for LLM adjudication."""
    return bool(_credential_literal(value)) and not _strong_unquoted_credential(value)


def _valid_url_credential(value: str) -> bool:
    stripped = value.strip()
    if len(stripped) < 6 or re.search(r"[\[\]{}()<>]", stripped) or stripped[0] in "$%&!~^|":
        return False
    return not re.fullmatch(
        r"(?i)(?:example|sample|demo|dummy|test|your[_-]?\w*|xxx+|<.*>)(?:[_-]\w+)*", stripped
    )


def _valid_cookie_literal(value: str) -> bool:
    if re.search(r"[A-Za-z_]\(", value):
        return False
    if re.fullmatch(r"(?:[A-Za-z_][A-Za-z0-9_]*\.)+[A-Za-z_][A-Za-z0-9_]*", value):
        return False
    return bool(re.search(r"\d", value)) or bool(re.search(r"[-/=%]", value))


def _is_name_token(word: str) -> bool:
    """True for a capitalized word that can be part of a person name."""
    core = word.strip(".,;:!?'\"`-")
    if len(core) < 2 or not core[0].isupper() or core.isupper():
        return False
    if any(char.isdigit() for char in core) or not any(char.islower() for char in core):
        return False
    return not _ORG_NAME.search(core) and core.lower() not in _NAME_STOPWORDS


def _is_person_attribution(line: str, start: int, name_end: int) -> bool:
    """Keep only spans that sit in an attribution slot and are not organization names."""
    prefix = line[:start].rstrip(" \t")
    if prefix and prefix[-1] not in ":<(=[\"'*/#,-" and not _AUTHOR_PREFIX.search(prefix):
        return False
    if _ORG_SUFFIX.match(line[name_end:]):
        return False
    if prefix.endswith(","):
        segment = _ATTRIBUTION_WORDS.sub(" ", prefix[:-1].rsplit(",", 1)[-1])
        if _ORG_NAME.search(segment):
            return False
    return not _collective_suffix(line, name_end)


def _collective_suffix(line: str, name_end: int) -> bool:
    """True when the words directly after a span name an organization rather than a person."""
    tail = line[name_end:]
    seen = 0
    for match in re.finditer(r"[A-Za-z\u00c0-\u024f']+", tail):
        if re.search(r"[.,;:]", tail[:match.start()]):
            return False
        word = match.group(0)
        if _COLLECTIVE_ORG.fullmatch(word):
            return True
        if word.lower() in _NAME_STOPWORDS or word.lower() in _NAME_PARTICLES:
            continue
        seen += 1
        if seen >= 3:
            return False
    return False


def _is_prose_line(line: str) -> bool:
    """True for natural-language lines (documentation, HTML/Markdown prose) without code syntax."""
    text = _HTML_TAG.sub(" ", line)
    if _CODE_PUNCTUATION.search(text):
        return False
    return len(re.findall(r"[A-Za-z\u00c0-\u024f']+", text)) >= 5


def _is_plausible_email(local: str, domain: str) -> bool:
    """Reject file paths, dummy identities, example domains and role-based mailboxes."""
    tld = domain.rsplit(".", 1)[-1].lower()
    if len(tld) < 2 or not tld.isalpha() or tld in _EMAIL_TLD_BLOCKLIST:
        return False
    return not _EXAMPLE_EMAIL_DOMAIN.fullmatch(domain) and not _ROLE_EMAIL_LOCAL.fullmatch(local)


def _author_name_spans(line: str) -> list[tuple[int, int, str]]:
    """Collect capitalized person-name sequences from a copyright/author line."""
    tokens = [
        (match.start(), match.end(), match.group(0))
        for match in re.finditer(r"[A-Za-z'\u00c0-\u024f.-]+", line)
    ]
    spans: list[tuple[int, int, str]] = []
    cursor = 0
    while cursor < len(tokens):
        start, previous_end, word = tokens[cursor]
        if not _is_name_token(word):
            cursor += 1
            continue
        name_end = previous_end
        taken = 1
        following = cursor + 1
        sentence_end = word[-1] in ".,;:"
        while following < len(tokens) and not sentence_end:
            next_start, next_end, next_word = tokens[following]
            if next_start - previous_end != 1:
                break
            if _is_name_token(next_word):
                previous_end = name_end = next_end
                taken += 1
                following += 1
                sentence_end = next_word[-1] in ".,;:"
                continue
            if next_word.strip(".,;:").lower() in _NAME_PARTICLES:
                previous_end = next_end
                following += 1
                continue
            break
        if taken >= 2 and _is_person_attribution(line, start, name_end):
            value = line[start:name_end].rstrip(".,;:")
            if len(value) >= 5 and " " in value:
                spans.append((start, start + len(value), value))
        cursor = max(following, cursor + 1)
    return spans


def _is_public_routable(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """True for real routable IPv4 literals worth reviewing as personal network identifiers."""
    if address.version != 4:
        return False
    if (address.is_private or address.is_loopback or address.is_reserved or address.is_multicast
            or address.is_unspecified or address.is_link_local):
        return False
    if str(address) in _PUBLIC_RESOLVERS:
        return False
    return not any(address in network for network in _DOCUMENTATION_NETWORKS)


def _context_hint(line: str, start: int, end: int, kind: str) -> str:
    """Retain code structure while removing all likely values from the line."""
    hint = f"{line[:start]}[REDACTED:{kind}]{line[end:]}"
    hint = re.sub(r"(['\"])(?:(?!\1).)*\1", r"\1[REDACTED]\1", hint)
    hint = re.sub(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", "[REDACTED]", hint)
    hint = re.sub(r"(?<![\w:])(?:\d{1,3}\.){3}\d{1,3}(?![\w:])", "[REDACTED]", hint)
    hint = re.sub(r"\b[A-Za-z0-9_+./:@=-]{12,}\b", "[REDACTED]", hint)
    hint = re.sub(r"(?<!\d)\d{4,}(?!\d)", "[REDACTED]", hint)
    return hint[:240]


def _append(
    output: list[dict[str, Any]], line: str, line_number: int, match: re.Match[str] | None, *,
    category: str, kind: str, severity: str, confidence: str, validator: str,
    span: tuple[int, int] | None = None, matched_value: str | None = None,
) -> None:
    start, end = span or match.span()
    output.append({
        "category": category,
        "kind": kind,
        "line": line_number,
        "severity": severity,
        "confidence": confidence,
        "validator": validator,
        "context_hint": _context_hint(line, start, end, kind),
        "matched_value": matched_value if matched_value is not None else match.group(0),
    })


def _scan(
    output: list[dict[str, Any]], line: str, line_number: int, pattern: str | re.Pattern[str], *,
    category: str, kind: str, severity: str = "high", confidence: str = "high",
    validator: str = "pattern", validate: Callable[[str], bool] | None = None,
) -> None:
    compiled = re.compile(pattern) if isinstance(pattern, str) else pattern
    for match in compiled.finditer(line):
        groups = match.groupdict()
        value = groups["value"] if groups.get("value") is not None else match.group(0)
        if not _not_placeholder(value) or (validate is not None and not validate(value)):
            continue
        span = match.span("value") if "value" in groups else match.span()
        _append(output, line, line_number, match, category=category, kind=kind, severity=severity,
                confidence=confidence, validator=validator, span=span, matched_value=value)


def security_candidates(content: str) -> list[dict[str, Any]]:
    """Detect repository PII and credentials without returning matched values."""
    candidates: list[dict[str, Any]] = []
    complete_private_key_lines = set()
    private_key_block = re.compile(
        r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----\s+"
        r"[A-Za-z0-9+/=\r\n]{64,}\s+-----END (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----"
    )
    for match in private_key_block.finditer(content):
        line_number = content.count("\n", 0, match.start()) + 1
        complete_private_key_lines.add(line_number)
        candidates.append({
            "category": "secret", "kind": "PRIVATE_KEY", "line": line_number,
            "severity": "high", "confidence": "high", "validator": "complete PEM private-key block",
            "context_hint": "[REDACTED:PRIVATE_KEY_BLOCK]",
            "matched_value": match.group(0),
        })
    lines = content.splitlines()
    test_card_fixture = any(number in content for number in _TEST_CARD_NUMBERS)
    for line_number, line in enumerate(lines, 1):
        if len(candidates) >= _MAX_CANDIDATES:
            break
        # Credentials and authentication material.
        secret_rules = (
            ("AWS_ACCESS_KEY", re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"), "provider prefix and length"),
            ("API_KEY", re.compile(
                r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|glpat-[A-Za-z0-9_-]{20,}|"
                r"sk-(?:proj-)?[A-Za-z0-9_-]{20,}|AIza[0-9A-Za-z_-]{35}|sk_live_[A-Za-z0-9]{20,})\b"
            ), "provider signature"),
            ("CLOUD_TOKEN", re.compile(
                r"\b(?:xox[abprs]-[A-Za-z0-9-]{20,}|\d{8,10}:[A-Za-z0-9_-]{30,})\b"
            ), "provider signature"),
            ("JWT", re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"), "JWT structure"),
            ("AUTHORIZATION", re.compile(
                r"(?i)\bAuthorization\s*[:=]\s*['\"]?(?:Bearer|Basic)\s+[A-Za-z0-9+/_.=-]{12,}"
            ), "authorization header"),
            ("PASSWORD_HASH", re.compile(
                r"\$(?:2[aby]\$\d{2}\$[./A-Za-z0-9]{53}|argon2(?:id|i|d)\$[^\s'\"]+|pbkdf2-[^\s'\"]+)"
            ), "password-hash signature"),
            ("DB_CONNECTION", re.compile(
                r"(?i)\b(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis)://"
                r"[^\s/:@]+:[^\s/@]+@[^\s'\"]+"
            ), "credentialed database URI"),
            ("AUTH_URL", re.compile(r"(?i)\bhttps?://[^\s/:@]+:[^\s/@]+@[^\s'\"]+"), "credentialed URL"),
        )
        for kind, pattern, validator in secret_rules:
            _scan(candidates, line, line_number, pattern, category="secret", kind=kind, validator=validator)

        if line_number not in complete_private_key_lines:
            _scan(
                candidates, line, line_number,
                re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----"),
                category="secret", kind="PRIVATE_KEY", confidence="contextual",
                validator="private-key marker without complete block",
            )
        _scan(
            candidates, line, line_number, _OPENVPN_STATIC_KEY,
            category="secret", kind="PRIVATE_KEY", validator="OpenVPN static key block",
        )

        _scan(
            candidates, line, line_number,
            re.compile(
                r"(?i)[A-Za-z0-9_.\-]*(?:password|passwd|pwd|passphrase|pin)[A-Za-z0-9_\-]*\s*[:=]\s*"
                r"['\"](?P<value>[^'\"]{6,})['\"]"
            ),
            category="secret", kind="PASSWORD", confidence="contextual", validator="credential assignment",
            validate=_quoted_credential_value,
        )
        _scan(
            candidates, line, line_number,
            re.compile(
                r"(?i)[A-Za-z0-9_.\-]*(?:api[_-]?key|apikey|access[_-]?token|auth[_-]?token|"
                r"client[_-]?secret|secret[_-]?key|private[_-]?key|secret|token)[A-Za-z0-9_\-]*\s*[:=]\s*"
                r"['\"](?P<value>[A-Za-z0-9_./+=~-]{16,})['\"]"
            ),
            category="secret", kind="API_KEY", confidence="contextual", validator="credential assignment",
            validate=_quoted_credential_value,
        )
        _scan(
            candidates, line, line_number,
            re.compile(
                r"(?i)[A-Za-z0-9_.\-]*(?:password|passwd|pwd|passphrase|secret|token|api[_-]?key|apikey|"
                r"access[_-]?key|client[_-]?secret)[A-Za-z0-9_\-]*\s*,\s*['\"](?P<value>[^'\"]{6,})['\"]"
            ),
            category="secret", kind="PASSWORD", confidence="contextual", validator="credential argument",
            validate=_quoted_credential_value,
        )
        for confidence, validate in (("high", _strong_unquoted_credential), ("contextual", _weak_unquoted_credential)):
            _scan(
                candidates, line, line_number,
                re.compile(
                    r"(?i)[A-Za-z0-9_.\-]*(?:password|passwd|pwd|passphrase|secret|token|api[_-]?key|apikey|"
                    r"access[_-]?key|client[_-]?secret|auth[_-]?token)[A-Za-z0-9_\-]*(?:\s*:=\s*|\s*=\s*|\s*:\s+)"
                    r"(?P<value>[^\s'\"#][^\s'\"#]{5,})"
                ),
                category="secret", kind="PASSWORD", confidence=confidence,
                validator="unquoted credential assignment", validate=validate,
            )
        _scan(
            candidates, line, line_number, _URL_CREDENTIAL_PARAM,
            category="secret", kind="API_KEY", confidence="contextual",
            validator="URL query credential parameter", validate=_valid_url_credential,
        )
        if _CONN_STRING.search(line):
            _scan(
                candidates, line, line_number,
                re.compile(r"(?i)\b(?:password|pwd)\s*=\s*(?P<value>[^;\s'\"]{3,})"),
                category="secret", kind="PASSWORD", confidence="contextual",
                validator="connection-string credential segment",
            )
        if _COOKIE_CONTEXT.search(line):
            _scan(
                candidates, line, line_number,
                re.compile(
                    r"(?i)(?:set-cookie\s*:|cookie\s*[:=]|session(?:id)?\s*[:=])\s*"
                    r"['\"]?(?P<value>[A-Za-z0-9_./+=%-]{16,})"
                ),
                category="secret", kind="COOKIE", confidence="contextual", validator="cookie context",
                validate=_valid_cookie_literal,
            )

        # Strongly validated identity and financial identifiers.
        _scan(candidates, line, line_number, re.compile(r"(?<!\d)[1-9]\d{16}[0-9Xx](?!\d)"),
              category="pii", kind="ID_CARD_CN", validator="GB 11643 checksum/date/region", validate=_valid_cn_id)
        if _SSN_CONTEXT.search(line):
            _scan(candidates, line, line_number, re.compile(r"(?<!\d)\d{3}-\d{2}-\d{4}(?!\d)"),
                  category="pii", kind="SSN", validator="SSA allocation rules and SSN context", validate=_valid_ssn)
        _scan(candidates, line, line_number, re.compile(r"\b[A-Z]{2}\d{2}(?:[ ]?[A-Z0-9]){11,30}\b", re.I),
              category="pii", kind="IBAN", validator="ISO 13616 mod-97", validate=_valid_iban)
        _scan(
            candidates, line, line_number,
            re.compile(
                r"\b[A-Z]{6}[0-9LMNPQRSTUV]{2}[ABCDEHLMPRST][0-9LMNPQRSTUV]{2}"
                r"[A-Z][0-9LMNPQRSTUV]{3}[A-Z]\b", re.I,
            ),
            category="pii", kind="TAX_ID_IT", validator="Italian codice fiscale checksum",
            validate=_valid_italian_tax_id,
        )
        if _CARD_CONTEXT.search(line) and not _IMEI_CONTEXT.search(line) and not test_card_fixture:
            _scan(candidates, line, line_number, re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)"),
                  category="pii", kind="CREDIT_CARD", validator="Luhn and card field context",
                  validate=lambda value: _luhn(value, 13, 19))
        if _TFN_CONTEXT.search(line):
            _scan(candidates, line, line_number, re.compile(r"(?<!\d)(?:(?:\d[ ]?){9}|(?:\d[ ]?){11})(?!\d)"),
                  category="pii", kind="TAX_ID_AU", validator="Australian TFN/ABN checksum", validate=_valid_tfn)
        if _IMEI_CONTEXT.search(line):
            _scan(candidates, line, line_number, re.compile(r"(?<!\d)\d{15}(?!\d)"),
                  category="pii", kind="IMEI", validator="IMEI Luhn", validate=lambda value: _luhn(value, 15, 15))
        if _ROUTING_CONTEXT.search(line):
            _scan(candidates, line, line_number, re.compile(r"(?<!\d)\d{9}(?!\d)"),
                  category="pii", kind="ABA_ROUTING", validator="ABA checksum", validate=_valid_aba)
        if _EIN_CONTEXT.search(line):
            _scan(candidates, line, line_number, re.compile(r"(?<!\d)\d{2}-\d{7}(?!\d)"),
                  category="pii", kind="TAX_ID_US", validator="US EIN structure and tax-ID context")

        # Contact data and context-dependent identifiers require LLM adjudication.
        for match in _EMAIL_PATTERN.finditer(line):
            if not _is_plausible_email(match.group(1), match.group(2)):
                continue
            if re.search(r"\w+://[^\s]*$", line[:match.start()]):
                continue
            _append(candidates, line, line_number, match, category="pii", kind="EMAIL", severity="medium",
                    confidence="contextual", validator="RFC-like email structure")
        if (_STRONG_AUTHOR_MARKER.search(line)
                or (_WEAK_AUTHOR_MARKER.search(line) and (_COMMENT_LINE.search(line) or _is_prose_line(line)))
                or (_PROFESSION_CONTEXT.search(line) and _is_prose_line(line))):
            for start, end, value in _author_name_spans(line):
                _append(candidates, line, line_number, None, category="pii", kind="PERSON_NAME", severity="medium",
                        confidence="contextual", validator="copyright or author attribution", span=(start, end),
                        matched_value=value)
        _scan(candidates, line, line_number, re.compile(r"(?<!\d)(?:\+?86[- ]?)?1[3-9]\d{9}(?!\d)"),
              category="pii", kind="PHONE", severity="medium", confidence="contextual", validator="CN mobile structure")
        if _PHONE_CONTEXT.search(line):
            _scan(candidates, line, line_number, re.compile(r"(?<!\d)0\d{2,3}[- ]?\d{7,8}(?!\d)"),
                  category="pii", kind="PHONE", severity="medium", confidence="contextual",
                  validator="CN landline structure")
            _scan(candidates, line, line_number, re.compile(r"(?<!\w)\+[1-9]\d{6,14}(?!\d)"),
                  category="pii", kind="PHONE", severity="medium", confidence="contextual", validator="E.164 structure")
        if _PERSON_CONTEXT.search(line):
            _scan(
                candidates, line, line_number,
                re.compile(r"(?P<value>[A-Z][a-z]{1,30}(?:[ '-][A-Z][a-z]{1,30}){1,3})"),
                category="pii", kind="PERSON_NAME", severity="medium", confidence="contextual",
                validator="name field context",
                validate=lambda value: not _NAME_LABEL.fullmatch(value.lower().strip()),
            )
        if _BANK_CONTEXT.search(line) and not re.search(r"\b[A-Z]{2}\d{2}", line, re.I):
            _scan(candidates, line, line_number, re.compile(r"(?<!\d)(?:\d[ -]?){8,30}(?!\d)"),
                  category="pii", kind="BANK_ACCOUNT", confidence="contextual", validator="bank-account context")
        if _CVV_CONTEXT.search(line) and not test_card_fixture:
            _scan(
                candidates, line, line_number,
                re.compile(
                    r"(?i)\b(?:cvv2?|cvc2?|card[_ -]?security[_ -]?code|安全码)\b"
                    r"[^0-9\n]{0,40}(?P<value>(?<!\d)\d{3,4}(?!\d))"
                ),
                category="pii", kind="CVV", confidence="contextual", validator="CVV field context",
            )

        for match in re.finditer(r"(?<![\w:])(?:\d{1,3}\.){3}\d{1,3}(?![\w:])", line):
            try:
                address = ipaddress.ip_address(match.group(0))
            except ValueError:
                continue
            if not _IP_CONTEXT.search(line) and not _INFRA_CONTEXT.search(line):
                if not _is_public_routable(address) or _VERSION_CONTEXT.search(line):
                    continue
            category = "internal_endpoint" if address.is_private and _INFRA_CONTEXT.search(line) else "pii"
            _append(candidates, line, line_number, match, category=category, kind="IP_V4", severity="medium",
                    confidence="contextual", validator="IPv4 parser and context")
        for match in re.finditer(r"(?<![\w:])(?:[0-9A-Fa-f]{0,4}:){2,7}[0-9A-Fa-f]{0,4}(?![\w:])", line):
            try:
                address = ipaddress.ip_address(match.group(0))
            except ValueError:
                continue
            if address.version == 6 and (_IP_CONTEXT.search(line) or _INFRA_CONTEXT.search(line)):
                category = "internal_endpoint" if address.is_private and _INFRA_CONTEXT.search(line) else "pii"
                _append(candidates, line, line_number, match, category=category, kind="IP_V6", severity="medium",
                        confidence="contextual", validator="IPv6 parser and context")
        if re.search(r"(?i)\b(?:mac|hardware[_ -]?address)\b", line):
            _scan(candidates, line, line_number,
                  re.compile(r"(?i)(?<![0-9a-f])(?:[0-9a-f]{2}[:-]){5}[0-9a-f]{2}(?![0-9a-f])"),
                  category="pii", kind="MAC", severity="medium", confidence="contextual", validator="MAC field context")
        if _INFRA_CONTEXT.search(line) and not _IMPORT_LINE.search(line):
            _scan(candidates, line, line_number, _INTERNAL_DOMAIN, category="internal_endpoint",
                  kind="INTERNAL_DOMAIN", severity="medium", confidence="contextual",
                  validator="internal-domain suffix and infrastructure context")

    seen: set[tuple[Any, ...]] = set()
    unique = []
    for item in candidates:
        key = (item["category"], item["kind"], item["line"], item["confidence"])
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


def confirmed_security_findings(candidates: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Convert high-confidence rule matches to coarse public security labels."""
    labels = {
        "pii": "Security.PII_Exposure",
        "secret": "Security.Secret_Credentials",
        "internal_endpoint": "Security.Internal_Endpoint_Exposure",
    }
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for candidate in candidates:
        if candidate.get("confidence") == "high":
            grouped[candidate["category"]].append(candidate)
    findings = []
    for category, items in grouped.items():
        summary = _format_evidence(items)
        findings.append({
            "label": labels[category],
            "reason": f"Deterministic sensitive-data validation matched {summary}.",
        })
    return findings


def contextual_security_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {key: value for key, value in candidate.items() if key != "matched_value"}
        for candidate in candidates
        if candidate.get("confidence") == "contextual"
    ]


def security_evidence(candidates: list[dict[str, Any]], category: str) -> str:
    """Return raw local evidence for a confirmed contextual-review category."""
    return _format_evidence([candidate for candidate in candidates if candidate["category"] == category])


def _format_evidence(candidates: list[dict[str, Any]]) -> str:
    shown = ", ".join(
        f"[{candidate['kind']}] line {candidate['line']} value="
        f"{json.dumps(candidate['matched_value'], ensure_ascii=False)}"
        for candidate in candidates[:_MAX_EVIDENCE_ITEMS]
    )
    if len(candidates) > _MAX_EVIDENCE_ITEMS:
        shown += f", ... (+{len(candidates) - _MAX_EVIDENCE_ITEMS} more matches)"
    return shown
