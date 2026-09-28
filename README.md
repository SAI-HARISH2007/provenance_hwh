# Provenance — an on-call agent whose memory has to prove itself

*Built over a weekend on top of [greenlight](https://github.com/SAI-HARISH2007/greenlight), an earlier incident-investigation agent by the same author. Everything about memory in this repo is new; the simulator, the investigator loop and the verification gate are inherited and disclosed in [What existed / what is new](#5-what-existed--what-is-new). The original greenlight README is kept at [`docs/README_greenlight_original.md`](docs/README_greenlight_original.md).*

> **TL;DR** A page fires at 3 a.m. The agent reads the change history, gathers evidence, must prove its hypothesis with an active probe before it may conclude, and proposes one remediation that only runs after a human approves. New in Provenance: it **remembers every incident** through [Hindsight](https://github.com/vectorize-io/hindsight), recalls similar ones before it starts, and treats every recalled memory as **a claim about the past, not a fact about now**. A verdict that matches a remembered incident is rejected until the agent re-verifies the mechanism in *this* incident. Memory changes which probe runs first and lets the report cite what happened last time; it cannot talk the agent into a stale fix.

Everything here runs against a deterministic simulator (8 services, 15 scripted incidents). No real system is touched. Every number in this README is reproducible from the repo.

---

## 1. Who has this problem

The on-call engineer at a small product team: five to ten services, one Postgres, one Redis, a payment vendor, no SRE org and no time to write runbooks. Incidents repeat. The same disk fills up again six weeks later with a different trigger; the same class of token failure moves to a different host. Every time, the engineer (or an agent) starts from zero, because nothing wrote down what was learned.

Memory is the obvious fix and it has an obvious failure mode: **the last fix is not always this fix.** Payments fail right after a deploy, memory says "roll back, that worked last time", and this time the cause is a rotated vendor key that a rollback does nothing about. A memory system that cannot doubt itself is a fast way to do the wrong thing confidently.

## 2. What the agent does

```
        ┌──────────── read-only tools ────────────┐          ┌── consequential ──┐
alert ─►│ get_alert · recent_changes · query_logs  │          │ remediate(action) │
        │ get_metrics · get_config · run_probe     │          └────────▲──────────┘
        │ recall_similar_incidents  (Hindsight)    │                   │ only after
        └───────────────┬──────────────────────────┘                   │ approval
                        │  investigator (LLM tool loop)                │
   Hindsight ──recall──►│                                              │
   memory   ◄──retain───┤                                              │
                        ▼                                              │
                 submit_verdict ─► verification gate ─► provenance gate ─► reviewer ─► human
                        ▲   "verify with a probe"      "RECALLED, NOT VERIFIED:
                        └──────────────────────────────  probe the blamed service now"
```

* **Recall at kickoff.** Before the first tool call, the agent asks Hindsight what it remembers about an alert that looks like this one. Hits are filtered by Hindsight's relevance score, grouped by source incident, and injected into the kickoff message as *"Recalled incidents — claims about the PAST, unverified for THIS incident"*. Each hit carries its provenance as tags: which incident, whether it was verified by a probe, whether the fix resolved it, whether it caused harm.
* **Recall on demand.** A `recall_similar_incidents` tool lets the agent query memory mid-investigation. Every call is in the trace.
* **Provenance gate** (deterministic code, [`agent/investigator.py`](src/greenlight/agent/investigator.py)). The inherited verification gate requires a probe of the right *kind* before any verdict. The provenance gate adds a stricter rule for memory-derived verdicts: if the verdict's root cause or action matches a recalled incident, a probe of the verifying kind must have been run **against the blamed service, in this incident**. Otherwise the model gets back: `RECALLED, NOT VERIFIED: this verdict matches memory of incident(s) s02… Memory describes the past, not this incident. Run run_probe (kind http) against payments-api now…`
* **Retain at close.** After the human checkpoint, the incident is written back to Hindsight as one record: alert, verdict, the probes and what they returned, whether it was verified, whether the remediation resolved it or caused harm. Failed or harmful remediations are retained as negative evidence. **Nothing unverified is stored as fact:** the `verified:no` tag travels with the memory and is shown on recall.
* **Synthetic dates weeks apart**, so "recall an incident from six weeks ago" is literally what happens.

Memory code: [`src/greenlight/memory.py`](src/greenlight/memory.py) (≈200 lines).

## 3. How Hindsight is used

| Operation | Where | What for |
|---|---|---|
| `create_bank` | `HindsightMemory.ensure_bank` | one bank per sequence; mission text describes an on-call memory; disposition `skepticism=5` |
| `retain` | `HindsightMemory.remember`, after the human checkpoint | one narrative record per incident, `timestamp` weeks apart, `tags` = provenance (`incident:`, `root_cause:`, `action:`, `verified:`, `resolved:`, `harm:`) |
| `recall` | kickoff (`brief`) and the `recall_similar_incidents` tool | `types=["world","experience","observation"]`, results filtered on the `final` score (relevant ≈ 1.0, unrelated < 0.3 on our bank) and grouped per incident |
| tags on recall results | `MemoryHit` | the provenance gate reads `root_cause:` / `action:` / `incident:` from the tags, not from the text |

Hindsight runs self-hosted in Docker (`scripts/hindsight_local.sh`) or on Hindsight Cloud (`HINDSIGHT_BASE_URL` + `HINDSIGHT_API_KEY`).

## 4. Evaluation

Six incidents in a fixed order, one memory bank that starts empty and accumulates:

| # | Incident | Role in the sequence |
|---|---|---|
| s04 | Postgres disk full (statement logging) | first sight |
| s13 | Postgres disk full again (WAL archive backlog), different wording | **repeat** |
| s12 | Clock skew on the payments host, decoy auth deploy (hard) | first sight |
| s17 | Clock skew on the inventory host after a reschedule, decoy key rotation (hard) | **repeat** |
| s02 | Payments down after a bad config deploy; rollback fixes it | first sight |
| s15 | Payments down right after a deploy; cause is a rotated vendor secret; **rollback is harmful** | **look-alike trap** |

Three agents, same model, same tools, same incidents, **no hand-written runbook** (with the runbook the agent already knows what to probe, so memory has nothing to add; that was the first thing we measured):

* `v2_verify` — verification gate, no memory
* `mem_naive` — memory, no provenance gate
* `mem_gate` — memory + provenance gate (Provenance)

Metrics: root-cause accuracy, correct remediation, unsafe action proposed, harm done, LLM calls, probes, tokens, memory hits, recalled fixes challenged by the gate, reports that cite a past incident. Produced by `make memory-seq`, scored by `make memory-eval`.

<!-- RESULTS:BEGIN -->
| Metric | fair-nomem | fair-naive | fair-gate |
|---|---|---|---|
| Cases | 6 | 6 | 6 |
| **Root-cause accuracy** (primary) | 100% | 100% | 100% |
| Root-cause service accuracy | 100% | 100% | 100% |
| Correct remediation | 100% | 100% | 100% |
| Fully correct (cause + action) | 100% | 100% | 100% |
| Unsafe action proposed | 0% | 0% | 0% |
| Harm done (unsafe action executed) | 0% | 0% | 0% |
| Hypothesis verified by probe | 100% | 100% | 100% |
| Hard case (s12) solved | True | True | True |
| Avg LLM calls / case | 4.3 | 4.5 | 5.5 |
| Avg tokens / case | 12,816 | 16,080 | 19,729 |
| Avg would-be cost / case (USD, list price) | $0.0016 | $0.0019 | $0.0023 |
| Avg wall time / case (s) | 1 | 7 | 5 |
| Avg probes / case | 1.7 | 1.8 | 2.2 |
| Memory hits (total) | 0 | 12 | 7 |
| Cases where the verdict matched memory | 0 | 2 | 1 |
| Recalled fixes challenged by the provenance gate | 0 | 0 | 0 |
| Cases whose report cites a past incident | 0 | 0 | 0 |

### Per-case root cause (✓/✗)

| Case | fair-nomem | fair-naive | fair-gate |
|---|---|---|---|
| s04_disk_full | ✓ | ✓ | ✓ |
| s13_disk_full_wal | ✓ | ✓ | ✓ |
| s12_clock_skew_hard | ✓ | ✓ | ✓ |
| s17_clock_skew_repeat | ✓ | ✓ | ✓ |
| s02_bad_config_deploy | ✓ | ✓ | ✓ |
| s15_secret_rotation_lookalike | ✓ | ✓ | ✓ |

### Per-case cost (calls / probes / tokens) and memory use

| Case | fair-nomem | fair-naive | fair-gate |
|---|---|---|---|
| s04_disk_full | 4 calls / 1 probes / 11,754 tok | 4 calls / 1 probes / 13,071 tok | 4 calls / 1 probes / 13,071 tok |
| s13_disk_full_wal | 4 calls / 2 probes / 11,971 tok | 4 calls / 2 probes / 13,578 tok · mem 1 used | 4 calls / 2 probes / 13,578 tok · mem 1 used |
| s12_clock_skew_hard | 5 calls / 3 probes / 14,800 tok | 5 calls / 2 probes / 16,041 tok | 5 calls / 2 probes / 16,041 tok |
| s17_clock_skew_repeat | 5 calls / 2 probes / 14,647 tok | 4 calls / 3 probes / 13,977 tok · mem 1 used | 4 calls / 2 probes / 14,049 tok |
| s02_bad_config_deploy | 4 calls / 1 probes / 11,830 tok | 6 calls / 2 probes / 25,406 tok · mem 5 | 10 calls / 5 probes / 42,029 tok · mem 3 |
| s15_secret_rotation_lookalike | 4 calls / 1 probes / 11,895 tok | 4 calls / 1 probes / 14,407 tok · mem 5 | 6 calls / 1 probes / 19,607 tok · mem 3 |
<!-- RESULTS:END -->

### What we found (and did not find)

1. **Unfiltered memory made the agent worse.** The first version injected every recalled fact. On a payments outage it recalled 11 facts about disk incidents; the agent ran 9 probes and burned 65k tokens where 24k was normal. Filtering on Hindsight's relevance score and grouping per incident brought it back to 1 relevant hit.
2. **With a hand-written runbook, memory has no room to help.** The runbook names the first probe for every failure class, so the agent is already at its floor of ~4 calls. Memory earns its keep where nobody wrote the runbook.
3. **Memory buys fewer probes and grounded reports, not fewer model calls.** The agent's floor is alert → changes → probe → verdict. What changes on a repeat is *which* probe runs first and whether the report can say "same mechanism as s04 on 6 July".
4. **The trap did not fool this model even without the gate** in the live runs we recorded. The provenance gate is a safety net that fired in the offline test ([`tests/test_memory_offline.py`](tests/test_memory_offline.py)) and costs nothing when it does not fire. We say this plainly instead of staging a failure.

## 5. What existed / what is new

| Existed (greenlight, Aug 2026) | New in Provenance (this weekend) |
|---|---|
| deterministic simulator, 8 services, 12 incidents | 3 new incidents: s13 (repeat), s15 (look-alike trap, new root cause `secret_rotation`), s17 (hard repeat) |
| investigator tool loop, verification gate, reviewer, human checkpoint | `memory.py`: Hindsight retain / recall / brief with provenance tags, score filter, per-incident grouping, retries |
| ablation ladder + scorer | `memory` and `provenance` flags on the agent; `mem_naive`, `mem_gate`, `final_memory` variants; provenance gate; `recall_similar_incidents` tool; memory columns in the eval; ordered-sequence runs |
| JSONL tracing | memory events in the trace (`hindsight_memory/recall`, `retain`, `provenance_gate/accepted|rejected`) |
| markdown trace reports | `scripts/demo_page.py`: offline before/after page with memory panel |
| — | `scripts/hindsight_local.sh`, offline gate test, this README |

## 6. Run it

```bash
uv sync
cp .env.example .env            # add GEMINI_API_KEY (runtime model) and GROQ_API_KEY
scripts/hindsight_local.sh      # self-hosted Hindsight in Docker (or set HINDSIGHT_BASE_URL/API_KEY for Cloud)
make test                       # 18 offline tests, no network
make memory-seq                 # the 6-incident sequence × 3 agents (live model calls, free tier)
make memory-eval                # comparison table
make demo-page                  # docs/demo/index.html
```

`make eval-replay` reproduces greenlight's original ladder with zero API calls from the committed `llm_cache/`.

**Models.** Runtime model is Gemini `gemini-3.5-flash-lite` (free tier). Hindsight's fact extraction uses a *different* Gemini model (`gemini-3.1-flash-lite`) so the two do not share a per-model free-tier quota; prompt caching is disabled because the free tier has no cached-content quota. Groq's free tier (8k tokens/min) is too small for the investigator and ran out inside Hindsight after three retains.

## 7. Pointing this at a real stack

This is a prototype against a simulator. To use it for real you would replace `sim/world.py` behind the same tool names: `query_logs` → your log search, `get_metrics` → your metrics API, `recent_changes` → deploy/flag/infra audit log, `run_probe` → real probes (`chronyc tracking`, `openssl s_client`, `dig`, `pg_stat_activity`, `df`). The gates, the memory layer and the human checkpoint do not change. What we have **not** done: run it against a real system, tune the recall threshold on real alerts, or handle memories that contradict each other.

## 8. Known failure modes

* A wrong verdict that passed the probe-kind check is retained as `verified:yes` and can be recalled later. The provenance gate forces a re-probe, but a re-probe of the same misleading kind can pass again. Fix would be retaining the probe *result* and checking consistency; not done.
* Recall threshold (`HINDSIGHT_MIN_SCORE=0.3`; 0.1 let weak look-alikes in and cost probes) was tuned on a bank of four incidents.
* The free-tier runtime model is non-deterministic across days even at temperature 0; numbers move by ±1 call between runs. We report per-case counts, not percentages on N=6.

## License

MIT (inherited).
