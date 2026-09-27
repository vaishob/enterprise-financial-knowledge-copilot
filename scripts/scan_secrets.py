"""Focused source scan, not a replacement for a maintained secret scanner."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = [re.compile(r"sk-[A-Za-z0-9]{32,}"), re.compile(r"AKIA[0-9A-Z]{16}"),
            re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")]
EXCLUDED = {"node_modules", ".next", ".git", ".venv", "__pycache__", "data", ".mypy_cache", "dist", "build"}
def main():
    failures = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or set(path.relative_to(ROOT).parts) & EXCLUDED:
            continue
        if path.name == "scan_secrets.py" or path.suffix not in {".py", ".json", ".md", ".yml", ".yaml", ".ts", ".tsx", ".toml", ".example"}:
            continue
        value = path.read_text(encoding="utf-8", errors="replace")
        if any(pattern.search(value) for pattern in PATTERNS):
            failures.append(str(path.relative_to(ROOT)))
    print("Potential secrets in: " + ", ".join(failures) if failures else "No matched credential patterns in source files.")
    return 1 if failures else 0
if __name__ == "__main__":
    raise SystemExit(main())
