### Incident Report: Payments API Degradation

#### Summary
At 2026-08-30T03:12:00.000Z, an alert fired for `payments-api` indicating high latency (p95 > 8s) and a ~62% failure rate. This propagated through the `api-gateway`, causing checkout requests to time out.

#### Timeline
- **02:50:32Z**: First `paygate request timeout` logged by `payments-api`.
- **02:52:03Z**: First `paygate 503 Service Unavailable body='upstream maintenance'` logged.
- **03:12:00Z**: Alert triggered as failure rates sustained around 60%-64% with p95 latency exceeding 8 seconds.

#### Root Cause
The third-party payment provider (`paygate`) is experiencing an outage / maintenance window (`upstream maintenance`), causing requests to time out at the configured 8-second limit.

#### Evidence
- Upstream HTTP 503 responses and timeouts from `https://api.paygate.example/charges`.
- `payments-api.error_rate_pct` metrics surging from <1% to ~64%.
- `api-gateway` showing downstream 504 Gateway Timeouts corresponding to upstream `payments-api` calls.

#### Remediation
1. Enable the circuit breaker on `payments-api` to fail fast instead of holding threads/connections and waiting for 8-second timeouts.
2. Escalate to the vendor (`paygate`) regarding the ongoing maintenance/outage.

#### Follow-ups
- Configure automatic circuit breaking and fallback responses for third-party payment dependencies.
- Review gateway timeout settings to prevent cascading thread exhaustion.