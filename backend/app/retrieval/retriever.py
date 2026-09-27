import math
from dataclasses import dataclass

from sqlalchemy import exists, func, select

from backend.app.core.config import ROLES, Settings
from backend.app.core.database import Chunk, ChunkRole, Database
from backend.app.retrieval.text import idf_weights, keyword_coverage, terms


def authorized_statement(role: str):
    if role not in ROLES:
        raise PermissionError("Unknown role")
    statement = select(Chunk).where(Chunk.active.is_(True), Chunk.quarantined.is_(False))
    if role != "admin":
        statement = statement.where(exists().where(ChunkRole.chunk_id == Chunk.chunk_id, ChunkRole.role == role))
    return statement


def chunk_dict(chunk: Chunk) -> dict:
    names = ("chunk_id", "document_id", "document_title", "document_version", "source", "section", "page",
             "classification", "allowed_roles", "effective_date", "text")
    return {name: getattr(chunk, name) for name in names}


def cosine(left: list, right: list) -> float:
    if len(left) != len(right):
        raise ValueError("Embedding dimension mismatch; re-ingest with the configured embedding profile")
    denominator = math.sqrt(sum(x*x for x in left) * sum(y*y for y in right))
    return sum(x*y for x, y in zip(left, right, strict=True)) / denominator if denominator else 0.0


@dataclass
class RetrievalResult:
    candidates: list[dict]
    context: list[dict]


class Retriever:
    def __init__(self, db: Database, settings: Settings):
        self.db, self.settings = db, settings

    def retrieve(self, query: str, vector: list[float], role: str) -> list[dict]:
        statement = authorized_statement(role)
        with self.db.session() as session:
            if self.db.is_postgres:
                # WHERE contains permission EXISTS before candidates can leave the database.
                # Materialize ACL scope before computing rank; authorized rows alone enter ranking.
                scope = statement.cte("authorized_chunks").prefix_with("MATERIALIZED")
                similarity = 1 - scope.c.embedding.cosine_distance(vector)
                lexical = func.ts_rank_cd(func.to_tsvector("english", scope.c.text),
                                          func.plainto_tsquery("english", query))
                combined = self.settings.hybrid_weight * similarity + (1-self.settings.hybrid_weight) * lexical
                query_stmt = select(scope, similarity.label("vector_score"), lexical.label("fts_score")).order_by(
                    combined.desc(), scope.c.chunk_id).limit(self.settings.retrieval_top_k * 4)
                rows = session.execute(query_stmt).mappings().all()
                candidates = []
                for pgrow in rows:
                    candidate = {name: pgrow[name] for name in ("chunk_id", "document_id", "document_title",
                                 "document_version", "source", "section", "page", "classification",
                                 "allowed_roles", "effective_date", "text")}
                    candidate["vector_score"] = max(0.0, float(pgrow["vector_score"]))
                    candidate["fts_score"] = float(pgrow["fts_score"])
                    candidates.append(candidate)
            else:
                # Query filters permissions; unauthorized vectors/text are never loaded or scored.
                chunks = session.scalars(statement).all()
                candidates = []
                for chunk in chunks:
                    candidate = chunk_dict(chunk)
                    candidate["vector_score"] = max(0.0, cosine(vector, chunk.embedding))
                    candidates.append(candidate)
        weights = idf_weights([f"{row['document_title']} {row['text']}" for row in candidates])
        for row in candidates:
            row["keyword_score"] = keyword_coverage(query, f"{row['document_title']} {row['text']}", weights)
            row["score"] = (self.settings.hybrid_weight * row["vector_score"] +
                            (1-self.settings.hybrid_weight) * row["keyword_score"])
        candidates.sort(key=lambda row: (-row["score"], row["chunk_id"]))
        return [row for row in candidates[:self.settings.retrieval_top_k]
                if row["score"] >= self.settings.min_retrieval_score]

    def rerank(self, question: str, candidates: list[dict]) -> list[dict]:
        for row in candidates:
            # Deterministic token coverage reranker; no claim to a cross-encoder's semantic quality.
            row["reranker_score"] = (0.65 * keyword_coverage(question, row["text"]) +
                                      0.25 * row["score"] +
                                      0.10 * keyword_coverage(question, row["document_title"]))
        if self.settings.enable_reranking:
            candidates = sorted(candidates, key=lambda row: (-row["reranker_score"], row["chunk_id"]))
        return candidates[:self.settings.rerank_top_k]


def rewrite_query(question: str, enabled: bool) -> str:
    return " ".join(terms(question)) if enabled else question
