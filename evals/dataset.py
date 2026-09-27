"""Golden data loading with a frozen manifest: drift requires explicit versioning."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATASET_DIR = ROOT / "evals" / "datasets"


def load_cases(split: str = "all") -> list[dict]:
    if split not in {"all", "development", "regression"}:
        raise ValueError("Unknown dataset split")
    names = ["development", "regression"] if split == "all" else [split]
    cases = []
    manifest = json.loads((DATASET_DIR / "manifest.json").read_text(encoding="utf-8"))
    for name in names:
        raw = (DATASET_DIR / f"{name}.json").read_bytes()
        if hashlib.sha256(raw).hexdigest() != manifest["files"][f"{name}.json"]["sha256"]:
            raise ValueError(f"Frozen {name} dataset changed; review and version the manifest")
        cases.extend(json.loads(raw))
    if len({c["id"] for c in cases}) != len(cases):
        raise ValueError("Duplicate golden case IDs")
    return cases


def dataset_fingerprint(cases: list[dict]) -> str:
    return hashlib.sha256(json.dumps(cases, sort_keys=True).encode()).hexdigest()
