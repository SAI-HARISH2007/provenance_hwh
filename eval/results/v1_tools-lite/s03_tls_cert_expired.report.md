# Incident Report: auth-api TLS Certificate Expiration

## Summary
At 2026-08-30T03:12:00.000Z, `api-gateway` fired a P1 alert due to a 41% 401/5xx error rate across authenticated routes. Investigation revealed that the `auth-api` service was down because its TLS certificate expired at `03:00:00Z`, causing all TLS handshakes and downstream authentication requests from the API gateway to fail.

## Timeline
- **02:20:00Z**: `orders-api` deploy shipped (unrelated).
- **03:00:00Z**: `auth-api` TLS certificate expired (`notAfter=2026-08-30T03:00:00Z`).
- **03:12:00Z**: `api-gateway` P1 alert fires (`401/5xx rate 41% on all authenticated routes`).
- **03:12:xxZ**: Investigation confirms `auth-api` certificate expired 12 minutes prior.

## Root Cause
`tls_cert_expired`: The TLS certificate for `auth-api` expired, preventing any secure connections or authentication validation.

## Evidence
1. `get_alert`: `auth-api` status is listed as `down`.
2. `run_probe (kind=http, target=auth-api)`: `TLS handshake failed: certificate expired`.
3. `run_probe (kind=cert, target=auth-api)`: `subject=CN=auth-api.internal notAfter=2026-08-30T03:00:00Z — EXPIRED 12 minutes ago`.

## Proposed Remediation
Rotate the TLS certificate for `auth-api` (`rotate_tls_cert`). This is safe as it re-establishes valid cryptographic identity and trust for the authentication service without modifying code or application state.

## Follow-ups
- Implement automated certificate renewal monitoring and alerting well in advance of expiration (e.g., 30 days and 7 days prior).
- Review certificate auto-renewal mechanisms for all internal services.