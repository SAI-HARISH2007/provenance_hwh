# Incident Report: API Gateway 401 Errors on Inventory Routes

## Summary
At 2026-08-30T03:12:00.000Z, an alert fired indicating an elevated 401 error rate (6.8%) on `/v1/inventory/*` routes through the `api-gateway`. The `inventory-api` service reports a degraded status with an error rate peaking near 74%.

## Timeline
- **2026-08-30T02:14:00.000Z**: `inventory-api` pods rescheduled from node `inv-2` to `inv-5` due to maintenance node drain.
- **2026-08-30T02:31:00.000Z**: `auth-api` rotated JWT signing key (`kid=2026-09b`).
- **2026-08-30T03:12:00.000Z**: Alert triggered for 401 rate spike on inventory routes.

## Root Cause
Elevated authentication/authorization failures occurring at the inventory service or downstream interactions following infrastructure node rescheduling.

## Evidence
- `inventory-api` error rate jumped from ~0.4% to 67.59%.
- `api-gateway` logs show multiple 401 responses on `/v1/inventory/*` paths upstreamed to `inventory-api`.

## Remediation
- Verify `inventory-api` pod health, environment variables, and token validation logic against the recent JWKS updates from `auth-api`.
- Monitor recovery as traffic re-balances.

## Follow-ups
- Investigate why pod rescheduling on `inventory-api` correlated with an increase in 401 responses.
- Ensure smooth propagation of JWKS keys across all backend services.