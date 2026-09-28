# Incident Report: Payments API Degradation

## Summary
At 2026-08-30T03:12:00.000Z, an alert fired for `payments-api` indicating high latency (p95 > 8s) and a failure rate of over 62%. Investigation revealed that the third-party payment gateway (`paygate`) is returning 503 errors and timing out, while the internal circuit breaker is turned off.

## Timeline
- **2026-08-30T02:50:32.000Z**: First Paygate timeout error logged in `payments-api`.
- **2026-08-30T02:52:04.000Z**: Paygate returns first 503 Service Unavailable ('upstream maintenance').
- **2026-08-30T03:12:00.000Z**: Alert fires as error rate reaches ~64.5% and latency p95 climbs above 8 seconds.

## Root Cause
Third-party payment gateway outage (`paygate`) compounded by an unmitigated client configuration where the circuit breaker is explicitly turned off (`'CIRCUIT_BREAKER': 'off'`).

## Evidence
- Logs show repeated `paygate request timeout after 8000ms` and `paygate 503 Service Unavailable body='upstream maintenance'`.  
- `payments-api` error rate spiked to 64.5%.  
- Config shows `CIRCUIT_BREAKER` set to `off`.

## Remediation
1. Enable the circuit breaker on `payments-api` to fast-fail requests and protect downstream callers.
2. Escalate to the third-party vendor regarding the Paygate outage.

## Follow-ups
- Ensure circuit breakers default to `on` across all API integrations.
- Implement automated fallback or graceful degradation when payment providers undergo maintenance.