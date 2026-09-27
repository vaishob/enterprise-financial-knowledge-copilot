import re

INJECTION_PATTERNS = [
    r"ignore\b.{0,40}\b(previous|prior|all|your)\b.{0,30}\b(instructions|policies|rules)",
    r"(reveal|print|show|disclose|repeat|output)\b.{0,45}\b(system prompt|hidden instructions|internal instructions)",
    r"(show|reveal|disclose|dump)\b.{0,40}\b(restricted|unauthorized|all internal|confidential)\b",
    r"(act as|pretend.{0,15}|you are now|role\s*[:=]|switch.{0,15})\s*(an?\s+)?admin",
    r"\b(fake|invent|fabricate|make up)\b.{0,25}\b(citation|source|policy)",
    r"\b(exfiltrate|jailbreak|bypass.{0,20}(rbac|authorization|guardrails))\b",
    r"(system|assistant)\s*:\s*(ignore|override|disclose)",
    r"<\s*/?\s*(system|instruction|script)\b",
]
PATTERNS = [re.compile(pattern, re.IGNORECASE | re.DOTALL) for pattern in INJECTION_PATTERNS]


def suspicious_instruction(value: str) -> bool:
    return any(pattern.search(value) for pattern in PATTERNS)


def redact_pii(value: str) -> str:
    """Illustrative redaction only; not production DLP. Applied before review persistence."""
    value = re.sub(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", "[EMAIL]", value, flags=re.I)
    value = re.sub(r"\b(?:SYN[-_]?ACC|ACC|ACCT|ACCOUNT)[-_ :]*[A-Z0-9]{4,}\b", "[ACCOUNT]", value, flags=re.I)
    value = re.sub(r"(?<!\w)(?:\+?\d[\d .()-]{7,}\d)(?!\w)", "[PHONE]", value)
    return value


def normalize_space(value: str) -> str:
    return " ".join(value.split())
