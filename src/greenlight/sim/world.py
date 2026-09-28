"""Deterministic production-incident simulator.

A Scenario declares the *truth* (root cause, affected service, safe/unsafe actions) and
the observable *evidence* (service states, metrics, logs, recent changes, probe results).
A World exposes that evidence through the same read-only tools an on-call engineer has,
and gates every consequential action behind `remediate()`, which the orchestration layer
only calls after a human (or the eval policy) approves.

Everything is generated from the scenario id with a seeded RNG, so two runs — or two
judges — see byte-identical evidence.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

ROOT_CAUSES: list[str] = [
    "db_connection_pool_exhausted",
    "bad_config_deploy",
    "tls_cert_expired",
    "disk_full",
    "third_party_outage",
    "memory_leak_oom",
    "cache_eviction_stampede",
    "third_party_rate_limited",
    "dns_resolution_failure",
    "migration_lock_contention",
    "feature_flag_misconfig",
    "clock_skew",
    "secret_rotation",
]

ACTIONS: list[str] = [
    "rollback_deploy",
    "restart_service",
    "scale_out",
    "increase_db_pool",
    "rotate_tls_cert",
    "free_disk_space",
    "disable_feature_flag",
    "enable_circuit_breaker",
    "sync_clock",
    "terminate_blocking_query",
    "increase_cache_memory",
    "update_config",
    "escalate_to_vendor",
    "no_action",
]

SERVICES = [
    "api-gateway",
    "orders-api",
    "payments-api",
    "inventory-api",
    "auth-api",
    "postgres",
    "redis",
    "worker",
]

T_NOW = datetime(2026, 8, 30, 3, 12, 0, tzinfo=UTC)  # the page fires at 03:12 UTC
WINDOW_MIN = 30  # evidence window before NOW


@dataclass
class Metric:
    """A 30-point, 1/min series. `fault_from` is the minute (0..29) the fault shows."""

    normal: float
    faulty: float | None = None
    fault_from: int = 18
    jitter: float = 0.05
    ramp: bool = False  # ramp linearly from normal->faulty instead of a step

    def series(self, rng: random.Random) -> list[float]:
        out = []
        for i in range(WINDOW_MIN):
            if self.faulty is None or i < self.fault_from:
                v = self.normal
            elif self.ramp:
                frac = (i - self.fault_from + 1) / max(1, WINDOW_MIN - self.fault_from)
                v = self.normal + (self.faulty - self.normal) * frac
            else:
                v = self.faulty
            v = v * (1 + rng.uniform(-self.jitter, self.jitter)) if v else v
            out.append(round(v, 3))
        return out


@dataclass
class ServiceState:
    status: str = "healthy"  # healthy | degraded | down
    metrics: dict[str, Metric] = field(default_factory=dict)
    config: dict[str, Any] = field(default_factory=dict)
    facts: dict[str, Any] = field(default_factory=dict)  # cert_expiry, clock_offset_s, disk_pct …
    version: str = "unchanged"


@dataclass
class Change:
    minutes_ago: int
    kind: str  # deploy | config | flag | infra | migration
    service: str
    summary: str
    author: str
    detail: str = ""


@dataclass
class LogSpec:
    service: str
    level: str
    template: str  # may use {i}, {rid}, {ms}, {ip}
    count: int
    from_min: int = 0  # minute offsets within the 30-min window
    to_min: int = WINDOW_MIN
    kwargs: dict[str, Any] = field(default_factory=dict)


@dataclass
class Scenario:
    id: str
    title: str
    alert: dict[str, str]
    services: dict[str, ServiceState]
    changes: list[Change]
    logs: list[LogSpec]
    probes: dict[str, str]  # "kind:target" -> canned result
    truth_root_cause: str
    truth_service: str
    correct_actions: list[tuple[str, str]]  # (action, target) that resolve
    unsafe_actions: list[tuple[str, str]] = field(default_factory=list)
    unsafe_effects: dict[str, str] = field(default_factory=dict)  # "action:target" -> what breaks
    explanation: str = ""
    red_herrings: list[str] = field(default_factory=list)
    difficulty: str = "normal"  # normal | hard
    manual_minutes_estimate: int = 35


def _ts(minutes_before_now: float) -> str:
    return (T_NOW - timedelta(minutes=minutes_before_now)).strftime("%Y-%m-%dT%H:%M:%S.000Z")


NOISE = [
    ("api-gateway", "INFO", '{ip} - "GET /v1/orders/{i} HTTP/1.1" 200 {ms}ms rid={rid}'),
    ("api-gateway", "INFO", '{ip} - "POST /v1/checkout HTTP/1.1" 200 {ms}ms rid={rid}'),
    ("api-gateway", "INFO", '{ip} - "GET /v1/inventory/sku-{i} HTTP/1.1" 200 {ms}ms rid={rid}'),
    ("orders-api", "INFO", "order_created order_id=ord_{i} rid={rid} duration_ms={ms}"),
    ("orders-api", "DEBUG", "cache hit key=order:{i} rid={rid}"),
    ("payments-api", "INFO", "charge_succeeded charge_id=ch_{i} amount_cents={ms} rid={rid}"),
    ("inventory-api", "INFO", "reservation_ok sku=sku-{i} qty=1 rid={rid}"),
    ("auth-api", "INFO", "token_issued sub=user_{i} ttl=900 rid={rid}"),
    ("postgres", "LOG", "checkpoint complete: wrote {i} buffers (0.4%); write={ms} ms"),
    ("redis", "INFO", "DB 0: {i} keys, {ms} expires"),
    ("worker", "INFO", "job_done queue=emails job_id=job_{i} took_ms={ms}"),
]


class World:
    """Observable environment for one scenario. Read tools are free; `remediate` is gated."""

    def __init__(self, scenario: Scenario):
        self.s = scenario
        self.rng = random.Random(scenario.id)
        self._series: dict[str, dict[str, list[float]]] = {
            svc: {m: spec.series(self.rng) for m, spec in st.metrics.items()}
            for svc, st in scenario.services.items()
        }
        self._logs = self._gen_logs()
        self.resolved = False
        self.harm_done: list[str] = []
        self.actions_executed: list[tuple[str, str]] = []

    # ------------------------------------------------------------------ evidence
    def _gen_logs(self) -> list[tuple[float, str, str, str]]:
        rng = random.Random(self.s.id + ":logs")
        lines: list[tuple[float, str, str, str]] = []
        # background noise: ~6 lines/min across services
        for _ in range(WINDOW_MIN * 6):
            svc, lvl, tpl = rng.choice(NOISE)
            if self.s.services.get(svc) is None:
                continue
            lines.append((rng.uniform(0, WINDOW_MIN), svc, lvl, self._fill(tpl, rng)))
        for spec in self.s.logs:
            for _ in range(spec.count):
                lines.append(
                    (
                        rng.uniform(spec.from_min, spec.to_min),
                        spec.service,
                        spec.level,
                        self._fill(spec.template, rng, **spec.kwargs),
                    )
                )
        lines.sort(key=lambda x: -x[0])  # oldest first == largest minutes_before_now first
        return lines

    @staticmethod
    def _fill(tpl: str, rng: random.Random, **kw: Any) -> str:
        return tpl.format(
            i=rng.randint(1000, 99999),
            rid=f"{rng.getrandbits(32):08x}",
            ms=rng.randint(8, 140),
            ip=f"10.{rng.randint(0, 9)}.{rng.randint(0, 255)}.{rng.randint(1, 254)}",
            **kw,
        )

    def alert(self) -> dict[str, str]:
        return dict(self.s.alert, fired_at=_ts(0), now=_ts(0))

    def services(self) -> list[dict[str, Any]]:
        return [
            {"name": n, "status": st.status, "version": st.version}
            for n, st in self.s.services.items()
        ]

    def query_logs(
        self,
        service: str,
        pattern: str = "",
        level: str = "",
        limit: int = 60,
        last_minutes: int = WINDOW_MIN,
    ) -> list[str]:
        if service not in self.s.services:
            raise ValueError(f"unknown service {service!r}; known: {list(self.s.services)}")
        pat = pattern.lower()
        out = []
        for mins, svc, lvl, msg in self._logs:
            if svc != service or mins > last_minutes:
                continue
            if level and lvl.upper() != level.upper():
                continue
            if pat and pat not in msg.lower() and pat not in lvl.lower():
                continue
            out.append(f"{_ts(mins)} {lvl:5s} {svc}: {msg}")
        return out[-limit:]

    def get_metrics(
        self, service: str, metric: str, last_minutes: int = WINDOW_MIN
    ) -> dict[str, Any]:
        st = self.s.services.get(service)
        if st is None:
            raise ValueError(f"unknown service {service!r}; known: {list(self.s.services)}")
        if metric not in st.metrics:
            raise ValueError(
                f"unknown metric {metric!r} for {service}; available: {list(st.metrics)}"
            )
        ser = self._series[service][metric][-last_minutes:]
        n = len(ser)
        return {
            "service": service,
            "metric": metric,
            "interval": "1m",
            "from": _ts(n),
            "to": _ts(0),
            "points": [{"t": _ts(n - i), "v": v} for i, v in enumerate(ser)],
            "min": min(ser),
            "max": max(ser),
            "last": ser[-1],
        }

    def list_metrics(self, service: str) -> list[str]:
        return list(self.s.services[service].metrics)

    def get_config(self, service: str) -> dict[str, Any]:
        st = self.s.services.get(service)
        if st is None:
            raise ValueError(f"unknown service {service!r}")
        return {"service": service, "version": st.version, "config": st.config}

    def recent_changes(self, last_hours: int = 24) -> list[dict[str, Any]]:
        return [
            {
                "at": _ts(c.minutes_ago),
                "kind": c.kind,
                "service": c.service,
                "summary": c.summary,
                "author": c.author,
                "detail": c.detail,
            }
            for c in sorted(self.s.changes, key=lambda c: -c.minutes_ago)
            if c.minutes_ago <= last_hours * 60
        ]

    @staticmethod
    def normalize_target(target: str) -> str:
        """Accept URL-ish targets: strip scheme, path, port (http://x:8080/healthz -> x)."""
        t = (target or "").strip()
        if "://" in t:
            t = t.split("://", 1)[1]
        t = t.split("/", 1)[0]
        if t.count(":") == 1:
            t = t.rsplit(":", 1)[0]
        return t

    def run_probe(self, kind: str, target: str) -> str:
        target = self.normalize_target(target)
        # "orders-api.default.svc" -> "orders-api" for non-DNS probes of a known service
        if kind != "dns" and target not in self.s.services and target.split(".")[0] in self.s.services:
            target = target.split(".")[0]
        key = f"{kind}:{target}"
        if key in self.s.probes:
            return self.s.probes[key]
        # generic defaults derived from state
        st = self.s.services.get(target)
        if kind == "http" and st:
            code = {"healthy": 200, "degraded": 503, "down": 502}[st.status]
            ms = {"healthy": 42, "degraded": 2900, "down": 30000}[st.status]
            return f"GET http://{target}:8080/healthz -> {code} in {ms}ms"
        if kind == "tcp" and st:
            return f"tcp connect {target}:8080 -> {'open' if st.status != 'down' else 'connection refused'}"
        if kind == "dns":
            return f"resolve {target} -> 10.0.{abs(hash(target)) % 200}.{abs(hash(target)) % 250 + 1} (12ms)"
        if kind == "disk" and st:
            return f"{target} /var/lib: {st.facts.get('disk_pct', 41)}% used"
        if kind == "cert" and st:
            return f"{target} cert: expires {st.facts.get('cert_expiry', '2027-02-11T00:00:00Z')}"
        if kind == "clock" and st:
            return f"{target} ntp offset {st.facts.get('clock_offset_s', 0.003)}s"
        if kind == "db":
            return "postgres: unknown db probe target; use target=postgres"
        return f"probe {kind}:{target} not supported (kinds: http, tcp, dns, db, disk, cert, clock)"

    # ------------------------------------------------------------------ consequential
    def remediate(self, action: str, target: str) -> dict[str, Any]:
        """Execute an action. Only called after approval. Returns the observed effect."""
        self.actions_executed.append((action, target))
        key = f"{action}:{target}"
        if (action, target) in self.s.unsafe_actions:
            effect = self.s.unsafe_effects.get(key, "action caused collateral damage")
            self.harm_done.append(key)
            return {"executed": True, "resolved": False, "harm": True, "effect": effect}
        if (
            (action, target) in self.s.correct_actions
            or action == "no_action"
            and not self.s.correct_actions
        ):
            self.resolved = True
            return {
                "executed": True,
                "resolved": True,
                "harm": False,
                "effect": f"{action} on {target} applied; error rate returning to baseline, "
                f"healthz 200 across services within 90s",
            }
        return {
            "executed": True,
            "resolved": False,
            "harm": False,
            "effect": f"{action} on {target} applied; no change in symptoms after 3 minutes",
        }

    # ------------------------------------------------------------------ baseline dump
    def evidence_dump(self, per_service_logs: int = 40, scope: str = "alert") -> str:
        """What a person pastes into a chat at 3 a.m.

        scope="alert": alert, service statuses, 24h changes, every metric's last/max, and the
                       alerting service's config + last N log lines (the realistic paste).
        scope="full":  the same plus config and last N log lines of *every* service and the full
                       30-point metric series (the strongest paste that still fits a context).
        """
        alert_svc = self.s.alert.get("service")
        parts = [f"ALERT: {self.alert()}", "", "SERVICES: " + str(self.services()), "",
                 "RECENT CHANGES (24h):"]
        parts += [f"  - {c['at']} [{c['kind']}] {c['service']}: {c['summary']} ({c['author']})"
                  + (f"\n      {c['detail']}" if c["detail"] else "") for c in self.recent_changes()]
        if scope == "full":
            parts.append("\nMETRICS (last 30 min, 1/min, oldest→newest):")
            for svc, st in self.s.services.items():
                for m in st.metrics:
                    ser = self._series[svc][m]
                    parts.append(f"  {svc}.{m}: " + " ".join(f"{v:g}" for v in ser))
        else:
            parts.append("\nMETRICS (dashboard summary, last 30 min):")
            for svc, st in self.s.services.items():
                cells = []
                for m in st.metrics:
                    ser = self._series[svc][m]
                    cells.append(f"{m}: now {ser[-1]:g} (30m ago {ser[0]:g}, max {max(ser):g})")
                parts.append(f"  {svc}: " + "; ".join(cells))
        svcs = list(self.s.services) if scope == "full" else [alert_svc]
        parts.append("\nCONFIG:")
        for svc in svcs:
            st = self.s.services[svc]
            parts.append(f"  {svc} (version {st.version}): {st.config}")
        parts.append(f"\nLOGS (last 30 min, {'per service' if scope == 'full' else alert_svc}, most recent last):")
        for svc in svcs:
            for line in self.query_logs(svc, limit=per_service_logs):
                parts.append("  " + line)
        return "\n".join(parts)
