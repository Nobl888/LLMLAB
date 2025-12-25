"""
Fixture upload endpoints.

Operations:
- Upload CSV fixture files with multipart/form-data
- Store files securely with tenant isolation
- Compute SHA256 hash and track metadata

Security:
- Requires valid API key (Authorization: Bearer ...)
- Requires X-Tenant-ID header for tenant isolation
- Files stored in tenant-specific subdirectories
"""

from fastapi import APIRouter, HTTPException, UploadFile, File, Header, Depends
from pydantic import BaseModel
import hashlib
import os
import logging
from pathlib import Path
from uuid import uuid4

import psycopg

from api_validation.public.routes.validate import require_api_key_bearer

router = APIRouter(tags=["fixtures"])
logger = logging.getLogger(__name__)


class FixtureUploadResponse(BaseModel):
    """Response after successful fixture upload."""

    fixture_id: str
    tenant_id: str
    sha256: str
    size_bytes: int
    fixture_path: str
    original_filename: str
    content_type: str


class FixtureMetaResponse(BaseModel):
    fixture_id: str
    tenant_id: str
    sha256: str
    size_bytes: int
    original_filename: str
    content_type: str
    status: str


class FixtureListResponse(BaseModel):
    fixtures: list[FixtureMetaResponse]


class FixtureDeleteResponse(BaseModel):
    fixture_id: str
    deleted: bool
    purged: bool


@router.post("/api/fixtures/upload", response_model=FixtureUploadResponse)
async def upload_fixture(
    file: UploadFile = File(...),
    x_tenant_id: str = Header(..., alias="X-Tenant-ID"),
    auth: dict = Depends(require_api_key_bearer),
) -> FixtureUploadResponse:
    """Upload a CSV fixture file.

    Security:
    - Requires Authorization: Bearer <api-key>
    - Requires X-Tenant-ID header
    - Files are isolated per tenant in separate subdirectories

    Validation:
    - Only .csv files are accepted
    - Files are streamed to disk in chunks (memory-efficient)
    - SHA256 hash computed during streaming
    - Optional size cap via MAX_FIXTURE_BYTES

    Storage:
    - Files saved to UPLOAD_ROOT env var (default: /tmp/llmlab_uploads)
    - Path: {UPLOAD_ROOT}/{tenant_id}/{fixture_id}.csv

    Returns:
    - fixture_id: UUID identifier for this fixture
    - tenant_id: Tenant who owns this fixture
    - sha256: Hash of file contents
    - size_bytes: File size in bytes
    - fixture_path: Server-side path to file (redacted)
    - original_filename: Original filename from upload
    - content_type: MIME type from upload
    """

    if not x_tenant_id:
        raise HTTPException(
            status_code=400,
            detail={"code": "MISSING_TENANT_ID", "message": "X-Tenant-ID header is required"},
        )

    if x_tenant_id != auth["tenant_id"]:
        raise HTTPException(
            status_code=403,
            detail={"code": "TENANT_MISMATCH", "message": "X-Tenant-ID doesn't match API key tenant"},
        )

    if not file.filename:
        raise HTTPException(status_code=400, detail={"code": "MISSING_FILENAME", "message": "File must have a filename"})

    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_FILE_TYPE", "message": "Only .csv files are accepted", "allowed_extensions": [".csv"]},
        )

    upload_root = os.getenv("UPLOAD_ROOT", "/tmp/llmlab_uploads")

    max_bytes_env = os.getenv("MAX_FIXTURE_BYTES")
    max_bytes: int | None = None
    if max_bytes_env:
        try:
            v = int(max_bytes_env)
            if v > 0:
                max_bytes = v
        except Exception:
            max_bytes = None

    tenant_dir = Path(upload_root) / x_tenant_id
    tenant_dir.mkdir(parents=True, exist_ok=True)

    fixture_id = str(uuid4())
    fixture_path = tenant_dir / f"{fixture_id}.csv"

    sha256_hash = hashlib.sha256()
    size_bytes = 0
    chunk_size = 8192

    try:
        with open(fixture_path, "wb") as f:
            while chunk := await file.read(chunk_size):
                if max_bytes is not None and (size_bytes + len(chunk)) > max_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail={
                            "code": "FIXTURE_TOO_LARGE",
                            "message": "Fixture exceeds MAX_FIXTURE_BYTES",
                            "max_bytes": int(max_bytes),
                        },
                    )
                f.write(chunk)
                sha256_hash.update(chunk)
                size_bytes += len(chunk)

        dsn = os.getenv("DATABASE_URL")
        if not dsn:
            raise HTTPException(status_code=503, detail={"code": "DB_NOT_CONFIGURED", "message": "DATABASE_URL not set"})

        with psycopg.connect(dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    insert into fixtures (
                      id, tenant_id, storage_path, sha256, size_bytes, original_filename, content_type, status
                    ) values (
                      %s, %s, %s, %s, %s, %s, %s, 'active'
                    )
                    """,
                    (
                        fixture_id,
                        x_tenant_id,
                        str(fixture_path),
                        sha256_hash.hexdigest(),
                        size_bytes,
                        file.filename,
                        (file.content_type or "text/csv"),
                    ),
                )
            conn.commit()

        logger.info(
            "Fixture uploaded: fixture_id=%s tenant_id=%s size=%s sha256=%s...",
            fixture_id,
            x_tenant_id,
            size_bytes,
            sha256_hash.hexdigest()[:12],
        )

        return FixtureUploadResponse(
            fixture_id=fixture_id,
            tenant_id=x_tenant_id,
            sha256=sha256_hash.hexdigest(),
            size_bytes=size_bytes,
            fixture_path="[REDACTED]",
            original_filename=file.filename,
            content_type=file.content_type or "text/csv",
        )

    except HTTPException:
        if fixture_path.exists():
            try:
                fixture_path.unlink()
            except Exception:
                pass
        raise

    except Exception as e:
        if fixture_path.exists():
            try:
                fixture_path.unlink()
            except Exception:
                pass

        logger.error("Fixture upload failed: %s", e)
        raise HTTPException(
            status_code=500,
            detail={"code": "UPLOAD_FAILED", "message": f"Failed to save fixture: {str(e)}"},
        )


@router.get("/api/fixtures/{fixture_id}", response_model=FixtureMetaResponse)
async def get_fixture_meta(
    fixture_id: str,
    x_tenant_id: str = Header(..., alias="X-Tenant-ID"),
    auth: dict = Depends(require_api_key_bearer),
) -> FixtureMetaResponse:
    if not x_tenant_id:
        raise HTTPException(status_code=400, detail={"code": "MISSING_TENANT_ID", "message": "X-Tenant-ID header is required"})
    if x_tenant_id != auth["tenant_id"]:
        raise HTTPException(status_code=403, detail={"code": "TENANT_MISMATCH", "message": "X-Tenant-ID doesn't match API key tenant"})

    dsn = os.getenv("DATABASE_URL")
    if not dsn:
        raise HTTPException(status_code=503, detail={"code": "DB_NOT_CONFIGURED", "message": "DATABASE_URL not set"})

    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select tenant_id, sha256, size_bytes, original_filename, content_type, status
                from fixtures
                where id = %s and tenant_id = %s
                """,
                (fixture_id, x_tenant_id),
            )
            row = cur.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail={"code": "FIXTURE_NOT_FOUND", "message": "Fixture not found"})

    tenant_id, sha256, size_bytes, original_filename, content_type, status = row
    return FixtureMetaResponse(
        fixture_id=str(fixture_id),
        tenant_id=str(tenant_id),
        sha256=str(sha256),
        size_bytes=int(size_bytes),
        original_filename=str(original_filename),
        content_type=str(content_type),
        status=str(status),
    )


@router.get("/api/fixtures", response_model=FixtureListResponse)
async def list_fixtures(
    x_tenant_id: str = Header(..., alias="X-Tenant-ID"),
    auth: dict = Depends(require_api_key_bearer),
) -> FixtureListResponse:
    if not x_tenant_id:
        raise HTTPException(status_code=400, detail={"code": "MISSING_TENANT_ID", "message": "X-Tenant-ID header is required"})
    if x_tenant_id != auth["tenant_id"]:
        raise HTTPException(status_code=403, detail={"code": "TENANT_MISMATCH", "message": "X-Tenant-ID doesn't match API key tenant"})

    dsn = os.getenv("DATABASE_URL")
    if not dsn:
        raise HTTPException(status_code=503, detail={"code": "DB_NOT_CONFIGURED", "message": "DATABASE_URL not set"})

    fixtures: list[FixtureMetaResponse] = []
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select id, tenant_id, sha256, size_bytes, original_filename, content_type, status
                from fixtures
                where tenant_id = %s
                order by created_at desc
                limit 200
                """,
                (x_tenant_id,),
            )
            rows = cur.fetchall() or []

    for fixture_id, tenant_id, sha256, size_bytes, original_filename, content_type, status in rows:
        fixtures.append(
            FixtureMetaResponse(
                fixture_id=str(fixture_id),
                tenant_id=str(tenant_id),
                sha256=str(sha256),
                size_bytes=int(size_bytes),
                original_filename=str(original_filename),
                content_type=str(content_type),
                status=str(status),
            )
        )

    return FixtureListResponse(fixtures=fixtures)


@router.delete("/api/fixtures/{fixture_id}", response_model=FixtureDeleteResponse)
async def delete_fixture(
    fixture_id: str,
    x_tenant_id: str = Header(..., alias="X-Tenant-ID"),
    auth: dict = Depends(require_api_key_bearer),
) -> FixtureDeleteResponse:
    if not x_tenant_id:
        raise HTTPException(status_code=400, detail={"code": "MISSING_TENANT_ID", "message": "X-Tenant-ID header is required"})
    if x_tenant_id != auth["tenant_id"]:
        raise HTTPException(status_code=403, detail={"code": "TENANT_MISMATCH", "message": "X-Tenant-ID doesn't match API key tenant"})

    dsn = os.getenv("DATABASE_URL")
    if not dsn:
        raise HTTPException(status_code=503, detail={"code": "DB_NOT_CONFIGURED", "message": "DATABASE_URL not set"})

    storage_path: str | None = None
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select storage_path, status
                from fixtures
                where id = %s and tenant_id = %s
                """,
                (fixture_id, x_tenant_id),
            )
            row = cur.fetchone()

            if not row:
                raise HTTPException(status_code=404, detail={"code": "FIXTURE_NOT_FOUND", "message": "Fixture not found"})

            storage_path, current_status = row

            if str(current_status) != "active":
                return FixtureDeleteResponse(fixture_id=str(fixture_id), deleted=True, purged=False)

            cur.execute(
                """
                update fixtures
                set status = 'deleted', deleted_at = now()
                where id = %s and tenant_id = %s
                """,
                (fixture_id, x_tenant_id),
            )
        conn.commit()

    purged = False
    try:
        if storage_path and Path(str(storage_path)).exists():
            Path(str(storage_path)).unlink()
            purged = True
    except Exception:
        purged = False

    return FixtureDeleteResponse(fixture_id=str(fixture_id), deleted=True, purged=purged)
