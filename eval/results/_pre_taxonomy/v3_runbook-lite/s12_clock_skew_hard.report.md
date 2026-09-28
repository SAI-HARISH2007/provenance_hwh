# Incident Report: Payments-API 401 Unauthorized Errors via Checkout

## Summary
The `api-gateway` triggered a P1 alert due to a 9.5% 401 error rate on `/v1/checkout`. While `auth-api` is healthy, requests routed through `payments-api` failed JWT verification with `InvalidIssuedAt` errors. Probing revealed that `payments-api` (running on node `payments-3`) has a clock offset of -412.3 seconds because `chronyd` is not running following a host reboot at 02:02 UTC.

## Timeline
- **02:02 UTC**: Node `payments-3` hosting `payments-api` rebooted after a kernel patch; chronyd failed to start, causing clock skew.
- **02:39 UTC**: `auth-api` deployed `auth-1.6.0` switching JWT signing to ES256 with dual-verify enabled.
- **03:12 UTC**: P1 alert fired for `api-gateway` 401 rate on `/v1/checkout`.

## Root Cause
`clock_skew`: The system clock on `payments-api` is out of sync by -412 seconds due to `chronyd` not running after a node reboot, causing JWT claims with `iat` in the "future" (relative to the skewed clock) to fail validation (`InvalidIssuedAt`).

## Evidence
- `run_probe clock payments-api`: `payments-api (node payments-3) ntp offset -412.3s — chronyd not running`
- `query_logs payments-api`: Frequent `jwt verification failed: InvalidIssuedAt` warnings.

## Proposed Remediation
Sync the clock on `payments-api` / start and enable `chronyd` on node `payments-3`.
