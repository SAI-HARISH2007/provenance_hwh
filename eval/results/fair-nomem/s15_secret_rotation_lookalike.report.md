# Incident Report: payments-api Secret Rotation Outage

## Summary
At 2026-08-30T03:12:00Z, `payments-api` began failing 100% of charge requests (P1 alert). Investigation revealed that a scheduled Vault secret rotation updated `PAYGATE_API_KEY` from version `v7` to `v8` and revoked `v7` at the vendor at 03:04:00Z. Because `payments-api` loads its API key into memory only at process start, the running service instances continued attempting payments using the revoked `v7` key, resulting in 401 Unauthorized responses from the Paygate API.

## Timeline
- **2026-08-30T03:01:00Z**: `payments-api` deployment (`payments-2.16.0`) shipped.
- **2026-08-30T03:04:00Z**: Vault scheduled 90-day secret rotation executed: `PAYGATE_API_KEY` rotated from `v7` to `v8` (old key `v7` revoked at vendor).
- **2026-08-30T03:12:00Z**: P1 alert fires (`charge_failed rate 100% for 4m`).
- **2026-08-30T03:15:00Z**: Investigation identifies running `payments-api` processes are still holding `v7`.

## Root Cause
`secret_rotation`: `payments-api` caches/reads secrets at process startup and does not support dynamic reloading upon rotation, causing authentication failures once Vault rotated and revoked the key upstream.

## Evidence
- `recent_changes`: Vault rotation log at `03:04:00.000Z` noting `PAYGATE_API_KEY v7 -> v8 (old key revoked at vendor)` and `consumers must reload the secret; payments-api reads it at process start`.
- `get_config` on `payments-api`: Shows `PAYGATE_API_KEY_VERSION: v7 (loaded at process start 3d ago)`.
- `query_logs` on `payments-api`: Continuous `status=401 body={"error":"invalid_api_key","key_version":"v7"}` errors.
- `run_probe`: Confirmed vendor is up (`200 OK`) and explicitly noted key `v7` is revoked and `v8` is active.

## Proposed Remediation
Restart `payments-api` to force a process restart, picking up the new `v8` secret from Vault. This is safe as `payments-api` is a stateless application layer.

## Follow-ups
- Implement dynamic secret reloading or a periodic secret refresh in `payments-api` to avoid required service restarts during Vault secret rotations.
