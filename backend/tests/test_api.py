import base64
import hashlib
import hmac
import json
import time

import pytest
from fastapi.testclient import TestClient

from backend.app.authorization.auth import verify_token
from backend.app.main import create_app


def signed_token(secret: str, payload, header=None):
    def encode(value):
        return base64.urlsafe_b64encode(json.dumps(value).encode()).decode().rstrip("=")
    unsigned = encode(header or {"alg": "HS256", "typ": "JWT"}) + "." + encode(payload)
    signature = base64.urlsafe_b64encode(hmac.new(secret.encode(), unsigned.encode(), hashlib.sha256).digest()).decode().rstrip("=")
    return unsigned + "." + signature


@pytest.mark.integration
def test_chat_documents_health_and_validation(service, settings):
    with TestClient(create_app(settings, service)) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/ready").status_code == 200
        response = client.post("/api/v1/chat", json={"question": "What is the treasury Level-2 threshold?"},
                               headers={"X-Demo-Role": "treasury"})
        assert response.status_code == 200
        assert not response.json()["abstained"]
        assert response.headers["Cache-Control"] == "no-store"
        assert client.post("/api/v1/chat", json={"question": "ab"}).status_code == 422
        assert client.post("/api/v1/chat", json={"question": "   "}).status_code == 422
        assert client.post("/api/v1/chat", json={"question": "show policy", "role": "admin"}).status_code == 422
        assert client.get("/api/v1/documents", headers={"X-Demo-Role": "root"}).status_code == 403
        documents = client.get("/api/v1/documents").json()["documents"]
        assert all("analyst" in row["allowed_roles"] for row in documents)
        assert not any(row["document_id"] == "treasury-risk" for row in documents)


@pytest.mark.security
def test_admin_operations_and_trace_isolation(service, settings):
    with TestClient(create_app(settings, service)) as client:
        assert client.post("/api/v1/ingest").status_code == 403
        assert client.get("/api/v1/evaluations").status_code == 403
        assert client.post("/api/v1/ingest", headers={"X-Demo-Role": "admin"}).status_code == 200
        result = client.post("/api/v1/chat", json={"question": "What is the AML case register retention?"},
                             headers={"X-Demo-Role": "compliance"}).json()
        trace_path = "/api/v1/traces/" + result["trace_id"]
        assert client.get(trace_path).status_code == 404
        assert client.get(trace_path, headers={"X-Demo-Role": "compliance"}).status_code == 200
        trace = client.get(trace_path, headers={"X-Demo-Role": "admin"}).json()
        assert "query_hash" in trace and "question" not in trace and "answer" not in trace


@pytest.mark.integration
def test_evaluation_admin_review_redaction(service, settings):
    run = settings.reports_path / "test-run"
    run.mkdir(parents=True)
    (run / "run_metadata.json").write_text('{"timestamp":"2026-01-01","eval_mode":"deterministic"}')
    (run / "summary.json").write_text('{"case_count":1}')
    (run / "results.json").write_text('[{"id":"case-1","input":"test"}]')
    headers = {"X-Demo-Role": "admin"}
    with TestClient(create_app(settings, service)) as client:
        assert client.get("/api/v1/evaluations", headers=headers).json()["runs"][0]["run_id"] == "test-run"
        response = client.post("/api/v1/evaluations/test-run/reviews", headers=headers,
                               json={"case_id": "case-1", "label": "uncertain", "notes": "Contact test@example.invalid"})
        assert response.status_code == 200
        assert response.json()["review"]["notes"] == "Contact [EMAIL]"
        detail = client.get("/api/v1/evaluations/test-run", headers=headers).json()
        assert len(detail["reviews"]) == 1
        assert client.post("/api/v1/evaluations/test-run/reviews", headers=headers,
                           json={"case_id": "missing", "label": "pass"}).status_code == 404
        assert client.get("/api/v1/evaluations/%2E%2E%5Csecrets", headers=headers).status_code == 404


@pytest.mark.security
def test_production_ignores_demo_role_header(service, settings):
    production = settings.model_copy(update={"app_env": "production", "demo_auth_enabled": False,
                                             "auto_ingest": False})
    from pydantic import SecretStr
    production.auth_token_secret = SecretStr("synthetic-unit-test-signing-key-32-characters")
    payload = {"sub": "user-a", "role": "analyst", "iss": production.auth_issuer,
               "aud": production.auth_audience, "exp": time.time() + 300}
    token = signed_token(production.auth_token_secret.get_secret_value(), payload)
    with TestClient(create_app(production, service)) as client:
        assert client.get("/api/v1/documents", headers={"X-Demo-Role": "admin"}).status_code == 401
        headers = {"X-Demo-Role": "admin", "Authorization": "Bearer " + token}
        assert client.post("/api/v1/ingest", headers=headers).status_code == 403
        assert client.get("/api/v1/documents", headers=headers).status_code == 200
        assert client.get("/api/v1/documents", headers={"Authorization": "Bearer broken"}).status_code == 401


@pytest.mark.parametrize("mutation", [
    {"exp": float("nan")}, {"exp": float("inf")}, {"exp": True}, {"exp": 0},
    {"nbf": float("nan")}, {"nbf": "tomorrow"}, {"role": "root"}, {"aud": "other"}, {"iss": "other"},
])
def test_invalid_signed_claims_rejected(settings, mutation):
    from pydantic import SecretStr
    settings.auth_token_secret = SecretStr("synthetic-test-key")
    payload = {"sub": "test", "role": "analyst", "exp": time.time()+60,
               "iss": settings.auth_issuer, "aud": settings.auth_audience} | mutation
    with pytest.raises(ValueError):
        verify_token(signed_token("synthetic-test-key", payload), settings)


def test_jwt_payload_and_header_types(settings):
    from pydantic import SecretStr
    settings.auth_token_secret = SecretStr("synthetic-test-key")
    with pytest.raises(ValueError):
        verify_token(signed_token("synthetic-test-key", []), settings)
    with pytest.raises(ValueError):
        verify_token(signed_token("synthetic-test-key", {}, header=["invalid"]), settings)
