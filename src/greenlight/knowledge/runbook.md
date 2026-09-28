# On-call runbook (team memory)

This is the team's accumulated knowledge from past incidents. It is *retrieved* by the agent,
not hard-coded truth: it says what to check, never what the answer is.

## Symptom → first checks
- 5xx / timeouts on checkout: check `recent_changes` first (deploys, flags, infra), then the
  upstream named in gateway errors, then Postgres `connections_used` and `locks_waiting`.
- "connection slots reserved" / "QueuePool limit": Postgres connection budget. Ask *who* holds
  the connections (`run_probe db postgres`) — a new consumer (worker, migration) usually did.
- 401s while auth-api is healthy: compare *which* verifier fails. If only one service rejects
  tokens, suspect that host's clock (`run_probe clock <service>`) before suspecting auth.
- TLS / x509 errors: `run_probe cert <service>`; certificates expire at exact minutes.
- "No space left on device": `run_probe disk <service>`; look for a recent logging/config change.
- Vendor 5xx/timeouts: `run_probe http api.paygate.example` to separate *vendor down* from *we
  are calling it wrong* (404 = our URL/config) or *we are rate-limiting ourselves* (429 + a job).
- Latency up, cache hit-rate down, DB CPU up: Redis `evicted_keys_per_min` / `used_memory_pct`.
  Postgres is usually the victim, not the cause.
- "still waiting for … Lock": `run_probe db postgres` shows the blocking pid. Never restart
  Postgres to clear a lock.
- OOMKilled / restart loops: memory series + the most recent deploy of that service.
- "no such host": `run_probe dns <name>`; check infra changes (namespace moves, retired names).
- ValidationError for a *subset* of requests after a flag change: feature flag, not a deploy.

## Safety rules (consequential actions)
- Stateful services (postgres, redis): never `restart_service`; prefer targeted actions
  (`terminate_blocking_query`, `free_disk_space`, `increase_cache_memory`).
- Roll back only the change you have evidence for; rolling back an unrelated deploy can
  re-introduce fixed bugs (it has, twice).
- Do not `scale_out` a service that is leaking memory or holding connections — it multiplies
  the problem.
- Escalate to a vendor only after a probe shows the vendor itself is unhealthy.
- When a dependency moved (new hostname, new endpoint), fix the *caller's* config (`update_config`)
  rather than rolling back the caller's unrelated deploy.
- Every remediation requires human approval; include the evidence the approver needs.

## Verification standard
A root cause is *verified* only when a probe (`run_probe`) or a metric directly confirms the
mechanism (e.g. pool at 100/100 held by worker; clock offset -412s; cert notAfter in the past;
NXDOMAIN; disk 100%). Log lines alone are a hypothesis.
