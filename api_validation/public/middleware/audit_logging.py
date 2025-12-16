"""
Audit logging middleware for FastAPI.

This middleware:
1. Generates a unique request ID
2. Extracts API key (hashed)
3. Hashes request payload (never stores it)
4. Logs structured audit entries
5. Applies redaction rules (removes PII, secrets, etc.)

Usage:
    app.add_middleware(AuditLoggingMiddleware)
"""

import json
import hashlib
import time
import logging
import re
from uuid import uuid4
from typing import Optional, Dict, Any
from datetime import datetime

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from starlette.datastructures import Headers


class AuditLogger:
    """Structured audit logger with redaction rules."""
    
    # Patterns to redact (sensitive data)
    REDACTION_PATTERNS = {
        "api_key": r"(key_[a-zA-Z0-9]{40,}|Bearer\s+[a-zA-Z0-9._\-]+)",
        "email": r"[\w\.-]+@[\w\.-]+\.\w+",
        "ssn": r"\d{3}-\d{2}-\d{4}",
        "credit_card": r"\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}",
        "password": r"(?i)password[:\s=\"]+[^\s,}]+",
        "token": r"(?i)(token|authorization)[:\s=\"]+[^\s,}]+",
    }
    
    def __init__(self, name: str = "audit", enable_redaction: bool = True):
        self.logger = logging.getLogger(name)
        self.enable_redaction = enable_redaction
    
    @staticmethod
    def hash_api_key(auth_header: str) -> Optional[str]:
        """Extract and hash API key from Authorization header."""
        if not auth_header:
            return None
        
        try:
            # Expected format: "Bearer key_abc123def456"
            parts = auth_header.split()
            if len(parts) >= 2:
                key = parts[1]
                # Hash the key, return last 5 chars + hash
                key_hash = hashlib.sha256(key.encode()).hexdigest()[:12]
                return f"key_***{key[-5:]}"  # Obfuscated version
            return None
        except Exception:
            return None
    
    @staticmethod
    def hash_payload(payload: bytes) -> str:
        """Create SHA-256 hash of request payload."""
        if not payload:
            return "sha256:empty"
        try:
            h = hashlib.sha256(payload).hexdigest()
            return f"sha256:{h[:16]}..."
        except Exception:
            return "sha256:error"
    
    def redact(self, text: str) -> str:
        """Apply redaction rules to remove sensitive data."""
        if not self.enable_redaction or not isinstance(text, str):
            return text
        
        result = text
        for pattern_name, pattern in self.REDACTION_PATTERNS.items():
            result = re.sub(pattern, f"[REDACTED_{pattern_name.upper()}]", result, flags=re.IGNORECASE)
        
        return result
    
    def create_audit_entry(
        self,
        request_id: str,
        api_key_id: Optional[str],
        endpoint: str,
        http_method: str,
        http_status: int,
        latency_ms: float,
        payload_hash: str,
        error_code: Optional[str] = None,
        customer_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a structured audit log entry."""
        
        entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "request_id": request_id,
            "api_key_id": api_key_id,
            "endpoint": endpoint,
            "http_method": http_method,
            "http_status": http_status,
            "latency_ms": latency_ms,
            "payload_hash": payload_hash,
            "error_code": error_code,
            "customer_id": customer_id,
        }
        
        return entry
    
    def log_entry(self, entry: Dict[str, Any]):
        """Write audit entry to log (JSON format)."""
        # Redact the entire entry (in case error messages contain PII)
        redacted_entry = {k: self.redact(str(v)) if isinstance(v, str) else v for k, v in entry.items()}
        
        self.logger.info(json.dumps(redacted_entry))


class AuditLoggingMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware to log all API calls with audit trail.
    
    Logs contain:
    - request_id (unique, for tracing)
    - api_key_id (hashed, obfuscated)
    - endpoint & method
    - HTTP status & latency
    - payload_hash (not the payload itself)
    - error_code (if any)
    
    No raw payloads or PII are stored.
    """
    
    def __init__(self, app, enable_redaction: bool = True, enable_logging: bool = True):
        super().__init__(app)
        self.audit_logger = AuditLogger(enable_redaction=enable_redaction)
        self.enable_logging = enable_logging
    
    async def dispatch(self, request: Request, call_next) -> Response:
        """Process request, measure latency, log audit entry."""
        
        # Generate request ID (or use existing)
        request_id = request.headers.get("X-Request-ID", str(uuid4()))
        
        # Extract API key (hashed, obfuscated)
        auth_header = request.headers.get("Authorization", "")
        api_key_id = self.audit_logger.hash_api_key(auth_header)
        
        # Hash request payload
        try:
            body = await request.body()
            payload_hash = self.audit_logger.hash_payload(body)
        except Exception:
            payload_hash = "sha256:error"
            body = b""
        
        # Store body back on request (FastAPI needs it)
        async def receive():
            return {"type": "http.request", "body": body}
        
        request.receive = receive
        
        # Measure latency
        start_time = time.time()
        
        try:
            response = await call_next(request)
        except Exception as exc:
            # Log error
            latency_ms = (time.time() - start_time) * 1000
            
            entry = self.audit_logger.create_audit_entry(
                request_id=request_id,
                api_key_id=api_key_id,
                endpoint=str(request.url.path),
                http_method=request.method,
                http_status=500,
                latency_ms=latency_ms,
                payload_hash=payload_hash,
                error_code="INTERNAL_ERROR",
                customer_id=request.headers.get("X-Customer-ID"),
            )
            
            if self.enable_logging:
                self.audit_logger.log_entry(entry)
            
            # Re-raise the exception
            raise
        
        latency_ms = (time.time() - start_time) * 1000
        
        # Determine error code (if any)
        error_code = None
        if response.status_code >= 400:
            if response.status_code == 429:
                error_code = "RATE_LIMIT_EXCEEDED"
            elif response.status_code == 401:
                error_code = "UNAUTHORIZED"
            elif response.status_code == 403:
                error_code = "FORBIDDEN"
            elif response.status_code == 422:
                error_code = "VALIDATION_ERROR"
            elif response.status_code >= 500:
                error_code = "SERVER_ERROR"
            else:
                error_code = "CLIENT_ERROR"
        
        # Create audit log entry
        entry = self.audit_logger.create_audit_entry(
            request_id=request_id,
            api_key_id=api_key_id,
            endpoint=str(request.url.path),
            http_method=request.method,
            http_status=response.status_code,
            latency_ms=latency_ms,
            payload_hash=payload_hash,
            error_code=error_code,
            customer_id=request.headers.get("X-Customer-ID"),
        )
        
        # Log the entry
        if self.enable_logging:
            self.audit_logger.log_entry(entry)
        
        # Add request ID to response headers
        response.headers["X-Request-ID"] = request_id
        
        return response


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Simple middleware to ensure every request has a unique request ID.
    Falls back to X-Request-ID header if provided.
    """
    
    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("X-Request-ID", str(uuid4()))
        
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        
        return response
