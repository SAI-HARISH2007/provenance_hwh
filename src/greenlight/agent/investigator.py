"""Advanced solution: tool-using investigator with optional verification gate, runbook memory,
reviewer agent and human approval checkpoint. Each feature is a flag so the changelog can
attribute improvement to a single change.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from ..common import Verdict, git_sha, parse_json_block, verdict_from_dict
from ..llm import LLM
from ..memory import HindsightMemory, MemoryHit, hits_to_json
from ..sim import ACTIONS, ROOT_CAUSES, Scenario, World
from ..tracing import TraceWriter, new_run_id, sha256_text
from .tools import RECALL_TOOL, TOOLS, dispatch

PROMPTS = Path(__file__).parent.parent / "prompts"
RUNBOOK = Path(__file__).parent.parent / "knowledge" / "runbook.md"


@dataclass
class VariantConfig:
    name: str
    verify: bool = False  # reject verdicts that have no probe/metric verification
    runbook: bool = False  # inject team runbook into the system prompt (memory)
    reviewer: bool = False  # second-agent review before finalising
    approval: bool = True  # human checkpoint before executing remediation
    memory: bool = False  # Hindsight long-term memory (recall at kickoff, retain at close)
    provenance: bool = True  # memory-derived verdicts must be re-verified in THIS incident
    max_steps: int = 16
    max_verify_rejections: int = 2


VARIANTS: dict[str, VariantConfig] = {
    "v1_tools": VariantConfig("v1_tools"),
    "v2_verify": VariantConfig("v2_verify", verify=True),
    "v3_runbook": VariantConfig("v3_runbook", verify=True, runbook=True),
    "v4_reviewer": VariantConfig("v4_reviewer", verify=True, runbook=True, reviewer=True),
    "final": VariantConfig("final", verify=True, runbook=True, reviewer=True, approval=True),
    # Memory without the hand-written runbook: the fair test of "does the agent learn?"
    "mem_naive": VariantConfig("mem_naive", verify=True, memory=True, provenance=False),
    "mem_gate": VariantConfig("mem_gate", verify=True, memory=True),
    "v5_memory_naive": VariantConfig(
        "v5_memory_naive", verify=True, runbook=True, memory=True, provenance=False
    ),
    "v5_memory": VariantConfig("v5_memory", verify=True, runbook=True, memory=True),
    "final_memory": VariantConfig(
        "final_memory", verify=True, runbook=True, reviewer=True, approval=True, memory=True
    ),
}

PROBE_KINDS = ("db", "clock", "cert", "dns", "disk", "http", "tcp")

# Which probe *kind* directly tests the mechanism behind each root cause. A verdict is
# "verified" when a probe of an acceptable kind was run (changelog: gate v2 — gate v1 matched
# the probe *target* against the blamed service and rejected correct DNS verdicts).
VERIFYING_PROBES: dict[str, set[str]] = {
    "db_connection_pool_exhausted": {"db"},
    "migration_lock_contention": {"db"},
    "disk_full": {"disk"},
    "tls_cert_expired": {"cert"},
    "clock_skew": {"clock"},
    "dns_resolution_failure": {"dns"},
    "third_party_outage": {"http"},
    "third_party_rate_limited": {"http"},
    "bad_config_deploy": {"http"},
    "memory_leak_oom": {"http"},
    "cache_eviction_stampede": {"db", "http"},
    "feature_flag_misconfig": {"http"},
    "secret_rotation": {"http"},
    "poison_message": {"http", "db"},
}
BUDGET_WARNING_STEPS = 3


def _system_prompt(cfg: VariantConfig) -> str:
    txt = (PROMPTS / "agent_system.md").read_text()
    txt = txt.replace("{{ROOT_CAUSES}}", json.dumps(ROOT_CAUSES)).replace(
        "{{ACTIONS}}", json.dumps(ACTIONS)
    )
    rb = (
        ("\n\n# Team runbook (memory from past incidents)\n" + RUNBOOK.read_text())
        if cfg.runbook
        else ""
    )
    mem = (
        "\n\n# Long-term memory (Hindsight)\n"
        "You remember past incidents. A `# Recalled incidents` block may be in the kickoff message and "
        "you can call `recall_similar_incidents` at any time. Every recalled incident is a claim about "
        "the PAST, never a fact about NOW: symptoms repeat, causes differ. Use memory to decide which "
        "probe to run FIRST, then let the probe decide. A verdict that matches a recalled incident is "
        "rejected unless you re-verified the mechanism with a probe against the blamed service in this "
        "incident. If the probe disagrees with memory, trust the probe and say so in the report. If a "
        "recalled incident helped (or misled you), cite its id in the report's evidence."
        if cfg.memory
        else ""
    )
    return txt.replace("{{RUNBOOK}}", rb).replace("{{MEMORY}}", mem)


def default_eval_approver(v: Verdict, report: str, ctx: dict[str, Any]) -> tuple[str, str]:
    """Stand-in for the human during batch evaluation.

    Policy: auto-approve only when nothing upstream objected. If the reviewer agent rejected the
    final verdict (or verification is missing), the action is NOT executed — it is left for a
    human. This is what makes the reviewer worth its tokens: disagreement never becomes action.
    """
    if ctx.get("reviewer_approved") is False:
        return "denied", "auto policy: reviewer rejected the final verdict -> requires a human (not executed)"
    if ctx.get("verified") is False:
        return "denied", "auto policy: verdict not verified by a probe -> requires a human (not executed)"
    return "approved", "auto-approve policy (eval mode): reviewer approved / no objections"


@dataclass
class RunOutcome:
    verdict: Verdict
    meta: dict[str, Any] = field(default_factory=dict)


class Investigator:
    def __init__(
        self,
        cfg: VariantConfig,
        llm: LLM,
        trace_root: Path = Path("traces"),
        approver: Callable[[Verdict, str], tuple[str, str]] | None = None,
        memory: HindsightMemory | None = None,
    ):
        self.cfg = cfg
        self.llm = llm
        self.trace_root = trace_root
        self.approver = approver or default_eval_approver
        self.memory = memory if cfg.memory else None
        if cfg.memory and memory is None:
            raise ValueError(f"variant {cfg.name} needs a HindsightMemory")

    # ------------------------------------------------------------------ main
    def run(self, scenario: Scenario) -> RunOutcome:
        world = World(scenario)
        cfg = self.cfg
        run_id = new_run_id(f"{cfg.name}-{scenario.id}")
        sys_p = _system_prompt(cfg)
        t0 = time.monotonic()
        probes: list[str] = []
        tool_log: list[str] = []
        verdict: Verdict | None = None
        rejections = 0
        reviewer_note: dict[str, Any] | None = None
        status = "fail"
        hits: list[MemoryHit] = []
        memory_rejections = 0
        memory_checks: list[dict[str, Any]] = []
        tools = TOOLS + ([RECALL_TOOL] if self.memory else [])
        with TraceWriter(run_id, root=self.trace_root) as tw:
            self.llm.on_event = lambda et, **f: getattr(tw, et)(**f)
            tw.run_start(
                problem_id=scenario.id,
                agent_version=git_sha(),
                model=self.llm.model,
                params={"temperature": self.llm.temperature, "max_steps": cfg.max_steps},
                tools=[t["function"]["name"] for t in tools],
                sandbox="simulation",
                prompt_hashes={"agent_system.md": sha256_text(sys_p)},
                variant=cfg.name,
                flags=asdict(cfg),
            )
            tw.instruction(role="system", name="agent_system.md", content=sys_p)
            user0 = (
                "A page just fired. Investigate and submit a verdict. Start with get_alert and "
                "recent_changes."
            )
            if self.memory is not None:
                t_rc = time.monotonic()
                try:
                    alert = world.alert()
                    err_lines = [
                        line.split(": ", 1)[-1]
                        for line in world.query_logs(alert["service"], "", "ERROR", 3)
                        + world.query_logs(alert["service"], "", "WARN", 2)
                    ]
                    hits = self.memory.brief(alert, world.recent_changes(24), err_lines)
                    err = None
                except Exception as e:  # noqa: BLE001 — memory outage must not kill the run
                    hits, err = [], f"{type(e).__name__}: {e}"
                    tw.error(where="memory", kind=type(e).__name__, message=str(e), recoverable=True)
                block = self.memory.format_hits(hits)
                user0 = user0 + "\n\n" + block
                tw.feedback(
                    source="hindsight_memory",
                    signal="recall",
                    detail=hits_to_json(hits) if not err else err,
                    n_hits=len(hits),
                    bank=self.memory.bank_id,
                    latency_ms=int((time.monotonic() - t_rc) * 1000),
                )
            tw.instruction(role="user", name="kickoff", content=user0)
            msgs: list[dict[str, Any]] = [
                {"role": "system", "content": sys_p},
                {"role": "user", "content": user0},
            ]
            calls_start = self.llm.calls
            for step in range(1, cfg.max_steps + 1):
                if cfg.max_steps - step == BUDGET_WARNING_STEPS - 1:
                    warn = (f"Budget: {BUDGET_WARNING_STEPS} steps left. Stop exploring and call submit_verdict "
                            "with your best-supported hypothesis now.")
                    msgs.append({"role": "user", "content": warn})
                    tw.feedback(source="orchestrator", signal="budget_warning", detail=warn)
                tw.llm_request(
                    n_messages=len(msgs), tools_offered=[t["function"]["name"] for t in tools]
                )
                resp = self.llm.chat(msgs, tools=tools, max_tokens=8192)
                tw.llm_response(
                    stop_reason=resp.stop_reason,
                    text=resp.text,
                    tool_calls=[
                        {"id": c.id, "name": c.name, "input": c.arguments} for c in resp.tool_calls
                    ],
                    output_tokens=resp.output_tokens,
                    latency_ms=resp.latency_ms,
                    input_tokens=resp.input_tokens,
                    cached=resp.cached,
                    step=step,
                )
                if not resp.tool_calls:
                    # model answered in prose: nudge it to use the tool
                    msgs.append(resp.raw_message or {"role": "assistant", "content": resp.text})
                    msgs.append(
                        {
                            "role": "user",
                            "content": "Continue with tool calls; finish with submit_verdict.",
                        }
                    )
                    tw.feedback(
                        source="orchestrator",
                        signal="nudge",
                        detail="no tool call; asked to continue",
                    )
                    continue
                msgs.append(resp.raw_message)
                finished = False
                for tc in resp.tool_calls:
                    tw.tool_call(tool_call_id=tc.id, name=tc.name, input=tc.arguments)
                    t1 = time.monotonic()
                    if tc.name == "submit_verdict":
                        cand = verdict_from_dict(tc.arguments)
                        ok, why = self._verification_gate(cand, probes, cfg)
                        if ok and self.memory is not None and cfg.provenance:
                            ok, why, src = self._provenance_gate(cand, probes, hits)
                            if src:
                                memory_checks.append(
                                    {"step": step, "sources": src, "accepted": ok, "reason": why,
                                     "verdict": f"{cand.root_cause}@{cand.service}->{cand.action}:{cand.target}"}
                                )
                                tw.feedback(
                                    source="provenance_gate",
                                    signal="accepted" if ok else "rejected",
                                    detail=why,
                                    sources=src,
                                )
                            if not ok:
                                memory_rejections += 1
                        if not ok and rejections < cfg.max_verify_rejections:
                            rejections += 1
                            tw.tool_result(
                                tool_call_id=tc.id,
                                ok=False,
                                output=why,
                                duration_ms=int((time.monotonic() - t1) * 1000),
                            )
                            tw.feedback(source="verification_gate", signal="rejected", detail=why)
                            msgs.append({"role": "tool", "tool_call_id": tc.id, "content": why})
                            continue
                        if cfg.reviewer:
                            review = self._review(cand, tool_log, tw)
                            reviewer_note = review
                            if (
                                not review.get("approve", True)
                                and rejections < cfg.max_verify_rejections
                            ):
                                rejections += 1
                                fb = (
                                    "Reviewer did not approve. Issues: "
                                    + "; ".join(review.get("issues", []))
                                    + ". Suggested checks: "
                                    + "; ".join(review.get("suggested_checks", []))
                                    + ". Address them (run the checks) and submit again."
                                )
                                tw.tool_result(
                                    tool_call_id=tc.id,
                                    ok=False,
                                    output=fb,
                                    duration_ms=int((time.monotonic() - t1) * 1000),
                                )
                                tw.feedback(source="reviewer_agent", signal="rejected", detail=fb)
                                msgs.append({"role": "tool", "tool_call_id": tc.id, "content": fb})
                                continue
                        verdict = cand
                        tw.tool_result(
                            tool_call_id=tc.id,
                            ok=True,
                            output="verdict accepted",
                            duration_ms=int((time.monotonic() - t1) * 1000),
                        )
                        msgs.append(
                            {"role": "tool", "tool_call_id": tc.id, "content": "verdict accepted"}
                        )
                        finished = True
                        break
                    try:
                        if tc.name == "recall_similar_incidents" and self.memory is not None:
                            more = self.memory.recall(str(tc.arguments.get("query", "")))
                            hits = hits + [h for h in more if h.text not in {x.text for x in hits}]
                            out = self.memory.format_hits(more)
                            tw.feedback(
                                source="hindsight_memory", signal="recall_tool",
                                detail=hits_to_json(more), n_hits=len(more),
                            )
                        else:
                            out = dispatch(world, tc.name, tc.arguments)
                        ok = True
                    except Exception as e:  # noqa: BLE001 — surface tool errors to the model
                        out, ok = f"tool error: {type(e).__name__}: {e}", False
                        tw.error(
                            where="tool", kind=type(e).__name__, message=str(e), recoverable=True
                        )
                    if tc.name == "run_probe":
                        probes.append(
                            f"{tc.arguments.get('kind')}:{tc.arguments.get('target')} -> {out}"
                        )
                    tool_log.append(f"{tc.name}({json.dumps(tc.arguments)}) ->\n{out}")
                    tw.tool_result(
                        tool_call_id=tc.id,
                        ok=ok,
                        output=out,
                        duration_ms=int((time.monotonic() - t1) * 1000),
                    )
                    msgs.append({"role": "tool", "tool_call_id": tc.id, "content": out})
                if finished:
                    break
            if verdict is None:
                tw.error(
                    where="orchestrator",
                    kind="NoVerdict",
                    message="max steps reached without submit_verdict",
                    recoverable=False,
                )
                verdict = Verdict(summary="no verdict within step budget")
                status = "fail"
            else:
                status = "success"

            # ---- consequential action: human checkpoint, then execute in the simulation
            exec_result: dict[str, Any] | None = None
            decision, by = "skipped", "n/a"
            reviewer_ok = (reviewer_note or {}).get("approve", True) if cfg.reviewer else None
            if status == "success" and verdict.action != "no_action":
                q = f"Approve remediation `{verdict.action}` on `{verdict.target}`?"
                if cfg.approval:
                    ctx = {"reviewer_approved": reviewer_ok, "gate_rejections": rejections,
                           "verified": self._is_verified(verdict, probes)}
                    decision, note = self.approver(verdict, verdict.report_markdown, ctx)
                    by = "human" if "auto" not in note else "eval-policy"
                    tw.human_checkpoint(question=q, decision=decision, by=by, detail=note)
                else:
                    decision, by = "approved", "no-gate"
                    tw.decision(
                        summary="execute remediation without checkpoint (variant has approval=False)",
                        options_considered=["execute", "skip"],
                        chosen="execute",
                        rationale="variant flag",
                    )
                if decision == "approved":
                    exec_result = world.remediate(verdict.action, verdict.target)
                    tw.tool_call(
                        tool_call_id="remediate",
                        name="remediate",
                        input={"action": verdict.action, "target": verdict.target},
                    )
                    tw.tool_result(
                        tool_call_id="remediate",
                        ok=not exec_result["harm"],
                        output=json.dumps(exec_result),
                        duration_ms=0,
                    )
                    tw.feedback(
                        source="simulation",
                        signal="resolved"
                        if exec_result["resolved"]
                        else ("harm" if exec_result["harm"] else "no_effect"),
                        detail=exec_result["effect"],
                    )

            calls = self.llm.calls - calls_start
            wall = round(time.monotonic() - t0, 2)
            verified = self._is_verified(verdict, probes)
            meta = {
                "variant": cfg.name,
                "run_id": run_id,
                "trace": str(self.trace_root / f"{run_id}.jsonl"),
                "model": self.llm.model,
                "status": status,
                "llm_calls": calls,
                "input_tokens": 0,
                "output_tokens": 0,
                "wall_s": wall,
                "probes_run": len(probes),
                "verified": verified,
                "gate_rejections": rejections,
                "reviewer": reviewer_note,
                "reviewer_approved": reviewer_ok,
                "approval": {"decision": decision, "by": by},
                "actions_executed": world.actions_executed,
                "harm_done": world.harm_done,
                "resolved": world.resolved,
                "remediation_effect": exec_result,
                "memory_hits": len(hits),
                "memory_used": any(
                    h.root_cause == verdict.root_cause or h.action == verdict.action for h in hits
                ),
                "memory_rejections": memory_rejections,
                "memory_checks": memory_checks,
                "memory_cited": sorted(
                    {
                        h.incident_id
                        for h in hits
                        if h.incident_id
                        and (
                            h.incident_id in verdict.report_markdown
                            or h.incident_id in verdict.summary
                            or h.incident_id in " ".join(verdict.evidence)
                        )
                    }
                ),
            }
            if self.memory is not None and status == "success":
                try:
                    rec = self.memory.remember(scenario, verdict, probes, meta)
                    tw.feedback(source="hindsight_memory", signal="retain", detail=json.dumps(rec))
                    meta["memory_retained"] = rec
                except Exception as e:  # noqa: BLE001
                    tw.error(where="memory", kind=type(e).__name__, message=str(e), recoverable=True)
                    meta["memory_retained"] = None
            tw.run_end(
                status=status,
                final_output=json.dumps(asdict(verdict))[:2000],
                score=None,
                n_tool_calls=len(tool_log),
                n_retries=rejections,
                verified=verified,
                harm=bool(world.harm_done),
                resolved=world.resolved,
            )
        return RunOutcome(verdict=verdict, meta=meta)

    # ------------------------------------------------------------------ gates
    @staticmethod
    def _is_verified(v: Verdict, probes: list[str]) -> bool:
        """Verified = a probe of the kind that tests this root cause's mechanism was run."""
        kinds_run = {p.split(":", 1)[0] for p in probes}
        return bool(kinds_run & VERIFYING_PROBES.get(v.root_cause, set()))

    def _verification_gate(
        self, v: Verdict, probes: list[str], cfg: VariantConfig
    ) -> tuple[bool, str]:
        if not cfg.verify:
            return True, "ok"
        if self._is_verified(v, probes):
            return True, "ok"
        kinds = "/".join(sorted(VERIFYING_PROBES.get(v.root_cause, set()))) or "http"
        return False, (
            f"VERIFICATION REQUIRED: a `{v.root_cause}` verdict must be confirmed by a `{kinds}` probe "
            "(run_probe) before it can be accepted. Run it and submit again; if the probe contradicts "
            "you, revise the hypothesis."
        )

    def _provenance_gate(
        self, v: Verdict, probes: list[str], hits: list[MemoryHit]
    ) -> tuple[bool, str, list[str]]:
        """Memory-derived verdicts need stronger proof than fresh ones.

        A verdict whose root cause or action matches a recalled incident is accepted only if a probe
        of the verifying kind was run against the blamed service (or the action target) in THIS
        incident. The plain verification gate only checks the probe kind; here the target must match
        too, because "the same symptom" is exactly when a remembered fix is most tempting and most
        likely to be wrong.
        """
        recalled = [h for h in hits if h.root_cause == v.root_cause or h.action == v.action]
        if not recalled:
            return True, "fresh verdict (no matching memory)", []
        sources = sorted({h.incident_id for h in recalled if h.incident_id})
        need = VERIFYING_PROBES.get(v.root_cause, set())
        ok_probes = []
        for p in probes:
            kind, rest = p.split(":", 1)
            target = rest.split(" ->", 1)[0].strip()
            if kind in need and target in (v.service, v.target):
                ok_probes.append(p[:120])
        if ok_probes:
            return True, f"memory-derived verdict re-verified in this incident by {ok_probes[0]}", sources
        kinds = "/".join(sorted(need)) or "http"
        return False, (
            f"RECALLED, NOT VERIFIED: this verdict matches memory of incident(s) {', '.join(sources) or 'unknown'}. "
            "Memory describes the past, not this incident. Run `run_probe` "
            f"(kind {kinds}) against `{v.service or v.target}` now. If the result does not show the same "
            "mechanism as the remembered incident, revise the hypothesis instead of reusing the old fix."
        ), sources

    def _review(self, v: Verdict, tool_log: list[str], tw: TraceWriter) -> dict[str, Any]:
        sys_p = (PROMPTS / "reviewer_system.md").read_text()
        transcript = "\n\n".join(tool_log)[-24000:]
        user = f"INVESTIGATION TRANSCRIPT:\n{transcript}\n\nPROPOSED VERDICT:\n{json.dumps(asdict(v), indent=1)[:6000]}"
        tw.instruction(role="system", name="reviewer_system.md", content=sys_p)
        tw.llm_request(n_messages=2, tools_offered=[], agent="reviewer")
        resp = self.llm.chat(
            [{"role": "system", "content": sys_p}, {"role": "user", "content": user}],
            max_tokens=8192,
        )
        tw.llm_response(
            stop_reason=resp.stop_reason,
            text=resp.text,
            tool_calls=[],
            output_tokens=resp.output_tokens,
            latency_ms=resp.latency_ms,
            agent="reviewer",
        )
        try:
            d = parse_json_block(resp.text)
        except Exception as e:  # noqa: BLE001
            tw.error(
                where="parser",
                kind=type(e).__name__,
                message=f"reviewer output unparseable: {e}",
                recoverable=True,
            )
            d = {
                "approve": True,
                "issues": [],
                "note": "reviewer output unparseable; approved by default",
            }
        tw.feedback(
            source="reviewer_agent",
            signal="approve" if d.get("approve") else "reject",
            detail=json.dumps(d)[:2000],
        )
        return d
