#!/usr/bin/env bash
# Download candidate models listed in docs/models.md into $MODELS_DIR and print sha256 sums.
# Usage: MODELS_DIR=/opt/averon/models ./download-models.sh [stt|llm|all]
set -euo pipefail
MODELS_DIR="${MODELS_DIR:-/opt/averon/models}"
WHAT="${1:-all}"
mkdir -p "$MODELS_DIR"
cd "$MODELS_DIR"

WHISPER_BASE=https://huggingface.co/ggerganov/whisper.cpp/resolve/main
STT_FILES=(ggml-base.bin ggml-base-q5_1.bin ggml-base-q8_0.bin ggml-small.bin ggml-small-q5_1.bin ggml-small-q8_0.bin ggml-large-v3-turbo-q5_0.bin)
# GGUF file names change upstream; confirm each URL on the model page before running.
LLM_URLS=(
  https://huggingface.co/Qwen/Qwen3-1.7B-GGUF/resolve/main/Qwen3-1.7B-Q8_0.gguf
  https://huggingface.co/Qwen/Qwen3-4B-GGUF/resolve/main/Qwen3-4B-Q4_K_M.gguf
  https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf
)

fetch() {
  local url="$1" out="$2"
  if [ -f "$out" ]; then echo "skip $out (exists)" >&2; return; fi
  curl -fL --retry 3 -o "$out.part" "$url"
  mv "$out.part" "$out"
}

if [[ "$WHAT" == stt || "$WHAT" == all ]]; then
  for f in "${STT_FILES[@]}"; do fetch "$WHISPER_BASE/$f" "$f"; done
fi
if [[ "$WHAT" == llm || "$WHAT" == all ]]; then
  for u in "${LLM_URLS[@]}"; do fetch "$u" "$(basename "$u")"; done
  echo "Gemma 3 4B requires accepting the Gemma terms on Hugging Face; download it manually." >&2
fi

sha256sum -- *.bin *.gguf 2>/dev/null | tee SHA256SUMS
