# Incident Report: Authenticated Routes 5xx Outage

## Summary
At 2026-08-30T03:12:00.000Z, `api-gateway` triggered a P1 alert indicating a 401/5xx error rate spike of ~41% across all authenticated routes. The root cause is an expired or invalid TLS certificate on `auth-api`, leading to continuous TLS handshake failures across all upstream callers (`api-gateway` and `orders-api`).

## Timeline
- **02:52:05Z**: `orders-api` logs first `auth introspection failed: tls handshake failure` errors.
- **02:53:32Z**: `api-gateway` logs `upstream auth-api: TLS handshake error`.
- **03:12:00Z**: `api-gateway` error rate spikes to ~42%; P1 alert fires.

## Root Cause
`auth-api` TLS certificate has expired or is misconfigured, causing all TLS handshakes to fail and taking down authentication services (`auth-api` status: `down`).

## Evidence
- `auth-api.error_rate_pct` is at ~97% - 103%.
- Logs show repeated `TLS handshake error` and `auth introspection failed: tls handshake failure` targeting `auth-api`.

## Remediation
1. Rotate the TLS certificate on `auth-api` (`rotate_tls_cert`).
2. Verify health checks and error rates return to nominal levels.

## Follow-ups
- Implement automated certificate expiration monitoring and alerting.
- Review certificate rotation pipelines to prevent manual or automated expiry.