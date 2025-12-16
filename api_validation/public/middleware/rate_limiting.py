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
from typing import Optional, Callable
from functools import wraps

from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


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
    
    @classmethod
    def get_rate_limit_for_key(cls, api_key_id: Optional[str]) -> int:
        """Get rate limit for a specific API key (could be customized per tier)."""
        # TODO: Implement tiered rate limits (e.g., premium keys get higher limits)
        return cls.DEFAULT_RATE_LIMIT


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
    
    async def dispatch(self, request: Request, call_next):
        """Check rate limit and payload size before processing."""
        
        # Extract API key from Authorization header
        auth_header = request.headers.get("Authorization", "")
        api_key_id = self._extract_api_key_id(auth_header)
        
        # Check payload size (if applicable)
        if request.method in ["POST", "PUT", "PATCH"]:
            content_length = request.headers.get("Content-Length")
            if content_length:
                size_bytes = int(content_length)
                max_size_bytes = self.config.MAX_REQUEST_PAYLOAD_MB * 1024 * 1024
                
                if size_bytes > max_size_bytes:
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
        
        if api_key_id and not self.limiter.is_allowed(api_key_id, limit):
            remaining = self.limiter.get_remaining(api_key_id, limit)
            reset_time = self.limiter.get_reset_time(api_key_id)
            
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
                    "Retry-After": str(int(reset_time)),
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
        
        return response
    
    @staticmethod
    def _extract_api_key_id(auth_header: str) -> Optional[str]:
        """Extract obfuscated API key ID from Authorization header."""
        if not auth_header:
            return None
        
        try:
            parts = auth_header.split()
            if len(parts) >= 2:
                key = parts[1]
                # Return a simple hash for identification
                import hashlib
                return hashlib.sha256(key.encode()).hexdigest()[:12]
            return None
        except Exception:
            return None


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
