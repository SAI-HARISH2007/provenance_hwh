# Incident Report: Payments API Failure

## Summary
At 2026-08-30T03:12:00Z, the `payments-api` service triggered a P1 alert indicating a 100% charge failure rate. Investigation revealed that a recent deploy (`payments-2.15.0`) at 03:03:00Z migrated `PAYGATE_URL` to `https://api.paygate.example/v2/`, which resulted in 404 errors on outgoing requests to the payment gateway.

## Timeline
- **2026-08-30T03:03:00Z**: `payments-api: payments-2.15.0` deployed, updating `PAYGATE_URL` to `https://api.paygate.example/v2/`.
- **2026-08-30T03:12:00Z**: `payments-api` fires P1 alert: `charge_failed rate 100% for 4m`.

## Root Cause
A bad configuration deploy (`bad_config_deploy`) in `payments-api` introduced an incorrect PayGate v2 base URL/endpoint configuration (`https://api.paygate.example/v2/`), causing all charge requests to return HTTP 404 errors.

## Evidence
- Alert: `payments-api` service down, charge failure rate 100%.
- Recent changes: `payments-api` version `payments-2.15.0` deployed at 03:03:00Z migrated `PAYGATE_URL` to `https://api.paygate.example/v2/`.
- Logs: `payments-api` query logs consistently show `paygate request failed: status=404`.

## Proposed Remediation
Roll back the `payments-api` deploy (`rollback_deploy`) to the previous stable version (`payments-2.14.x`) to restore correct PayGate endpoint configuration and resume successful transaction processing.