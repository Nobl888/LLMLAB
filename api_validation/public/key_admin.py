"""Admin endpoints for API key management.

These endpoints must never be publicly accessible without strong authentication.
We use the same stealth smoke-key gate used for other diagnostic/admin routes.
"""

from fastapi import APIRouter, HTTPException, status, Security
from pydantic import BaseModel
from typing import Optional
import os
import psycopg
import secrets
import hashlib
from uuid import uuid4

from api_validation.public.routes.validate import require_smoke_key

router = APIRouter(prefix="/admin/keys", tags=["admin"], dependencies=[Security(require_smoke_key)], include_in_schema=False)


class CreateKeyRequest(BaseModel):
    tenant_id: str
    scopes: Optional[str] = ""


class CreateKeyResponse(BaseModel):
    key: str
    key_prefix: str
    tenant_id: str


class BootstrapTenantRequest(BaseModel):
    tenant_name: Optional[str] = ""
    scopes: Optional[str] = ""


class BootstrapTenantResponse(BaseModel):
    tenant_id: str
    api_key: str
    key_prefix: str


@router.post("/", response_model=CreateKeyResponse, status_code=status.HTTP_201_CREATED)
def create_api_key(req: CreateKeyRequest):
    """
    Create a new API key for a tenant.
    Returns the full key once (never stored in plaintext).
    """
    dsn = os.getenv("DATABASE_URL")
    if not dsn:
        raise HTTPException(status_code=500, detail="Database not configured")
    
    # Generate secure random key
    api_key = f"llm_{secrets.token_urlsafe(32)}"
    key_prefix = api_key[:12]  # Store prefix for identification
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    
    try:
        with psycopg.connect(dsn) as conn:
            with conn.cursor() as cur:
                # Insert key
                cur.execute(
                    """
                    INSERT INTO api_keys (id, tenant_id, key_prefix, key_hash, scopes, status)
                    VALUES (%s, %s, %s, %s, %s, 'active')
                    """,
                    (str(uuid4()), req.tenant_id, key_prefix, key_hash, req.scopes)
                )
            conn.commit()
        
        return CreateKeyResponse(
            key=api_key,
            key_prefix=key_prefix,
            tenant_id=req.tenant_id
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create key: {str(e)}")


@router.post("/bootstrap", response_model=BootstrapTenantResponse, status_code=status.HTTP_201_CREATED)
def bootstrap_tenant(req: BootstrapTenantRequest) -> BootstrapTenantResponse:
    """Create a new tenant + issue an API key (admin-only).

    This is intentionally:
    - smoke-key gated (stealth 404 without X-Smoke-Key)
    - hidden from OpenAPI (router include_in_schema=False)
    - minimal (no user system)

    Use this for initial client testing when you don't yet have a tenant_id.
    """
    dsn = os.getenv("DATABASE_URL")
    if not dsn:
        raise HTTPException(status_code=500, detail="Database not configured")

    tenant_id = str(uuid4())
    tenant_name = (req.tenant_name or "").strip() or f"bootstrap:{tenant_id[:8]}"

    api_key = f"llm_{secrets.token_urlsafe(32)}"
    key_prefix = api_key[:12]
    key_hash = hashlib.sha256(api_key.encode("utf-8")).hexdigest()

    try:
        with psycopg.connect(dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "insert into tenants (id, name, status) values (%s, %s, 'active')",
                    (tenant_id, tenant_name),
                )
                cur.execute(
                    """
                    INSERT INTO api_keys (id, tenant_id, key_prefix, key_hash, scopes, status)
                    VALUES (%s, %s, %s, %s, %s, 'active')
                    """,
                    (str(uuid4()), tenant_id, key_prefix, key_hash, (req.scopes or "")),
                )
            conn.commit()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to bootstrap tenant: {str(e)}")

    return BootstrapTenantResponse(tenant_id=tenant_id, api_key=api_key, key_prefix=key_prefix)
