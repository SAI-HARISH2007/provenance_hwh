# Incident Report: Payments-API Outage

## Summary
At 2026-08-30T03:12:00.000Z, the `payments-api` service experienced a 100% charge failure rate after a recent deployment migrating to PayGate v2 endpoints. All outgoing requests to PayGate resulted in HTTP 404 errors due to an incorrect URL configuration.

## Timeline
- **2026-08-30T03:03:00.000Z**: `payments-api` deployed version `payments-2.15.0`, updating `PAYGATE_URL` to `https://api.paygate.example/v2/`.
- **2026-08-30T03:08:00.000Z**: Error rates begin spiking immediately following the deployment.
- **2026-08-30T03:12:00.000Z**: Alert fires indicating `payments-api` `charge_failed` rate is at 100% for 4 minutes.

## Root Cause
A bad configuration/deploy introduced an invalid or mistyped `PAYGATE_URL` path (`/v2/`), causing the downstream vendor API to return 404 Not Found responses for all charging requests.

## Evidence
- Recent changes log showing `PAYGATE_URL` update: `https://api.paygate.example -> https://api.paygate.example/v2/`
- `payments-api` logs showing continuous `paygate request failed: status=404` errors.
- `payments-api.error_rate_pct` metric jumping to ~100% right after 03:03 UTC.

## Remediation
Update the configuration for `payments-api` to correct the `PAYGATE_URL` endpoint to the proper path.

## Follow-ups
1. Verify PayGate v2 endpoint documentation and correct base pathing conventions.
2. Implement integration tests verifying external API connectivity and correct route resolution during CI/CD.