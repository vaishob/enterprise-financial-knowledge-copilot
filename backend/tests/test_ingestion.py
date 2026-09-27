import json

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from backend.app.core.config import Settings
from backend.app.core.database import Chunk
from backend.app.ingestion.chunking import chunk_text, token_count


@pytest.mark.parametrize("strategy", ["fixed", "recursive"])
def test_chunk_boundaries_overlap_and_metadata(strategy, settings):
    from backend.app.service import RagService
    instance = RagService(settings.model_copy(update={"chunk_strategy": strategy, "chunk_size": 40, "chunk_overlap": 8}))
    result = instance.ingest()
    assert result["documents"] == 16
    assert result["chunks"] > 55
    with instance.db.session() as session:
        chunks = session.scalars(select(Chunk)).all()
    assert all(token_count(chunk.text) <= 40 for chunk in chunks)
    assert all(len(chunk.embedding) == settings.embedding_dimensions for chunk in chunks)
    assert all(chunk.document_id and chunk.allowed_roles and chunk.source and chunk.section for chunk in chunks)
    assert len({chunk.chunk_id for chunk in chunks}) == len(chunks)


def test_fixed_overlap_preserves_tokens():
    pieces = chunk_text("zero one two three four five six seven eight nine", "fixed", 6, 2)
    assert pieces == ["zero one two three four five", "four five six seven eight nine"]


def test_reingest_idempotent_and_invalid_corpus_atomic(service, tmp_path):
    original = service.chunk_count()
    assert service.ingest()["chunks"] == original
    bad = tmp_path / "bad.json"
    bad.write_text('[{"document_id":"broken"}]', encoding="utf-8")
    with pytest.raises(ValidationError):
        service.ingest(bad)
    assert service.chunk_count() == original


def test_invalid_embedding_batch_cannot_replace_index(service, monkeypatch):
    before = service.chunk_count()
    monkeypatch.setattr(service.embedder, "embed", lambda texts: [[1.0] for _ in texts])
    with pytest.raises(ValueError, match="dimensions"):
        service.ingest()
    assert service.chunk_count() == before


def test_duplicate_document_ids_rejected(service, tmp_path):
    corpus = json.loads(service.settings.corpus_path.read_text(encoding="utf-8"))
    corpus.append(corpus[0])
    bad = tmp_path / "duplicate.json"
    bad.write_text(json.dumps(corpus), encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate"):
        service.ingest(bad)


def test_configuration_validation():
    with pytest.raises(ValidationError):
        Settings(chunk_size=40, chunk_overlap=40)
    with pytest.raises(ValidationError):
        Settings(app_env="production")
    with pytest.raises(ValidationError):
        Settings(retrieval_top_k=3, rerank_top_k=5)
    with pytest.raises(ValidationError):
        Settings(llm_provider="openai", llm_api_key=None)
