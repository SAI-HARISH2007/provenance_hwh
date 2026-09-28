# Incident Report: Payments-Api Degraded Due to Third-Party Outage

## Summary
At 2026-08-30T03:12:00.000Z, `payments-api` triggered a P1 page due to charge p95 latency exceeding 8s and a 62% failure rate. Investigation revealed that the third-party payment gateway (`api.paygate.example`) is experiencing an outage / upstream maintenance, returning 503 Service Unavailable responses and causing requests from `payments-api` to time out.

## Timeline
- **2026-08-30T02:52:31.000Z**: First 503 error received from `paygate` in `payments-api` logs.
- **2026-08-30T02:52:00Z - 02:55:00Z**: Latency spikes on `payments-api` as timeouts accumulate (p95 jumps from ~120ms to ~8000ms).
- **2026-08-30T03:12:00.000Z**: Alert fires (`payments-api` charge p95 > 8s and 62% failures).
- **Investigation**: Logs and HTTP probe to `https://api.paygate.example` confirm vendor outage ("Degraded performance — investigating").

## Root Cause
Third-party outage (`third_party_outage`). The external payment gateway `api.paygate.example` is returning 503 errors and timing out, while `payments-api` lacks an active circuit breaker to fast-fail traffic.

## Proposed Remediation
Enable the circuit breaker on `payments-api` (`enable_circuit_breaker`) to prevent request pileups and timeouts while waiting for the third party to recover. Escalate to the vendor as needed.

## Follow-ups
- Monitor third-party vendor status for recovery.
- Review default circuit breaker policies for external API integrations.
