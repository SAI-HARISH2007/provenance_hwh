# Incident Report: inventory-api 401 Rate Spike due to Clock Skew

## Summary
At 2026-08-30T03:12:00.000Z, `api-gateway` fired an alert for a 6.8% 401 error rate on `/v1/inventory/*` routes. Investigation revealed that `inventory-api` pods (recently rescheduled to node `inv-5` at 02:14 UTC) were rejecting valid JWTs signed after the `auth-api` key rotation at 02:31 UTC with `InvalidToken (claims check)` errors. Probing the clock on `inventory-api` revealed a significant time offset of -287.4 seconds with NTP daemon (`chronyd`) inactive.

## Timeline
- **2026-08-30T02:14:00Z**: `inventory-api` pods rescheduled from node `inv-2` to node `inv-5` during node maintenance.
- **2026-08-30T02:31:00Z**: `auth-api` rotated JWT signing key (`kid=2026-09b`).
- **2026-08-30T03:12:00Z**: Alert fires for 401 rate on `/v1/inventory/*`.
- **Investigation**: Logs showed `jwt verification failed: InvalidToken (claims check)` for tokens with `kid=2026-09b`. Clock probe on `inventory-api` (`inv-5`) showed an offset of -287.4s with `chronyd` inactive.

## Root Cause
**Clock skew** on node `inv-5` hosting `inventory-api`. Because the node's clock was behind by ~4.7 minutes, newly issued tokens (with `iat` / `nbf` timestamps corresponding to the current real time) appeared to be issued in the future from the perspective of `inventory-api`, causing JWT claims validation to fail.

## Evidence
- `get_alert`: `api-gateway` degraded due to 401 rate on `/v1/inventory/*`.
- `query_logs` (`inventory-api`): Frequent `jwt verification failed: InvalidToken (claims check)` warnings for `kid=2026-09b`.
- `run_probe` (`clock`, `inventory-api`): `ntp offset -287.4s — chronyd inactive (unit disabled)`.

## Proposed Remediation
Sync the clock on the affected node (`inv-5`) and enable/start `chronyd`. (Action: `sync_clock`)
