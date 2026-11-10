# Model registry

Every engine and model used or benchmarked by Averon is listed here **before** results for it are reported (spec `inference-services`, "License recorded before use").
Weights are never committed. They live on the VPS under `${MODELS_DIR}` (default `/opt/averon/models`) and are mounted read-only.

`sha256` is filled in when the file is downloaded (task 2.3); verify with `sha256sum -c docs/models.sha256`.

## Engines

| Engine | Version / pin | License | Source |
|---|---|---|---|
| whisper.cpp (`whisper-server`) | tag `v1.9.5`, built from source by `deploy/whisper/Dockerfile` | MIT | https://github.com/ggml-org/whisper.cpp |
| llama.cpp (`llama-server`) | `ghcr.io/ggml-org/llama.cpp:server@sha256:ca40726778c25a7fadce42c09bada8484eab22e28bc283bdbf212e87b1555390` (pinned 2026-11-08) | MIT | https://github.com/ggml-org/llama.cpp |
| ffmpeg / ffprobe | Debian package in `ai-runner` image | LGPL-2.1+ / GPL (distro build) | https://ffmpeg.org |

## Speech-to-text candidates (Whisper, ggml format)

All files are from https://huggingface.co/ggerganov/whisper.cpp (`resolve/main/<file>`). The Whisper weights are released by OpenAI under the **MIT** license.

| ID | File | Quantization | Approx. size | Role | sha256 |
|---|---|---|---|---|---|
| `whisper-base` | `ggml-base.bin` | f16 | 148 MB | PRD baseline | TBD |
| `whisper-base-q5_1` | `ggml-base-q5_1.bin` | q5_1 | 60 MB | PRD baseline (quantized) | TBD |
| `whisper-base-q8_0` | `ggml-base-q8_0.bin` | q8_0 | 82 MB | PRD baseline (quantized) | TBD |
| `whisper-small` | `ggml-small.bin` | f16 | 488 MB | PRD baseline | TBD |
| `whisper-small-q5_1` | `ggml-small-q5_1.bin` | q5_1 | 190 MB | PRD baseline (quantized) | TBD |
| `whisper-small-q8_0` | `ggml-small-q8_0.bin` | q8_0 | 264 MB | PRD baseline (quantized) | TBD |
| `whisper-large-v3-turbo-q5_0` | `ggml-large-v3-turbo-q5_0.bin` | q5_0 | 574 MB | Stretch (Bangla accuracy risk, design D4) | TBD |

## Translation candidates (GGUF, Q4_K_M unless noted, ≤ 4B parameters)

Re-check for a newer Qwen generation at download time. If you add one, add a row here, with its license, before benchmarking it.

| ID | Model | GGUF source | License | Notes | sha256 |
|---|---|---|---|---|---|
| `qwen3-1.7b-q8` | Qwen3-1.7B (instruct, thinking disabled), file `Qwen3-1.7B-Q8_0.gguf` (≈1.8 GB; the official repo ships Q8_0 only) | https://huggingface.co/Qwen/Qwen3-1.7B-GGUF | Apache-2.0 | Smallest Qwen candidate | TBD |
| `qwen3-4b-q4km` | Qwen3-4B (instruct, thinking disabled) | https://huggingface.co/Qwen/Qwen3-4B-GGUF | Apache-2.0 | Primary Qwen candidate | TBD |
| `qwen2.5-1.5b-q4km` | Qwen2.5-1.5B-Instruct | https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF | Apache-2.0 | Previous-generation reference | TBD |
| `gemma3-4b-q4km` | Gemma 3 4B IT | https://huggingface.co/google/gemma-3-4b-it-qat-q4_0-gguf (or community Q4_K_M) | Gemma Terms of Use (commercial use allowed with use-policy restrictions; review before beta) | Non-Qwen alternative | TBD |

### Excluded

| Model | Reason |
|---|---|
| Qwen2.5-3B-Instruct | Qwen Research License (non-commercial), so it can't be used for a product |
| Any 7B+ model | Q4 weights ≈ 4.5 GB or more, which exceeds the llama `mem_limit` in design D3 |
| Ollama-served models | PRD: llama.cpp is the only serving stack |

## Selected for MVP

To be filled in by task 9.2 after the go/no-go decision.

| Stage | Model ID | Prompt version | Runner contract version |
|---|---|---|---|
| STT | — | — | — |
| Translation | — | — | — |
