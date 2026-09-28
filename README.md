# Provenance — an on-call agent whose memory has to prove itself

*Built over a weekend on top of [greenlight](https://github.com/SAI-HARISH2007/greenlight), an earlier incident-investigation agent by the same author. Everything about memory in this repo is new; the simulator, the investigator loop and the verification gate are inherited and disclosed in [What existed / what is new](#5-what-existed--what-is-new). The original greenlight README is kept at [`docs/README_greenlight_original.md`](docs/README_greenlight_original.md).*

> **TL;DR** A page fires at 3 a.m. The agent reads the change history, gathers evidence, must prove its hypothesis with an active probe before it may conclude, and proposes one remediation that only runs after a human approves. New in Provenance: it **remembers every incident** through [Hindsight](https://github.com/vectorize-io/hindsight), recalls similar ones before it starts, and treats every recalled memory as **a claim about the past, not a fact about now**. A verdict that matches a remembered incident is rejected until the agent re-verifies the mechanism in *this* incident. Memory changes which probe runs first and lets the report cite what happened last time; it cannot talk the agent into a stale fix.

Everything here runs against a deterministic simulator (8 services, 16 scripted incidents). No real system is touched. Every number in this README is reproducible from the repo.

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

Memory code: [`src/greenlight/memory.py`](src/greenlight/memory.py), ~330 lines including the docstrings.

## 3. How Hindsight is used

| Operation | Where | What for |
|---|---|---|
| `create_bank` | `HindsightMemory.ensure_bank` | one bank per sequence; mission text describes an on-call memory; disposition `skepticism=5` |
| `retain` | `HindsightMemory.remember`, after the human checkpoint | one narrative record per incident, `timestamp` weeks apart, `tags` = provenance (`incident:`, `root_cause:`, `action:`, `verified:`, `resolved:`, `harm:`) |
| `recall` | kickoff (`brief`) and the `recall_similar_incidents` tool | `types=["world","experience","observation"]`, results filtered on the `final` score (relevant ≈ 1.0, unrelated < 0.3 on our bank) and grouped per incident |
| tags on recall results | `MemoryHit` | the provenance gate reads `root_cause:` / `action:` / `incident:` from the tags, not from the text |
| age limit | `filter_by_age` in `memory.py` | `HINDSIGHT_MAX_AGE_DAYS=N` drops recalled incidents older than N days (default 0 = no limit); undated hits are kept |

Hindsight runs self-hosted in Docker or on Hindsight Cloud.

**Self-hosted, one command.** [`docker-compose.yml`](docker-compose.yml) is the same container the
shell script starts, with the volume and ports already set:

```bash
cp .env.example .env        # put GEMINI_API_KEY in it (docker compose reads .env for you)
make hindsight              # docker compose up -d hindsight, then wait for /health
```

or, without make: `docker compose up -d hindsight` and wait for `curl -sf http://localhost:8888/health`
to answer. `scripts/hindsight_local.sh [gemini|groq]` does the same thing and is what you want if
Groq should do the extraction (it needs Groq's own provider/base-url handling — see the comments in
the compose file). Hindsight is on `:8888` (the API `HINDSIGHT_BASE_URL` points at) and `:9999`
(control plane). It is only needed for the memory runs; the offline tests and `make eval-replay`
never touch it.

**Hindsight Cloud** needs no Docker at all: set `HINDSIGHT_BASE_URL` + `HINDSIGHT_API_KEY` in `.env`
and skip the rest.

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

A second look-alike trap, **s16** (a worker crash-looping on one poisoned queue message; looks like the memory-leak incident s06, but rollback and restart both cause harm), was added after the sequence above was recorded. Its own before/after pair is in the section below.

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

### The s16 pair: the first incident the agent gets wrong

`make`-free reproduction: `python -m greenlight.run --variant v2_verify --cases s06_memory_leak_oom s16_poison_message` and the same with `--variant mem_gate --reset-bank`.

| | no memory | memory + gate |
|---|---|---|
| s06 memory leak (rollback is the fix) | correct, 8 calls | correct, 12 calls, retained |
| s16 poison message (looks like s06; rollback is harmful) | **wrong**: called it a memory leak, proposed a rollback on a service that does not exist, incident not resolved | **wrong, the same way**; recall returned 0 hits, so the gate had nothing to check |

Two honest readings. First, s16 is the only incident in the suite where this agent fails, so it is the right place to keep working. Second, memory did not help because recall never surfaced s06: the two incidents are worded differently enough (`inventory-api` OOMKilled after a deploy vs. `worker` restart loop on one job) that the relevance score fell under the 0.3 cutoff. Lowering the cutoff brings back the noise problem from finding 1. Retaining a short symptom signature alongside the narrative record is the next thing to try.

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
| — | **s16 poison-message incident** (new root cause `poison_message`, probe map, evidence test) — Kotam Satya Rithul |
| — | **Memory age limit** (`HINDSIGHT_MAX_AGE_DAYS`, `filter_by_age`, tests) — Seshivardhini Dulam |

## 6. Run it

From a fresh clone (Python ≥ 3.13 and [uv](https://docs.astral.sh/uv/); every dependency version is
pinned in `uv.lock`, which CI verifies is in sync before installing it):

```bash
git clone <this repo> greenlight && cd greenlight

uv sync --frozen            # installs the project + dev group exactly as uv.lock pins them
uv run pytest -q            # the test suite: 51 offline tests, no network, no API key
uv run ruff check .         # lint (what CI runs)
```

`make setup` / `make test` / `make lint` are the same three commands. Every push runs
`uv lock --check`, `uv sync --locked`, `ruff` and `pytest` on GitHub Actions
([`.github/workflows/ci.yml`](.github/workflows/ci.yml)),
plus a coverage gate that fails below 60%:

```bash
uv run pytest --cov=greenlight --cov-fail-under=60
```

Now the parts that need a model and a memory server:

```bash
cp .env.example .env       # add GEMINI_API_KEY (runtime model) and GROQ_API_KEY
make hindsight             # self-hosted Hindsight in Docker (§3), or set HINDSIGHT_BASE_URL/API_KEY
make memory-seq            # the 6-incident sequence × 3 agents (live model calls, free tier)
make memory-eval           # comparison table
make demo-page             # docs/demo/index.html
```

`make eval-replay` is meant to reproduce greenlight's original ladder with **zero API calls** — it
replays the committed `llm_cache/` and needs neither a key nor a running Hindsight, so it is the
fastest way to see this work end to end:

```bash
cp .env.example .env && make eval-replay
```

> **Known gap (found 28 Sep 2026, not yet re-recorded).** `llm_cache/` is content-addressed by
> *model + exact prompt bytes*, and the taxonomy and the s13/s15/s16/s17 scenarios changed after the
> last recording. All 16 baseline cache keys now miss, so `make eval-replay` currently stops with
> `replay-only mode: no cached response for key …` before it produces a table. It is a stale cache,
> not a setup problem — `GEMINI_API_KEY` is not needed *once the cache is current*. To refresh it,
> run `make baseline && make agent` once with a key and commit the new `llm_cache/`; after that
> `make eval-replay` is self-contained again. The recorded numbers in §4 are in `eval/results/`
> regardless, and `uv run python -m greenlight.eval --runs baseline final` re-scores them with no
> model calls at all.

**Configuration.** Every variable the code reads is in [`.env.example`](.env.example) with a one-line
comment: the two model keys and `LLM_PROVIDER`/`LLM_MODEL`, the `HINDSIGHT_*` knobs
(`BASE_URL`, `API_KEY`, `LLM_MODEL`, `MAX_AGE_DAYS`, `MIN_SCORE`, `MAX_INCIDENTS`), and the three
reproducibility knobs (`DOTENV_PATH`, `LLM_CACHE_DIR`, `LLM_REPLAY_ONLY`). The defaults are what
produced the numbers in §4.

**Models.** Runtime model is Gemini `gemini-3.5-flash-lite` (free tier). Hindsight's fact extraction uses a *different* Gemini model (`gemini-3.1-flash-lite`) so the two do not share a per-model free-tier quota; prompt caching is disabled because the free tier has no cached-content quota. Groq's free tier (8k tokens/min) is too small for the investigator and ran out inside Hindsight after three retains.

## 7. Pointing this at a real stack

This is a prototype against a simulator. To use it for real you would replace `sim/world.py` behind the same tool names: `query_logs` → your log search, `get_metrics` → your metrics API, `recent_changes` → deploy/flag/infra audit log, `run_probe` → real probes (`chronyc tracking`, `openssl s_client`, `dig`, `pg_stat_activity`, `df`). The gates, the memory layer and the human checkpoint do not change. What we have **not** done: run it against a real system, tune the recall threshold on real alerts, or handle memories that contradict each other.

## 8. Team

| Who | Did |
|---|---|
| Sai Haresh Anand S | memory layer, provenance gate, scenarios s13/s15/s17, eval, demo page, README |
| Kotam Satya Rithul | s16 poison-message incident and its test; fixture realism review; the demo video |
| Seshivardhini Dulam | memory age limit and its tests; adversarial review of the memory design |
| Hita Hasini Sakalabhaktula | buyer's-eye review of the README (the questions behind §7 and §9); the "who is this for" section of the video |

## 9. Known failure modes

* **s16 (poison message) is failed by every variant.** The model anchors on the memory-leak pattern and proposes a rollback; it even invents a target service. Memory does not rescue it because recall does not match the differently worded s06 record at the 0.3 cutoff.

* A wrong verdict that passed the probe-kind check is retained as `verified:yes` and can be recalled later. The provenance gate forces a re-probe, but a re-probe of the same misleading kind can pass again. Fix would be retaining the probe *result* and checking consistency; not done.
* Recall threshold (`HINDSIGHT_MIN_SCORE=0.3`; 0.1 let weak look-alikes in and cost probes) was tuned on a bank of four incidents.
* The free-tier runtime model is non-deterministic across days even at temperature 0; numbers move by ±1 call between runs. We report per-case counts, not percentages on N=6.

## License

MIT (inherited).
