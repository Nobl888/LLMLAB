"""
Rate limiting and resource protection middleware for FastAPI.

This module provides:
- Per-API-key rate limiting (requests per minute)
- Payload size enforcement
- Request timeout handling
- Cost control (optional cost tracking)

Usage:
    from slowapi import Limiter
    from slowapi.util import get_remote_address
    
    limiter = Limiter(key_func=get_api_key_from_token)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    
    @app.post("/api/validate")
    @limiter.limit("100/minute")
    async def validate(request: Request, body: ValidateRequest):
        ...
"""

import os
from typing import Optional, Callable, Tuple
from functools import wraps
from datetime import datetime, timezone

from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

import psycopg


class RateLimitConfig:
    """Configuration for rate limiting and resource protection."""
    
    # Rate limits per API key (requests per minute)
    DEFAULT_RATE_LIMIT = int(os.getenv("RATE_LIMIT_PER_MINUTE", "100"))
    BURST_ALLOWANCE = int(os.getenv("RATE_LIMIT_BURST", "150"))
    
    # Payload size limits
    MAX_REQUEST_PAYLOAD_MB = int(os.getenv("MAX_REQUEST_PAYLOAD_MB", "10"))
    MAX_RESPONSE_SIZE_MB = int(os.getenv("MAX_RESPONSE_SIZE_MB", "50"))
    
    # Request timeout (seconds)
    REQUEST_TIMEOUT_SECONDS = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "30"))
    
    # Cost tracking (optional)
    ENABLE_COST_TRACKING = os.getenv("ENABLE_COST_TRACKING", "false").lower() == "true"
    COST_PER_REQUEST_CENTS = float(os.getenv("COST_PER_REQUEST_CENTS", "1.0"))  # $0.01 per request

    # Monthly quotas (Postgres-backed; requires DATABASE_URL)
    ENABLE_MONTHLY_QUOTAS = os.getenv("ENABLE_MONTHLY_QUOTAS", "false").lower() == "true"
    MONTHLY_QUOTA_DEFAULT = int(os.getenv("MONTHLY_QUOTA_DEFAULT", "200"))
    MONTHLY_QUOTA_FREE = int(os.getenv("MONTHLY_QUOTA_FREE", "200"))
    MONTHLY_QUOTA_STARTER = int(os.getenv("MONTHLY_QUOTA_STARTER", "10000"))
    MONTHLY_QUOTA_PRO = int(os.getenv("MONTHLY_QUOTA_PRO", "50000"))
    
    @classmethod
    def get_rate_limit_for_key(cls, api_key_id: Optional[str]) -> int:
        """Get rate limit for a specific API key (could be customized per tier)."""
        # TODO: Implement tiered rate limits (e.g., premium keys get higher limits)
        return cls.DEFAULT_RATE_LIMIT

    @classmethod
    def _parse_tier_from_scopes(cls, scopes: Optional[str]) -> str:
        if not scopes:
            return "free"
        normalized = [
            p.strip().lower()
            for p in scopes.replace(";", ",").replace(" ", ",").split(",")
            if p.strip()
        ]
        for token in normalized:
            if token.startswith("tier:") or token.startswith("tier="):
                return token.split(":", 1)[-1].split("=", 1)[-1].strip() or "free"
            if token.startswith("plan:") or token.startswith("plan="):
                return token.split(":", 1)[-1].split("=", 1)[-1].strip() or "free"
        if "starter" in normalized:
            return "starter"
        if "pro" in normalized:
            return "pro"
        if "free" in normalized:
            return "free"
        return "free"

    @classmethod
    def get_monthly_quota_for_scopes(cls, scopes: Optional[str]) -> int:
        """Return the enforced monthly quota for a given key scopes string."""
        tier = cls._parse_tier_from_scopes(scopes)
        if tier == "starter":
            return cls.MONTHLY_QUOTA_STARTER
        if tier == "pro":
            return cls.MONTHLY_QUOTA_PRO
        if tier == "free":
            return cls.MONTHLY_QUOTA_FREE
        # Unknown tier: fall back to default (conservative)
        return cls.MONTHLY_QUOTA_DEFAULT


def _month_key(now: Optional[datetime] = None) -> str:
    dt = now or datetime.now(timezone.utc)
    return f"{dt.year:04d}-{dt.month:02d}"


def _next_month_start_epoch(now: Optional[datetime] = None) -> int:
    dt = now or datetime.now(timezone.utc)
    year, month = dt.year, dt.month
    if month == 12:
        year += 1
        month = 1
    else:
        month += 1
    return int(datetime(year, month, 1, 0, 0, 0, tzinfo=timezone.utc).timestamp())


class PostgresMonthlyQuota:
    """Postgres-backed monthly quota counter keyed by api_keys.key_hash."""

    def __init__(self, dsn: str):
        self._dsn = dsn

    def check_and_increment(self, key_prefix: str, key_hash: str, month: str, increment: int = 1) -> Tuple[bool, int, Optional[str]]:
        """Return (allowed, used_after, scopes)."""
        with psycopg.connect(self._dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    select scopes, status
                    from api_keys
                    where key_prefix = %s and key_hash = %s
                    """,
                    (key_prefix, key_hash),
                )
                row = cur.fetchone()
                if not row:
                    # Unknown key: do not enforce quota here; auth will reject later.
                    return True, 0, None
                scopes, key_status = row
                if str(key_status).lower() != "active":
                    # Let auth layer reject; quota not applicable.
                    return True, 0, scopes

                cur.execute(
                    """
                    insert into api_key_monthly_usage (key_hash, month, request_count)
                    values (%s, %s, 0)
                    on conflict (key_hash, month) do nothing
                    """,
                    (key_hash, month),
                )

                cur.execute(
                    """
                    update api_key_monthly_usage
                    set request_count = request_count + %s,
                        updated_at = now()
                    where key_hash = %s and month = %s
                    returning request_count
                    """,
                    (increment, key_hash, month),
                )
                used_after = int(cur.fetchone()[0])
                conn.commit()

        return True, used_after, scopes


class InMemoryRateLimiter:
    """
    Simple in-memory rate limiter (for single-instance deployment).
    For distributed deployments, use Redis.
    """
    
    def __init__(self):
        self.requests = {}  # {api_key_id: [timestamp1, timestamp2, ...]}
    
    def is_allowed(self, api_key_id: str, limit: int, window_seconds: int = 60) -> bool:
        """Check if request is within rate limit."""
        import time
        
        now = time.time()
        window_start = now - window_seconds
        
        if api_key_id not in self.requests:
            self.requests[api_key_id] = []
        
        # Remove old requests outside the window
        self.requests[api_key_id] = [
            ts for ts in self.requests[api_key_id] if ts > window_start
        ]
        
        # Check if within limit
        if len(self.requests[api_key_id]) >= limit:
            return False
        
        # Record this request
        self.requests[api_key_id].append(now)
        return True
    
    def get_remaining(self, api_key_id: str, limit: int, window_seconds: int = 60) -> int:
        """Get remaining requests in the current window."""
        import time
        
        now = time.time()
        window_start = now - window_seconds
        
        if api_key_id not in self.requests:
            return limit
        
        count = len([ts for ts in self.requests[api_key_id] if ts > window_start])
        return max(0, limit - count)
    
    def get_reset_time(self, api_key_id: str, window_seconds: int = 60) -> float:
        """Get the time when rate limit will reset."""
        import time
        
        if api_key_id not in self.requests or not self.requests[api_key_id]:
            return time.time()
        
        oldest = min(self.requests[api_key_id])
        return oldest + window_seconds


class RateLimitingMiddleware(BaseHTTPMiddleware):
    """
    Middleware to enforce rate limits and payload size caps.
    
    Returns:
    - HTTP 429 Too Many Requests if rate limit exceeded
    - HTTP 413 Payload Too Large if payload exceeds limit
    """
    
    def __init__(self, app):
        super().__init__(app)
        self.limiter = InMemoryRateLimiter()
        self.config = RateLimitConfig()
        self._quota = None
        if self.config.ENABLE_MONTHLY_QUOTAS:
            dsn = os.getenv("DATABASE_URL")
            if dsn:
                self._quota = PostgresMonthlyQuota(dsn)
    
    async def dispatch(self, request: Request, call_next):
        """Check rate limit and payload size before processing."""
        
        # Extract API key from Authorization header
        auth_header = request.headers.get("Authorization", "")
        api_key_id, api_key_prefix, api_key_hash = self._extract_api_key_identifiers(auth_header)
        
        # Check payload size (if applicable)
        if request.method in ["POST", "PUT", "PATCH"]:
            content_length = request.headers.get("Content-Length")
            if content_length:
                try:
                    size_bytes = int(content_length)
                except Exception:
                    size_bytes = None
                max_size_bytes = self.config.MAX_REQUEST_PAYLOAD_MB * 1024 * 1024

                if size_bytes is not None and size_bytes > max_size_bytes:
                    return JSONResponse(
                        status_code=status.HTTP_413_PAYLOAD_TOO_LARGE,
                        content={
                            "status": "error",
                            "error": {
                                "code": "PAYLOAD_TOO_LARGE",
                                "message": f"Request payload exceeds {self.config.MAX_REQUEST_PAYLOAD_MB} MB limit",
                                "limit_mb": self.config.MAX_REQUEST_PAYLOAD_MB,
                                "received_mb": round(size_bytes / (1024 * 1024), 2),
                            }
                        }
                    )
        
        # Check rate limit
        limit = self.config.get_rate_limit_for_key(api_key_id)

        monthly_quota_headers: Optional[dict] = None

        # Monthly quota (optional; Postgres-backed)
        if self.config.ENABLE_MONTHLY_QUOTAS:
            if not self._quota:
                # Quotas enabled but DB not configured. Fail closed to avoid unlimited exposure.
                return JSONResponse(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    content={
                        "status": "error",
                        "error": {
                            "code": "QUOTA_DB_NOT_CONFIGURED",
                            "message": "Monthly quotas are enabled but DATABASE_URL is not configured",
                        },
                    },
                )

            if api_key_prefix and api_key_hash:
                month = _month_key()
                allowed, used_after, scopes = self._quota.check_and_increment(
                    key_prefix=api_key_prefix,
                    key_hash=api_key_hash,
                    month=month,
                    increment=1,
                )
                if not allowed:
                    # Currently unused path; check_and_increment returns allowed=True.
                    pass

                quota = self.config.get_monthly_quota_for_scopes(scopes)
                reset_at = _next_month_start_epoch()
                remaining = max(0, quota - used_after) if quota > 0 else 0
                monthly_quota_headers = {
                    "X-MonthlyQuota-Limit": str(quota),
                    "X-MonthlyQuota-Used": str(used_after),
                    "X-MonthlyQuota-Remaining": str(remaining),
                    "X-MonthlyQuota-Reset": str(reset_at),
                }
                if quota > 0 and used_after > quota:
                    return JSONResponse(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        content={
                            "status": "error",
                            "error": {
                                "code": "MONTHLY_QUOTA_EXCEEDED",
                                "message": f"Monthly quota of {quota} requests exceeded",
                                "month": month,
                                "quota": quota,
                                "used": used_after,
                                "remaining": remaining,
                                "reset_at": reset_at,
                            }
                        },
                        headers=monthly_quota_headers,
                    )
        
        if api_key_id and not self.limiter.is_allowed(api_key_id, limit):
            remaining = self.limiter.get_remaining(api_key_id, limit)
            reset_time = self.limiter.get_reset_time(api_key_id)

            # Retry-After should be seconds until reset (not an epoch timestamp).
            import time
            retry_after_seconds = max(0, int(reset_time - time.time()))
            
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "status": "error",
                    "error": {
                        "code": "RATE_LIMIT_EXCEEDED",
                        "message": f"Rate limit of {limit} requests per minute exceeded",
                        "limit": limit,
                        "remaining": remaining,
                        "reset_at": reset_time,
                    }
                },
                headers={
                    "Retry-After": str(retry_after_seconds),
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": str(remaining),
                    "X-RateLimit-Reset": str(int(reset_time)),
                }
            )
        
        # Process request
        response = await call_next(request)
        
        # Add rate limit headers to response
        if api_key_id:
            remaining = self.limiter.get_remaining(api_key_id, limit)
            reset_time = self.limiter.get_reset_time(api_key_id)
            
            response.headers["X-RateLimit-Limit"] = str(limit)
            response.headers["X-RateLimit-Remaining"] = str(remaining)
            response.headers["X-RateLimit-Reset"] = str(int(reset_time))

        # Add monthly quota headers (if enabled and available)
        if monthly_quota_headers:
            for k, v in monthly_quota_headers.items():
                response.headers[k] = v
        
        return response
    
    @staticmethod
    def _extract_api_key_identifiers(auth_header: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Return (api_key_id, key_prefix, key_hash) from Authorization header.

        - api_key_id is a safe identifier for in-memory rate limiting.
        - key_prefix/key_hash match the DB schema used by api_keys.
        """
        if not auth_header:
            return None, None, None

        try:
            parts = auth_header.split()
            if len(parts) < 2:
                return None, None, None

            raw_key = parts[1]
            if not raw_key:
                return None, None, None

            import hashlib

            key_prefix = raw_key[:12]
            key_hash = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

            # Keep in-memory key stable and non-secret. Prefix is already stored server-side.
            api_key_id = key_prefix
            return api_key_id, key_prefix, key_hash
        except Exception:
            return None, None, None


class PayloadSizeMiddleware(BaseHTTPMiddleware):
    """
    Dedicated middleware for strict payload size enforcement.
    Use this if you need more control over which endpoints are affected.
    """
    
    def __init__(self, app, max_mb: int = 10, excluded_paths: Optional[list] = None):
        super().__init__(app)
        self.max_bytes = max_mb * 1024 * 1024
        self.excluded_paths = excluded_paths or ["/health", "/docs", "/openapi.json"]
    
    async def dispatch(self, request: Request, call_next):
        # Skip check for excluded paths
        if any(request.url.path.startswith(p) for p in self.excluded_paths):
            return await call_next(request)
        
        # Check payload size
        if request.method in ["POST", "PUT", "PATCH"]:
            content_length = request.headers.get("Content-Length")
            if content_length:
                size_bytes = int(content_length)
                
                if size_bytes > self.max_bytes:
                    return JSONResponse(
                        status_code=status.HTTP_413_PAYLOAD_TOO_LARGE,
                        content={
                            "status": "error",
                            "error": {
                                "code": "PAYLOAD_TOO_LARGE",
                                "message": f"Request payload exceeds {self.max_bytes / (1024*1024)} MB limit",
                            }
                        }
                    )
        
        return await call_next(request)


def rate_limit_by_key(
    limit: int = 100,
    window_seconds: int = 60,
) -> Callable:
    """
    Decorator for rate limiting per API key.
    
    Usage:
        @rate_limit_by_key(limit=100, window_seconds=60)
        async def my_endpoint(request: Request):
            ...
    """
    
    def decorator(func: Callable) -> Callable:
        limiter = InMemoryRateLimiter()
        
        @wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            auth_header = request.headers.get("Authorization", "")
            api_key_id = RateLimitingMiddleware._extract_api_key_id(auth_header)
            
            if api_key_id and not limiter.is_allowed(api_key_id, limit, window_seconds):
                remaining = limiter.get_remaining(api_key_id, limit, window_seconds)
                
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail={
                        "error": "RATE_LIMIT_EXCEEDED",
                        "limit": limit,
                        "remaining": remaining,
                    }
                )
            
            return await func(request, *args, **kwargs)
        
        return wrapper
    
    return decorator
