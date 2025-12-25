#!/usr/bin/env bash
set -euo pipefail

payload_path="${1:-templates/client/validate_contract_invoice.json}"

base_url="${LLMLAB_API_BASE_URL:-${LLMLAB_API_BASE:-}}"
if [[ -z "${base_url}" ]]; then
  echo "ERROR: Set LLMLAB_API_BASE_URL (preferred) or LLMLAB_API_BASE" >&2
  exit 1
fi
if [[ -z "${LLMLAB_API_KEY:-}" ]]; then
  echo "ERROR: Set LLMLAB_API_KEY" >&2
  exit 1
fi
if [[ -z "${LLMLAB_TENANT_ID:-}" ]]; then
  echo "ERROR: Set LLMLAB_TENANT_ID" >&2
  exit 1
fi
if [[ ! -f "${payload_path}" ]]; then
  echo "ERROR: payload file not found: ${payload_path}" >&2
  exit 1
fi

url="${base_url%/}/api/contracts/validate"

curl -sS -X POST "${url}" \
  -H "Authorization: Bearer ${LLMLAB_API_KEY}" \
  -H "X-Tenant-ID: ${LLMLAB_TENANT_ID}" \
  -H "Content-Type: application/json" \
  -d @"${payload_path}" \
| python -m json.tool
