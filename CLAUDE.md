# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Current state

Week 1 (AI proof of concept, OpenSpec change `ai-inference-poc`) is in progress. The Laravel backend and the Expo product app do not exist yet. `AI_Voice_Translator_MVP_PRD.pdf` (v1.1) is the source of truth. Re-read it before making architectural decisions.

| Path | What it is |
|---|---|
| `ai/` | Python AI runner (`run_turn.py`, package `averon_ai/`). **Standard library only** (plus ffmpeg), so the Week 2 Laravel worker image can embed it |
| `deploy/` | Docker Compose: `whisper` (whisper-server, built from a pinned tag), `llama` (llama-server, pinned by digest), `ai-runner`. Internal network, no published ports |
| `poc/` | Test-set manifest + validator, benchmark harness (`bench/`), review sheets (`review/`), throwaway Expo TTS check (`tts-check/`), reports |
| `docs/models.md` | Model registry: source, quantization, sha256, **license** (record before benchmarking any model) |

Model weights live outside the repo in `${MODELS_DIR}` (VPS: `/opt/averon/models`). Recordings are in `/opt/averon/poc-data`. Neither is ever committed.

## Commands

| What | Command |
|---|---|
| Runner tests | `cd ai && python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt && .venv/bin/pytest -q` |
| PoC tooling tests | `cd poc && python3 -m venv .venv && .venv/bin/pip install -r bench/requirements.txt && .venv/bin/pytest -q tests` |
| Start the stack | `cd deploy && cp .env.example .env && docker compose up -d --wait` |
| One turn | `docker compose exec -T ai-runner python run_turn.py --turn-id t1 --audio /data/audio/x.m4a --source bn-BD --target ar` (or `--text "..."`) |
| Crash test | `deploy/crash-service.sh whisper\|llama` (SIGKILL inside the container. `docker kill` counts as a manual stop and does not test the restart policy) |
| Build manifest | `python3 poc/testset/build_manifest.py --recordings recordings.csv` (`--plan FILE --speakers bn:spk01,ar:spk02` for a blank sheet). Drafts never become references |
| Validate test set | `python3 poc/testset/validate_manifest.py poc/testset/manifest.jsonl [--audio-dir /opt/averon/poc-data/audio]` |
| Benchmark | `poc/.venv/bin/python poc/bench/run_bench.py stt\|mt\|e2e ...` (see its `--help`) |
| TTS check app | `cd poc/tts-check && npm ci && npx tsc --noEmit && npx expo start` |

The full VPS sequence for finishing Week 1 is in `poc/RUNBOOK.md`.

Gotchas: whisper-server and llama-server reject `--flag=value`, so put the flag and its value in separate compose `command` items. Docker Desktop on Linux can only mount paths under `$HOME`.

### Runner contract (`ai/run_turn.py`, contract version 1.1)

Language codes are `bn-BD` and `ar` (1.1; 1.0 used `ar-SA`, which is now rejected). The runner prints exactly one JSON object on stdout: `contract_version, turn_id, status, source_language, target_language, transcription, translation, models{stt, translation, prompt_version}, timings_ms, audio_duration_seconds, error_code, retryable, usage[]`. Exit codes are `0` completed, `2` invalid_arguments, `3` non-retryable failure, `4` retryable failure (`*_unavailable`, `*_timeout`). The error codes are fixed in `ai/averon_ai/errors.py`. stderr holds key=value logs and never contains transcript or translation text. Prompts are versioned JSON files in `ai/averon_ai/prompts/`.

## Planning changes (OpenSpec)

This project uses OpenSpec (`schema: spec-driven`), with the `/opsx:propose`, `/opsx:explore`, `/opsx:apply`, `/opsx:update`, `/opsx:sync` and `/opsx:archive` commands and the matching `openspec-*` skills in `.claude/`. Before planning or implementing a feature, check `openspec/changes/` for an active change. Main specs live in `openspec/specs/`. AI context for writing artifacts goes in `openspec/config.yaml`.

## What is being built

The project is a shared-device voice interpreter for **Bangla (bn-BD) ↔ Arabic (ar)**. Arabic output is Modern Standard Arabic. Arabic input may be MSA or an everyday dialect. (The PRD says Saudi Arabic; the owner changed this to plain Arabic on 2026-11-14.). One person taps to record a clip of up to 30 seconds. The server transcribes and translates it. The phone shows the source and translated text and reads the translation aloud with the device's own TTS. Then the other person replies in the opposite direction. This is an MVP / private beta.

Out of scope: real-time streaming, calls, multi-device sync, accounts/payments, voice cloning, other language pairs, permanent audio storage, and certified medical, legal or emergency use.

## Planned architecture (from the PRD)

| Layer | Choice |
|---|---|
| Mobile | React Native + Expo + TypeScript (recording, UI, native TTS) |
| Backend | Modular Laravel monolith, PHP 8.4+, behind Nginx |
| DB / queue | MySQL 8, Laravel **database** queue |
| STT | Whisper.cpp (multilingual; benchmark base/small and quantized builds) |
| Translation | llama.cpp serving a small quantized multilingual instruct model (Qwen-family is a candidate, not decided) |
| TTS | On-device Android/iOS TTS only, no server TTS |
| Deploy | Docker Compose on an existing Hostinger KVM 2 VPS (2 vCPU, 8 GB RAM, Ubuntu 26.04, Mumbai) |

**Request flow (PRD v1.1):** the mobile app uploads audio → Laravel validates it and stores it in private temp storage → the queued job `ProcessTranslation` runs the Python runner (`ai/run_turn.py`, via Symfony Process) → the runner calls the private whisper-server, then llama-server, and returns one JSON result → Laravel saves both texts and usage, then marks the turn complete (or failed, retrying only when `retryable`) → the mobile app polls `GET /api/v1/turns/{id}`, displays the result and speaks it → the temp audio is deleted. Laravel's provider contracts (below) wrap the runner. Don't add FastAPI unless a real need appears.

**Turn states:** `awaiting_upload → uploaded → processing → completed | failed`

**API (`/api/v1`):** `POST/GET conversations`, `GET/DELETE conversations/{id}`, `POST conversations/{id}/turns` (audio upload), `GET turns/{id}` (poll).

**Tables:** `conversations` (uuid, nullable user_id, mode, source/target language), `translation_turns` (uuid, conversation_id, speaker, languages, source_text, translated_text, audio_input_path, status, duration_seconds, processing_time_ms, error_code), `processing_usage` (turn_id, provider, operation, model, processing_time_ms, input_units, estimated_cost). Index the UUIDs and foreign keys.

### Provider abstraction

Controllers never call AI services directly. Laravel depends on these contracts so implementations can be swapped:

```php
interface SpeechToTextProvider {
    public function transcribe(string $audioPath, string $language): TranscriptionResult;
}
interface TranslationProvider {
    public function translate(string $text, string $sourceLanguage, string $targetLanguage, ?string $dialect = null): TranslationResult;
}
```

Suggested layout: `app/Domain/{Conversation,Translation,Usage}`, `app/Services/AI/{Contracts,Speech/WhisperCppProvider.php,Translation/LlamaCppProvider.php}`, `app/Services/Audio`, `app/Jobs/ProcessTranslation.php`, plus `Http/{Controllers,Requests,Resources}`.

## Hard constraints

- **Zero incremental cost.** Paid providers (Google STT, Azure Speech, OpenAI, etc.) may exist only behind the provider interfaces and stay **disabled by default**. **Never silently fall back to a paid provider.** If local inference fails or a free quota runs out, return a clear error.
- **Modern Standard Arabic must be asked for explicitly.** The bn→ar prompt requests clear, simple MSA and forbids regional dialect forms. The ar→bn prompt must cope with MSA and dialect input. Any installed Arabic TTS voice is acceptable.
- **The VPS is small.** Run one inference job at a time (single worker), with job timeouts and memory limits. Don't run Ollama alongside llama.cpp. No GPU models.
- **Model services stay private.** Whisper.cpp and llama.cpp are reachable only from Laravel on the Docker network, never on public ports. Model files live outside the repo, and their licenses must be documented.
- **Audio handling.** Validate content, MIME type, size and duration (30 s or less) on the server, and ignore client-supplied metadata. Use idempotency keys for turn creation and upload. Delete input audio after processing, and remove abandoned or failed uploads on a schedule. Never log raw audio or transcripts.
- **Record usage even for local inference**: model name, elapsed time, resource notes. `estimated_cost` is 0 for local processing.
- Mobile: no AI credentials in the app. Check installed TTS voices at runtime, and always keep the translated text visible when no suitable voice exists.
- Don't promise a fixed latency target. Latency, quality and RAM are proof-of-concept gates, measured on the real VPS with a test set of at least 100 utterances and judged by native speakers.

## Roadmap

1. Week 1: AI proof of concept on the VPS (Whisper.cpp, llama.cpp, device TTS, resource profiling) and a go/no-go decision.
2. Week 2: Laravel backend.
3. Week 3: Expo app.
4. Week 4: Native-speaker review, hardening, private beta.
