# LLMlab Validation API - Quick Start

## Base URL
```
https://llmlab-t6zg.onrender.com
```

## Health Check
**Endpoint:** `GET /health`  
**Authentication:** None (public)  
**Purpose:** Platform health monitoring (suitable for Render health checks)

```bash
curl -i https://llmlab-t6zg.onrender.com/health
```

**Response (200 OK):**
```json
{
  "status": "ok",
  "service": "llmlab-validation-api",
  "version": "1.0.0",
  "commit": "<GIT_SHA>",
  "timestamp": "2025-12-16T13:40:00Z"
}
```
> Note: `commit` value reflects the actual deployed git SHA for debugging/support.

---

## Validate Endpoint
**Endpoint:** `POST /api/validate`  
**Authentication:** Required (`Authorization: Bearer <api-key>`)  
**Purpose:** Validate code changes against baseline with cryptographic evidence

### Required Headers
```
Authorization: Bearer key_<your-api-key>
X-Tenant-ID: <your-tenant-id>
Content-Type: application/json
```

### Minimal Request (Mock Mode - Works Today)
```bash
curl -X POST https://llmlab-t6zg.onrender.com/api/validate \
  -H "Authorization: Bearer <YOUR_API_KEY>" \
  -H "X-Tenant-ID: <YOUR_TENANT_ID>" \
  -H "Content-Type: application/json" \
  -d '{
    "baseline_output": {"total_revenue": 1000000, "profit_margin": 0.25},
    "candidate_output": {"total_revenue": 1000500, "profit_margin": 0.251},
    "test_data": {"period": "2024-Q4", "dataset": "historical"}
  }'
```

> **Note:** This example uses **mock mode** where you provide output data directly. The API also supports **KPI kit mode** with file paths (`baseline_kpi_path`, `candidate_kpi_path`, `fixture_path`), but this requires server-side file access and is currently limited to internal/admin use. For external API consumers, use mock mode as shown above.

### Response (200 OK)
```json
{
  "trace_id": "550e8400-e29b-41d4-a716-446655440000",
  "request_id": "c759fefc-8969-4641-8406-06d2d9d73c86",
  "status": "ok",
  "risk": {
    "score": 2.3,
    "category": "low",
    "confidence": 89.5
  },
  "summary": {
    "pass_rate": 0.95,
    "total_checks": 20,
    "failed_checks": 1
  },
  "recommendation": "APPROVE_WITH_MONITORING",
  "evidence": {
    "baseline_hash": "sha256:a1b2c3d4...",
    "candidate_hash": "sha256:e5f6g7h8...",
    "test_data_hash": "sha256:i9j0k1l2...",
    "timestamp": "2025-12-16T13:40:00Z",
    "domain": "analytics_kpi"
  }
}
```

### Request Schema

**Mock Mode** (recommended for external API consumers):
- `baseline_output` (object, required): Baseline output data (dict/object with metrics)
- `candidate_output` (object, required): Candidate output data (dict/object with metrics)
- `test_data` (object, optional): Test cases/data metadata used
- `include_details` (boolean, optional): Return detailed explanation (default: false)

**KPI Kit Mode** (server-side only - requires file access):
- `baseline_kpi_path` (string): Path to baseline KPI .py file
- `candidate_kpi_path` (string): Path to candidate KPI .py file
- `fixture_path` (string): Path to CSV fixture for execution
- `kpi_type` (string): `profitmetrics` | `countmetrics` | `percentagemetrics` | `aggregationmetrics`

> **Current Limitation:** KPI kit mode requires server-side file access on Render's ephemeral filesystem. External API consumers should use mock mode. File upload support may be added in a future release.

---

## API Keys & Authentication

### Getting API Keys
API keys are issued per tenant. Contact your administrator or use the admin key management endpoint.

### Environment Variables (Render)
Set these in Render Dashboard → Environment:
```
SMOKE_KEY=<RENDER_GENERATED_SECRET>   # For /_smoke diagnostic endpoint (generate long random value)
ENABLE_AUDIT_LOGGING=true             # Enable structured audit logs
ENABLE_RATE_LIMITING=true             # Enable per-tenant rate limits
ENABLE_REDACTION=true                 # Redact sensitive data in logs
```

### Protected Endpoints
- `GET /health` - Public (no auth required)
- `POST /api/validate` - Requires `Authorization: Bearer <api-key>` + `X-Tenant-ID` header
- `GET /_smoke` - Requires `X-Smoke-Key: <YOUR_SMOKE_KEY>` header (admin/diagnostic use only, returns 404 without valid key)

---

## Error Responses

**Missing Tenant ID (400):**
```json
{
  "trace_id": "550e8400-e29b-41d4-a716-446655440000",
  "request_id": "c759fefc-8969-4641-8406-06d2d9d73c86",
  "status": "error",
  "error": {
    "code": "MISSING_TENANT_ID",
    "message": "X-Tenant-ID header is required for all requests"
  }
}
```

**Authentication Error (401):**
```json
{
  "status": "error",
  "error": {
    "code": "UNAUTHORIZED",
    "message": "Invalid or missing API key"
  }
}
```

**Rate Limit Exceeded (429):**
```json
{
  "status": "error",
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Too many requests. Please retry after 60 seconds."
  }
}
```

---

## Security Features
- **Audit Logging:** All requests logged with request ID, hashed API key, payload hash, latency
- **Rate Limiting:** Per-tenant, per-API-key limits (configurable)
- **Payload Redaction:** PII/secrets automatically redacted from logs
- **Request ID Tracing:** Use `X-Request-ID` header for distributed tracing
- **Cryptographic Evidence:** SHA256 hashes for baseline, candidate, and test data

---

## Support & Documentation
- **API Docs (Swagger):** https://llmlab-t6zg.onrender.com/docs
- **API Docs (ReDoc):** https://llmlab-t6zg.onrender.com/redoc
- **OpenAPI Spec:** https://llmlab-t6zg.onrender.com/openapi.json

---

## Deployment Status
✅ **Production Ready** - Health checks passing, stealth diagnostics secured, audit logging enabled
