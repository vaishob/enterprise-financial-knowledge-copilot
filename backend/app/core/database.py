from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String, Text, create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from sqlalchemy.pool import StaticPool


class Base(DeclarativeBase):
    pass


class Chunk(Base):
    __tablename__ = "chunks"
    chunk_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    document_id: Mapped[str] = mapped_column(String(100), index=True)
    document_title: Mapped[str] = mapped_column(String(300))
    document_version: Mapped[str] = mapped_column(String(40))
    source: Mapped[str] = mapped_column(Text)
    section: Mapped[str] = mapped_column(String(300))
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    classification: Mapped[str] = mapped_column(String(60))
    allowed_roles: Mapped[list] = mapped_column(JSON)
    effective_date: Mapped[str] = mapped_column(String(10))
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    quarantined: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    text: Mapped[str] = mapped_column(Text)
    # PostgreSQL native vector; SQLite JSON fallback. IndexProfile prevents mixing vector models.
    embedding: Mapped[list] = mapped_column(Vector().with_variant(JSON, "sqlite"))


class ChunkRole(Base):
    __tablename__ = "chunk_roles"
    chunk_id: Mapped[str] = mapped_column(ForeignKey("chunks.chunk_id", ondelete="CASCADE"), primary_key=True)
    role: Mapped[str] = mapped_column(String(30), primary_key=True, index=True)


class IndexProfile(Base):
    __tablename__ = "index_profile"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    profile: Mapped[dict] = mapped_column(JSON)


class AuditRecord(Base):
    __tablename__ = "audit_records"
    trace_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    timestamp: Mapped[str] = mapped_column(String(40), default=lambda: datetime.now(UTC).isoformat())
    user_id_hash: Mapped[str] = mapped_column(String(64))
    role: Mapped[str] = mapped_column(String(30))
    payload: Mapped[dict] = mapped_column(JSON)


class Review(Base):
    __tablename__ = "reviews"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(150), index=True)
    case_id: Mapped[str] = mapped_column(String(120))
    reviewer_hash: Mapped[str] = mapped_column(String(64))
    label: Mapped[str] = mapped_column(String(15))
    notes: Mapped[str] = mapped_column(Text)
    timestamp: Mapped[str] = mapped_column(String(40), default=lambda: datetime.now(UTC).isoformat())


class Database:
    def __init__(self, url: str):
        if url.startswith("sqlite:///") and not url.endswith(":memory:"):
            Path(url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
        kwargs: dict[str, Any] = {}
        if url.startswith("sqlite"):
            kwargs["connect_args"] = {"check_same_thread": False}
            if url.endswith(":memory:"):
                kwargs["poolclass"] = StaticPool
        self.engine = create_engine(url, pool_pre_ping=True, **kwargs)
        self.is_postgres = self.engine.dialect.name == "postgresql"
        if not self.is_postgres:
            @event.listens_for(self.engine, "connect")
            def sqlite_fk(dbapi_connection, _connection_record):
                dbapi_connection.execute("PRAGMA foreign_keys=ON")
        if self.is_postgres:
            with self.engine.connect() as conn:
                if not conn.execute(text("SELECT 1 FROM pg_extension WHERE extname='vector'")).scalar():
                    raise RuntimeError("pgvector extension missing; apply scripts/postgres-init.sql")
        Base.metadata.create_all(self.engine)
        if self.is_postgres:
            with self.engine.begin() as conn:
                conn.execute(text("CREATE INDEX IF NOT EXISTS chunks_fts_idx ON chunks USING gin(to_tsvector('english', text))"))
        self.session = sessionmaker(self.engine, expire_on_commit=False)

    def ready(self) -> bool:
        with self.engine.connect() as conn:
            return conn.execute(text("SELECT 1")).scalar() == 1
