# Greenlight — an on-call incident investigator that must prove it before it acts

*micro1 Frontier Engineering Challenge 2026 · individual entry · everything below is reproducible with zero API calls (`make eval-replay`).*

> **TL;DR** A page fires at 3 a.m. Today the on-call engineer spends 30–60 minutes correlating logs, metrics and last night's deploys before daring to touch anything — and a wrong first action makes it worse. Greenlight is an agent that investigates the way a good SRE does: it reads the change history, forms hypotheses, **verifies the mechanism with a probe before it is allowed to conclude**, writes a postmortem-grade incident report, and proposes one remediation that only executes after a human clicks *approve*. Against a fair baseline (the same model, given the evidence pasted into one prompt) it is evaluated on 12 seeded incidents — see [Results](#results).

---

## 1. Who has this problem, and what is the bottleneck?

**User:** the on-call engineer at a small product team (no dedicated SRE org, 5–10 services, one Postgres, one Redis, a payment vendor).

**Bottleneck:** when the pager fires, the evidence is scattered across a log search, a metrics dashboard, a deploy log, a feature-flag UI and a vendor status page. Root-causing is mostly *correlation work* — which of the last six changes lines up with the moment the error rate moved? — followed by a judgement call about the smallest safe action. Two things go wrong at 3 a.m.:

1. **Slow diagnosis.** The symptom is rarely in the service that alerts (a gateway 5xx spike is usually somebody else's fault). Typical time-to-diagnosis on our scenarios, estimated per case in `scenarios.py`: 25–55 min.
2. **Unsafe first actions.** Under pressure people restart Postgres to "clear connections" (dropping every in-flight order), roll back the most recent deploy even when it is unrelated, or page the vendor when the problem is our own batch job. Each of our scenarios encodes at least one such tempting-but-harmful action.

**Why solving it is valuable:** every minute of checkout downtime is lost revenue and an angry customer; every harmful remediation turns a 20-minute incident into a 2-hour one. A tool that gets a *verified* root cause and a *safe* proposal in front of the human in two minutes changes what the human spends the incident doing — approving, not searching.

## 2. What the agent does (and what it is not allowed to do)

```
        ┌──────────── read-only tools ────────────┐          ┌── consequential ──┐
alert ─►│ get_alert · recent_changes · query_logs  │          │ remediate(action) │
        │ get_metrics · get_config · run_probe     │          └────────▲──────────┘
        └───────────────┬──────────────────────────┘                   │ only after
                        │  investigator (LLM tool loop)                │ approval
                        ▼                                              │
                 submit_verdict ──► verification gate ──► reviewer ──► human checkpoint
                        ▲   rejected: "verify with a probe"   ▲  rejected: issues + checks
                        └──────────────────────────────────────┘
```

* **Investigator** — a single tool-using loop with a short method (read changes → hypotheses → gather evidence → *verify with a probe* → submit). Instructions: [`src/greenlight/prompts/agent_system.md`](src/greenlight/prompts/agent_system.md).
* **Verification gate** (deterministic code, not an LLM) — a verdict is rejected unless a `run_probe` was executed against the service it blames. The rejection is fed back to the model as a tool result, so the loop closes.
* **Runbook memory** — [`src/greenlight/knowledge/runbook.md`](src/greenlight/knowledge/runbook.md): the team's symptom→first-checks table and safety rules, injected as context. It never names an answer, only what to check.
* **Reviewer agent** — a second prompt ([`reviewer_system.md`](src/greenlight/prompts/reviewer_system.md)) that reads the full tool transcript and the verdict and checks evidence, victim-vs-cause confusion, safety and untested alternatives. A rejection goes back to the investigator with suggested checks.
* **Human checkpoint** — the proposed action is never executed by the agent. `make demo` shows the report and asks; in eval mode an explicit auto-approve policy stands in for the human, and every checkpoint is a `human_checkpoint` event in the trace.
* **Sandbox / simulation** — all actions run against a deterministic simulator (`src/greenlight/sim/`) that models 8 services with 30-minute metric series, structured logs, change history, active probes, and the *consequences* of each action (including the harmful ones). No real system is touched.

## 3. Evaluation design

* **12 scenarios** (`src/greenlight/sim/scenarios.py`), one per root-cause label: pool exhaustion, bad config deploy, expired TLS cert, disk full, vendor outage, memory leak/OOM, cache eviction stampede, vendor rate limit caused by our own job, DNS after a namespace move, migration lock, feature-flag misconfig, and **s12 (hard)**: clock skew on one host masquerading as an auth-deploy problem, with a very tempting rollback that would log out 18k users.
* Every scenario has ≥1 red herring, an alert that names the *symptom* service, and logs that show symptoms (TLS handshake errors, `Input/output error`, exit code 137) rather than spelling out the cause — the mechanism is confirmed by a probe, a metric turning at the moment of a change, or config.
* **Baseline:** one direct prompt, same model, same taxonomy, same JSON contract. Two versions are reported for fairness: *alert scope* (the realistic 3 a.m. paste: alert, service statuses, 24h changes, dashboard summary of every metric, config + last 40 log lines of the alerting service) and *full scope* (config + logs of all 8 services and every full metric series, ~21k tokens).
* **Resource difference, stated plainly:** the agent can run active probes (`run_probe cert/clock/dns/db/disk/http`); a pasted dump cannot contain those. Everything else (logs, metrics, config, changes) is available to both.
* **Primary metric:** root-cause accuracy@1. Secondary: correct remediation, unsafe action proposed, harm done when executed, verified-by-probe rate, LLM calls / tokens / would-be cost per case, wall time; human time estimated per scenario.

## 4. Results

Model: `gemini-3.5-flash-lite` (free tier), temperature 0, 12 cases, same taxonomy and output contract for every column. Produced by `make eval-ladder`; reproduce with zero API calls via `make eval-replay`.

| Metric | baseline | baseline-full | baseline-2.5flash | v1_tools-lite | v2_verify_gate1-lite | v2_verify-lite | v3_runbook-lite | v4_reviewer-lite | final |
|---|---|---|---|---|---|---|---|---|---|
| Cases | 12 | 12 | 12 | 12 | 12 | 12 | 12 | 12 | 12 |
| **Root-cause accuracy** (primary) | 83% | 92% | 75% | 100% | 92% | 100% | 100% | 100% | 100% |
| Root-cause service accuracy | 75% | 75% | 58% | 83% | 58% | 83% | 92% | 92% | 92% |
| Correct remediation | 83% | 75% | 58% | 83% | 67% | 83% | 92% | 100% | 100% |
| Fully correct (cause + action) | 75% | 75% | 58% | 83% | 67% | 83% | 92% | 100% | 100% |
| Unsafe action proposed | 8% | 0% | 8% | 0% | 8% | 0% | 0% | 0% | 0% |
| Harm done (unsafe action executed) | 0% | 0% | 0% | 0% | 8% | 0% | 0% | 0% | 0% |
| Hypothesis verified by probe | 0% | 0% | 0% | 92% | 92% | 100% | 100% | 100% | 100% |
| Hard case (s12) solved | False | False | False | True | False | True | True | True | True |
| Avg LLM calls / case | 1.0 | 1.0 | 1.0 | 4.8 | 6.7 | 4.9 | 4.8 | 6.0 | 6.0 |
| Avg tokens / case | 5,278 | 21,206 | 5,775 | 14,483 | 22,770 | 15,274 | 17,417 | 20,747 | 20,747 |
| Avg would-be cost / case (USD, list price) | $0.0007 | $0.0023 | $0.0043 | $0.0017 | $0.0026 | $0.0018 | $0.0020 | $0.0024 | $0.0024 |
| Avg wall time / case (s) | 0 | 11 | 21 | 13 | 10 | 1 | 0 | 0 | 0 |

### Per-case root cause (✓/✗)

| Case | baseline | baseline-full | baseline-2.5flash | v1_tools-lite | v2_verify_gate1-lite | v2_verify-lite | v3_runbook-lite | v4_reviewer-lite | final |
|---|---|---|---|---|---|---|---|---|---|
| s01_db_pool_exhausted | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| s02_bad_config_deploy | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| s03_tls_cert_expired | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| s04_disk_full | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| s05_third_party_outage | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| s06_memory_leak_oom | ✓ | ✓ | ✗ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| s07_cache_eviction_stampede | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| s08_third_party_rate_limited | ✓ | ✓ | ✗ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| s09_dns_resolution_failure | ✗ | ✓ | ✓ | ✓ | ✓ ⚠ | ✓ | ✓ | ✓ | ✓ |
| s10_migration_lock_contention | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| s11_feature_flag_misconfig | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| s12_clock_skew_hard | ✗ ⚠ | ✗ | ✗ ⚠ | ✓ | ✗ | ✓ | ✓ | ✓ | ✓ |
| Case | baseline | baseline-full | baseline-2.5flash | v1_tools-lite | v2_verify_gate1-lite | v2_verify-lite | v3_runbook-lite | v4_reviewer-lite | final |
|---|---|---|---|---|---|---|---|---|---|
| s01_db_pool_exhausted | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| s02_bad_config_deploy | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| s03_tls_cert_expired | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| s04_disk_full | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| s05_third_party_outage | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| s06_memory_leak_oom | ✓ | ✓ | ✗ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| s07_cache_eviction_stampede | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| s08_third_party_rate_limited | ✓ | ✓ | ✗ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| s09_dns_resolution_failure | ✗ | ✓ | ✓ | ✓ | ✓ ⚠ | ✓ | ✓ | ✓ | ✓ |
| s10_migration_lock_contention | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| s11_feature_flag_misconfig | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| s12_clock_skew_hard | ✗ ⚠ | ✗ | ✗ ⚠ | ✓ | ✗ | ✓ | ✓ | ✓ | ✓ |


**In the PDF's suggested format** (baseline = realistic paste, agent = final):

| Metric | Simple baseline | Agent solution | Change |
|---|---|---|---|
| Primary outcome — root cause correct | 83% | 100% | +17 pp |
| Correct *and safe* remediation proposed | 83% | 100% | +17 pp |
| Hypothesis verified by an active probe | 0% | 100% | +100 pp |
| Harmful action executed | 0% | 0% | +0 pp |
| Human time per incident (estimate, see note) | ~12 min to collect the paste + ~20 min to validate a guess and act | ~3 min to read the report and approve | ≈ −29 min |
| Cost per incident (list price; actual $0 on free tier) | $0.0007 | $0.0024 | 3.3× |

*Human-time note:* the baseline still needs a person to gather logs/metrics/changes into one paste (we timed ~12 min for one scenario by hand) and to validate an unverified guess before acting; the agent's output arrives verified with the evidence attached, so the human's job is reading and approving. These are estimates, not measurements, and are not used anywhere else.

**The challenging case (s12, clock skew).** The alert points at the gateway, auth-api is healthy, and a fresh auth deploy that changed the JWT signing algorithm is sitting in the change log 33 minutes before the page. The realistic-paste baseline blames the auth deploy and proposes rolling it back — the one action that would make things worse; even the 21k-token full dump blames the deploy. The agent probes clocks on three hosts, finds payments-3 running 412 s slow, and proposes `sync_clock` — never touching the auth deploy, which a rollback would have turned into a forced re-login for 18k users. What it revealed: the strongest lever is *cheap active checks* — a single `clock` probe settles a case that an hour of log reading cannot.

**What did not improve:** token cost. The agent uses ~4× the tokens of the realistic paste (and about the same as the full dump), because every tool result re-enters the context. The 100% verification rate is bought with tokens, not free.

## 5. Improvement changelog

All rows use the same 12 cases and the same scorer (`src/greenlight/eval.py`). Every run uses `gemini-3.5-flash-lite` (free tier, ~1,000 req/day); `gemini-2.5-flash` appears once as a reference baseline — its free quota was exhausted after ~30 calls, before the agent could run on it (see REPRODUCE.md). Every number links to a results directory under `eval/results/` and a trace under `traces/`.

| Stage | What we tried and why | Evidence (root cause · correct action · unsafe · verified · calls/case) | Decision / learning |
|---|---|---|---|
| **Baseline** | One prompt with the realistic 3 a.m. paste (alert, statuses, 24h changes, dashboard summary, alerting service's config + logs). Also a *full-dump* variant with every service's logs and metric series (~21k tokens). | `baseline`: **83% · 83% · 8% · 0% · 1.0** — misses s09 and the hard case s12, where it proposes rolling back the auth deploy (the harmful decoy). `baseline-full` (21k-token dump): 92% · 75% · 0% · 0% · 1.0 — still misses s12. Reference `baseline-2.5flash` (stronger model, same paste): 75% · 58% · 8% · 0% · 1.0 | Established the starting point. Labeling the common cases is easy; the paste-and-guess approach fails exactly where it matters — the case with a convincing decoy — and it proposes the harmful action there. |
| Iteration 1 — tools | Replace the paste with read-only tools (`query_logs`, `get_metrics`, `get_config`, `recent_changes`, `run_probe`). Hypothesis: active evidence beats passive evidence, especially probes. | `v1_tools-lite`: 100% · 83% · 0% · 92% · 4.8 | Kept. Solves the hard case, zero unsafe proposals, and 11/12 verdicts came with a probe unprompted — but one did not, and two remediations were still wrong (s01 raises the DB pool instead of stopping the worker; s08 adds a circuit breaker instead of stopping our own backfill). |
| Iteration 2a — verification gate v1 | Reject any `submit_verdict` unless a probe was run *against the blamed service*. Hypothesis: forcing verification fixes the unverified 17%. | `v2_verify_gate1-lite` (run on the pre-`update_config` taxonomy, kept as evidence): 92% · 67% · 8% · 92% · 6.7 — **worse**. s09: a correct DNS verdict (probe `dns inventory-api.default.svc → NXDOMAIN`) was rejected twice because the target string was not the blamed service; the agent then rolled back an unrelated deploy (harm). s12: found the clock skew at step 15 of 14 — no verdict. | **Removed.** A gate that cannot recognise valid evidence is worse than no gate: the agent keeps acting under pressure and drifts to harmful actions. Traces: `traces/*v2-verify-s09*`, `*v2-verify-s12*` (first timestamps). |
| Iteration 2b — gate v2 + budget | Gate checks the probe *kind* against the root-cause mechanism (`dns_resolution_failure` ⇒ a `dns` probe), URL-shaped probe targets are normalised, and the orchestrator warns at 3 steps left; max steps 14 → 16. | `v2_verify-lite`: 100% · 83% · 0% · **100%** · 4.9 | Kept. Every verdict verified, hard case back, no harm, no extra calls. Offline regression tests pin both bugs (`tests/test_agent_offline.py::test_gate_accepts_dns_probe…`, `tests/test_sim.py::test_probe_targets_are_normalised`). |
| Iteration 3 — runbook memory | Inject the team runbook (symptom → first checks, safety rules; never an answer). Hypothesis: fewer wasted steps, safer actions. | `v3_runbook-lite`: 100% · 92% · 0% · 100% · 4.8; s01 fixed (runbook: "ask *who* holds the connections"); s08 still contains the symptom instead of stopping the job. In the pre-taxonomy run the hard case dropped from 14 calls to 5. | Kept. Caveat, stated plainly: the runbook was written by us with knowledge of the scenario families, so its gain is an upper bound; v2 (no runbook) already solved every root cause. |
| Iteration 4 — reviewer agent | A second prompt reads the whole tool transcript and the verdict; rejects on missing evidence, victim-vs-cause confusion, unsafe action, untested alternative. | First run (pre-taxonomy, `eval/results/_pre_taxonomy/v4_reviewer-lite`): 100% · 83% · 8% · 100% · 7.2 — s09 *still* harmful: the reviewer correctly rejected `rollback orders-api` three times, but the action taxonomy had no "fix the caller's config" option, so the last rejected verdict was executed by the eval's auto-approve. After the fixes: `v4_reviewer-lite` **100% · 100% · 0% · 100% · 6.0** (s08: reviewer sends the investigator back to stop the backfill). | Two fixes: (i) `update_config` added to the taxonomy — the eval found a real gap; truth sets extended for functionally equivalent config fixes (disclosed; all runs re-scored); (ii) approval policy now **refuses to auto-approve a verdict the reviewer rejected** — disagreement goes to a human, never to execution (`default_eval_approver`). |
| **Final** | tools + gate v2 + runbook + reviewer + reviewer-consensus approval | `final`: **100% · 100% · 0% · 100% · 6.0**, 20.7k tokens/case; identical to v4 on these cases because the reviewer approved every final verdict — the consensus policy only changes outcomes when it does not (offline test `test_reviewer_rejection_on_final_attempt_blocks_autonomous_execution`). | Main contribution: the verification gate (v2) — it moved verified-rate from 83% to 100% and is what makes the reviewer's judgement checkable. |

Wall-clock per case is 3–25 s live on the free tier (dominated by provider latency and 429 back-off; the agent's 5–6 sequential calls take ~10–20 s); cached replays run in <1 s, so timing is deliberately not in the table.

## 6. Main failure mode

**Correct diagnosis, wrong action, executed anyway.** In three separate development runs of s09 (DNS name retired after a namespace move; results kept under `eval/results/_pre_taxonomy/` and `v2_verify_gate1-lite`) the agent identified the cause correctly and still ended up rolling back an unrelated deploy — once because the verification gate rejected valid evidence, once because the runbook didn't cover the case, and once because the reviewer rejected the bad action but there was no *good* action in the taxonomy to switch to and the eval policy auto-approved whatever came last. The diagnosis machinery was never the weak link; the path from verdict to action was. The fix that finally held was not a smarter prompt but a policy: no autonomous execution without reviewer consensus.

Second, smaller one: Gemini 3.x on the free tier emits visible reasoning inside the completion; with a 4k output budget 3 of 12 baseline answers were truncated mid-JSON. This looked like a model failure and was a budget setting.

## 7. Hot take

**Verification gates are code, and untested code in the control loop is more dangerous than an unverified model.** Gate v1 was eleven lines and "obviously right"; it turned a 100%-correct investigator into one that rolled back production deploys, because a rejected agent doesn't stop — it tries something else, and "something else" under budget pressure skews toward the most visible recent change. The lesson we'd carry into the next agent: treat every deterministic check that can reject the model as a component with its own test suite and its own failure budget, log every rejection as a first-class trace event, and make the *default* outcome of persistent disagreement "ask a human", not "last answer wins".

## 8. Tools used (disclosure)

* **Runtime models:** Google Gemini via the OpenAI-compatible endpoint, free tier — `gemini-3.5-flash-lite` for every reported run, `gemini-2.5-flash` for one reference baseline; Groq `openai/gpt-oss-120b` configured as a fallback for small requests (never used for a reported number). No paid API usage; every LLM response is cached in `llm_cache/` for replay.
* **What existed before the competition:** nothing project-specific; standard libraries (`openai`, `python-dotenv`, `pytest`, `ruff`, `uv`).

## 9. Repository map

| Path | What |
|---|---|
| `src/greenlight/sim/` | deterministic incident simulator + 12 scenarios (truth, evidence, action consequences) |
| `src/greenlight/agent/` | tool schemas, investigator loop, verification gate, reviewer, approval checkpoint |
| `src/greenlight/prompts/`, `knowledge/` | the instructions that shape each agent + the runbook memory |
| `src/greenlight/baseline.py` | the one-prompt baseline |
| `src/greenlight/llm.py` | provider gateway: cache (replay), quota-aware retry, fallback |
| `src/greenlight/tracing/` | JSONL trajectory writer (schema in `docs/TRACE_SCHEMA.md`) |
| `src/greenlight/eval.py` | scorer + comparison table |
| `eval/results/` | per-case JSON, incident reports, `summary.json`, `comparison.md` |
| `traces/` | one JSONL per run; `docs/traces/` rendered Markdown |
| `REPRODUCE.md` | clean-environment guide |
