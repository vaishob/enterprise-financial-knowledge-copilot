import base64
import hashlib
import hmac
import json
import math
import time
from dataclasses import dataclass

from fastapi import HTTPException, Request

from backend.app.core.config import ROLES, Settings


@dataclass(frozen=True)
class Identity:
    user_id: str
    role: str


def _decode(segment: str) -> bytes:
    return base64.urlsafe_b64decode(segment + "=" * (-len(segment) % 4))


def verify_token(token: str, settings: Settings) -> Identity:
    """Small HS256 verifier for a trusted gateway-issued token, not an identity provider."""
    if not settings.auth_token_secret:
        raise ValueError("Bearer authentication is not configured")
    header_segment, payload_segment, signature_segment = token.split(".")
    header = json.loads(_decode(header_segment))
    if not isinstance(header, dict):
        raise ValueError("Invalid JWT header")
    if header.get("alg") != "HS256" or header.get("typ", "JWT") != "JWT":
        raise ValueError("Unsupported JWT")
    expected = hmac.new(settings.auth_token_secret.get_secret_value().encode(),
                        f"{header_segment}.{payload_segment}".encode(), hashlib.sha256).digest()
    if not hmac.compare_digest(expected, _decode(signature_segment)):
        raise ValueError("Invalid signature")
    payload = json.loads(_decode(payload_segment))
    if not isinstance(payload, dict):
        raise ValueError("Invalid JWT payload")
    expiry = payload.get("exp")
    if not isinstance(expiry, (int, float)) or isinstance(expiry, bool) or not math.isfinite(expiry) or expiry <= time.time():
        raise ValueError("Expired or missing expiration")
    not_before = payload.get("nbf", 0)
    if not isinstance(not_before, (int, float)) or isinstance(not_before, bool) or not math.isfinite(not_before) or not_before > time.time():
        raise ValueError("Token not valid yet")
    if payload.get("iss") != settings.auth_issuer or payload.get("aud") != settings.auth_audience:
        raise ValueError("Incorrect issuer or audience")
    if payload.get("role") not in ROLES or not isinstance(payload.get("sub"), str) or not payload["sub"]:
        raise ValueError("Invalid principal")
    return Identity(payload["sub"], payload["role"])


def identity(request: Request) -> Identity:
    settings = request.app.state.settings
    if settings.demo_auth_enabled and settings.app_env in {"demo", "development", "test"}:
        role = request.headers.get("X-Demo-Role", "analyst")
        if role not in ROLES:
            raise HTTPException(403, "Unknown demo role")
        # Deliberately fixed demo identity; a client cannot spoof another trace owner.
        return Identity("demo:" + role, role)
    authorization = request.headers.get("Authorization", "")
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "Bearer authentication required", headers={"WWW-Authenticate": "Bearer"})
    try:
        return verify_token(authorization.removeprefix("Bearer "), settings)
    except (ValueError, KeyError, TypeError, json.JSONDecodeError, OverflowError) as exc:
        raise HTTPException(401, "Invalid bearer token", headers={"WWW-Authenticate": "Bearer"}) from exc


def require_admin(request: Request) -> Identity:
    principal = identity(request)
    if principal.role != "admin":
        raise HTTPException(403, "Administrator role required")
    return principal
