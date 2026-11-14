## Context

The project is greenfield: it holds only the PRD (v1.1), `CLAUDE.md` and an empty OpenSpec setup, and it is not yet a git repository. The target is an existing Hostinger KVM 2 VPS (2 vCPU, 8 GB RAM, 100 GB, Ubuntu 26.04, Mumbai). The workspace's other projects (`blog`, `landing`, `portfolio`) deploy to "the same server" over SSH. It is **unconfirmed** whether that is this VPS. If it is, their PHP-FPM and PM2 processes also come out of the 8 GB, so the memory budget below starts from a measured baseline rather than an assumed one.

PRD v1.1 puts a **Python CLI runner** between Laravel and the inference engines, invoked by a Laravel queue job. `CLAUDE.md` still describes Laravel calling Whisper.cpp/llama.cpp directly. This design follows the PRD. Requirements are in `specs/inference-services`, `specs/ai-runner` and `specs/poc-evaluation`. Motivation is in proposal.md.

## Goals / Non-Goals

**Goals:**
- Use the same runner contract that Week 2 Laravel will call, so the PoC also de-risks the integration, not only the models.
- Make swapping candidate models a config change (env plus a service restart), not a code change.
- Get trustworthy numbers from the real VPS with as little extra infrastructure as possible.

**Non-Goals:**
- Production hardening of the stack (TLS, backups, Nginx, firewall rules beyond "no published ports"). That comes with the Week 2 backend.
- Laravel, MySQL, public HTTP API, Expo product app.
- Fine-tuning models, or building a Bangla-specific Whisper fine-tune (recorded only as a fallback option).
- Any paid or external provider adapter, even a disabled one. The provider interfaces live in Laravel (Week 2).

## Decisions

### D1. Repository layout
```
ai/                      Python runner (stdlib-only package) + tests
  run_turn.py            thin entry point (matches PRD's conceptual command)
  averon_ai/             audio.py, stt.py, translate.py, prompts/, errors.py, result.py, config.py
  tests/
deploy/
  docker-compose.yml     whisper, llama, ai-runner on an internal network
  .env.example           MODELS_DIR, model file names, limits, timeouts
poc/
  testset/manifest.jsonl + validate_manifest.py
  bench/                 run_bench.py, metrics.py, profile.py, requirements.txt
  review/                generated blinded CSV sheets + import script
  tts-check/             throwaway Expo app (Expo Go)
  reports/               results + go-no-go.md
docs/models.md           model registry: source, file, quantization, sha256, license
```
Runtime data (models, recordings, raw results) lives under `/opt/averon/{models,poc-data}` on the VPS and is git-ignored.
*Alternative:* separate repos for AI and backend. Rejected: one small team, and the runner contract and the Laravel job should evolve together.

### D2. Inference engines run as long-lived HTTP servers on an internal Docker network
- **STT:** the Whisper.cpp `whisper-server` (HTTP `/inference`) in its own container, with `-t 2` and the model passed via env.
- **Translation:** the llama.cpp `llama-server` (OpenAI-compatible `/v1/chat/completions`, `/health`) with `--parallel 1`, `-t 2`, `-c 2048` and the model via env.
- Both images are pinned by digest. The compose network is `internal: true` and no service has a `ports:` entry. Models are mounted read-only from `${MODELS_DIR}`. Each service has `mem_limit`, `restart: unless-stopped` and a healthcheck (llama `/health`; whisper a TCP/HTTP probe).

*Why:* model weights stay loaded (the PRD asks for this explicitly), and the runner stays a thin HTTP client.
*Alternative:* spawn `whisper-cli`/`llama-cli` per turn. Rejected: it reloads the model every turn, which on 2 vCPU adds seconds and doubles peak RAM churn. *Alternative:* Ollama. Rejected by the PRD's one-serving-stack rule.

Both services use 2 threads, because a turn runs STT and translation sequentially and only one turn runs at a time (single worker), so they never compete for CPU.

### D3. Memory budget (starting point, confirmed by measurement)
| Component | Budget |
|---|---|
| OS + Docker | ~0.8 GB |
| Future MySQL 8 (tuned small) | ~1.0 GB |
| Future PHP-FPM + queue worker + Nginx | ~0.7 GB |
| Other apps already on the VPS (if any) | measured baseline |
| **whisper** `mem_limit` | 1.5 GB |
| **llama** `mem_limit` | 3.5 GB |

Task 2.1 measures the real baseline first. If other apps live on the VPS, the llama limit and the LLM candidate size shrink to fit. This rules out 7B-class models (Q4 is about 4.5 GB of weights) and keeps candidates at 4B parameters or fewer.

### D4. Candidate models
- **STT:** `ggml-base`, `ggml-small` and their quantized (`q5_1`/`q8_0`) variants, as the PRD asks. A stretch candidate is `ggml-large-v3-turbo-q5_0` (~550 MB), included because Whisper base/small Bangla accuracy is a known weak point. It only qualifies if it fits the latency the owner accepts.
- **Translation:** Qwen-family instruct GGUF at Q4_K_M in the 1.5B–4B range (the current Qwen generation at implementation time), plus at least one non-Qwen alternative of similar size (for example a Gemma-family instruct model). The final list is fixed in `docs/models.md` with licenses before benchmarking.
- Language is always forced (`bn` / `ar`). Whisper auto-detect is never used, because direction is known from the UI.

### D5. Runner design
- **Python 3.12+, standard library only** (`argparse`, `json`, `urllib.request`, `subprocess`, `logging`). The Week 2 Laravel worker image can then embed it with no pip dependencies. ffmpeg/ffprobe are the only system dependencies. Tests use pytest with stdlib `http.server` fakes.
- **Pipeline:** validate args → `ffprobe` the content (duration, decodability; the file name is ignored) → reject over 30 s or zero-length → `ffmpeg` to 16 kHz mono PCM WAV in a temp dir → STT → empty-check → translate → emit JSON → delete the temp WAV (the input file belongs to the caller).
- **Output:** one JSON object on stdout (schema in `specs/ai-runner`), plus `retryable` and a `usage[]` array. Exit codes: `0` completed, `2` invalid arguments, `3` non-retryable processing failure, `4` retryable failure. Laravel can then decide on retry from the exit code alone.
- **Contract version 1.1** (2026-11-14): supported codes are `bn-BD` and `ar`. Version 1.0 used `ar-SA`, which is now rejected as `invalid_arguments`.
- **Error code to retryable mapping:** `*_unavailable`, `*_timeout` → retryable; everything else → not retryable.
- **Logging:** stderr only, structured key=value, with turn_id/stage/ms/model/error_code. A unit test asserts that no input or output text reaches stderr.
- **Timeouts** come from env/flags (defaults: STT 90 s, translation 60 s, total 180 s). They are tuned after the benchmark.
- **Translation-only mode** (`--text`) lets the benchmark measure MT quality on reference transcripts, isolated from STT errors.

### D6. Prompting for Modern Standard Arabic
- A system prompt per direction is stored as versioned text files in `averon_ai/prompts/`. The prompt version is reported in `models`, so review results trace back to it.
- bn→ar: "Translate into clear Modern Standard Arabic (فصحى) that any Arabic speaker understands, in simple everyday wording, not a regional dialect. Output only the translation." This comes with 3–5 few-shot pairs in simple MSA. The few-shot pairs are reviewed by a native Arabic speaker before use.
- ar→bn: natural everyday Bangladeshi Bangla, with numbers, prices and dates preserved. The Arabic input may be MSA or dialect; the prompt says so.
- Generation settings: temperature ≈ 0.2, bounded `max_tokens` (≈ 3× input length, capped), stop on newline. Post-processing strips quotes and any `<think>…</think>` block, and model "thinking" modes are disabled.
- The `--dialect` flag overrides the Arabic register sentence for prompt-variant experiments (e.g. strict MSA vs. simple MSA) (PRD §13: "test prompt variants").

### D7. Benchmark strategy: stage-wise first, then end-to-end
1. **STT sweep:** every STT candidate over all audio → CER/WER (normalization: Unicode NFC, strip punctuation/diacritics/tatweel, unify Arabic alef/ya/ta-marbuta forms, Bangla digit to Latin digit mapping), per language/accent/noise, plus latency and peak RAM.
2. **MT sweep:** every LLM candidate over the **reference** transcripts (`--text`) → chrF (an automatic signal only), latency, peak RAM.
3. **End-to-end:** the top 1–2 combinations over all audio through `run_turn.py`, with both services loaded together. These produce the latency (median/p95), combined peak RAM, reliability and review sheets used for the decision.

The harness runs on the VPS host and calls the runner via `docker compose exec ai-runner …`, sequentially. It samples `docker stats` every 1 s for CPU and reads cgroup v2 `memory.peak` per container for peak RAM. It also re-runs a sample of utterances after killing a service, to confirm the restart and `*_unavailable` behaviour.
*Why stage-wise:* it cuts runtime from |STT|×|LLM|×100 runs to |STT|×100 + |LLM|×100 + 2×100. It also lets reviewers tell an STT failure apart from a translation failure.

### D8. Human review
- Review sheets are CSV files (they open in Google Sheets). Per direction there are two sheets: end-to-end outputs and reference-transcript outputs. Rows are shuffled and the model/run identity is hidden. A separate key file maps rows back.
- Scoring columns: adequacy 1–5, fluency 1–5, acceptable Y/N, standard-Arabic Y/N (bn→ar only), and a comment. An import script aggregates the results into the report.
- **Proposed decision criteria** (confirmed by the owner before review starts, task 6.1):
  - At least 80% of end-to-end outputs acceptable in each direction.
  - At least 85% of bn→ar outputs rated "standard Arabic".
  - At least 98% of valid-audio turns complete without timeout/internal error.
  - Zero OOM kills, and combined inference peak RAM within the D3 budget.
  - Cost = 0.
  - Latency has no fixed threshold. The owner judges median/p95 for conversational usability, and the report proposes a target.
  - The working list, with definitions, the decision rule and added criteria C9 (numbers/prices/dates), C10 (no weak category/accent/noise slice) and C11 (no content in runner logs), is `poc/reports/criteria.md`. Once the owner confirms it, that file is authoritative.

### D9. Device TTS check
A throwaway Expo app (`poc/tts-check`, run in Expo Go, so no native build) uses `expo-speech` `getAvailableVoicesAsync()` to list `bn*`/`ar*` voices and speaks bundled sample translations exported from the end-to-end run. It shows text whenever no voice exists. Results (device, OS, voices, intelligibility verdict) are recorded by hand in the report. It is not the base of the Week 3 app.

### D10. Test-set recording
Utterances are recorded by consenting native speakers on phones (Arabic speakers from several countries, reading both MSA and dialect prompts) (the same kind of microphone as production), in the m4a/AAC format a phone app will upload, plus some noisy-environment clips. The files live in `/opt/averon/poc-data/audio`. The manifest (scripted prompts plus references) is versioned in git. Reference translations are written or approved by native speakers of the target language.

## Risks / Trade-offs

- **Weak Bangla STT on base/small** → stretch candidate large-v3-turbo-q5; report per-accent CER; fallback options for the decision report include shorter clips or a ggml-converted Bangla fine-tune (license check required).
- **LLM mixes dialect into its Arabic, or sounds stiff** → explicit MSA prompt plus native-reviewed few-shot examples, prompt-variant runs via `--dialect`, "standard Arabic" column as a gate (C3).
- **Arabic STT on dialect speech** → the test set mixes MSA and dialect prompts and reports CER separately, so the decision sees both.
- **CPU latency too high on 2 vCPU** → quantized models, 2 threads, measure per stage, and set no promise; the decision report may choose "go with conditions" (e.g. shorter max clip).
- **VPS shared with other apps (unconfirmed)** → measure the baseline before setting limits; shrink candidates; the report records the headroom.
- **Benchmark disturbs live sites on the same VPS** → run the sweeps off-peak, keep memory limits strict, and run one inference at a time.
- **Small review sample, or a single reviewer's bias** → at least 2 reviewers per direction where possible; record inter-reviewer disagreement.
- **Recordings are personal data** → consent, kept off git and off logs, deleted or retained per the owner's decision after the PoC.
- **Pinned upstream images change behaviour** → pin by digest; record the versions in `docs/models.md`.
- **Stdlib-only runner is more verbose than using httpx/requests** → accepted, in exchange for zero-dependency embedding in the PHP worker image.

## Migration Plan

Greenfield, so there is nothing to migrate. Deploy: copy `deploy/` to the VPS, place the models in `${MODELS_DIR}`, run `docker compose up -d`. Rollback: `docker compose down` and remove `/opt/averon` (no other system depends on it). If the decision is no-go, the stack is torn down the same way, and the report and code stay in git.

## Open Questions

- Who are the native-speaker recorders and reviewers, and when are they available? This affects the schedule, not the design.
- Should the PoC recordings be kept after the PoC (as a regression set) or deleted? This is the owner's privacy decision, recorded in the report.
- Is the VPS shared with `blog`/`landing`/`portfolio`? This is answered by measurement in task 2.1, and only changes numeric limits.
