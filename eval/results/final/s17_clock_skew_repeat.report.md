# Incident Report: inventory-api Clock Skew Causing JWT Validation Failures

## Summary
At 2026-08-30T03:12:00.000Z, an alert fired indicating a 401 rate of 6.8% on `/v1/inventory/*` via `api-gateway`, while `auth-api` and other routes remained healthy. Investigation revealed that `inventory-api` pods were recently rescheduled to a new node (`inv-5`) during maintenance, where time synchronization (`chronyd`) was inactive, resulting in a clock offset of ~-287.4 seconds. This clock skew caused JWT claims checks (such as `nbf` / `exp`) to fail for newly issued tokens (`kid=2026-09b`), returning 401 errors.

## Timeline
- **2026-08-30T02:14:00.000Z**: `inventory-api` pods rescheduled from node `inv-2` to node `inv-5` (node drain for maintenance).
- **2026-08-30T02:31:00.000Z**: `auth-api` rotates JWT signing key (`kid=2026-09b`).
- **2026-08-30T02:54:52.000Z**: `inventory-api` begins logging `jwt verification failed: InvalidToken (claims check)` warnings for tokens signed with `kid=2026-09b`.
- **2026-08-30T03:12:00.000Z**: Alert fires due to elevated 401 rate on `/v1/inventory/*`.

## Root Cause
**Clock skew** (`clock_skew`): The node `inv-5` hosting the rescheduled `inventory-api` pods had an inactive NTP daemon (`chronyd`), leading to a clock offset of -287.4 seconds. Because token validation relies on synchronized time to check time-based claims (`nbf` / `exp`), valid tokens were rejected as invalid.

## Evidence
1. **Logs**: `query_logs` for `inventory-api` showed repeated `jwt verification failed: InvalidToken (claims check)` warnings for tokens signed with `kid=2026-09b`.
2. **Probe**: `run_probe clock inventory-api` returned: `inventory-api (node inv-5) ntp offset -287.4s — chronyd inactive (unit disabled)`.

## Proposed Remediation
Sync the clock / enable and start `chronyd` on node `inv-5` (or restart/reschedule `inventory-api` to a properly synchronized node). We propose executing `sync_clock` on `inventory-api`.

## Follow-ups
- Ensure node bootstrap scripts ensure `chronyd` is enabled and running on all Kubernetes worker nodes.
- Add node-level clock skew monitoring alerts.
