# WSL note: keep the venv on the Linux FS (a venv on /mnt/c is very slow). Set once per shell:
#   export UV_PROJECT_ENVIRONMENT=$HOME/.venvs/micro1 UV_CACHE_DIR=$HOME/.cache/uv
MODEL ?= gemini-3.5-flash-lite
CASES ?=
COMPOSE ?= docker compose
.PHONY: setup test coverage lint hindsight hindsight-stop baseline agent ablation eval eval-replay traces demo clean memory-seq memory-eval demo-page

setup:            ## clean-env install (Python 3.13 + uv), pinned by uv.lock
	uv sync --frozen

test:             ## offline tests: simulator, tracing, LLM cache, agent loop with a fake LLM
	uv run pytest -q

coverage:         ## offline tests + the coverage gate CI enforces (>= 60%)
	uv run pytest --cov=greenlight --cov-report=term-missing --cov-fail-under=60

lint:
	uv run ruff check .

hindsight:        ## start (or restart) self-hosted Hindsight in Docker, then wait for /health
	$(COMPOSE) up -d hindsight
	@printf "waiting for http://localhost:8888/health "
	@for i in $$(seq 1 60); do \
	  if curl -sf http://localhost:8888/health >/dev/null 2>&1; then \
	    echo " Hindsight is up (API :8888, control plane :9999)"; exit 0; \
	  fi; \
	  printf "."; sleep 3; \
	done; \
	echo; echo "Hindsight did not become healthy: $(COMPOSE) logs hindsight"; exit 1

hindsight-stop:
	$(COMPOSE) down

baseline:         ## simple baseline: one prompt with the evidence dump (needs GEMINI_API_KEY unless cached)
	uv run python -m greenlight.baseline --model $(MODEL) --tag baseline $(if $(CASES),--cases $(CASES),)

agent:            ## final agent workflow (tools + verification gate + runbook + reviewer + approval)
	uv run python -m greenlight.run --variant final --model $(MODEL) --tag final $(if $(CASES),--cases $(CASES),)

ablation:         ## the changelog ladder (v1..v4), see README §5
	for v in v1_tools v2_verify v3_runbook v4_reviewer; do \
	  uv run python -m greenlight.run --variant $$v --model $(MODEL) --tag $$v-lite; done

eval-ladder:      ## comparison table across every stage of the changelog
	uv run python -m greenlight.eval --runs baseline baseline-full v1_tools-lite v2_verify_gate1-lite v2_verify-lite v3_runbook-lite v4_reviewer-lite final

eval:             ## score + comparison table for the headline runs
	uv run python -m greenlight.eval --runs baseline final

eval-replay:      ## reproduce every number with ZERO API calls (uses committed llm_cache/ + results)
	LLM_REPLAY_ONLY=1 uv run python -m greenlight.baseline --model $(MODEL) --tag baseline
	LLM_REPLAY_ONLY=1 uv run python -m greenlight.run --variant final --model $(MODEL) --tag final
	uv run python -m greenlight.eval --runs baseline final

traces:           ## render traces/*.jsonl -> docs/traces/*.md
	uv run python scripts/trace_report.py

demo:             ## one interactive end-to-end run with a real human approval prompt
	uv run python -m greenlight.run --variant final --model $(MODEL) --tag demo --approve ask --cases s12_clock_skew_hard

SEQ ?= s04_disk_full s13_disk_full_wal s12_clock_skew_hard s17_clock_skew_repeat s02_bad_config_deploy s15_secret_rotation_lookalike

memory-seq:       ## the memory story: same 4 incidents in order, without memory then with a fresh Hindsight bank
	uv run python -m greenlight.run --variant v2_verify --model $(MODEL) --tag fair-nomem --cases $(SEQ)
	uv run python -m greenlight.run --variant mem_naive --model $(MODEL) --tag fair-naive --bank provenance-fair-naive --reset-bank --cases $(SEQ)
	uv run python -m greenlight.run --variant mem_gate --model $(MODEL) --tag fair-gate --bank provenance-fair-gate --reset-bank --cases $(SEQ)
	uv run python -m greenlight.eval --runs fair-nomem fair-naive fair-gate

memory-eval:      ## score the memory sequence (no API calls) and paste the table into the README
	uv run python -m greenlight.eval --runs fair-nomem fair-naive fair-gate
	uv run python scripts/fill_results.py

demo-page:        ## offline demo page from results + traces -> docs/demo/index.html
	uv run python scripts/gate_demo.py
	uv run python scripts/demo_page.py --runs fair-nomem fair-naive fair-gate gate-demo

clean:
	rm -rf eval/results/tmp sandbox_work
