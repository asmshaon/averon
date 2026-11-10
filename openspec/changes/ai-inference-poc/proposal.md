## Why

The PRD (v1.1) treats local AI quality, latency and memory on the existing 2 vCPU / 8 GB Hostinger VPS as a go/no-go gate, not a given. Nothing should be built in Laravel or Expo until we know that Whisper.cpp and a small quantized llama.cpp model can turn Bangla (bn-BD) and Saudi Arabic (ar-SA) speech into usable, Saudi-colloquial translations on that box, at zero incremental cost. This change is Week 1 of the roadmap: build just enough of the AI path to measure it, then make the decision on evidence.

## What Changes

- Add private Whisper.cpp (STT) and llama.cpp (translation) inference services on the VPS with Docker Compose. Both are reachable only on the internal Docker network, run with memory limits and one inference at a time, and load model files from outside the repository.
- Add a Python CLI **AI runner** (`run_turn.py`), the same runner the Week 2 Laravel queue job will call. It accepts a validated audio path (or a text input for translation-only runs), source and target language, dialect instruction and turn ID. It calls the private services and prints one structured JSON result with transcription, translation, model identifiers, per-stage durations and a normalized error code. It uses explicit timeouts and non-zero exit codes on failure, and it never logs audio or transcript content.
- Add translation prompts that explicitly ask for natural Saudi colloquial Arabic (bn→ar) and natural Bangladeshi Bangla (ar→bn).
- Add a **PoC evaluation kit**:
  - a manifest-driven test set of at least 100 real utterances across both directions and the PRD's categories (greetings, directions, shopping, food, workplace, numbers/prices/dates, formal/informal Bangla, accents, Saudi colloquialisms, background noise);
  - a benchmark harness that runs every utterance through each candidate model combination and records CER/WER, latency (median/p95, per stage), peak RAM, CPU and failures;
  - native-speaker review sheets for translation adequacy, fluency and "sounds Saudi";
  - a throwaway on-device TTS check that lists installed bn/ar voices and speaks sample translations on real Android and iOS devices.
- Produce a **go/no-go report** that recommends one STT model and one translation model (with licenses documented) or records a no-go and its reasons.
- Initialise the project repository layout (`ai/`, `deploy/`, `poc/`, `docs/`) and git.

Not included: Laravel backend, database, public API, the Expo product app, and any paid or external provider (no paid code paths are written in this change).

## Capabilities

### New Capabilities

- `inference-services`: private, resource-bounded Whisper.cpp and llama.cpp services on the VPS, covering network isolation, model storage outside the repo, single-inference concurrency and license documentation.
- `ai-runner`: the Python CLI contract for processing one turn (inputs, structured JSON output, normalized error codes, exit codes, timeouts, Saudi-dialect prompting, no content logging, no paid fallback).
- `poc-evaluation`: the test set, benchmark measurements, native-speaker review, device-TTS check and the go/no-go decision record.

### Modified Capabilities

None. There are no existing specs.

## Impact

- **New code:** `ai/` (Python runner package and tests), `deploy/` (Docker Compose and env example), `poc/` (test-set manifest, benchmark harness, review templates, TTS check app, reports), `docs/models.md`.
- **Infrastructure:** new containers on the existing VPS. They need Docker plus about 1–5 GB of disk for model files under a host path such as `/opt/averon/models`. No public ports are opened.
- **Dependencies:** Whisper.cpp and llama.cpp (MIT), ffmpeg, Python 3.x (the runner itself uses the standard library only; the benchmark adds jiwer/sacrebleu and similar), plus candidate model weights whose licenses must be recorded.
- **People:** native Bangla and Saudi Arabic speakers to record utterances and review translations, and at least one Android and one iOS device for the TTS check.
- **Docs:** `CLAUDE.md` describes Laravel calling Whisper.cpp/llama.cpp directly, while PRD v1.1 puts a Python runner in between. This change follows the PRD, and `CLAUDE.md` is updated to match.
- **Downstream:** the Week 2 Laravel change depends on the `ai-runner` JSON contract and error codes defined here, and goes ahead only if the gate is a "go".
