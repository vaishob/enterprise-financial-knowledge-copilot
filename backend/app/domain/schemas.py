from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.app.core.config import ROLES


class Section(BaseModel):
    section: str = Field(min_length=1)
    text: str = Field(min_length=1)
    page: int | None = None


class Document(BaseModel):
    document_id: str = Field(min_length=1, max_length=100, pattern=r"^[\w.-]+$")
    document_title: str
    document_version: str
    source: str
    classification: str
    allowed_roles: list[str] = Field(min_length=1)
    effective_date: date
    active: bool = True
    sections: list[Section] = Field(min_length=1)

    @field_validator("allowed_roles")
    @classmethod
    def valid_roles(cls, value):
        if not set(value).issubset(ROLES):
            raise ValueError("Unknown document role")
        return sorted(set(value))


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=3, max_length=2000)

    @field_validator("question")
    @classmethod
    def not_blank(cls, value):
        value = value.strip()
        if len(value) < 3:
            raise ValueError("Question must contain at least 3 non-whitespace characters")
        return value


class Claim(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=2000)
    quote: str = Field(min_length=1, max_length=2000)
    chunk_id: str


class GeneratedClaims(BaseModel):
    model_config = ConfigDict(extra="forbid")
    claims: list[Claim] = Field(default_factory=list, max_length=10)
    abstain: bool = False


class Citation(BaseModel):
    citation_id: int
    document_id: str
    document_title: str
    document_version: str
    section: str
    chunk_id: str
    excerpt: str
    source: str
    effective_date: str
    allowed_roles: list[str]


class TokenUsage(BaseModel):
    input_tokens: int
    output_tokens: int
    total_tokens: int
    estimated: bool = True
    estimated_cost_usd: float = 0


class ChatResponse(BaseModel):
    answer: str
    citations: list[Citation]
    retrieval_context: list[dict]
    trace_id: str
    latency_ms: float
    token_usage: TokenUsage
    timings: dict[str, float]
    guardrail_decisions: list[str]
    abstained: bool


class ReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    case_id: str = Field(min_length=1, max_length=120)
    label: Literal["pass", "fail", "uncertain"]
    notes: str = Field(default="", max_length=3000)
