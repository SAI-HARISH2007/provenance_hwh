# Incident Report: auth-api TLS Certificate Expiration

## Summary
At 2026-08-30T03:12:00Z, an alert fired for `api-gateway` reporting a 401/5xx error rate of 41% on all authenticated routes. Investigation revealed that `auth-api` was marked as `down` due to an expired TLS certificate.

## Timeline
- **02:20 UTC**: Last deploy (`orders-api`) occurred (unrelated).
- **03:00 UTC**: TLS certificate for `auth-api` (`CN=auth-api.internal`) expired (`notAfter=2026-08-30T03:00:00Z`).
- **03:00–03:03 UTC**: `auth-api` error rate jumped to ~96–103%.
- **03:12 UTC**: P1 alert fired.

## Root Cause
The TLS certificate for `auth-api` expired at `2026-08-30T03:00:00Z`, causing all TLS handshakes and requests to fail with certificate expiration errors, making `auth-api` completely unavailable and breaking authentication across the platform.

## Evidence
- `run_probe cert auth-api`: showed certificate expired 12 minutes ago (`notAfter=2026-08-30T03:00:00Z`).
- `run_probe http http://auth-api`: returned `TLS handshake failed: certificate expired`.
- `get_metrics error_rate_pct` for `auth-api`: showed a sudden jump from ~0.4% to 100% at 03:00 UTC.

## Proposed Remediation
Rotate the TLS certificate on `auth-api`.
Action: `rotate_tls_cert` on target `auth-api`.

## Follow-ups
- Implement automated TLS certificate monitoring and renewal (e.g., via cert-manager or automated alerting 7 days prior to expiry).