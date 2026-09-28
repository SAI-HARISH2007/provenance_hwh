#!/usr/bin/env bash
# Start (or restart) a self-hosted Hindsight server in Docker for local development.
# Extraction LLM: Gemini by default (Groq's free quota runs out after a few retains); embeddings run
# locally. Provider prompt caching is off: Gemini's free tier has no cached-content quota.
# Usage: scripts/hindsight_local.sh [groq|gemini]
set -euo pipefail
PROVIDER="${1:-gemini}"
set -a; [ -f .env ] && . ./.env; set +a
case "$PROVIDER" in
  # Groq goes through Hindsight's generic OpenAI-compatible provider: the native "groq" provider
  # requests a paid service tier that free accounts do not have.
  groq)   KEY="${GROQ_API_KEY:?GROQ_API_KEY missing in .env}";   MODEL="${HINDSIGHT_LLM_MODEL:-openai/gpt-oss-20b}"; PROVIDER=openai; BASE_URL=https://api.groq.com/openai/v1 ;;
  gemini) KEY="${GEMINI_API_KEY:?GEMINI_API_KEY missing in .env}"; MODEL="${HINDSIGHT_LLM_MODEL:-gemini-3.1-flash-lite}"; BASE_URL= ;;
  *) echo "provider must be groq or gemini"; exit 1 ;;
esac
docker rm -f hindsight >/dev/null 2>&1 || true
docker run -d --name hindsight -p 8888:8888 -p 9999:9999 \
  -e HINDSIGHT_API_LLM_PROVIDER="$PROVIDER" -e HINDSIGHT_API_LLM_API_KEY="$KEY" -e HINDSIGHT_API_LLM_MODEL="$MODEL" \
  ${BASE_URL:+-e HINDSIGHT_API_LLM_BASE_URL="$BASE_URL"} \
  -e HINDSIGHT_API_EMBEDDINGS_PROVIDER=local \
  -e HINDSIGHT_API_LLM_PROMPT_CACHE_ENABLED=false \
  -v hindsight-data:/home/hindsight/.pg0 ghcr.io/vectorize-io/hindsight:latest >/dev/null
printf "waiting for http://localhost:8888/health "
for _ in $(seq 1 60); do
  if curl -sf http://localhost:8888/health >/dev/null 2>&1; then echo; echo "Hindsight up (provider=$PROVIDER model=$MODEL). API :8888, control plane :9999"; exit 0; fi
  printf "."; sleep 3
done
echo; echo "Hindsight did not become healthy; see: docker logs hindsight"; exit 1
