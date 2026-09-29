# Incident Report: auth-api Certificate Expiration

## Summary
At 2026-08-30T03:12:00.000Z, `api-gateway` fired an alert for a 401/5xx error rate of 41% across authenticated routes. Investigation revealed that the `auth-api` service was down because its TLS certificate expired exactly at 03:00:00Z.

## Timeline
- **02:20:00Z**: `orders-api` deploy (unrelated refactor)
- **03:00:00Z**: `auth-api` TLS certificate expiration (`notAfter=2026-08-30T03:00:00Z`)
- **03:12:00Z**: P1 alert fired due to authentication failures across the API gateway

## Root Cause
`tls_cert_expired`: The TLS certificate for `auth-api` expired at 2026-08-30T03:00:00Z, causing all inbound TLS connections and token verification requests to fail with TLS handshake errors and subsequent 401/5xx errors at the gateway.

## Evidence
- `run_probe` on `http://auth-api.internal/health` returned `TLS handshake failed: certificate expired`.
- `run_probe cert auth-api` confirmed `notAfter=2026-08-30T03:00:00Z — EXPIRED 12 minutes ago`.

## Proposed Remediation
Rotate the TLS certificate for `auth-api` (`rotate_tls_cert`). This is safe, targeted, and directly resolves the handshake failures.
