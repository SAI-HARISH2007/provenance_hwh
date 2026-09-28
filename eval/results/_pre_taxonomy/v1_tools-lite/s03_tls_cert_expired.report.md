# Incident Report: auth-api TLS Certificate Expiration

## Summary
At 2026-08-30T03:12:00Z, `api-gateway` fired a P1 alert indicating a 401/5xx error rate of 41% on authenticated routes. Investigation revealed that the `auth-api` service is down because its TLS certificate expired at 03:00:00Z.

## Timeline
- **02:20:00Z**: `orders-api` deploy (unrelated change).
- **03:00:00Z**: `auth-api` TLS certificate (`auth-api.internal`) expired (`notAfter=2026-08-30T03:00:00Z`).
- **03:12:00Z**: `api-gateway` alerts on high 401/5xx error rates due to `auth-api` being unreachable via TLS.

## Root Cause
`tls_cert_expired` on the `auth-api` service.

## Evidence
1. `get_alert`: `auth-api` is marked as down (`auth-1.5.0`).
2. `run_probe (kind: http)` on `auth-api`: `TLS handshake failed: certificate expired`.
3. `run_probe (kind: cert)` on `auth-api`: certificate expired 12 minutes ago (`notAfter=2026-08-30T03:00:00Z`).

## Proposed Remediation
Rotate the TLS certificate for `auth-api`. This is safe and directly addresses the expired certificate causing TLS handshakes to fail.

## Follow-ups
- Implement automated certificate renewal monitoring and alerting well before expiration.
