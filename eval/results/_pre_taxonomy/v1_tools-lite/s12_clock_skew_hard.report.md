# Incident Report: Payments-API High Error Rate & 401s on Checkout

## Summary
At 2026-08-30T03:12:00Z, a P1 alert fired for `api-gateway` due to a high 401 rate (9.5%) on `/v1/checkout`, and `payments-api` was reported as degraded. Investigations revealed that `payments-api` on host `payments-3` had its system clock skewed by -412.3 seconds because `chronyd` was not running after a node reboot at 02:02Z. Consequently, JWT validation rejected incoming tokens due to `InvalidIssuedAt` (clock skew), causing widespread request failures.

## Timeline
- **2026-08-30T02:02:00Z**: `payments-api` host (`payments-3`) rebooted after kernel patch (by ops-bot). `chronyd` failed to start automatically, leaving the system clock unsynced.
- **2026-08-30T02:39:00Z**: `auth-api` deployed `auth-1.6.0` switching JWT signing to ES256 with dual-verify enabled.
- **2026-08-30T03:00:00Z**: Error rate on `payments-api` spiked from ~0.4% to ~90% as requests hit the unsynced pod and failed JWT `InvalidIssuedAt` checks.
- **2026-08-30T03:12:00Z**: P1 alert fired.

## Root Cause
**Clock Skew**: Following a host reboot, `chronyd` was not running on the `payments-api` node (`payments-3`), resulting in a 412.3-second clock skew that caused `InvalidIssuedAt` JWT validation failures.

## Evidence
- `run_probe(kind="clock", target="payments-api")`: `payments-api (node payments-3) ntp offset -412.3s — chronyd not running`
- `query_logs(service="payments-api", pattern="fail")`: Repeated `jwt verification failed: InvalidIssuedAt` log entries.
- `get_metrics(service="payments-api", metric="error_rate_pct")`: Sudden jump in error rate from ~0.4% to ~90% starting around 03:00Z.

## Proposed Remediation
- **Action**: `sync_clock` on `payments-api` (and ensure `chronyd` is enabled/started on node `payments-3`).
- **Safety**: Syncing the clock brings the server time back into agreement with `auth-api` and eliminates `InvalidIssuedAt` validation errors immediately without restarting stateful services or rolling back deployments.
