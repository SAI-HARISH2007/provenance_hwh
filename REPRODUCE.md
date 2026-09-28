# Reproduction guide — from a clean machine

Everything below was verified on Ubuntu 24.04 (WSL2) with Python 3.13.12 and uv 0.11.
Approximate wall-clock and cost are given per step. **Actual API cost is $0** (free tiers);
the tables also report the *would-be* cost at list price so the numbers transfer.

## 0. What you need
- Python ≥ 3.13 and [uv](https://docs.astral.sh/uv/) (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- For live runs only: a free Google AI Studio key → `GEMINI_API_KEY` (https://aistudio.google.com).
  Optional fallback: a free Groq key → `GROQ_API_KEY`.
- **No key is needed to reproduce the main result** — see step 3.

## 1. Install (≈1 min)
```bash
git clone <this repo> greenlight && cd greenlight
uv sync                      # creates .venv, installs pinned deps from uv.lock
uv run pytest                # 12 offline tests: simulator, tracing, LLM cache, agent loop (fake LLM)
```

## 2. The data
There is no external dataset. `src/greenlight/sim/scenarios.py` defines 12 seeded incident
scenarios (logs, metrics, config, change history, probe results, ground truth). They are
generated deterministically from the scenario id, so every machine sees byte-identical evidence.
`uv run python -c "from greenlight.sim import SCENARIOS, World; print(World(SCENARIOS['s01_db_pool_exhausted']).evidence_dump()[:3000])"`
prints what the baseline gets to see for case 1.

## 3. Reproduce the main result with zero API calls (≈10 s)
Every LLM response used for the reported numbers is committed in `llm_cache/` (content-addressed
by model + messages). Replay mode refuses to make network calls:
```bash
make eval-replay
```
Expected output: the comparison table in `eval/results/comparison.md` (also reproduced in the
README), per-case JSON + incident reports under `eval/results/{baseline,final}/`, and fresh
trajectories under `traces/`.

## 4. Re-run live (needs GEMINI_API_KEY; ≈2 min baseline, ≈10 min agent; $0, ~85 requests)
```bash
cp .env.example .env && edit .env          # GEMINI_API_KEY=...
make baseline                              # 12 calls
make agent                                 # ~8 calls/case, 12 cases
make eval
```
Free-tier note (measured 30 Aug 2026): `gemini-3.5-flash-lite` allows ~1,000 requests/day per
project; `gemini-3.5-flash` only 20/day and `gemini-2.5-flash` exhausted after ~30 calls, which
is why every reported number uses flash-lite. If you hit a *daily* quota the client raises
`DailyQuotaExhausted` immediately instead of retrying; wait for the reset (midnight Pacific) or
use a second Google Cloud project key. Results differ slightly between live runs because the free
tier does not guarantee determinism even at temperature 0; the cached run is the one reported.

## 5. Watch one realistic execution with a human in the loop (≈2 min)
```bash
make demo        # runs the hard case; prints the incident report and asks you to approve the fix
```

## 6. Read the trajectories
```bash
make traces      # renders traces/*.jsonl to docs/traces/*.md
```
Each JSONL trace holds the agent instructions, every tool call and response, gate/reviewer
feedback, retries, the human checkpoint and the final result (schema in docs/TRACE_SCHEMA.md).

## Versions
| Component | Version |
|---|---|
| Python | 3.13.12 |
| uv | 0.11.25 |
| openai (client lib) | see `uv.lock` |
| Eval model (all reported numbers) | `gemini-3.5-flash-lite` via the Gemini OpenAI-compatible endpoint, temperature 0 |
| Reference baseline | `gemini-2.5-flash` (baseline only; quota exhausted before the agent could run) |
| Fallback | Groq `openai/gpt-oss-120b` (only for requests < 7k tokens) |
