# Incident Report: payments-api Charge Failures (100% Failure Rate)

## Summary
At 2026-08-30T03:12:00.000Z, an alert fired for `payments-api` indicating a 100% charge failure rate over the last 4 minutes. Investigation revealed that a scheduled Vault secret rotation (`PAYGATE_API_KEY` v7 -> v8) occurred at 03:04 UTC and revoked the old key (`v7`). Because `payments-api` loads environment secrets at process start, it continued using the cached/in-memory `v7` key, resulting in HTTP 401 `invalid_api_key` errors from PayGate.

## Timeline
- **2026-08-30T03:01:00.000Z**: `payments-api` deployed version `payments-2.16.0` (retry jitter).
- **2026-08-30T03:04:00.000Z**: Vault scheduled 90-day secret rotation for `PAYGATE_API_KEY` from `v7` to `v8`. The old key `v7` was revoked at the vendor.
- **2026-08-30T03:08:00Z - 03:12:00Z**: `payments-api` continues making requests with expired key `v7`, causing 100% charge failures (401 Unauthorized).
- **2026-08-30T03:12:00.000Z**: Alert fires (`charge_failed rate 100% for 4m`).

## Root Cause
**secret_rotation**: The `PAYGATE_API_KEY` was rotated in Vault from version `v7` to `v8`, and the old key `v7` was revoked at the vendor. Since `payments-api` reads secrets at process start, it was holding onto the stale `v7` key in memory.

## Evidence
1. `recent_changes` showed Vault rotation of `PAYGATE_API_KEY v7 -> v8` at 03:04 UTC with note: *"consumers must reload the secret; payments-api reads it at process start"*.
2. `get_config` for `payments-api` confirmed `PAYGATE_API_KEY_VERSION: v7 (loaded at process start 3d ago)`.
3. `query_logs` for `payments-api` showed errors: `paygate request failed: status=401 body={"error":"invalid_api_key","key_version":"v7"}`.
4. `run_probe` confirmed `https://api.paygate.example/status` is healthy.

## Proposed Remediation
Restart the `payments-api` service to pick up the new `PAYGATE_API_KEY` version `v8` from Vault/environment. This is safe, standard operational procedure for secret rotations where apps load env vars at startup.
