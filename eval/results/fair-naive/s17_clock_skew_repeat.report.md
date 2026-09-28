# Incident Report: inventory-api 401 Authentication Failures Due to Clock Skew

## Summary
At 2026-08-30T03:12:00Z, `api-gateway` raised a P2 alert for a 6.8% 401 error rate specifically on `/v1/inventory/*` routes, while `auth-api` and other services remained healthy. Investigation revealed that `inventory-api` pods (rescheduled during a node maintenance drain to node `inv-5` at 02:14 UTC) had an inactive NTP daemon (`chronyd` disabled) resulting in a clock offset of **-287.4 seconds** (~4.8 minutes slow). Because the clock was nearly 5 minutes behind, incoming JWT tokens issued by `auth-api` had `nbf` (not before) claims in the future relative to `inventory-api`'s local time, causing validation failure.

## Timeline
- **2026-08-30T02:14:00Z**: `inventory-api` pods rescheduled from node `inv-2` to `inv-5` due to node drain for maintenance. Node `inv-5` had chronyd disabled.
- **2026-08-30T02:31:00Z**: `auth-api` rotated JWT signing key (`kid=2026-09b`).
- **2026-08-30T02:54:52Z onwards**: `inventory-api` logs begin flooding with `jwt verification failed: InvalidToken (claims check)` as clients authenticated with new tokens whose `nbf`/`exp` claims fell outside `inventory-api`'s skewed clock window.
- **2026-08-30T03:12:00Z**: `api-gateway` fires P2 alert for 401 rate on `/v1/inventory/*`.

## Root Cause
`clock_skew` on the host node (`inv-5`) running `inventory-api` pods. Chronyd was inactive on node `inv-5`, causing a clock offset of -287.4s which failed JWT time-window validation (`nbf`/`exp`).

## Evidence
- `inventory-api` clock probe: `ntp offset -287.4s — chronyd inactive (unit disabled)`
- `auth-api` and `api-gateway` clock probes: NTP offset near 0.001s / 0.003s.
- `inventory-api` logs: Continuous `jwt verification failed: InvalidToken (claims check) sub=... kid=2026-09b`.
- `recent_changes`: Pods moved to `inv-5` at 02:14 UTC.

## Proposed Remediation
Sync clock / enable and start `chronyd` on node `inv-5` hosting `inventory-api`, or restart/reschedule the pods to a node with active NTP.
