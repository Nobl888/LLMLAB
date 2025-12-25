"""Self-serve signup: create a tenant + issue an API key.

Goal: enable "zero-touch" onboarding so devs can get:
- tenant_id
- api_key (plaintext, returned once)

Security posture:
- Disabled by default (ENABLE_SELF_SERVE_SIGNUP=false)
- Requires CAPTCHA verification (Cloudflare Turnstile)
- DB-backed rate limiting (per-IP and global, rolling window)
- Avoids storing raw emails or IPs (stores salted hashes only)

This endpoint is intentionally minimal. It is not a full user system.
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import uuid4
from urllib import request as urlrequest
from urllib import parse as urlparse

import psycopg
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

router = APIRouter(tags=["signup"])


class SignupRequest(BaseModel):
    email: str = Field(..., description="Email used for abuse prevention (not stored in plaintext)")
    turnstile_token: str = Field(..., description="Cloudflare Turnstile token")
    scopes: Optional[str] = Field("", description="Optional scopes for the issued key")


class SignupResponse(BaseModel):
    tenant_id: str
    api_key: str
    key_prefix: str


def _require_env(name: str) -> str:
    v = os.getenv(name)
    if not v:
        raise RuntimeError(f"Missing required env var: {name}")
    return v


def _sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _salted_hash(*, salt: str, value: str) -> str:
    return _sha256_hex(salt + "|" + value)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _turnstile_verify(*, token: str, remoteip: Optional[str]) -> bool:
    secret = _require_env("TURNSTILE_SECRET_KEY")

    payload = {
        "secret": secret,
        "response": token,
    }
    if remoteip:
        payload["remoteip"] = remoteip

    data = urlparse.urlencode(payload).encode("utf-8")
    req = urlrequest.Request(
        url="https://challenges.cloudflare.com/turnstile/v0/siteverify",
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )

    try:
        with urlrequest.urlopen(req, timeout=10) as resp:
            raw = resp.read().decode("utf-8")
    except Exception:
        return False

    try:
        obj = json.loads(raw)
    except Exception:
        return False

    return bool(obj.get("success"))


def _get_client_ip(request: Request) -> Optional[str]:
    # Render sets X-Forwarded-For. Use the first IP if present.
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip() or None
    return request.client.host if request.client else None


def _enforce_signup_rate_limits(*, conn: psycopg.Connection, ip_hash: str) -> None:
    window_minutes = int(os.getenv("SIGNUP_WINDOW_MINUTES", "1440"))
    per_ip_limit = int(os.getenv("SIGNUP_LIMIT_PER_IP", "5"))
    global_limit = int(os.getenv("SIGNUP_LIMIT_GLOBAL", "200"))

    since = _now_utc() - timedelta(minutes=window_minutes)

    with conn.cursor() as cur:
        cur.execute("select count(1) from signup_events where created_at >= %s", (since,))
        total = int(cur.fetchone()[0])
        if total >= global_limit:
            raise HTTPException(
                status_code=429,
                detail={"code": "SIGNUP_RATE_LIMIT", "message": "Signup temporarily rate-limited. Try again later."},
            )

        cur.execute(
            "select count(1) from signup_events where ip_hash = %s and created_at >= %s",
            (ip_hash, since),
        )
        per_ip = int(cur.fetchone()[0])
        if per_ip >= per_ip_limit:
            raise HTTPException(
                status_code=429,
                detail={"code": "SIGNUP_RATE_LIMIT", "message": "Signup temporarily rate-limited for this network. Try again later."},
            )


@router.post("/api/signup", response_model=SignupResponse)
def signup(body: SignupRequest, request: Request) -> SignupResponse:
    if os.getenv("ENABLE_SELF_SERVE_SIGNUP", "false").lower() != "true":
        raise HTTPException(status_code=404, detail="Not found")

    dsn = os.getenv("DATABASE_URL")
    if not dsn:
        raise HTTPException(status_code=503, detail={"code": "DB_NOT_CONFIGURED", "message": "DATABASE_URL not set"})

    if not body.email or "@" not in body.email or len(body.email) > 254:
        raise HTTPException(status_code=400, detail={"code": "INVALID_EMAIL", "message": "Invalid email"})

    client_ip = _get_client_ip(request)
    ok = _turnstile_verify(token=body.turnstile_token, remoteip=client_ip)
    if not ok:
        raise HTTPException(status_code=400, detail={"code": "CAPTCHA_FAILED", "message": "CAPTCHA verification failed"})

    ip_salt = os.getenv("SIGNUP_IP_SALT")
    email_salt = os.getenv("SIGNUP_EMAIL_SALT")
    if not ip_salt or not email_salt:
        raise HTTPException(status_code=503, detail={"code": "SIGNUP_NOT_CONFIGURED", "message": "Signup not configured"})

    ip_hash = _salted_hash(salt=ip_salt, value=(client_ip or "unknown"))
    email_hash = _salted_hash(salt=email_salt, value=body.email.strip().lower())

    tenant_id = str(uuid4())
    api_key = f"llm_{secrets.token_urlsafe(32)}"
    key_prefix = api_key[:12]
    key_hash = hashlib.sha256(api_key.encode("utf-8")).hexdigest()

    tenant_name = f"selfserve:{email_hash[:12]}"

    with psycopg.connect(dsn) as conn:
        _enforce_signup_rate_limits(conn=conn, ip_hash=ip_hash)

        with conn.cursor() as cur:
            cur.execute(
                "insert into tenants (id, name, status) values (%s, %s, 'active')",
                (tenant_id, tenant_name),
            )

            cur.execute(
                """
                insert into api_keys (id, tenant_id, key_prefix, key_hash, scopes, status)
                values (%s, %s, %s, %s, %s, 'active')
                """,
                (str(uuid4()), tenant_id, key_prefix, key_hash, (body.scopes or "")),
            )

            cur.execute(
                """
                insert into signup_events (id, created_at, ip_hash, email_hash)
                values (%s, %s, %s, %s)
                """,
                (str(uuid4()), _now_utc(), ip_hash, email_hash),
            )

        conn.commit()

    return SignupResponse(tenant_id=tenant_id, api_key=api_key, key_prefix=key_prefix)
