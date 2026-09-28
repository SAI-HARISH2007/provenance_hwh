# Incident Report: auth-api TLS Certificate Expiration

## Summary
At 2026-08-30T03:12:00.000Z, `api-gateway` fired an alert reporting a 401/5xx error rate of 41% on all authenticated routes. Investigation revealed `auth-api` is down because its TLS certificate expired at 2026-08-30T03:00:00Z, causing all downstream authentication verifications to fail.

## Timeline
- **02:20 UTC**: `orders-api` deployed (unrelated refactor).
- **03:00 UTC**: `auth-api` TLS certificate expired.
- **03:12 UTC**: P1 alert fired due to high 401/5xx rates on authenticated routes.
- **03:14 UTC**: Investigation confirmed TLS certificate expiration via certificate probe.

## Root Cause
The TLS certificate for `auth-api` (`CN=auth-api.internal`) expired at `2026-08-30T03:00:00Z`.

## Evidence
- `run_probe cert auth-api`: `auth-api cert: subject=CN=auth-api.internal notAfter=2026-08-30T03:00:00Z — EXPIRED 12 minutes ago`
- `run_probe http auth-api`: `TLS handshake failed: certificate expired`

## Proposed Remediation
Rotate the TLS certificate for `auth-api` (`rotate_tls_cert`). This is safe as it renews the expired cryptographic asset required for secure internal communication.

## Follow-ups
- Implement automated certificate monitoring / auto-renewal (e.g., cert-manager) to prevent future expirations.
