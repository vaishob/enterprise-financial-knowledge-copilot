import hashlib
import json
import math
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

from sqlalchemy import delete, func, select

from backend.app.core.config import ROLES, Settings
from backend.app.core.database import AuditRecord, Chunk, ChunkRole, Database, IndexProfile
from backend.app.domain.schemas import ChatRequest, Document
from backend.app.generation.grounding import ABSTENTION, build_context, sufficient_evidence, validate_claims
from backend.app.guardrails.security import suspicious_instruction
from backend.app.ingestion.chunking import chunk_text, token_count
from backend.app.observability.telemetry import (
    abstention_counter,
    emit_audit,
    exception_counter,
    latency_histogram,
    model_counter,
    request_counter,
    retrieval_counter,
    stage,
)
from backend.app.providers.embeddings import create_embedder
from backend.app.providers.generation import create_generator
from backend.app.retrieval.retriever import Retriever, authorized_statement, rewrite_query


class RagService:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or Settings()
        self.db = Database(self.settings.database_url)
        self.embedder = create_embedder(self.settings)
        self.generator = create_generator(self.settings)
        self.retriever = Retriever(self.db, self.settings)
        self._lock = threading.RLock()

    def index_profile(self):
        return {"embedding_provider": self.settings.embedding_provider, "embedding_model": self.settings.embedding_model,
                "embedding_dimensions": self.settings.embedding_dimensions,
                "chunk_strategy": self.settings.chunk_strategy, "chunk_size": self.settings.chunk_size,
                "chunk_overlap": self.settings.chunk_overlap}

    def index_compatible(self) -> bool:
        with self.db.session() as session:
            profile = session.get(IndexProfile, 1)
            return profile is not None and profile.profile == self.index_profile()

    def chunk_count(self) -> int:
        with self.db.session() as session:
            return session.scalar(select(func.count()).select_from(Chunk)) or 0

    def ingest(self, corpus_path: Path | str | None = None) -> dict:
        path = Path(corpus_path) if corpus_path else self.settings.corpus_path
        documents = [Document.model_validate(row) for row in json.loads(path.read_text(encoding="utf-8"))]
        ids = [document.document_id for document in documents]
        if len(set(ids)) != len(ids):
            raise ValueError("Corpus contains duplicate document IDs")
        prepared = []
        for document in documents:
            for section in document.sections:
                quarantine = suspicious_instruction(section.text)
                for index, content in enumerate(chunk_text(section.text, self.settings.chunk_strategy,
                                                           self.settings.chunk_size, self.settings.chunk_overlap)):
                    stable = f"{document.document_id}|{document.document_version}|{section.section}|{index}|{content}"
                    chunk_id = "chk-" + hashlib.sha256(stable.encode()).hexdigest()[:24]
                    prepared.append(Chunk(
                        chunk_id=chunk_id, document_id=document.document_id, document_title=document.document_title,
                        document_version=document.document_version, source=document.source, section=section.section,
                        page=section.page, classification=document.classification,
                        allowed_roles=document.allowed_roles, effective_date=document.effective_date.isoformat(),
                        active=document.active, quarantined=quarantine, text=content,
                        embedding=[0.0] * self.settings.embedding_dimensions,
                    ))
        clean = [chunk for chunk in prepared if not chunk.quarantined]
        for start in range(0, len(clean), self.settings.embedding_batch_size):
            batch = clean[start:start+self.settings.embedding_batch_size]
            texts = [f"{chunk.document_title}. {chunk.text}" for chunk in batch]
            vectors = self.embedder.embed(texts)
            if len(vectors) != len(batch):
                raise ValueError("Embedding provider returned an incorrect batch length")
            for chunk, vector in zip(batch, vectors, strict=True):
                if len(vector) != self.settings.embedding_dimensions or not all(math.isfinite(x) for x in vector):
                    raise ValueError("Embedding provider returned invalid vector dimensions/values")
                chunk.embedding = vector
        # All parsing and remote calls finish before this atomic replacement. Failure preserves old index.
        with self._lock, self.db.session.begin() as session:
            session.execute(delete(ChunkRole))
            session.execute(delete(Chunk))
            session.add_all(prepared)
            session.flush()
            session.add_all(ChunkRole(chunk_id=chunk.chunk_id, role=role)
                            for chunk in prepared for role in chunk.allowed_roles)
            session.merge(IndexProfile(id=1, profile=self.index_profile()))
        return {"documents": len(documents), "chunks": len(prepared),
                "quarantined_chunks": sum(chunk.quarantined for chunk in prepared),
                "inactive_chunks": sum(not chunk.active for chunk in prepared), "profile": self.index_profile()}

    def documents(self, role: str) -> list[dict]:
        with self.db.session() as session:
            chunks = session.scalars(authorized_statement(role)).all()
        result = {}
        for chunk in chunks:
            if chunk.document_id not in result:
                result[chunk.document_id] = {key: getattr(chunk, key) for key in (
                    "document_id", "document_title", "document_version", "classification",
                    "effective_date", "source", "allowed_roles")}
                result[chunk.document_id]["chunks"] = 0
            result[chunk.document_id]["chunks"] += 1
        return sorted(result.values(), key=lambda row: row["document_title"])

    def ask(self, question: str, role: str, user_id: str = "demo") -> dict:
        if role not in ROLES:
            raise PermissionError("Unknown role")
        question = ChatRequest(question=question).question
        started = perf_counter()
        trace_id = str(uuid.uuid4())
        timings = {name + "_ms": 0.0 for name in (
            "preprocessing", "retrieval", "reranking", "context", "generation", "citation_verification", "guardrails")}
        decisions: list[str] = []
        context: list[dict] = []
        candidates: list[dict] = []
        citations: list[dict] = []
        answer = ABSTENTION
        usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0,
                 "estimated": True, "estimated_cost_usd": 0.0}
        invocations, error_type = 0, None
        request_counter.add(1, {"role": role})
        with stage(timings, "request"):
            try:
                with stage(timings, "preprocessing"):
                    blocked = suspicious_instruction(question)
                    query = rewrite_query(question, self.settings.query_rewrite_enabled)
                if blocked:
                    decisions.append("input_instruction_blocked")
                else:
                    with self._lock:
                        if not self.index_compatible():
                            raise ValueError("Index configuration mismatch or missing index; ingest first")
                        with stage(timings, "retrieval"):
                            vectors = self.embedder.embed([query])
                            candidates = self.retriever.retrieve(query, vectors[0], role)
                            retrieval_counter.add(1, {"role": role})
                        with stage(timings, "reranking"):
                            ranked = self.retriever.rerank(question, candidates)
                        with stage(timings, "context"):
                            context = build_context(ranked, self.settings.max_context_tokens)
                    decisions.extend(["authorization_before_retrieval", "quarantined_content_excluded",
                                      "active_versions_only", "bounded_context"])
                    with stage(timings, "guardrails"):
                        enough = sufficient_evidence(question, context)
                    if not enough:
                        decisions.append("insufficient_evidence")
                    else:
                        with stage(timings, "generation"):
                            invocations += 1
                            model_counter.add(1, {"provider": self.settings.llm_provider})
                            generated = self.generator.generate(question, context)
                        usage = {"input_tokens": generated.input_tokens, "output_tokens": generated.output_tokens,
                                 "total_tokens": generated.input_tokens + generated.output_tokens,
                                 "estimated": generated.estimated,
                                 "estimated_cost_usd": round((generated.input_tokens * self.settings.input_cost_per_million +
                                                             generated.output_tokens * self.settings.output_cost_per_million) / 1_000_000, 8)}
                        with stage(timings, "citation_verification"):
                            answer, citations = validate_claims(generated.claims, context, role)
                        decisions.append("exact_quote_citations_verified" if citations else "generator_abstained")
            except Exception as exc:
                # Fail closed. The exception class is useful operationally without exposing provider payloads.
                error_type = type(exc).__name__
                exception_counter.add(1, {"type": error_type})
                decisions.append("pipeline_error_fail_closed:" + error_type)
                answer, citations = ABSTENTION, []
        abstained = not bool(citations)
        latency = round((perf_counter()-started)*1000, 3)
        if abstained:
            abstention_counter.add(1, {"role": role})
        latency_histogram.record(latency, {"provider": self.settings.llm_provider})
        response = {"answer": answer, "citations": citations, "retrieval_context": context, "trace_id": trace_id,
                    "latency_ms": latency, "token_usage": usage, "timings": timings,
                    "guardrail_decisions": decisions, "abstained": abstained}
        audit = {"trace_id": trace_id, "timestamp": datetime.now(UTC).isoformat(), "role": role,
                 "query_hash": hashlib.sha256(question.encode()).hexdigest(),
                 "retrieved_document_ids": sorted({row["document_id"] for row in context}),
                 "retrieved_chunk_ids": [row["chunk_id"] for row in context],
                 "candidate_count": len(candidates), "context_tokens": sum(token_count(row["text"]) for row in context),
                 "model_provider": self.settings.llm_provider, "model_name": self.settings.llm_model,
                 "prompt_version": self.settings.prompt_version, "token_usage": usage,
                 "latency_ms": latency, "timings": timings, "guardrail_decisions": decisions,
                 "abstained": abstained, "model_invocation_count": invocations, "error_type": error_type,
                 "evaluation_metadata": {"mode": "runtime", "profile": self.index_profile()}}
        # Audit durability is mandatory: if storage fails, the API returns 503 rather than an unaudited answer.
        with self.db.session.begin() as session:
            session.add(AuditRecord(trace_id=trace_id, user_id_hash=hashlib.sha256(user_id.encode()).hexdigest(),
                                    role=role, payload=audit))
        emit_audit(audit)
        return response
