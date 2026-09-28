# Incident Report: inventory-api JWT 401 Unauthorized Errors Due to Clock Skew

## Summary
At 2026-08-30T03:12:00.000Z, a P2 page fired for `api-gateway` due to a 6.8% 401 error rate on `/v1/inventory/*` routes, while all other services and routes remained healthy. Investigation revealed that `inventory-api` pods (rescheduled to node `inv-5` at 02:14 UTC during maintenance) suffer from severe clock skew (-287.4 seconds offset, with `chronyd` inactive). Because `inventory-api`'s local clock is ~4.8 minutes behind actual time, newly issued JWTs signed with key `kid=2026-09b` (rotated at 02:31 UTC) fail `nbf` (not before) / claims validation checks, causing widespread 401 Unauthorized responses.

## Timeline
- **2026-08-30T02:14:00.000Z**: `ops-bot` reschedules `inventory-api` pods from node `inv-2` to node `inv-5` (node drain for maintenance).
- **2026-08-30T02:31:00.000Z**: `auth-api` rotates JWT signing key to `kid=2026-09b`.
- **2026-08-30T02:54:52.000Z**: `inventory-api` begins logging `jwt verification failed: InvalidToken (claims check)` for tokens with `kid=2026-09b`.
- **2026-08-30T03:12:00.000Z**: Alert fires on `api-gateway` for 401 rate on `/v1/inventory/*`.

## Root Cause
`clock_skew`: Node `inv-5` running `inventory-api` has a clock offset of -287.4 seconds and `chronyd` is inactive, causing validation failures for time-sensitive JWT claims.

## Evidence
- `get_alert`: `api-gateway` reporting 401 rate 6.8% on `/v1/inventory/*`.
- `recent_changes`: `inventory-api` pods rescheduled to node `inv-5` at 02:14 UTC.
- `query_logs`: `inventory-api` continuous `jwt verification failed: InvalidToken (claims check)` errors with `kid=2026-09b`.
- `run_probe` (clock): `inventory-api (node inv-5) ntp offset -287.4s — chronyd inactive (unit disabled)`.

## Proposed Remediation
Sync the system clock and enable/start `chronyd` on node `inv-5` hosting `inventory-api`, or restart the pods so they are scheduled on a node with correct time. Proposing `sync_clock` action on `inventory-api`.
