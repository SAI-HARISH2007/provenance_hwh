# Incident Report: API Gateway Authentication Outage

## Summary
At 2026-08-30T03:12:00.000Z, the `api-gateway` reported a P1 alert indicating that the 401/5xx error rate reached ~41% across all authenticated routes. The root cause was identified as expired TLS certificates on the `auth-api` service, causing upstream TLS handshakes to fail and bringing down the authentication service.

## Timeline
- **02:53:32Z**: First `TLS handshake error` logged by `api-gateway` when communicating with `auth-api`.
- **03:12:00Z**: `api-gateway` fires P1 alert as error rates spike past 40%.
- **03:12:00Z**: Incident response initiated.

## Root Cause
The `auth-api` service TLS certificates expired or became invalid, causing the `api-gateway` to fail TLS handshakes when routing authenticated requests. This effectively disabled `auth-api` (status: down, error rate: 98%).

## Evidence
- Service status shows `auth-api` is `down` while other services remain healthy.
- `auth-api` error rate jumped to `98.046%`.
- Log entries in `api-gateway`: `ERROR api-gateway: upstream auth-api: TLS handshake error; retrying upstream`.

## Remediation
1. Rotate and deploy valid TLS certificates for the `auth-api` service.
2. Verify upstream connectivity and TLS handshakes from `api-gateway` to `auth-api`.

## Follow-ups
- Implement automated TLS certificate expiration monitoring and alerting (e.g., alert 30 days prior to expiration).
- Review certificate management automation (such as cert-manager or automated rotation scripts).