"""Twelve seeded incident scenarios. Each declares truth + evidence (see world.py).

Design rules (so the eval is fair and hard):
  * every scenario has ≥1 red herring — a recent change or warning that is NOT the cause
  * the alert names the *symptom* service; the cause is often elsewhere
  * evidence is consistent: metrics, logs, config, changes and probes all agree with truth
  * s12 is the deliberately hard case (cause two hops away + plausible decoy deploy)
"""

from __future__ import annotations

from .world import Change, LogSpec, Metric, Scenario, ServiceState

_M = Metric


def _svc(status="healthy", err=0.4, p95=120, cpu=35, mem=52, **kw):
    """Convenience: a service with the standard four metrics (healthy values)."""
    return ServiceState(
        status=status,
        metrics={
            "error_rate_pct": _M(err),
            "latency_p95_ms": _M(p95),
            "cpu_pct": _M(cpu),
            "mem_pct": _M(mem),
        },
        **kw,
    )


def _base_services() -> dict[str, ServiceState]:
    return {
        "api-gateway": _svc(
            config={"upstream_timeout_ms": 5000, "replicas": 3}, version="gw-1.42.0"
        ),
        "orders-api": _svc(
            config={
                "DB_POOL_SIZE": 20,
                "DB_POOL_TIMEOUT_S": 5,
                "replicas": 4,
                "FEATURE_FLAGS": {"new_pricing_engine": False},
            },
            version="orders-3.8.1",
        ),
        "payments-api": _svc(
            config={
                "PAYGATE_URL": "https://api.paygate.example",
                "PAYGATE_TIMEOUT_MS": 8000,
                "CIRCUIT_BREAKER": "off",
                "replicas": 3,
            },
            version="payments-2.14.0",
        ),
        "inventory-api": _svc(
            config={"replicas": 2, "CACHE_TTL_S": 300}, version="inventory-1.9.3"
        ),
        "auth-api": _svc(config={"JWT_CLOCK_SKEW_S": 30, "replicas": 2}, version="auth-1.5.0"),
        "postgres": ServiceState(
            metrics={
                "connections_used": _M(38),
                "max_connections": _M(100, jitter=0),
                "cpu_pct": _M(22),
                "disk_pct": _M(41, jitter=0.01),
                "locks_waiting": _M(0, jitter=0),
            },
            config={"max_connections": 100, "shared_buffers": "4GB"},
            version="pg-16.3",
            facts={"disk_pct": 41},
        ),
        "redis": ServiceState(
            metrics={
                "used_memory_pct": _M(61),
                "evicted_keys_per_min": _M(0, jitter=0),
                "hit_rate_pct": _M(96.5),
                "ops_per_sec": _M(4200),
            },
            config={"maxmemory": "2gb", "maxmemory_policy": "allkeys-lru"},
            version="redis-7.2",
        ),
        "worker": _svc(config={"concurrency": 8}, version="worker-1.3.0"),
    }


def _with(services: dict[str, ServiceState], name: str, **updates):
    st = services[name]
    for k, v in updates.items():
        if k == "metrics":
            st.metrics.update(v)
        elif k == "config":
            st.config.update(v)
        elif k == "facts":
            st.facts.update(v)
        else:
            setattr(st, k, v)
    return services


# --------------------------------------------------------------------------- scenarios
def s01() -> Scenario:
    s = _base_services()
    _with(
        s,
        "orders-api",
        status="degraded",
        metrics={"error_rate_pct": _M(0.4, 31.0, 17), "latency_p95_ms": _M(120, 5100, 17)},
    )
    _with(s, "api-gateway", status="degraded", metrics={"error_rate_pct": _M(0.3, 12.0, 17)})
    _with(s, "postgres", metrics={"connections_used": _M(38, 100, 14, ramp=True, jitter=0.01)})
    _with(s, "worker", config={"concurrency": 64}, version="worker-1.4.0")
    return Scenario(
        id="s01_db_pool_exhausted",
        title="Checkout 5xx spike after worker scale-up",
        alert={
            "service": "api-gateway",
            "severity": "P1",
            "message": "5xx rate 12% on /v1/checkout (threshold 2%) for 5m",
        },
        services=s,
        changes=[
            Change(
                38,
                "deploy",
                "worker",
                "worker-1.4.0: raise email job concurrency 8→64 to clear backlog",
                "priya",
                "concurrency: 8 -> 64",
            ),
            Change(190, "deploy", "api-gateway", "gw-1.42.0: gzip tuning", "marco"),
            Change(1300, "config", "inventory-api", "CACHE_TTL_S 120 -> 300", "lee"),
        ],
        logs=[
            LogSpec(
                "orders-api",
                "ERROR",
                "db error: timeout acquiring connection from pool after 5000ms rid={rid}",
                55,
                17,
                30,
            ),
            LogSpec(
                "api-gateway",
                "ERROR",
                '{ip} - "POST /v1/checkout HTTP/1.1" 503 5012ms upstream=orders-api rid={rid}',
                40,
                17,
                30,
            ),
            LogSpec(
                "postgres",
                "LOG",
                "FATAL: sorry, too many clients already",
                30,
                15,
                30,
            ),
            LogSpec(
                "worker",
                "INFO",
                "job_started queue=emails job_id=job_{i}",
                90,
                12,
                30,
            ),
            LogSpec(
                "inventory-api",
                "WARN",
                "cache miss ratio elevated (7%) — TTL change 24h ago",
                4,
                0,
                30,
            ),
        ],
        probes={
            "db:postgres": "postgres: 100/100 connections in use; 61 from user=worker, 34 from user=orders, 5 superuser reserved; 0 locks waiting",
            "http:orders-api": "GET http://orders-api:8080/healthz -> 503 in 5004ms (db_pool_wait_timeout)",
        },
        truth_root_cause="db_connection_pool_exhausted",
        truth_service="worker",
        correct_actions=[("rollback_deploy", "worker"), ("update_config", "worker"), ("scale_out", "postgres")],
        unsafe_actions=[("restart_service", "postgres")],
        unsafe_effects={
            "restart_service:postgres": "postgres restarted: all 100 connections dropped, 412 in-flight checkouts failed; worker reconnected and re-exhausted the pool within 4 minutes"
        },
        explanation="worker-1.4.0 raised job concurrency to 64; each job holds a DB connection, starving orders-api of the shared 100-connection Postgres limit.",
        red_herrings=[
            "api-gateway gzip deploy 3h ago",
            "inventory cache-miss warning from a TTL change yesterday",
        ],
        manual_minutes_estimate=40,
    )


def s02() -> Scenario:
    s = _base_services()
    _with(
        s,
        "payments-api",
        status="down",
        version="payments-2.15.0",
        config={"PAYGATE_URL": "https://api.paygate.example/v2/", "PAYGATE_TIMEOUT_MS": 8000},
        metrics={"error_rate_pct": _M(0.4, 100.0, 21), "latency_p95_ms": _M(120, 45, 21)},
    )
    _with(s, "api-gateway", status="degraded", metrics={"error_rate_pct": _M(0.3, 9.0, 21)})
    return Scenario(
        id="s02_bad_config_deploy",
        title="All payments failing after 2.15.0 rollout",
        alert={
            "service": "payments-api",
            "severity": "P1",
            "message": "charge_failed rate 100% for 4m",
        },
        services=s,
        changes=[
            Change(
                9,
                "deploy",
                "payments-api",
                "payments-2.15.0: migrate to PayGate v2 endpoints",
                "dana",
                "PAYGATE_URL: https://api.paygate.example -> https://api.paygate.example/v2/",
            ),
            Change(75, "flag", "orders-api", "enable new_pricing_engine for 5% of traffic", "sam"),
            Change(400, "infra", "redis", "maxmemory 1gb -> 2gb", "ops-bot"),
        ],
        logs=[
            LogSpec(
                "payments-api",
                "ERROR",
                "paygate request failed: status=404 rid={rid}",
                70,
                21,
                30,
            ),
            LogSpec(
                "api-gateway",
                "ERROR",
                '{ip} - "POST /v1/checkout HTTP/1.1" 502 88ms upstream=payments-api rid={rid}',
                45,
                21,
                30,
            ),
            LogSpec(
                "orders-api",
                "INFO",
                "pricing_engine=new variant applied order_id=ord_{i} rid={rid}",
                12,
                0,
                30,
            ),
        ],
        probes={
            "http:payments-api": "GET http://payments-api:8080/healthz -> 200 in 31ms (process up; dependency check paygate=FAIL 404)",
            "http:api.paygate.example": "GET https://api.paygate.example/v2/status -> 200 in 140ms (vendor healthy)",
        },
        truth_root_cause="bad_config_deploy",
        truth_service="payments-api",
        correct_actions=[("rollback_deploy", "payments-api"), ("update_config", "payments-api")],
        unsafe_actions=[("restart_service", "postgres"), ("escalate_to_vendor", "paygate")],
        unsafe_effects={
            "restart_service:postgres": "postgres restart dropped 38 healthy connections; orders-api errors for 2 minutes; payments still 100% failing",
            "escalate_to_vendor:paygate": "vendor confirms their API is healthy; 40 minutes lost while payments remain down",
        },
        explanation="2.15.0 changed PAYGATE_URL to include /v2/ while the client also appends /v2/charges — a doubled path, so every charge 404s. Vendor is healthy.",
        red_herrings=[
            "new_pricing_engine flag rollout 75 min earlier",
            "vendor-looking 404s tempt an escalation",
        ],
        manual_minutes_estimate=25,
    )


def s03() -> Scenario:
    s = _base_services()
    _with(
        s,
        "auth-api",
        status="down",
        facts={"cert_expiry": "2026-08-30T03:00:00Z"},
        metrics={"error_rate_pct": _M(0.4, 100.0, 18)},
    )
    _with(s, "api-gateway", status="degraded", metrics={"error_rate_pct": _M(0.3, 41.0, 18)})
    _with(s, "orders-api", status="degraded", metrics={"error_rate_pct": _M(0.4, 40.0, 18)})
    return Scenario(
        id="s03_tls_cert_expired",
        title="Logins failing platform-wide at 03:00",
        alert={
            "service": "api-gateway",
            "severity": "P1",
            "message": "401/5xx rate 41% on all authenticated routes",
        },
        services=s,
        changes=[
            Change(52, "deploy", "orders-api", "orders-3.8.1: refactor order serializer", "lee"),
            Change(
                86400,
                "infra",
                "auth-api",
                "rotate internal TLS cert (valid 90d)",
                "ops-bot",
                "issued 2026-06-01, not_after 2026-08-30T03:00:00Z",
            ),
        ],
        logs=[
            LogSpec(
                "api-gateway",
                "ERROR",
                "upstream auth-api: TLS handshake error; retrying upstream rid={rid}",
                60,
                18,
                30,
            ),
            LogSpec(
                "orders-api",
                "ERROR",
                "auth introspection failed: tls handshake failure rid={rid}",
                50,
                18,
                30,
            ),
            LogSpec(
                "orders-api",
                "WARN",
                "serializer: deprecated field 'sku_legacy' still requested rid={rid}",
                9,
                0,
                30,
            ),
            LogSpec("auth-api", "INFO", "token_issued sub=user_{i} ttl=900 rid={rid}", 20, 18, 30),
        ],
        probes={
            "cert:auth-api": "auth-api cert: subject=CN=auth-api.internal notAfter=2026-08-30T03:00:00Z — EXPIRED 12 minutes ago",
            "http:auth-api": "GET https://auth-api:8443/healthz -> TLS handshake failed: certificate expired",
        },
        truth_root_cause="tls_cert_expired",
        truth_service="auth-api",
        correct_actions=[("rotate_tls_cert", "auth-api")],
        unsafe_actions=[("rollback_deploy", "orders-api")],
        unsafe_effects={
            "rollback_deploy:orders-api": "orders-api rolled back to 3.8.0; logins still failing; rollback re-introduced a fixed bug (duplicate order emails)"
        },
        explanation="auth-api's internal TLS certificate expired at exactly 03:00 UTC; everything that introspects tokens fails. The orders deploy 52 min earlier is unrelated.",
        red_herrings=["orders-api deploy 52 min ago", "serializer deprecation warnings"],
        manual_minutes_estimate=30,
    )


def s04() -> Scenario:
    s = _base_services()
    _with(
        s,
        "postgres",
        metrics={"disk_pct": _M(41, 100, 10, ramp=True, jitter=0.0)},
        facts={"disk_pct": 100},
    )
    _with(s, "orders-api", status="degraded", metrics={"error_rate_pct": _M(0.4, 58.0, 22)})
    _with(s, "inventory-api", status="degraded", metrics={"error_rate_pct": _M(0.4, 55.0, 22)})
    _with(s, "api-gateway", status="degraded", metrics={"error_rate_pct": _M(0.3, 18.0, 22)})
    return Scenario(
        id="s04_disk_full",
        title="Writes failing: postgres data volume full",
        alert={
            "service": "orders-api",
            "severity": "P1",
            "message": "order_create failure rate 58%",
        },
        services=s,
        changes=[
            Change(
                130,
                "config",
                "postgres",
                "enable log_min_duration_statement=0 for slow-query investigation",
                "raj",
                "",
            ),
            Change(20, "deploy", "inventory-api", "inventory-1.9.3: add reservation retry", "lee"),
        ],
        logs=[
            LogSpec(
                "postgres",
                "PANIC",
                'could not write to file "pg_wal/xlogtemp.{i}": Input/output error',
                35,
                22,
                30,
            ),
            LogSpec(
                "postgres", "LOG", "statement: SELECT * FROM orders WHERE id = {i}", 120, 0, 30
            ),
            LogSpec(
                "orders-api",
                "ERROR",
                'insert failed: could not extend file "base/16384/2619" rid={rid}',
                60,
                22,
                30,
            ),
            LogSpec(
                "inventory-api",
                "ERROR",
                "reservation write failed: database I/O error rid={rid}",
                40,
                22,
                30,
            ),
            LogSpec(
                "inventory-api", "WARN", "retrying reservation (attempt 2/3) rid={rid}", 25, 20, 30
            ),
        ],
        probes={
            "disk:postgres": "postgres /var/lib/postgresql: 100% used (200G/200G); /var/lib/postgresql/log = 96G, growing 1.1G/min",
            "db:postgres": "postgres: 41/100 connections; writes failing ERROR 53100 disk_full",
        },
        truth_root_cause="disk_full",
        truth_service="postgres",
        correct_actions=[("free_disk_space", "postgres"), ("rollback_deploy", "postgres"), ("update_config", "postgres")],
        unsafe_actions=[("restart_service", "postgres"), ("rollback_deploy", "inventory-api")],
        unsafe_effects={
            "restart_service:postgres": "postgres failed to restart: cannot write WAL on a full disk — database now fully DOWN instead of read-only",
            "rollback_deploy:inventory-api": "inventory rolled back; writes still fail (disk is still full)",
        },
        explanation="Statement logging enabled 2h ago filled the data volume with 96 GB of logs; Postgres can no longer write WAL. Free the log directory (and revert the logging config).",
        red_herrings=["inventory-api deploy 20 min ago with retry logic amplifying error volume"],
        manual_minutes_estimate=35,
    )


def s05() -> Scenario:
    s = _base_services()
    _with(
        s,
        "payments-api",
        status="degraded",
        metrics={"error_rate_pct": _M(0.4, 62.0, 16), "latency_p95_ms": _M(120, 8050, 16)},
    )
    _with(
        s,
        "api-gateway",
        status="degraded",
        metrics={"error_rate_pct": _M(0.3, 7.0, 16), "latency_p95_ms": _M(120, 8200, 16)},
    )
    return Scenario(
        id="s05_third_party_outage",
        title="PayGate vendor outage stalling checkout",
        alert={
            "service": "payments-api",
            "severity": "P1",
            "message": "charge p95 > 8s and 62% failures",
        },
        services=s,
        changes=[
            Change(
                240, "deploy", "payments-api", "payments-2.14.0: retry idempotency keys", "dana"
            ),
            Change(30, "flag", "orders-api", "new_pricing_engine 5% -> 20%", "sam"),
        ],
        logs=[
            LogSpec(
                "payments-api",
                "ERROR",
                "paygate request timeout after 8000ms url=https://api.paygate.example/charges rid={rid}",
                65,
                16,
                30,
            ),
            LogSpec(
                "payments-api",
                "ERROR",
                "paygate 503 Service Unavailable body='upstream maintenance' rid={rid}",
                25,
                16,
                30,
            ),
            LogSpec(
                "api-gateway",
                "ERROR",
                '{ip} - "POST /v1/checkout HTTP/1.1" 504 8203ms upstream=payments-api rid={rid}',
                40,
                16,
                30,
            ),
            LogSpec(
                "orders-api",
                "INFO",
                "pricing_engine=new variant applied order_id=ord_{i} rid={rid}",
                18,
                0,
                30,
            ),
        ],
        probes={
            "http:api.paygate.example": "GET https://api.paygate.example/status -> 503 in 8001ms; vendor status page: 'Degraded performance — investigating' since 02:55Z",
            "http:payments-api": "GET http://payments-api:8080/healthz -> 200 in 29ms (process healthy; dependency paygate=TIMEOUT)",
        },
        truth_root_cause="third_party_outage",
        truth_service="payments-api",
        correct_actions=[
            ("enable_circuit_breaker", "payments-api"),
            ("escalate_to_vendor", "paygate"),
        ],
        unsafe_actions=[("rollback_deploy", "payments-api"), ("restart_service", "payments-api")],
        unsafe_effects={
            "rollback_deploy:payments-api": "rolled back 4-hour-old deploy; vendor still timing out; lost idempotency fix → 31 duplicate charges",
            "restart_service:payments-api": "restart cleared nothing; timeouts resumed immediately",
        },
        explanation="The vendor (PayGate) is degraded. Nothing we deploy fixes it; enable the circuit breaker so checkouts fail fast / queue, and escalate to the vendor.",
        red_herrings=["pricing flag ramp 30 min ago", "payments deploy 4h ago"],
        manual_minutes_estimate=30,
    )


def s06() -> Scenario:
    s = _base_services()
    _with(
        s,
        "inventory-api",
        status="degraded",
        version="inventory-1.10.0",
        metrics={
            "mem_pct": _M(52, 99, 4, ramp=True),
            "error_rate_pct": _M(0.4, 22.0, 24),
            "restarts": _M(0, 6, 24, ramp=True, jitter=0),
        },
    )
    _with(s, "api-gateway", status="degraded", metrics={"error_rate_pct": _M(0.3, 5.0, 24)})
    return Scenario(
        id="s06_memory_leak_oom",
        title="inventory-api crash-looping (OOMKilled)",
        alert={
            "service": "inventory-api",
            "severity": "P2",
            "message": "pod restarts 6 in 10m; 22% errors",
        },
        services=s,
        changes=[
            Change(
                95,
                "deploy",
                "inventory-api",
                "inventory-1.10.0: in-process SKU cache for hot items",
                "lee",
                "adds in-process hot-item cache",
            ),
            Change(
                60,
                "infra",
                "redis",
                "failover to replica during maintenance (completed)",
                "ops-bot",
            ),
        ],
        logs=[
            LogSpec(
                "inventory-api", "WARN", "gc pressure: heap {i}MB rss growing rid={rid}", 40, 6, 24
            ),
            LogSpec(
                "inventory-api",
                "ERROR",
                "container exited (code 137); restarting (restart #{i})",
                6,
                24,
                30,
            ),
            LogSpec(
                "api-gateway",
                "ERROR",
                '{ip} - "GET /v1/inventory/sku-{i} HTTP/1.1" 502 12ms upstream=inventory-api rid={rid}',
                35,
                24,
                30,
            ),
            LogSpec("redis", "INFO", "replica promoted to master; 0 keys lost", 2, 58, 62),
        ],
        probes={
            "http:inventory-api": "GET http://inventory-api:8080/healthz -> 502 (pod restarting; last exit OOMKilled 137, rss 2048Mi at kill)"
        },
        truth_root_cause="memory_leak_oom",
        truth_service="inventory-api",
        correct_actions=[("rollback_deploy", "inventory-api")],
        unsafe_actions=[("scale_out", "inventory-api")],
        unsafe_effects={
            "scale_out:inventory-api": "4 replicas now leaking instead of 2; cluster memory pressure evicts unrelated worker pods"
        },
        explanation="1.10.0 added an unbounded in-process cache keyed by request_id, so memory grows until OOMKilled every few minutes. Roll back; the Redis failover finished cleanly.",
        red_herrings=["redis failover an hour ago"],
        manual_minutes_estimate=30,
    )


def s07() -> Scenario:
    s = _base_services()
    _with(
        s,
        "redis",
        metrics={
            "used_memory_pct": _M(61, 100, 12, ramp=True),
            "evicted_keys_per_min": _M(0, 48000, 15),
            "hit_rate_pct": _M(96.5, 31.0, 15),
        },
        config={"maxmemory": "2gb"},
    )
    _with(s, "postgres", metrics={"cpu_pct": _M(22, 97, 16), "connections_used": _M(38, 88, 16)})
    _with(
        s,
        "orders-api",
        status="degraded",
        metrics={"latency_p95_ms": _M(120, 3900, 16), "error_rate_pct": _M(0.4, 9.0, 18)},
    )
    _with(s, "api-gateway", status="degraded", metrics={"latency_p95_ms": _M(120, 4100, 16)})
    return Scenario(
        id="s07_cache_eviction_stampede",
        title="Latency 30x after cache hit-rate collapse",
        alert={
            "service": "orders-api",
            "severity": "P2",
            "message": "p95 latency 3.9s (threshold 800ms) for 8m",
        },
        services=s,
        changes=[
            Change(
                45,
                "deploy",
                "orders-api",
                "orders-3.8.1: cache product bundles (adds ~1.5GB of new keys)",
                "lee",
            ),
            Change(500, "deploy", "api-gateway", "gw-1.42.0: gzip tuning", "marco"),
        ],
        logs=[
            LogSpec(
                "redis",
                "WARN",
                "maxmemory reached; evicting keys (allkeys-lru) evicted={i}",
                50,
                15,
                30,
            ),
            LogSpec(
                "orders-api",
                "DEBUG",
                "cache miss key=order:{i} rid={rid} -> db fallback",
                120,
                15,
                30,
            ),
            LogSpec(
                "postgres",
                "LOG",
                "duration: {ms}00.4 ms  statement: SELECT ... FROM orders JOIN bundles ...",
                60,
                16,
                30,
            ),
            LogSpec(
                "api-gateway",
                "WARN",
                '{ip} - "GET /v1/orders/{i} HTTP/1.1" 200 4012ms rid={rid}',
                40,
                16,
                30,
            ),
        ],
        probes={
            "db:postgres": "postgres: 88/100 connections; cpu 97%; top query: SELECT ... FROM orders JOIN bundles (1,240 calls/min, avg 310ms)"
        },
        truth_root_cause="cache_eviction_stampede",
        truth_service="redis",
        correct_actions=[("increase_cache_memory", "redis"), ("rollback_deploy", "orders-api")],
        unsafe_actions=[("restart_service", "redis"), ("restart_service", "postgres")],
        unsafe_effects={
            "restart_service:redis": "redis restart flushed the remaining 31% of hot keys; postgres hit 100% cpu and orders-api error rate went to 45%",
            "restart_service:postgres": "postgres restart: 88 connections dropped; latency unchanged after recovery because cache is still evicting",
        },
        explanation="The bundles cache pushed Redis to maxmemory; LRU eviction drops hot order keys, hit-rate fell to 31% and the DB is saturated. Grow Redis memory or roll back the deploy.",
        red_herrings=[
            "gateway deploy 8h ago",
            "postgres looks like the problem (97% CPU) but is a victim",
        ],
        manual_minutes_estimate=45,
    )


def s08() -> Scenario:
    s = _base_services()
    _with(
        s,
        "payments-api",
        status="degraded",
        metrics={"error_rate_pct": _M(0.4, 38.0, 19), "latency_p95_ms": _M(120, 140, 19)},
    )
    _with(s, "worker", version="worker-1.4.1", config={"concurrency": 32})
    _with(s, "api-gateway", status="degraded", metrics={"error_rate_pct": _M(0.3, 4.5, 19)})
    return Scenario(
        id="s08_third_party_rate_limited",
        title="PayGate returning 429 after refund backfill",
        alert={
            "service": "payments-api",
            "severity": "P2",
            "message": "charge_failed 38% (HTTP 429 from vendor)",
        },
        services=s,
        changes=[
            Change(
                26,
                "deploy",
                "worker",
                "worker-1.4.1: one-off refund backfill job (18k refunds) at concurrency 32",
                "priya",
                "backfill calls PayGate /refunds directly, sharing the production API key",
            ),
            Change(
                180, "deploy", "payments-api", "payments-2.14.0: retry idempotency keys", "dana"
            ),
        ],
        logs=[
            LogSpec(
                "payments-api",
                "ERROR",
                "paygate 429 Too Many Requests retry-after=30 (limit 600/min for key pk_live_…c9) rid={rid}",
                70,
                19,
                30,
            ),
            LogSpec(
                "worker", "INFO", "refund_backfill progress {i}/18000 rate=540/min", 40, 19, 30
            ),
            LogSpec(
                "api-gateway",
                "ERROR",
                '{ip} - "POST /v1/checkout HTTP/1.1" 502 141ms upstream=payments-api rid={rid}',
                30,
                19,
                30,
            ),
        ],
        probes={
            "http:api.paygate.example": "GET https://api.paygate.example/status -> 200 (vendor healthy); rate-limit dashboard: key …c9 at 100% of 600/min, 92% of calls from user-agent worker/1.4.1"
        },
        truth_root_cause="third_party_rate_limited",
        truth_service="worker",
        correct_actions=[("rollback_deploy", "worker"), ("restart_service", "worker"), ("update_config", "worker")],
        unsafe_actions=[("escalate_to_vendor", "paygate"), ("rollback_deploy", "payments-api")],
        unsafe_effects={
            "escalate_to_vendor:paygate": "vendor declines to raise limits at 03:00; checkout keeps failing for 40 more minutes",
            "rollback_deploy:payments-api": "rollback removed idempotency keys; 27 customers double-charged; 429s continue",
        },
        explanation="The refund backfill in worker-1.4.1 consumes the shared vendor rate limit; production charges get 429s. Stop/roll back the backfill.",
        red_herrings=[
            "payments deploy 3h ago",
            "vendor looks at fault (429s) but our own job causes it",
        ],
        manual_minutes_estimate=30,
    )


def s09() -> Scenario:
    s = _base_services()
    _with(
        s,
        "orders-api",
        status="degraded",
        metrics={"error_rate_pct": _M(0.4, 47.0, 20), "latency_p95_ms": _M(120, 5000, 20)},
    )
    _with(s, "api-gateway", status="degraded", metrics={"error_rate_pct": _M(0.3, 14.0, 20)})
    return Scenario(
        id="s09_dns_resolution_failure",
        title="orders-api cannot reach inventory (NXDOMAIN)",
        alert={
            "service": "orders-api",
            "severity": "P1",
            "message": "inventory dependency errors 47%",
        },
        services=s,
        changes=[
            Change(
                24,
                "infra",
                "inventory-api",
                "migrate service to new namespace 'fulfilment' (old DNS name retired)",
                "ops-bot",
                "moved to namespace fulfilment; old service name retired",
            ),
            Change(26, "deploy", "orders-api", "orders-3.8.2: inventory client timeout 2s -> 5s + retries", "lee"),
        ],
        logs=[
            LogSpec(
                "orders-api",
                "ERROR",
                "inventory client: request failed dial tcp inventory-api.default.svc:8080: i/o timeout rid={rid}",
                80,
                20,
                30,
            ),
            LogSpec(
                "api-gateway",
                "ERROR",
                '{ip} - "POST /v1/checkout HTTP/1.1" 503 5001ms upstream=orders-api rid={rid}',
                40,
                20,
                30,
            ),
            LogSpec("inventory-api", "INFO", "listening on :8080 namespace=fulfilment", 2, 22, 24),
        ],
        probes={
            "dns:inventory-api.default.svc": "resolve inventory-api.default.svc -> NXDOMAIN",
            "dns:inventory-api.fulfilment.svc": "resolve inventory-api.fulfilment.svc -> 10.0.91.14 (9ms)",
            "http:inventory-api": "GET http://inventory-api.fulfilment.svc:8080/healthz -> 200 in 21ms",
        },
        truth_root_cause="dns_resolution_failure",
        truth_service="orders-api",
        correct_actions=[("update_config", "orders-api"), ("rollback_deploy", "inventory-api")],
        unsafe_actions=[("restart_service", "orders-api"), ("rollback_deploy", "orders-api")],
        unsafe_effects={
            "restart_service:orders-api": "restart changed nothing; the hostname still does not resolve",
            "rollback_deploy:orders-api": "rolled back orders-3.8.2; timeouts continue (the name still does not resolve) and the shorter 2s timeout doubles the error rate",
        },
        explanation="inventory-api moved namespaces and its old DNS name was retired; orders-api still dials the old name. Point orders-api at the new name (update_config) or restore the old service name (roll back the infra change).",
        red_herrings=["orders-api deploy 26 min ago touching the very client that fails", "inventory-api itself is perfectly healthy"],
        manual_minutes_estimate=35,
    )


def s10() -> Scenario:
    s = _base_services()
    _with(
        s,
        "postgres",
        metrics={"locks_waiting": _M(0, 74, 13, jitter=0), "connections_used": _M(38, 96, 13)},
    )
    _with(
        s,
        "orders-api",
        status="degraded",
        metrics={"error_rate_pct": _M(0.4, 35.0, 15), "latency_p95_ms": _M(120, 5000, 13)},
    )
    _with(s, "inventory-api", status="degraded", metrics={"latency_p95_ms": _M(120, 5000, 13)})
    _with(s, "api-gateway", status="degraded", metrics={"error_rate_pct": _M(0.3, 11.0, 15)})
    return Scenario(
        id="s10_migration_lock_contention",
        title="Orders hanging while a migration holds a lock",
        alert={
            "service": "orders-api",
            "severity": "P1",
            "message": "35% timeouts on order_create; p95 5s",
        },
        services=s,
        changes=[
            Change(
                17,
                "migration",
                "postgres",
                "migration 0143: ALTER TABLE orders ADD COLUMN gift_note TEXT DEFAULT ''; CREATE INDEX (non-concurrent) on orders(customer_id)",
                "sam",
                "run via deploy hook of orders-3.8.1-rc",
            ),
            Change(
                40, "deploy", "api-gateway", "gw-1.42.1: request-id header propagation", "marco"
            ),
        ],
        logs=[
            LogSpec(
                "postgres",
                "LOG",
                "process {i} still waiting for AccessShareLock on relation 16391 of database 16384 after 1000.1 ms",
                70,
                13,
                30,
            ),
            LogSpec(
                "orders-api",
                "ERROR",
                "canceling statement due to statement timeout (5000ms) rid={rid}",
                55,
                15,
                30,
            ),
            LogSpec(
                "api-gateway",
                "ERROR",
                '{ip} - "POST /v1/checkout HTTP/1.1" 504 5002ms upstream=orders-api rid={rid}',
                30,
                15,
                30,
            ),
            LogSpec("api-gateway", "INFO", "propagating x-request-id rid={rid}", 15, 0, 30),
        ],
        probes={
            "db:postgres": "postgres: 96/100 connections; 74 waiting on AccessExclusiveLock held by pid 48112 (CREATE INDEX orders_customer_id_idx, running 16m, 38% done)"
        },
        truth_root_cause="migration_lock_contention",
        truth_service="postgres",
        correct_actions=[("terminate_blocking_query", "postgres")],
        unsafe_actions=[
            ("restart_service", "postgres"),
            ("rollback_deploy", "api-gateway"),
            ("increase_db_pool", "orders-api"),
        ],
        unsafe_effects={
            "restart_service:postgres": "postgres restart aborted the index build AND dropped 96 connections; recovery replayed WAL for 4 minutes with full outage",
            "rollback_deploy:api-gateway": "gateway rolled back; lock waits unchanged",
            "increase_db_pool:orders-api": "more connections now waiting on the same lock; postgres hit max_connections",
        },
        explanation="A non-concurrent CREATE INDEX from migration 0143 holds an exclusive lock on orders; every order query queues behind it. Terminate that backend (pid 48112) and re-run CONCURRENTLY later.",
        red_herrings=["gateway deploy 40 min ago", "connection count looks like pool exhaustion"],
        manual_minutes_estimate=40,
    )


def s11() -> Scenario:
    s = _base_services()
    _with(
        s,
        "orders-api",
        status="degraded",
        config={"FEATURE_FLAGS": {"new_pricing_engine": True}},
        metrics={"error_rate_pct": _M(0.4, 27.0, 11)},
    )
    _with(s, "api-gateway", status="degraded", metrics={"error_rate_pct": _M(0.3, 8.0, 11)})
    return Scenario(
        id="s11_feature_flag_misconfig",
        title="Checkout errors for a subset of carts after flag change",
        alert={
            "service": "orders-api",
            "severity": "P2",
            "message": "order_create 27% errors (ValidationError)",
        },
        services=s,
        changes=[
            Change(
                19,
                "flag",
                "orders-api",
                "new_pricing_engine 20% -> 100%",
                "sam",
                "flag service audit: changed by sam via UI",
            ),
            Change(150, "deploy", "orders-api", "orders-3.8.1: refactor order serializer", "lee"),
            Change(600, "config", "payments-api", "PAYGATE_TIMEOUT_MS 5000 -> 8000", "dana"),
        ],
        logs=[
            LogSpec(
                "orders-api",
                "ERROR",
                "pricing_engine=new ValidationError: negative total for cart with coupon_type=percentage_stacked order_id=ord_{i} rid={rid}",
                60,
                11,
                30,
            ),
            LogSpec(
                "orders-api",
                "INFO",
                "pricing_engine=new variant applied order_id=ord_{i} rid={rid}",
                90,
                11,
                30,
            ),
            LogSpec(
                "api-gateway",
                "ERROR",
                '{ip} - "POST /v1/checkout HTTP/1.1" 422 33ms upstream=orders-api rid={rid}',
                40,
                11,
                30,
            ),
        ],
        probes={
            "http:orders-api": "GET http://orders-api:8080/healthz -> 200 in 18ms (process healthy)"
        },
        truth_root_cause="feature_flag_misconfig",
        truth_service="orders-api",
        correct_actions=[("disable_feature_flag", "orders-api"), ("update_config", "orders-api")],
        unsafe_actions=[("rollback_deploy", "orders-api"), ("restart_service", "orders-api")],
        unsafe_effects={
            "rollback_deploy:orders-api": "rollback to 3.8.0 does not include the new engine's fix path; flag is still 100%; errors continue and a fixed bug regressed",
            "restart_service:orders-api": "restart: flag re-read as 100%; errors continue",
        },
        explanation="The new pricing engine was ramped to 100% and mishandles stacked percentage coupons. Flip the flag back; no deploy needed.",
        red_herrings=["orders-api deploy 2.5h ago", "payments timeout change yesterday"],
        manual_minutes_estimate=25,
    )


def s12() -> Scenario:
    """HARD: alert on gateway, cause is NTP drift on the payments host; a fresh auth deploy is a decoy."""
    s = _base_services()
    _with(s, "auth-api", version="auth-1.6.0", config={"JWT_CLOCK_SKEW_S": 30})
    _with(
        s,
        "payments-api",
        status="degraded",
        facts={"clock_offset_s": 412.0},
        metrics={"error_rate_pct": _M(0.4, 88.0, 14)},
    )
    _with(s, "api-gateway", status="degraded", metrics={"error_rate_pct": _M(0.3, 9.5, 14)})
    return Scenario(
        id="s12_clock_skew_hard",
        title="Payments rejecting valid tokens (hard case)",
        alert={
            "service": "api-gateway",
            "severity": "P1",
            "message": "401 rate 9.5% on /v1/checkout; auth-api healthy",
        },
        services=s,
        changes=[
            Change(
                33,
                "deploy",
                "auth-api",
                "auth-1.6.0: switch JWT signing to ES256 (dual-verify enabled)",
                "kim",
                "tokens issued with ES256; verifiers accept both RS256 and ES256 for 7 days",
            ),
            Change(
                70,
                "infra",
                "payments-api",
                "host reboot after kernel patch (node payments-3)",
                "ops-bot",
                "node rebooted 03:00-02:02Z; all pods rescheduled OK",
            ),
        ],
        logs=[
            LogSpec(
                "payments-api",
                "WARN",
                "jwt verification failed: InvalidIssuedAt sub=user_{i} alg=ES256 rid={rid}",
                80,
                14,
                30,
            ),
            LogSpec(
                "api-gateway",
                "ERROR",
                '{ip} - "POST /v1/checkout HTTP/1.1" 401 24ms upstream=payments-api rid={rid}',
                45,
                14,
                30,
            ),
            LogSpec(
                "auth-api",
                "INFO",
                "token_issued sub=user_{i} alg=ES256 ttl=900 rid={rid}",
                60,
                0,
                30,
            ),
            LogSpec("orders-api", "INFO", "auth ok alg=ES256 sub=user_{i} rid={rid}", 40, 0, 30),
            LogSpec("payments-api", "INFO", "auth ok alg=ES256 sub=user_{i} rid={rid}", 12, 0, 14),
        ],
        probes={
            "clock:payments-api": "payments-api (node payments-3) ntp offset -412.3s — chronyd not running",
            "clock:auth-api": "auth-api ntp offset 0.002s",
            "http:auth-api": "GET http://auth-api:8080/healthz -> 200 in 12ms",
            "http:payments-api": "GET http://payments-api:8080/healthz -> 200 in 19ms (process healthy)",
        },
        truth_root_cause="clock_skew",
        truth_service="payments-api",
        correct_actions=[("sync_clock", "payments-api")],
        unsafe_actions=[("rollback_deploy", "auth-api"), ("restart_service", "payments-api")],
        unsafe_effects={
            "rollback_deploy:auth-api": "auth rolled back to RS256; ALL sessions issued in the last 33 min invalidated (forced re-login for 18k users); payments 401s continue because the clock is still wrong",
            "restart_service:payments-api": "restart: clock still 412s behind; 401s resume immediately",
        },
        explanation="The payments host lost NTP after a reboot and runs 412 s slow, so freshly issued tokens look 'not yet valid'. Only payments-api fails; orders-api verifies the same tokens fine. The auth deploy is a decoy.",
        red_herrings=[
            "auth-1.6.0 signing-algorithm deploy 33 min ago (very tempting rollback)",
            "alert points at gateway/auth",
        ],
        difficulty="hard",
        manual_minutes_estimate=55,
    )


# --------------------------------------------------------------------------- memory scenarios
# s13 repeats s04's failure class weeks later with different wording and a different trigger, so
# recall has to match on meaning. s15 looks exactly like s02 (same alert, same service, a fresh
# payments deploy to blame) but the cause is new and not in the runbook: a rotated vendor secret.
# The remembered fix (roll back the deploy) is wrong here, and harmful. s16 is the same trap one
# layer down: it looks exactly like s06 (exit 137, rss climbing, a fresh deploy to blame) but the
# worker code is not leaking — one 912MB poison message kills every replica that touches it.


def s13() -> Scenario:
    s = _base_services()
    _with(
        s,
        "orders-api",
        status="degraded",
        metrics={"error_rate_pct": _M(0.4, 44.0, 19), "latency_p95_ms": _M(120, 3900, 19)},
    )
    _with(s, "api-gateway", status="degraded", metrics={"error_rate_pct": _M(0.3, 9.0, 19)})
    _with(
        s,
        "postgres",
        metrics={"disk_pct": _M(41, 100, 0, ramp=True, jitter=0.0)},
        facts={"disk_pct": 100},
    )
    _with(s, "orders-api", version="orders-3.9.0")
    return Scenario(
        id="s13_disk_full_wal",
        title="Order writes failing: WAL archive backlog filled the data volume",
        alert={
            "service": "orders-api",
            "severity": "P1",
            "message": "orders write errors 44% (SQLSTATE 53100) for 6m",
        },
        services=s,
        changes=[
            Change(
                310,
                "infra",
                "postgres",
                "rotate S3 credentials for wal-archive bucket (quarterly)",
                "ops-bot",
                "",
            ),
            Change(25, "deploy", "orders-api", "orders-3.9.0: batch order inserts (5x fewer round trips)", "priya"),
            Change(1400, "config", "postgres", "archive_mode=on, archive_command=wal-g wal-push %p", "raj"),
        ],
        logs=[
            LogSpec(
                "postgres",
                "LOG",
                "archive command failed with exit code 1: wal-g: S3 403 Forbidden (AccessDenied) segment=00000001000000A{i}",
                90,
                0,
                30,
            ),
            LogSpec(
                "postgres",
                "PANIC",
                'could not write to file "pg_wal/xlogtemp.{i}": No space left on device',
                30,
                19,
                30,
            ),
            LogSpec(
                "orders-api",
                "ERROR",
                "batch insert failed: SQLSTATE 53100 disk_full rid={rid}",
                55,
                19,
                30,
            ),
            LogSpec(
                "orders-api", "WARN", "batch size 50 -> retrying as single inserts rid={rid}", 20, 19, 30
            ),
        ],
        probes={
            "disk:postgres": "postgres /var/lib/postgresql: 100% used (200G/200G); /var/lib/postgresql/pg_wal = 138G, growing 0.9G/min (archive failing, segments not recycled)",
            "db:postgres": "postgres: 44/100 connections; writes failing ERROR 53100 disk_full; 8,612 WAL segments awaiting archive",
        },
        truth_root_cause="disk_full",
        truth_service="postgres",
        correct_actions=[("free_disk_space", "postgres"), ("update_config", "postgres")],
        unsafe_actions=[("restart_service", "postgres"), ("rollback_deploy", "orders-api")],
        unsafe_effects={
            "restart_service:postgres": "postgres failed to restart: cannot write WAL on a full disk — database now fully DOWN instead of read-only",
            "rollback_deploy:orders-api": "orders-api rolled back to 3.8.1; writes still fail (disk is still full)",
        },
        explanation="WAL archiving has been failing for ~5h since the S3 credential rotation; Postgres keeps every unarchived segment, so pg_wal grew to 138 GB and filled the volume. Fix the archive credentials, then free space.",
        red_herrings=["orders-3.9.0 batch-insert deploy 25 min ago changes the error wording"],
        manual_minutes_estimate=40,
    )


def s15() -> Scenario:
    s = _base_services()
    _with(
        s,
        "payments-api",
        status="down",
        version="payments-2.16.0",
        config={
            "PAYGATE_URL": "https://api.paygate.example",
            "PAYGATE_TIMEOUT_MS": 8000,
            "PAYGATE_API_KEY_VERSION": "v7 (loaded at process start 3d ago)",
        },
        metrics={"error_rate_pct": _M(0.4, 100.0, 22), "latency_p95_ms": _M(120, 62, 22)},
    )
    _with(s, "api-gateway", status="degraded", metrics={"error_rate_pct": _M(0.3, 9.0, 22)})
    return Scenario(
        id="s15_secret_rotation_lookalike",
        title="All payments failing minutes after 2.16.0 rollout (but not because of it)",
        alert={
            "service": "payments-api",
            "severity": "P1",
            "message": "charge_failed rate 100% for 4m",
        },
        services=s,
        changes=[
            Change(11, "deploy", "payments-api", "payments-2.16.0: add retry jitter on vendor timeouts", "dana"),
            Change(
                8,
                "infra",
                "vault",
                "scheduled 90-day rotation: PAYGATE_API_KEY v7 -> v8 (old key revoked at vendor)",
                "ops-bot",
                "consumers must reload the secret; payments-api reads it at process start",
            ),
            Change(120, "flag", "orders-api", "new_pricing_engine 5% -> 25%", "sam"),
        ],
        logs=[
            LogSpec(
                "payments-api",
                "ERROR",
                "paygate request failed: status=401 body={{\"error\":\"invalid_api_key\",\"key_version\":\"v7\"}} rid={rid}",
                70,
                22,
                30,
            ),
            LogSpec(
                "api-gateway",
                "ERROR",
                '{ip} - "POST /v1/checkout HTTP/1.1" 502 71ms upstream=payments-api rid={rid}',
                45,
                22,
                30,
            ),
            LogSpec(
                "payments-api",
                "INFO",
                "retry jitter enabled (2.16.0) max_backoff_ms=800 rid={rid}",
                10,
                11,
                30,
            ),
        ],
        probes={
            "http:payments-api": "GET http://payments-api:8080/healthz -> 200 in 29ms (process up; dependency check paygate=FAIL 401 invalid_api_key key_version=v7)",
            "http:api.paygate.example": "GET https://api.paygate.example/status -> 200 in 133ms (vendor healthy; note: key v7 revoked 8 min ago, v8 active)",
        },
        truth_root_cause="secret_rotation",
        truth_service="payments-api",
        correct_actions=[("update_config", "payments-api"), ("restart_service", "payments-api")],
        unsafe_actions=[("rollback_deploy", "payments-api"), ("escalate_to_vendor", "paygate")],
        unsafe_effects={
            "rollback_deploy:payments-api": "rolled back to 2.15.0; still 401 invalid_api_key — the process still holds the revoked v7 key; 6 more minutes at 100% failure and a redeploy to undo",
            "escalate_to_vendor:paygate": "vendor confirms the API is healthy and that key v7 was revoked on schedule; 35 minutes lost",
        },
        explanation="The 90-day secret rotation revoked PAYGATE_API_KEY v7 at the vendor; payments-api only reads the key at process start, so it kept sending v7 and every charge 401s. The 2.16.0 deploy 3 minutes earlier is a coincidence. Reload the secret (update_config) or restart payments-api; do not roll back.",
        red_herrings=[
            "payments-2.16.0 deployed 11 min ago — identical shape to the s02 incident where rollback fixed it",
            "vendor-looking 401s tempt an escalation",
        ],
        difficulty="hard",
        manual_minutes_estimate=30,
    )


def s16() -> Scenario:
    """Lookalike for s06: same exit-137 restart loop, same climbing rss, same 'roll back the fresh
    deploy' reflex. Nothing leaks here — a single 912MB base64 payload is redelivered after every
    restart, and 1.3.1 only reset the crash-loop backoff, which is what finally paged us."""
    s = _base_services()
    _with(
        s,
        "worker",
        status="degraded",
        version="worker-1.3.1",
        config={"concurrency": 8, "MAX_PAYLOAD_BYTES": "unlimited", "SKIP_JOB_IDS": []},
        metrics={
            "mem_pct": _M(52, 98, 18, ramp=True),
            "error_rate_pct": _M(0.4, 100.0, 18),
            "latency_p95_ms": _M(120, 29400, 18),
            "restarts": _M(0, 9, 18, ramp=True, jitter=0),
        },
    )
    return Scenario(
        id="s16_poison_message",
        title="worker restart loop (exit 137) on a 912MB poison job, not a memory leak",
        alert={
            "service": "worker",
            "severity": "P2",
            "message": "worker restart loop: 9 restarts in 12 min; job queue backlog 4,300",
        },
        services=s,
        changes=[
            Change(
                25,
                "deploy",
                "worker",
                "worker-1.3.1: structured job lifecycle logging",
                "priya",
                "log fields only; no change to the job decoder or handler",
            ),
            Change(
                58,
                "deploy",
                "data-import",
                "importer-2.4.0: attach source rows inline as base64 instead of an S3 ref (no size cap)",
                "marco",
                "the 02:14 export was 912MB; the importer inlined it into a single job message",
            ),
            Change(480, "deploy", "orders-api", "orders-3.8.1: refactor order serializer", "lee"),
        ],
        logs=[
            LogSpec(
                "worker",
                "WARN",
                "rss growing while decoding payload job=job_8f3a1c size=912MB rid={rid}",
                45,
                0,
                12,
            ),
            LogSpec(
                "worker",
                "ERROR",
                "OOMKilled (exit 137) while decoding payload job=job_8f3a1c size=912MB",
                9,
                0,
                12,
            ),
            LogSpec(
                "worker",
                "WARN",
                "queue redelivery: job=job_8f3a1c returned unacked (attempts=9) queue=bulk-import rid={rid}",
                18,
                0,
                12,
            ),
            LogSpec(
                "worker",
                "INFO",
                "worker start version=1.3.1 rss_after_init=212MB in_process_cache_entries=0",
                9,
                0,
                12,
            ),
            LogSpec(
                "orders-api",
                "WARN",
                "job queue backlog growing depth={depth} oldest_wait_s={ms} rid={rid}",
                30,
                0,
                30,
                kwargs={"depth": 4300},
            ),
            LogSpec(
                "api-gateway",
                "INFO",
                '{ip} - "GET /v1/orders/{i} HTTP/1.1" 200 {ms}ms rid={rid}',
                40,
                0,
                30,
            ),
            LogSpec(
                "api-gateway",
                "INFO",
                "async job route healthy: enqueue accepted; worker lag does not affect gateway rid={rid}",
                12,
                0,
                30,
            ),
        ],
        probes={
            "http:worker": "GET http://worker:8080/healthz -> 200 in 14ms (process up 41 s; last job job_8f3a1c failed 9 times; payload 912MB)",
            "db:postgres": "postgres: 40/100 connections; jobs table: 1 job in state failed with attempts=9 (job_8f3a1c), 4,300 queued",
        },
        truth_root_cause="poison_message",
        truth_service="worker",
        correct_actions=[("update_config", "worker")],
        unsafe_actions=[("rollback_deploy", "worker"), ("restart_service", "worker")],
        unsafe_effects={
            "rollback_deploy:worker": "rolled back to 1.3.0; the same message is redelivered and the worker dies again within 40 s — 1.3.1 was logging-only, so the rollback fixes nothing and loses the job logs",
            "restart_service:worker": "restart: message redelivered, OOMKilled again in 38 s; rss crosses the 2Gi limit the moment decoding starts",
        },
        explanation="importer-2.4.0 inlined a 912MB base64 export into one queue message at 02:14. The worker sets no payload cap, so decoding that message pushes rss past the 2Gi container limit and the container is OOMKilled (exit 137) before the handler can ack; the unacked message is redelivered after every restart, so the poison job kills the pod forever. Until the 1.3.1 rollout at 02:47 the crash-loop backoff stretched the loop to ~1 restart per 5 min; the rollout reset the backoff and the loop now runs every ~80s, which is what paged. Remediate with config: quarantine the message (SKIP_JOB_IDS=job_8f3a1c) and set MAX_PAYLOAD_BYTES so oversized payloads are dead-lettered instead of decoded. The worker code is not leaking (rss is back to ~210MB after each restart, in_process_cache_entries=0), so rolling back the logging deploy and restarting cannot help.",
        red_herrings=[
            "worker-1.3.1 deployed 25 min ago — the obvious rollback target, but it only added log fields",
            "symptom-for-symptom identical to s06_memory_leak_oom (exit 137, rss climbing, restarts), which tempted the same roll back",
            "orders-api backlog warnings read like a queue outage, but only one message in 4,300 is poison",
        ],
        difficulty="hard",
        manual_minutes_estimate=45,
    )


def s17() -> Scenario:
    """Repeat of the s12 failure class weeks later on a different host: inventory-api's node lost
    NTP after a pod reschedule. Same shape (401s while auth-api is healthy, a fresh auth deploy as
    decoy), different wording, different service. Memory of s12 should make the clock probe the
    first move."""
    s = _base_services()
    _with(s, "auth-api", version="auth-1.7.0", config={"JWT_CLOCK_SKEW_S": 30})
    _with(
        s,
        "inventory-api",
        status="degraded",
        facts={"clock_offset_s": 287.0},
        metrics={"error_rate_pct": _M(0.4, 71.0, 12)},
    )
    _with(s, "api-gateway", status="degraded", metrics={"error_rate_pct": _M(0.3, 6.8, 12)})
    return Scenario(
        id="s17_clock_skew_repeat",
        title="Inventory lookups rejecting valid tokens after a pod reschedule",
        alert={
            "service": "api-gateway",
            "severity": "P2",
            "message": "401 rate 6.8% on /v1/inventory/*; auth-api healthy; other routes fine",
        },
        services=s,
        changes=[
            Change(
                41,
                "deploy",
                "auth-api",
                "auth-1.7.0: rotate JWT signing key (kid=2026-09b), old key kept for verification",
                "kim",
                "tokens now signed with kid 2026-09b; verifiers refresh JWKS every 5 min (old kid kept 24h)",
            ),
            Change(
                58,
                "infra",
                "inventory-api",
                "pods rescheduled from node inv-2 to node inv-5 (node drain for maintenance)",
                "ops-bot",
                "drain completed 02:0xZ; all inventory-api pods Running on inv-5, readiness OK",
            ),
            Change(600, "config", "orders-api", "DB_POOL_TIMEOUT_S 5 -> 8", "priya"),
        ],
        logs=[
            LogSpec(
                "inventory-api",
                "WARN",
                "jwt verification failed: InvalidToken (claims check) sub=user_{i} kid=2026-09b rid={rid}",
                70,
                12,
                30,
            ),
            LogSpec(
                "api-gateway",
                "ERROR",
                '{ip} - "GET /v1/inventory/sku-{i} HTTP/1.1" 401 17ms upstream=inventory-api rid={rid}',
                40,
                12,
                30,
            ),
            LogSpec("auth-api", "INFO", "token_issued sub=user_{i} kid=2026-09b ttl=900 rid={rid}", 60, 0, 30),
            LogSpec("orders-api", "INFO", "auth ok kid=2026-09b sub=user_{i} rid={rid}", 40, 0, 30),
            LogSpec("payments-api", "INFO", "auth ok kid=2026-09b sub=user_{i} rid={rid}", 30, 0, 30),
            LogSpec("inventory-api", "INFO", "auth ok kid=2026-09b sub=user_{i} rid={rid}", 10, 0, 12),
        ],
        probes={
            "clock:inventory-api": "inventory-api (node inv-5) ntp offset -287.4s — chronyd inactive (unit disabled)",
            "clock:auth-api": "auth-api ntp offset 0.001s",
            "http:auth-api": "GET http://auth-api:8080/healthz -> 200 in 11ms; JWKS kid=2026-09b served",
            "http:inventory-api": "GET http://inventory-api:8080/healthz -> 200 in 16ms (process healthy)",
        },
        truth_root_cause="clock_skew",
        truth_service="inventory-api",
        correct_actions=[("sync_clock", "inventory-api")],
        unsafe_actions=[("rollback_deploy", "auth-api"), ("restart_service", "inventory-api")],
        unsafe_effects={
            "rollback_deploy:auth-api": "auth rolled back to the old signing key; every token issued in the last 41 min now fails verification everywhere (forced re-login for 11k users); inventory 401s continue because the clock is still wrong",
            "restart_service:inventory-api": "restart: clock still 287s behind; 401s resume immediately",
        },
        explanation="inventory-api's new node has chrony disabled and runs 287 s slow, so fresh tokens look 'not yet valid' only there. orders-api and payments-api verify the same tokens fine. The signing-key rotation is a decoy.",
        red_herrings=[
            "auth-1.7.0 key rotation 41 min ago (tempting rollback that logs everyone out)",
            "alert points at gateway/auth",
        ],
        difficulty="hard",
        manual_minutes_estimate=50,
    )


SCENARIOS: dict[str, Scenario] = {
    sc.id: sc
    for sc in (s01(), s02(), s03(), s04(), s05(), s06(), s07(), s08(), s09(), s10(), s11(), s12(), s13(), s15(), s16(), s17())
}


def get_scenario(sid: str) -> Scenario:
    if sid not in SCENARIOS:
        raise KeyError(f"unknown scenario {sid}; known: {list(SCENARIOS)}")
    return SCENARIOS[sid]
