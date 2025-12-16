"""
API Key management endpoints (admin).

Operations:
- Create a new API key
- List API keys (redacted)
- Rotate a key (issue new, mark old for revocation)
- Revoke a key (immediate deactivation)
- Check key validity (health check)

Authentication:
- All endpoints require a valid admin API key (Authorization: Bearer ...)
- Admin keys have elevated scope ("admin") vs. regular keys ("api")
"""

from fastapi import APIRouter, HTTPException, status, Request, Depends
from datetime import datetime, timedelta
import uuid
import secrets
import json
import logging
from pydantic import BaseModel
from typing import Optional, List

router = APIRouter()
audit_logger = logging.getLogger("audit")


# Models
class CreateKeyRequest(BaseModel):
    """Request to create a new API key."""
    partner_name: str  # e.g., "Acme Corp"
    partner_id: Optional[str] = None  # Optional: unique identifier for partner
    tenant_id: Optional[str] = None  # Optional: sub-tenant within partner
    description: Optional[str] = None
    expires_in_days: Optional[int] = 365  # Default: 1 year


class CreateKeyResponse(BaseModel):
    """Response when key is created (returned only once)."""
    key_id: str  # Public ID (e.g., "key_abc123")
    secret: str  # Secret part (returned only once, never again)
    full_key: str  # Combined: "key_abc123:secret_xyz" (for Bearer token)
    created_at: str
    expires_at: str
    message: str  # "Store this securely; you'll never see the secret again"


class RotateKeyRequest(BaseModel):
    """Request to rotate (renew) an API key."""
    key_id: str
    grace_period_days: Optional[int] = 7  # Both old and new keys work for N days


class RotateKeyResponse(BaseModel):
    """Response when key is rotated."""
    old_key_id: str
    new_key_id: str
    new_secret: str
    new_full_key: str
    grace_period_until: str
    message: str


class RevokeKeyRequest(BaseModel):
    """Request to revoke (deactivate) an API key."""
    key_id: str
    reason: Optional[str] = None  # "compromised", "unused", etc.


class RevokeKeyResponse(BaseModel):
    """Response when key is revoked."""
    key_id: str
    revoked_at: str
    status: str  # "revoked"


class ListKeyResponse(BaseModel):
    """Summary of a key (never includes secret)."""
    key_id: str
    partner_id: Optional[str]
    tenant_id: Optional[str]
    description: Optional[str]
    status: str  # "active", "rotated", "revoked"
    created_at: str
    expires_at: str
    last_used_at: Optional[str]
    rotation_status: Optional[str]  # "active", "grace_period", "expired"


# Private: Key storage (in production, this would be a database)
# Format: {key_id: {secret_hash, partner_id, tenant_id, created_at, expires_at, status, ...}}
API_KEYS_DB = {}


def _validate_admin_key(request: Request) -> str:
    """
    Validate that the request has a valid admin API key.
    Returns the admin_key_id if valid; raises 401 otherwise.
    """
    auth_header = request.headers.get("Authorization", "")
    
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header (expected: Bearer <token>)"
        )
    
    key_material = auth_header[7:]  # Strip "Bearer "
    
    # TODO: Validate against hashed keys in database
    # For now, just log the attempt
    key_id = _extract_key_id_from_material(key_material)
    
    # TODO: Check if key has "admin" scope and is not expired
    # Placeholder validation (in production, check against DB)
    if not key_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key"
        )
    
    return key_id


def _extract_key_id_from_material(key_material: str) -> Optional[str]:
    """Extract key_id from key material (e.g., 'key_abc123:secret_xyz' -> 'key_abc123')."""
    try:
        key_id = key_material.split(":")[0]
        if key_id.startswith("key_"):
            return key_id
    except Exception:
        pass
    return None


def _generate_key_material() -> tuple[str, str]:
    """
    Generate new key material.
    Returns (key_id, secret).
    
    key_id: Public identifier (key_<12 random chars>)
    secret: Secret part (<48 random chars>, never logged)
    """
    key_id = f"key_{secrets.token_urlsafe(9)}"
    secret = secrets.token_urlsafe(36)
    return key_id, secret


def _hash_secret(secret: str) -> str:
    """
    Hash a secret using bcrypt (or similar).
    In production, use bcrypt.hashpw().
    
    For now, placeholder (should NOT be this simple).
    """
    import hashlib
    return "bcrypt:$2b$12$" + hashlib.sha256(secret.encode()).hexdigest()[:40]


# Endpoints

@router.post("/api/admin/keys", response_model=CreateKeyResponse)
async def create_key(
    request: Request,
    req_body: CreateKeyRequest
) -> CreateKeyResponse:
    """
    Create a new API key for a partner.
    
    The secret is returned ONLY in this response; store it securely.
    If lost, revoke and create a new key.
    
    All API keys use Bearer token format: Authorization: Bearer key_<id>:<secret>
    """
    
    # Validate admin access
    admin_key_id = _validate_admin_key(request)
    
    # Generate new key material
    key_id, secret = _generate_key_material()
    secret_hash = _hash_secret(secret)
    
    # Store in "database" (in production: PostgreSQL)
    now = datetime.utcnow()
    expires_at = now + timedelta(days=req_body.expires_in_days or 365)
    
    API_KEYS_DB[key_id] = {
        "key_id": key_id,
        "secret_hash": secret_hash,
        "partner_id": req_body.partner_id or str(uuid.uuid4()),
        "partner_name": req_body.partner_name,
        "tenant_id": req_body.tenant_id,
        "description": req_body.description,
        "status": "active",
        "scope": "api",  # Regular API scope (not admin)
        "created_at": now.isoformat(),
        "expires_at": expires_at.isoformat(),
        "last_used_at": None,
        "rotation_status": None,
    }
    
    # Log the creation (do NOT log the secret)
    audit_logger.info(json.dumps({
        "event": "api_key_created",
        "key_id": key_id,
        "partner_id": API_KEYS_DB[key_id]["partner_id"],
        "tenant_id": req_body.tenant_id,
        "by_admin": admin_key_id,
        "timestamp": now.isoformat(),
    }))
    
    # Return the key material (only time we show the secret)
    full_key = f"{key_id}:{secret}"
    
    return CreateKeyResponse(
        key_id=key_id,
        secret=secret,
        full_key=full_key,
        created_at=now.isoformat(),
        expires_at=expires_at.isoformat(),
        message="IMPORTANT: Store the secret securely (e.g., environment variable or secret manager). You will NOT see it again. If lost, revoke this key and create a new one."
    )


@router.get("/api/admin/keys", response_model=List[ListKeyResponse])
async def list_keys(request: Request) -> List[ListKeyResponse]:
    """
    List all API keys (redacted; no secrets).
    
    Filters can be added (e.g., ?partner_id=xyz, ?status=active).
    """
    
    # Validate admin access
    admin_key_id = _validate_admin_key(request)
    
    # TODO: Support filtering by partner_id, tenant_id, status, etc.
    # For now, return all (in production, filter by admin's scope)
    
    result = []
    for key_id, key_data in API_KEYS_DB.items():
        result.append(ListKeyResponse(
            key_id=key_id,
            partner_id=key_data.get("partner_id"),
            tenant_id=key_data.get("tenant_id"),
            description=key_data.get("description"),
            status=key_data.get("status"),
            created_at=key_data.get("created_at"),
            expires_at=key_data.get("expires_at"),
            last_used_at=key_data.get("last_used_at"),
            rotation_status=key_data.get("rotation_status"),
        ))
    
    return result


@router.post("/api/admin/keys/{key_id}/rotate", response_model=RotateKeyResponse)
async def rotate_key(
    request: Request,
    key_id: str,
    req_body: RotateKeyRequest
) -> RotateKeyResponse:
    """
    Rotate an API key.
    
    During the grace period (default 7 days), both the old and new keys work.
    After the grace period, the old key is automatically revoked.
    
    This is safer than immediate revocation (clients have time to update).
    """
    
    # Validate admin access
    admin_key_id = _validate_admin_key(request)
    
    # Check if key exists
    if key_id not in API_KEYS_DB:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Key {key_id} not found"
        )
    
    old_key_data = API_KEYS_DB[key_id]
    
    # Generate new key material
    new_key_id, new_secret = _generate_key_material()
    new_secret_hash = _hash_secret(new_secret)
    
    # Calculate grace period
    now = datetime.utcnow()
    grace_period_days = req_body.grace_period_days or 7
    grace_period_until = now + timedelta(days=grace_period_days)
    
    # Store new key
    API_KEYS_DB[new_key_id] = {
        "key_id": new_key_id,
        "secret_hash": new_secret_hash,
        "partner_id": old_key_data.get("partner_id"),
        "partner_name": old_key_data.get("partner_name"),
        "tenant_id": old_key_data.get("tenant_id"),
        "description": old_key_data.get("description"),
        "status": "active",
        "scope": old_key_data.get("scope"),
        "created_at": now.isoformat(),
        "expires_at": old_key_data.get("expires_at"),
        "last_used_at": None,
        "rotation_status": None,
    }
    
    # Mark old key as in grace period
    old_key_data["status"] = "rotated"
    old_key_data["rotation_status"] = "grace_period"
    old_key_data["grace_period_until"] = grace_period_until.isoformat()
    
    # Log the rotation (do NOT log new secret)
    audit_logger.info(json.dumps({
        "event": "api_key_rotated",
        "old_key_id": key_id,
        "new_key_id": new_key_id,
        "partner_id": old_key_data.get("partner_id"),
        "grace_period_until": grace_period_until.isoformat(),
        "by_admin": admin_key_id,
        "timestamp": now.isoformat(),
    }))
    
    full_key = f"{new_key_id}:{new_secret}"
    
    return RotateKeyResponse(
        old_key_id=key_id,
        new_key_id=new_key_id,
        new_secret=new_secret,
        new_full_key=full_key,
        grace_period_until=grace_period_until.isoformat(),
        message=f"New key is active now. Old key will be revoked in {grace_period_days} days. Both keys work during grace period."
    )


@router.post("/api/admin/keys/{key_id}/revoke", response_model=RevokeKeyResponse)
async def revoke_key(
    request: Request,
    key_id: str,
    req_body: RevokeKeyRequest
) -> RevokeKeyResponse:
    """
    Revoke an API key immediately.
    
    Use this if a key is compromised. For planned rotation, use /rotate instead.
    """
    
    # Validate admin access
    admin_key_id = _validate_admin_key(request)
    
    # Check if key exists
    if key_id not in API_KEYS_DB:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Key {key_id} not found"
        )
    
    key_data = API_KEYS_DB[key_id]
    
    # Mark as revoked
    now = datetime.utcnow()
    key_data["status"] = "revoked"
    key_data["revoked_at"] = now.isoformat()
    key_data["revocation_reason"] = req_body.reason or "admin_revoked"
    
    # Log the revocation
    audit_logger.info(json.dumps({
        "event": "api_key_revoked",
        "key_id": key_id,
        "partner_id": key_data.get("partner_id"),
        "reason": key_data.get("revocation_reason"),
        "by_admin": admin_key_id,
        "timestamp": now.isoformat(),
    }))
    
    return RevokeKeyResponse(
        key_id=key_id,
        revoked_at=now.isoformat(),
        status="revoked"
    )


@router.get("/api/admin/keys/{key_id}/validate")
async def validate_key(request: Request, key_id: str):
    """
    Validate a key (health check / introspection).
    Returns key status without revealing the secret.
    """
    
    # Validate admin access
    admin_key_id = _validate_admin_key(request)
    
    # Check if key exists
    if key_id not in API_KEYS_DB:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Key {key_id} not found"
        )
    
    key_data = API_KEYS_DB[key_id]
    
    # Check expiration
    expires_at = datetime.fromisoformat(key_data.get("expires_at", ""))
    is_expired = expires_at < datetime.utcnow()
    
    return {
        "key_id": key_id,
        "status": key_data.get("status"),
        "partner_id": key_data.get("partner_id"),
        "tenant_id": key_data.get("tenant_id"),
        "expires_at": key_data.get("expires_at"),
        "is_expired": is_expired,
        "last_used_at": key_data.get("last_used_at"),
    }
