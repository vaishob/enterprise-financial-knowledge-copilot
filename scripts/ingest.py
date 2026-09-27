"""Ingest the configured approved synthetic corpus."""
import json

from backend.app.service import RagService

if __name__ == "__main__":
    print(json.dumps(RagService().ingest(), indent=2))
