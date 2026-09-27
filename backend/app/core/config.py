from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[3]
ROLES = frozenset({"analyst", "treasury", "risk_manager", "compliance", "admin"})


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(ROOT / ".env"), extra="ignore", case_sensitive=False)

    app_env: Literal["demo", "development", "test", "production"] = "demo"
    database_url: str = f"sqlite:///{(ROOT / 'data' / 'copilot.db').as_posix()}"
    corpus_path: Path = ROOT / "synthetic_data" / "corpus.json"
    reports_path: Path = ROOT / "evals" / "reports"
    demo_auth_enabled: bool = True
    auth_token_secret: SecretStr | None = None
    auth_issuer: str = "financial-copilot"
    auth_audience: str = "financial-copilot-api"
    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
    auto_ingest: bool = True
    llm_provider: Literal["local", "openai", "bedrock", "ollama"] = "local"
    llm_model: str = "extractive-v1"
    llm_api_key: SecretStr | None = None
    llm_base_url: str = "https://api.openai.com/v1"
    ollama_base_url: str = "http://localhost:11434"
    aws_region: str = "us-east-1"
    aws_profile: str | None = None
    bedrock_model_id: str = ""
    provider_timeout_seconds: float = Field(default=30, gt=0, le=120)
    temperature: float = Field(default=0, ge=0, le=2)
    max_completion_tokens: int = Field(default=700, ge=64, le=8000)
    input_cost_per_million: float = Field(default=0, ge=0)
    output_cost_per_million: float = Field(default=0, ge=0)
    embedding_provider: Literal["hash", "openai", "sentence_transformer"] = "hash"
    embedding_model: str = "hash-bow-v1"
    embedding_api_key: SecretStr | None = None
    embedding_base_url: str = "https://api.openai.com/v1"
    embedding_dimensions: int = Field(default=384, ge=32, le=4096)
    embedding_batch_size: int = Field(default=32, ge=1, le=256)
    chunk_strategy: Literal["fixed", "recursive"] = "recursive"
    chunk_size: int = Field(default=180, ge=16, le=4000)
    chunk_overlap: int = Field(default=30, ge=0)
    retrieval_top_k: int = Field(default=8, ge=1, le=100)
    rerank_top_k: int = Field(default=5, ge=1, le=100)
    min_retrieval_score: float = Field(default=0.16, ge=0, le=1)
    hybrid_weight: float = Field(default=0.45, ge=0, le=1)
    enable_reranking: bool = True
    query_rewrite_enabled: bool = True
    max_context_tokens: int = Field(default=1800, ge=64, le=16000)
    prompt_version: str = "financial-grounding-v1.0"
    telemetry_enabled: bool = False
    otel_endpoint: str = "http://localhost:4318/v1/traces"

    @model_validator(mode="after")
    def validate_dependencies(self):
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("CHUNK_OVERLAP must be smaller than CHUNK_SIZE")
        if self.rerank_top_k > self.retrieval_top_k:
            raise ValueError("RERANK_TOP_K cannot exceed RETRIEVAL_TOP_K")
        if self.app_env == "production":
            if self.demo_auth_enabled:
                raise ValueError("DEMO_AUTH_ENABLED must be false in production")
            if not self.auth_token_secret or len(self.auth_token_secret.get_secret_value()) < 32:
                raise ValueError("Production requires an AUTH_TOKEN_SECRET of at least 32 characters")
            if self.auto_ingest:
                raise ValueError("AUTO_INGEST must be false in production; ingest explicitly as admin")
        if self.llm_provider == "openai" and not self.llm_api_key:
            raise ValueError("OpenAI generation requires LLM_API_KEY")
        if self.embedding_provider == "openai" and not (self.embedding_api_key or self.llm_api_key):
            raise ValueError("OpenAI embeddings require EMBEDDING_API_KEY or LLM_API_KEY")
        if self.llm_provider == "bedrock" and not self.bedrock_model_id:
            raise ValueError("Bedrock requires BEDROCK_MODEL_ID")
        return self

    def public_metadata(self) -> dict:
        keys = ("llm_provider", "llm_model", "embedding_provider", "embedding_model", "embedding_dimensions",
                "chunk_strategy", "chunk_size", "chunk_overlap", "retrieval_top_k", "rerank_top_k",
                "min_retrieval_score", "hybrid_weight", "enable_reranking", "max_context_tokens", "prompt_version")
        return {key: getattr(self, key) for key in keys}
