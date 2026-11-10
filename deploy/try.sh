#!/usr/bin/env bash
# Hands-on local testing of the Week 1 PoC stack.
#
#   ./try.sh up                          start whisper + llama + runner with small local models
#   ./try.sh text bn "আমি বাজারে যেতে চাই"   translate typed text (bn = Bangla -> Saudi Arabic, ar = reverse)
#   ./try.sh audio bn ~/Downloads/me.m4a  transcribe + translate a recording (phone voice memo, wav, mp3, ...)
#   ./try.sh crash llama                 kill the llama server and watch it come back
#   ./try.sh down                        stop everything
#   ./try.sh tests                       run the runner + PoC tooling test suites
#
# Models/recordings default to ~/.cache/averon-smoke (Docker Desktop can only mount paths under $HOME).
# Override with MODELS_DIR, STT_MODEL, LLM_MODEL. Missing default models are downloaded on `up`.
set -euo pipefail
cd "$(dirname "$0")"
ROOT="$(cd .. && pwd)"
BASE="${AVERON_LOCAL_DIR:-$HOME/.cache/averon-smoke}"
export MODELS_DIR="${MODELS_DIR:-$BASE/models}"
export POC_DATA_DIR="${POC_DATA_DIR:-$BASE/poc-data}"
export STT_MODEL="${STT_MODEL:-ggml-base-q5_1.bin}"
export STT_MODEL_ID="${STT_MODEL_ID:-${STT_MODEL%.*}}"
export LLM_MODEL="${LLM_MODEL:-qwen2.5-1.5b-instruct-q4_k_m.gguf}"
export LLM_MODEL_ID="${LLM_MODEL_ID:-${LLM_MODEL%.*}}"
ENV_FILE="$BASE/try.env"
mkdir -p "$MODELS_DIR" "$POC_DATA_DIR/audio"
env | grep -E '^(MODELS_DIR|POC_DATA_DIR|STT_MODEL|STT_MODEL_ID|LLM_MODEL|LLM_MODEL_ID)=' > "$ENV_FILE"
compose() { docker compose --env-file "$ENV_FILE" "$@"; }

lang_pair() {
  case "$1" in
    bn) echo "--source bn-BD --target ar-SA" ;;
    ar) echo "--source ar-SA --target bn-BD" ;;
    *) echo "direction must be bn (Bangla→Saudi Arabic) or ar (Saudi Arabic→Bangla)" >&2; exit 2 ;;
  esac
}

show() { python3 "$(dirname "$0")/show_result.py"; }  # pretty-print the runner JSON

fetch() {
  [ -f "$MODELS_DIR/$2" ] && return
  echo "Downloading $2 ..." >&2
  curl -fL --retry 3 -o "$MODELS_DIR/$2.part" "$1" && mv "$MODELS_DIR/$2.part" "$MODELS_DIR/$2"
}

case "${1:-}" in
  up)
    fetch "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base-q5_1.bin" ggml-base-q5_1.bin
    [ "$LLM_MODEL" = qwen2.5-1.5b-instruct-q4_k_m.gguf ] && fetch \
      "https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf" "$LLM_MODEL"
    compose up -d --build --wait
    compose ps --format 'table {{.Service}}\t{{.Status}}\t{{.Ports}}'
    echo "Ready. Try: ./try.sh text bn \"এটার দাম কত?\"" ;;
  text)
    [ $# -ge 3 ] || { echo "usage: ./try.sh text bn|ar \"sentence\"" >&2; exit 2; }
    # shellcheck disable=SC2046
    compose exec -T ai-runner python run_turn.py --turn-id "try-$(date +%s)" --text "$3" $(lang_pair "$2") | show ;;
  audio)
    [ $# -ge 3 ] && [ -f "$3" ] || { echo "usage: ./try.sh audio bn|ar /path/to/recording" >&2; exit 2; }
    name="try-$(date +%s).${3##*.}"
    cp "$3" "$POC_DATA_DIR/audio/$name"
    # shellcheck disable=SC2046
    compose exec -T ai-runner python run_turn.py --turn-id "${name%.*}" --audio "/data/audio/$name" $(lang_pair "$2") | show
    rm -f "$POC_DATA_DIR/audio/$name" ;;
  crash)
    ENV_FILE="$ENV_FILE" ./crash-service.sh "${2:-llama}" ;;
  logs)
    compose logs --tail "${2:-30}" ;;
  down)
    compose down ;;
  tests)
    (cd "$ROOT/ai" && { [ -d .venv ] || { python3 -m venv .venv && .venv/bin/pip -q install -r requirements-dev.txt; }; } && .venv/bin/pytest -q)
    (cd "$ROOT/poc" && { [ -d .venv ] || { python3 -m venv .venv && .venv/bin/pip -q install -r bench/requirements.txt; }; } && .venv/bin/pytest -q tests) ;;
  *)
    sed -n '2,13p' "$0" | sed 's/^# \{0,1\}//' ; exit 2 ;;
esac
