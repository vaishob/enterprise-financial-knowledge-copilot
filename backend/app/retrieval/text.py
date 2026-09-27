import re
from collections import Counter

STOPWORDS = set("""a an the is are was were be been being to of for and or in on at as by with from that this these those it its
what which who when where why how do does did can could should would must will may any all me my our your you i tell
please about under according policy policies procedure procedures standard standards guide section document documents
process requirements requirement required apply applicable current explain describe give provide find information
than then also before after into through within per each such both whether have has had
""".split())

ALIASES = {"mfa": "multi factor authentication", "kyc": "know your customer", "aml": "anti money laundering",
           "llm": "language model", "cap": "limit", "caps": "limits", "retention": "retained",
           "escalation": "escalate", "escalated": "escalate", "reporting": "report",
           "approval": "approve", "approved": "approve", "approves": "approve",
           "exceeds": "exceed", "exceeded": "exceed", "reviewed": "review", "reviews": "review", "exceeding": "exceed"}


def terms(text: str, expand: bool = True) -> list[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    result = []
    for word in words:
        if word in STOPWORDS:
            continue
        words_to_add = ALIASES.get(word, word).split() if expand else [word]
        for term in words_to_add:
            if len(term) > 4 and term.endswith("s") and not term.endswith(("ss", "us")):
                term = term[:-1]
            if term not in STOPWORDS:
                result.append(term)
    return result


def keyword_coverage(query: str, content: str, weights: dict[str, float] | None = None) -> float:
    wanted = set(terms(query))
    found = set(terms(content))
    if not wanted:
        return 0.0
    weights = weights or {}
    return sum(weights.get(t, 1.0) for t in wanted & found) / sum(weights.get(t, 1.0) for t in wanted)


def idf_weights(texts: list[str]) -> dict[str, float]:
    import math
    frequencies = Counter(term for text in texts for term in set(terms(text)))
    return {term: math.log(1 + len(texts) / (1 + count)) + 1 for term, count in frequencies.items()}
