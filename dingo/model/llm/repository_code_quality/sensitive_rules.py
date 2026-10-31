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
    output: list[dict[str, Any]], line: str, line_number: int, match: re.Match[str], *,
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
        value = match.groupdict().get("value", match.group(0))
        if not _not_placeholder(value) or (validate is not None and not validate(value)):
            continue
        span = match.span("value") if "value" in match.groupdict() else match.span()
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
    for line_number, line in enumerate(content.splitlines(), 1):
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
            candidates, line, line_number,
            re.compile(r"(?i)\b(?:password|passwd|pwd|passphrase|pin)\s*[:=]\s*['\"](?P<value>[^'\"]{6,})['\"]"),
            category="secret", kind="PASSWORD", confidence="contextual", validator="credential assignment",
        )
        _scan(
            candidates, line, line_number,
            re.compile(
                r"(?i)\b(?:api[_-]?key|access[_-]?token|client[_-]?secret)\s*[:=]\s*"
                r"['\"](?P<value>[A-Za-z0-9_./+=-]{16,})['\"]"
            ),
            category="secret", kind="API_KEY", confidence="contextual", validator="credential assignment",
        )
        if _COOKIE_CONTEXT.search(line):
            _scan(
                candidates, line, line_number,
                re.compile(
                    r"(?i)(?:set-cookie\s*:|cookie\s*[:=]|session(?:id)?\s*[:=])\s*"
                    r"['\"]?(?P<value>[A-Za-z0-9_./+=%-]{16,})"
                ),
                category="secret", kind="COOKIE", confidence="contextual", validator="cookie context",
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
        if _CARD_CONTEXT.search(line) and not _IMEI_CONTEXT.search(line):
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
        email_pattern = re.compile(r"\b[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@([A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+)\b")
        for match in email_pattern.finditer(line):
            if _EXAMPLE_EMAIL_DOMAIN.fullmatch(match.group(1)) or re.search(r"\w+://[^\s]*$", line[:match.start()]):
                continue
            _append(candidates, line, line_number, match, category="pii", kind="EMAIL", severity="medium",
                    confidence="contextual", validator="RFC-like email structure")
        _scan(candidates, line, line_number, re.compile(r"(?<!\d)(?:\+?86[- ]?)?1[3-9]\d{9}(?!\d)"),
              category="pii", kind="PHONE", severity="medium", confidence="contextual", validator="CN mobile structure")
        _scan(candidates, line, line_number, re.compile(r"(?<!\d)0\d{2,3}[- ]?\d{7,8}(?!\d)"),
              category="pii", kind="PHONE", severity="medium", confidence="contextual",
              validator="CN landline structure")
        if _PHONE_CONTEXT.search(line):
            _scan(candidates, line, line_number, re.compile(r"(?<!\w)\+[1-9]\d{6,14}(?!\d)"),
                  category="pii", kind="PHONE", severity="medium", confidence="contextual", validator="E.164 structure")
        if _PERSON_CONTEXT.search(line):
            _scan(
                candidates, line, line_number,
                re.compile(r"(?P<value>[A-Z][a-z]{1,30}(?:[ '-][A-Z][a-z]{1,30}){1,3})"),
                category="pii", kind="PERSON_NAME", severity="medium", confidence="contextual",
                validator="name field context",
            )
        if _BANK_CONTEXT.search(line) and not re.search(r"\b[A-Z]{2}\d{2}", line, re.I):
            _scan(candidates, line, line_number, re.compile(r"(?<!\d)(?:\d[ -]?){8,30}(?!\d)"),
                  category="pii", kind="BANK_ACCOUNT", confidence="contextual", validator="bank-account context")
        if _CVV_CONTEXT.search(line):
            _scan(candidates, line, line_number, re.compile(r"(?<!\d)\d{3,4}(?!\d)"),
                  category="pii", kind="CVV", confidence="contextual", validator="CVV field context")
        _scan(
            candidates, line, line_number,
            re.compile(r"\b(?:0x[a-fA-F0-9]{40}|(?:bc1|[13])[a-zA-HJ-NP-Z0-9]{25,59})\b"),
            category="pii", kind="CRYPTO_ADDRESS", severity="medium", confidence="contextual",
            validator="blockchain address structure",
        )

        for match in re.finditer(r"(?<![\w:])(?:\d{1,3}\.){3}\d{1,3}(?![\w:])", line):
            try:
                address = ipaddress.ip_address(match.group(0))
            except ValueError:
                continue
            if not _IP_CONTEXT.search(line) and not _INFRA_CONTEXT.search(line):
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
        if _INFRA_CONTEXT.search(line):
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
    return ", ".join(
        f"[{candidate['kind']}] line {candidate['line']} value="
        f"{json.dumps(candidate['matched_value'], ensure_ascii=False)}"
        for candidate in candidates
    )
