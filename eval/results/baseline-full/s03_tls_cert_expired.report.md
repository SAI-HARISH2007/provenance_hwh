# Incident Report: Authenticated Route Outage

## Summary
At 2026-08-30T03:12:00.000Z, an alert fired indicating a 401/5xx error rate of 41% across all authenticated routes. The root cause was identified as TLS handshake failures when communicating with the `auth-api` service, which is currently down due to TLS certificate expiration or configuration issues.

## Timeline
- **02:52:05Z**: `orders-api` begins logging TLS handshake failures during auth introspection.
- **02:53:32Z**: `api-gateway` starts logging TLS handshake errors targeting `auth-api`.
- **03:12:00Z**: P1 Alert fires as error rates spike to over 40% on gateway and orders services.

## Root Cause
Expired or invalid TLS certificates/handshake failure on the `auth-api` service preventing upstream communication from `api-gateway` and `orders-api`.

## Evidence
- `auth-api` service status: `down`.
- `api-gateway` and `orders-api` error rates jumped from ~0.3% to ~41% around 03:12Z.
- Log errors: `ERROR api-gateway: upstream auth-api: TLS handshake error; retrying upstream`
- Log errors: `ERROR orders-api: auth introspection failed: tls handshake failure`

## Remediation
1. Rotate and renew the TLS certificate/keys on the `auth-api` service.
2. Restart `auth-api` to load the new certificate.

## Follow-ups
- Implement automated alerting for TLS certificate expiration well in advance of expiry.
- Review certificate management lifecycle tooling.