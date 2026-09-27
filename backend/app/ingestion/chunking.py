import re

TOKEN = re.compile(r"\w+|[^\w\s]")


def token_count(text: str) -> int:
    """Deterministic tokenizer for local budgets; provider token counts can differ."""
    return len(TOKEN.findall(text))


def fixed_chunks(text: str, size: int, overlap: int) -> list[str]:
    if size <= overlap or overlap < 0:
        raise ValueError("Invalid chunk parameters")
    spans = list(TOKEN.finditer(text))
    result = []
    for start in range(0, len(spans), size - overlap):
        stop = min(start + size, len(spans))
        result.append(text[spans[start].start():spans[stop - 1].end()].strip())
        if stop == len(spans):
            break
    return result


def recursive_chunks(text: str, size: int, overlap: int) -> list[str]:
    """Respect paragraph/sentence boundaries, splitting oversized units with token offsets."""
    units = [s.strip() for s in re.split(r"\n\s*\n|(?<=[.!?])\s+(?=[A-Z])", text) if s.strip()]
    pieces: list[str] = []
    for unit in units:
        pieces.extend(fixed_chunks(unit, size, overlap) if token_count(unit) > size else [unit])
    result: list[str] = []
    current: list[str] = []
    for piece in pieces:
        if current and token_count(" ".join([*current, piece])) > size:
            result.append(" ".join(current))
            tail: list[str] = []
            for prior in reversed(current):
                if token_count(" ".join([prior, *tail])) > overlap:
                    break
                tail.insert(0, prior)
            current = tail
            if token_count(" ".join([*current, piece])) > size:
                current = []
        current.append(piece)
    if current:
        result.append(" ".join(current))
    return result


def chunk_text(text: str, strategy: str, size: int, overlap: int) -> list[str]:
    text = text.replace("\r\n", "\n").replace("\x00", "")
    if strategy == "fixed":
        return fixed_chunks(text, size, overlap)
    if strategy == "recursive":
        return recursive_chunks(text, size, overlap)
    raise ValueError(f"Unsupported chunk strategy: {strategy}")
