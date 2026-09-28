# Working notes for this repo

Read this before touching the code. Keep it short; the README is the public story.

## Layout
- `src/greenlight/memory.py` — Hindsight wrapper (`HindsightMemory`): `ensure_bank`, `brief` (kickoff recall), `recall`, `format_hits`, `remember` (retain with provenance tags), retries.
- `src/greenlight/agent/investigator.py` — `VariantConfig.memory` / `.provenance`; kickoff injection; `recall_similar_incidents` dispatch; `_provenance_gate`; retain after the checkpoint; `memory_*` fields in `meta`.
- `src/greenlight/sim/scenarios.py` — s13, s15, s17 at the bottom (memory scenarios). New root cause `secret_rotation` in `sim/world.py` and `VERIFYING_PROBES`.
- `src/greenlight/eval.py` — keeps run order (file mtime); memory columns; per-case cost table.
- `scripts/demo_page.py` — offline HTML demo from results + traces. `scripts/hindsight_local.sh` — Docker server.
- `tests/test_memory_offline.py` — the gate, scripted, no network.

## Running
- `.env` needs `GEMINI_API_KEY`, `GROQ_API_KEY`, `HINDSIGHT_BASE_URL` (default localhost:8888).
- Hindsight extraction model must differ from the runtime model (separate free-tier quotas). Prompt caching off.
- `make memory-seq` runs the ordered sequence; `--reset-bank` matters, the bank accumulates.
- Bank names: `provenance-<tag>`; use a fresh one per experiment.

## Gotchas found the hard way
- Groq's native provider in Hindsight requests a paid `service_tier`; use provider `openai` + Groq base URL. Groq free quota dies after ~3 retains anyway.
- Gemini free tier: `TotalCachedContentStorageTokensPerModelFreeTier limit=0` → set `HINDSIGHT_API_LLM_PROMPT_CACHE_ENABLED=false`. Per-model RPM ≈ 20 → keep observations off on the bank.
- If recall returns 0 hits for every case, check `error` events with `where=memory` in the trace; memory failures never abort a run.
- Identical prompts hit the LLM disk cache, so two memory variants with 0 hits produce identical runs (cache_hits ≈ calls). Not a bug, but it hides a memory outage.
- Trace JSON must never be sliced mid-string (`hits_to_json` caps hits, not characters).
