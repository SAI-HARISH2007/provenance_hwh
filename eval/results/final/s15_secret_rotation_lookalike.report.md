# Incident Report: payments-api Down Due to Expired/Revoked Secret

## Summary
The `payments-api` service experienced a 100% failure rate on charges (`charge_failed rate 100%`) due to using a revoked API key (v7) when communicating with the payment gateway (`api.paygate.example`). A scheduled Vault secret rotation had rotated the key from v7 to v8 at 03:04 UTC, revoking v7 at the vendor. Because `payments-api` loads its API key only at process start, it continued using v7, resulting in 401 Unauthorized errors from the vendor.

## Timeline
- **2026-08-30T03:04:00Z**: Vault rotates `PAYGATE_API_KEY` from v7 to v8. Old key v7 is revoked at the vendor.
- **2026-08-30T03:12:00Z**: P1 Alert fires: `payments-api` charge_failed rate reaches 100%.

## Root Cause
`secret_rotation`: Vault rotated the API key from v7 to v8 and revoked v7. `payments-api` reads the secret at process startup and had not been restarted to pick up the new v8 key.

## Evidence
- `recent_changes`: `vault: scheduled 90-day rotation: PAYGATE_API_KEY v7 -> v8 (old key revoked at vendor)`
- `get_config` (payments-api): `PAYGATE_API_KEY_VERSION: v7 (loaded at process start 3d ago)`
- `query_logs` (payments-api): `status=401 body={"error":"invalid_api_key","key_version":"v7"}`
- `run_probe`: `GET https://api.paygate.example/status -> 200 in 133ms (vendor healthy; note: key v7 revoked 8 min ago, v8 active)`

## Proposed Remediation
Restart `payments-api` (`restart_service`) to force it to reload the latest environment variables / secrets from Vault (v8).
