### Incident Report: Payments API 100% Charge Failure

**Summary:**
The `payments-api` service is experiencing a 100% charge failure rate, leading to a P1 alert. This issue started shortly after a recent deployment to migrate to PayGate v2 endpoints.

**Timeline:**
*   **2026-08-30T03:03:00Z:** `payments-api` version `payments-2.15.0` deployed, migrating to PayGate v2 endpoints and updating `PAYGATE_URL` to `https://api.paygate.example/v2/`.
*   **~2026-08-30T03:08:00Z:** `charge_failed` rate reached 100% (4 minutes before alert fired).
*   **2026-08-30T03:12:00Z:** P1 alert fired for `payments-api` due to 100% `charge_failed` rate. `payments-api` status is 'down', `api-gateway` is 'degraded'.

**Root Cause:**
The root cause is a `bad_config_deploy` to the `payments-api` service. The deployment introduced a new `PAYGATE_URL` pointing to `/v2/` endpoints, which are currently returning HTTP 404 "Not Found" errors, causing all payment requests to fail.

**Evidence:**
*   The alert explicitly states "charge_failed rate 100% for 4m" for `payments-api`.
*   `payments-api` service status is 'down' and its `error_rate_pct` spiked from 0.42% to 99.179%.
*   A recent deploy at `03:03:00Z` updated `payments-api` to version `payments-2.15.0` and changed `PAYGATE_URL` to `https://api.paygate.example/v2/`.
*   `payments-api` logs show repeated "paygate request failed: status=404" errors, indicating the new endpoint is not found.
*   `payments-api` latency significantly decreased (from ~123ms to ~43ms), consistent with requests failing quickly due to 404 responses.

**Remediation:**
Rollback the `payments-api` service to the previous stable version to revert the `PAYGATE_URL` change.

**Follow-ups:**
1.  Investigate why the PayGate v2 endpoints are returning 404s. Coordinate with the PayGate team or verify the correct v2 URL.
2.  Implement better pre-deployment validation for critical external API changes.
3.  Consider enabling circuit breakers (`CIRCUIT_BREAKER: 'off'`) to prevent cascading failures in similar scenarios.