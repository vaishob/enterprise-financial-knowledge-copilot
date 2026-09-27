import hashlib
import json
import re
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select

from backend.app.authorization.auth import Identity, identity, require_admin
from backend.app.core.database import AuditRecord, Review
from backend.app.domain.schemas import ChatRequest, ChatResponse, ReviewRequest
from backend.app.guardrails.security import redact_pii

router = APIRouter(prefix="/api/v1")


def _run_directory(request: Request, run_id: str) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,149}", run_id):
        raise HTTPException(404, "Evaluation run not found")
    root = request.app.state.settings.reports_path.resolve()
    path = (root / run_id).resolve()
    if path.parent != root or not path.is_dir():
        raise HTTPException(404, "Evaluation run not found")
    return path


def _json_file(path: Path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else default


@router.post("/chat", response_model=ChatResponse)
def chat(body: ChatRequest, request: Request, principal: Identity = Depends(identity)):
    return request.app.state.service.ask(body.question, principal.role, principal.user_id)


@router.post("/ingest")
def ingest(request: Request, principal: Identity = Depends(require_admin)):
    return request.app.state.service.ingest()


@router.get("/documents")
def documents(request: Request, principal: Identity = Depends(identity)):
    return {"documents": request.app.state.service.documents(principal.role)}


@router.get("/evaluations")
def evaluations(request: Request, principal: Identity = Depends(require_admin)):
    root = request.app.state.settings.reports_path
    runs = []
    if root.is_dir():
        for path in root.iterdir():
            if path.is_dir() and (path / "run_metadata.json").exists():
                runs.append({"run_id": path.name, "metadata": _json_file(path / "run_metadata.json", {}),
                             "summary": _json_file(path / "summary.json", {})})
    runs.sort(key=lambda row: str(row["metadata"].get("timestamp", row["run_id"])), reverse=True)
    return {"runs": runs}


def _reviews(service, run_id):
    with service.db.session() as session:
        rows = session.scalars(select(Review).where(Review.run_id == run_id).order_by(Review.timestamp.desc())).all()
    return [{key: getattr(row, key) for key in ("id", "run_id", "case_id", "label", "notes", "timestamp")}
            for row in rows]


@router.get("/evaluations/{run_id}")
def evaluation(run_id: str, request: Request, principal: Identity = Depends(require_admin)):
    path = _run_directory(request, run_id)
    return {"run_id": run_id, "metadata": _json_file(path / "run_metadata.json", {}),
            "summary": _json_file(path / "summary.json", {}),
            "results": _json_file(path / "results.json", []),
            "reviews": _reviews(request.app.state.service, run_id)}


@router.post("/evaluations/{run_id}/reviews")
def review(run_id: str, body: ReviewRequest, request: Request, principal: Identity = Depends(require_admin)):
    path = _run_directory(request, run_id)
    results = _json_file(path / "results.json", [])
    if isinstance(results, dict):
        results = results.get("results", [])
    valid_ids = {row.get("id", row.get("case_id")) for row in results}
    if body.case_id not in valid_ids:
        raise HTTPException(404, "Evaluation case not found")
    record = Review(id=str(uuid.uuid4()), run_id=run_id, case_id=body.case_id, label=body.label,
                    notes=redact_pii(body.notes), reviewer_hash=hashlib.sha256(principal.user_id.encode()).hexdigest())
    with request.app.state.service.db.session.begin() as session:
        session.add(record)
    return {"review": {key: getattr(record, key) for key in ("id", "run_id", "case_id", "label", "notes", "timestamp")}}


@router.get("/traces/{trace_id}")
def trace_detail(trace_id: str, request: Request, principal: Identity = Depends(identity)):
    with request.app.state.service.db.session() as session:
        record = session.get(AuditRecord, trace_id)
        user_hash = hashlib.sha256(principal.user_id.encode()).hexdigest()
        if record is None or (principal.role != "admin" and (
                record.role != principal.role or record.user_id_hash != user_hash)):
            # Existence is not revealed to another principal.
            raise HTTPException(404, "Trace not found")
        return record.payload
