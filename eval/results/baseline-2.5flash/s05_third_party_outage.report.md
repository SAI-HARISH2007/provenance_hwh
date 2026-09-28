## Incident Report: Payments API Degradation

### Summary
The `payments-api` service is currently experiencing a P1 alert with significantly elevated error rates (64.5%) and high p95 latency (>8 seconds) for charge requests. This degradation is directly attributable to an outage or maintenance event at our external payment gateway, `paygate.example`.

### Timeline
*   **2026-08-29T23:12:00Z**: A deploy to `payments-api` (version `payments-2.14.0`) occurred, adding retry idempotency keys. This change does not appear to be related to the current incident.
*   **2026-08-30T02:42:00Z**: A feature flag change on `orders-api` (new_pricing_engine 5% -> 20%) occurred. This is unrelated to the `payments-api` issue.
*   **2026-08-30T02:50:32Z**: The first `paygate request timeout after 8000ms` error was observed in `payments-api` logs, indicating issues with the external payment gateway.
*   **2026-08-30T02:52:04Z**: The first `paygate 503 Service Unavailable body='upstream maintenance'` error was observed, explicitly stating the external service's status.
*   **2026-08-30T03:12:00Z**: The P1 alert for `payments-api` fired, indicating `charge p95 > 8s and 62% failures`.

### Root Cause
**`third_party_outage`**: The external payment gateway, `https://api.paygate.example`, is experiencing an outage or scheduled maintenance, leading to timeouts and 503 Service Unavailable responses for requests originating from our `payments-api`.

### Evidence
*   **Metrics**: `payments-api` shows a drastic increase in `error_rate_pct` from ~0.4% to 64.5% and `latency_p95_ms` from ~115ms to ~8171ms, directly matching the alert conditions.
*   **Logs**: `payments-api` logs are saturated with errors such as `ERROR payments-api: paygate request timeout after 8000ms url=https://api.paygate.example/charges` and `ERROR payments-api: paygate 503 Service Unavailable body='upstream maintenance'`. The 8000ms timeout matches the `PAYGATE_TIMEOUT_MS` configuration.
*   **Dependencies**: All internal services (`api-gateway`, `orders-api`, `inventory-api`, `auth-api`, `postgres`, `redis`, `worker`) show healthy metrics, ruling out internal resource contention or failures.

### Remediation
**`escalate_to_vendor`**: Contact the `paygate.example` vendor immediately to report the issue and inquire about their status. Check their public status page for updates.

### Follow-ups
1.  **Enable Circuit Breaker**: Implement and enable a circuit breaker for `payments-api`'s calls to `paygate.example` to prevent cascading failures and improve resilience during external service outages. The current `CIRCUIT_BREAKER` config is `off`.
2.  **Monitor Vendor Status**: Continuously monitor the `paygate.example` status page and communications for resolution updates.
3.  **Alternative Payment Methods**: Evaluate the feasibility of implementing alternative payment processing methods or graceful degradation strategies during future third-party outages.