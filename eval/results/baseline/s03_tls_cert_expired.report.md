# Incident Report: Authenticated Route Outage

## Summary
At 2026-08-30T03:12:00.000Z, an alert fired for high 401/5xx error rates on authenticated routes at the `api-gateway`. Investigation revealed that the `auth-api` service is down and reporting TLS handshake errors.

## Timeline
- **02:53:32Z**: First `TLS handshake error` logged by `api-gateway` targeting `auth-api`.
- **03:12:00Z**: P1 alert triggered for 41% error rate on authenticated routes; `auth-api` confirmed down.

## Root Cause
The root cause is an expired TLS certificate on the `auth-api` service, preventing secure communication between the `api-gateway` and `auth-api`.

## Evidence
- `auth-api` status is `down` while other core data stores remain healthy.
- `auth-api` error rate spiked to 98%.
- Logs explicitly show: `ERROR api-gateway: upstream auth-api: TLS handshake error; retrying upstream`.

## Remediation
1. Rotate the expired TLS certificate on the `auth-api` service (`rotate_tls_cert`).
2. Verify health checks and connectivity recovery from `api-gateway`.

## Follow-ups
- Implement automated certificate expiration monitoring and alerting.
- Review certificate rotation tooling/runbooks.