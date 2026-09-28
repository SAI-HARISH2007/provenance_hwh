# Incident Report: Authenticated Route Outage

## Summary
At 2026-08-30T03:12:00.000Z, an alert fired indicating a 401/5xx error rate spike of 41% across authenticated routes at the api-gateway. Investigation revealed that the `auth-api` service is down due to TLS handshake failures.

## Timeline
- **02:53:32.000Z**: First TLS handshake error logged by api-gateway communicating with auth-api.
- **03:12:00.000Z**: P1 alert fires for high 401/5xx rate on authenticated routes.

## Root Cause
The root cause is an expired or misconfigured TLS certificate on the `auth-api` service, preventing the `api-gateway` from establishing a secure connection.

## Evidence
- `api-gateway` logs continuously report: `ERROR api-gateway: upstream auth-api: TLS handshake error; retrying upstream`
- `auth-api` service status is reported as `down` with an error rate of 98.05%.

## Remediation
1. Rotate/renew the TLS certificate on the `auth-api` service.
2. Verify TLS connectivity between `api-gateway` and `auth-api`.

## Follow-ups
- Implement automated certificate expiration monitoring and alerting (e.g., warning 30 days before expiry).
- Review certificate deployment pipelines.