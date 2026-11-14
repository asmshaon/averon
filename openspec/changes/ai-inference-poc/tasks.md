## 1. Repository setup

- [x] 1.1 Run `git init`, add `.gitignore` (models, `*.gguf`, `*.bin`, audio, `poc-data/`, raw results, `.env`, `node_modules`, `__pycache__`), and create the `ai/`, `deploy/`, `poc/`, `docs/` layout from design D1; verify with `git status` that only source files are tracked
- [x] 1.2 Update `CLAUDE.md`: describe the Python runner between Laravel and the inference services (PRD v1.1) and add the runner test command; verify the "Request flow" section matches design D2/D5
- [x] 1.3 Create `docs/models.md` with columns for source URL, file, quantization, sha256, size, license and engine version; verify it lists the Whisper.cpp and llama.cpp licenses and every candidate model from design D4 before any download

## 2. Inference services (VPS)

- [ ] 2.1 On the VPS, record baseline memory/CPU (`free -m`, `docker stats`, `ps`) and list any other apps running there; write the result to `poc/reports/baseline.md` and adjust the D3 limits if the VPS is shared
- [x] 2.2 Write `deploy/docker-compose.yml` with `whisper` and `llama` services (images pinned by digest, `internal: true` network, no `ports:`, read-only `${MODELS_DIR}` mount, `mem_limit`, 2 threads, `restart: unless-stopped`, healthchecks, llama `--parallel 1 -c 2048`); verify with `docker compose config` that no service publishes ports and none reserves a GPU
- [ ] 2.3 Write `deploy/.env.example` (MODELS_DIR, STT_MODEL, LLM_MODEL, limits, timeouts); download the candidate models to `/opt/averon/models` and record sha256 values in `docs/models.md`; verify `sha256sum -c` passes
- [ ] 2.4 Bring the stack up on the VPS; verify both healthchecks report healthy and a port scan from outside the VPS (e.g. `nmap` against the public IP) shows neither service port open
- [ ] 2.5 Kill each inference process; verify the container restarts automatically and returns to healthy

## 3. AI runner

- [x] 3.1 Scaffold the `ai/averon_ai` package, the `ai/run_turn.py` entry point and the argument parsing (turn ID, `--audio` | `--text`, `--source`, `--target`, `--dialect`, timeouts); verify pytest covers the `invalid_arguments` cases (unsupported code, same source/target, both or neither inputs)
- [x] 3.2 Implement the result/error module: JSON result schema, fixed error-code set, retryable mapping, exit codes 0/2/3/4, guaranteed single JSON object on any exception; verify with unit tests for every error code
- [x] 3.3 Implement audio handling: probe duration and decodability from content with ffprobe, reject over 30 s and empty audio, convert to 16 kHz mono WAV in a temp dir, delete the temp file afterwards; verify tests with fixture clips (valid m4a, 31 s clip, silent clip, mislabelled non-audio `.wav`)
- [x] 3.4 Implement the STT client against `whisper-server` with forced language (`bn`/`ar`), timeout, and unavailable/timeout/failed/empty mapping; verify tests against a stdlib fake server for each failure path
- [ ] 3.5 Write versioned prompt files for bn→ar (Modern Standard Arabic plus few-shot) and ar→bn (Bangladeshi Bangla, input may be MSA or dialect), and get the few-shot examples checked by a native Arabic speaker; verify a test asserts the `ar` request contains the MSA instruction and the `--dialect` override replaces it
- [x] 3.6 Implement the translation client against llama-server `/v1/chat/completions` (low temperature, bounded max_tokens, thinking disabled, strip quotes and `<think>` blocks, take the first line); verify tests with a fake server for success, timeout, unavailable and output cleanup
- [x] 3.7 Implement the `usage[]` entries (provider `local`, operation, model, ms, input units, `estimated_cost: 0`) and the prompt version in `models`; verify a test checks the usage on a full fake-server turn
- [x] 3.8 Add stderr key=value logging with no content; verify a test runs a full turn with debug logging and asserts no transcription or translation text appears in stderr
- [ ] 3.9 Add the `ai-runner` service (Python 3.12 + ffmpeg, stdlib only) to compose on the internal network; verify on the VPS that `docker compose exec ai-runner python run_turn.py …` on a real Bangla and a real Arabic clip returns `status: completed` with exit 0
- [x] 3.10 Rename `ar-SA` to `ar` across the runner (codes, prompt file names), PoC tooling (directions, tags, review columns, variants), tests, the TTS app and docs; bump the runner contract to 1.1 and record it in `CLAUDE.md`; verify both test suites pass and `grep -ri 'ar-SA\|saudi'` finds only the change history

## 4. Test set

- [ ] 4.1 Write the scripted prompt list (≥50 per direction) covering every PRD category, with reference transcripts and native-speaker reference translations, in `poc/testset/manifest.jsonl`; verify it has an entry per required category
- [x] 4.2 Write `poc/testset/validate_manifest.py` (counts, per-direction minimum, category coverage, references present, audio exists, duration ≤ 30 s via ffprobe); verify it fails on a deliberately broken manifest and passes on the real one
- [ ] 4.3 Collect consented phone recordings from multiple accents/speakers, including noisy clips, into `/opt/averon/poc-data/audio`; verify `validate_manifest.py` passes against the recordings
- [x] 4.4 Write `poc/testset/build_manifest.py` (prompt list + recordings sheet → manifest, one entry per recording, refuses prompts without an approved native-speaker reference, `--plan` writes a blank per-language recording sheet); verify tests show AI drafts are rejected and a full build passes `validate_manifest.py`
- [x] 4.5 Rewrite the prompt list for the new pair: about half of the ar→bn prompts in Modern Standard Arabic and half in everyday dialect (tags `msa` / `dialect`, required by the validator in place of `saudi_colloquial`), and redraft the bn→ar draft translations in MSA; verify the validator's tag rule and the 52/52 coverage

## 5. Benchmark harness

- [x] 5.1 Write `poc/bench/profile.py`: 1 s `docker stats` sampling plus cgroup v2 `memory.peak` per container, written to the run summary; verify a short run reports non-zero peak RAM for both services
- [x] 5.2 Write `poc/bench/metrics.py`: text normalization (NFC, punctuation/diacritics/tatweel, Arabic letter unification, Bangla digits), CER/WER via jiwer, chrF via sacrebleu, median/p95; verify unit tests on known Bangla and Arabic string pairs
- [x] 5.3 Write `poc/bench/run_bench.py` with `stt`, `mt` and `e2e` modes (design D7): sequential, swaps models via env plus service restart, writes per-utterance JSONL and a summary (latency per stage, success rate, error counts, peak RAM, external-call count); verify a 5-utterance dry run produces both files
- [x] 5.4 Add a fault-injection step to the e2e mode (kill a service mid-run); verify the affected turns report `*_unavailable`/`*_timeout` with `retryable: true` and the run continues after the restart
- [x] 5.5 Capture the runner's stderr in the harness (scanned, never stored) and count transcript/translation text found in it per run (criterion C11); verify a test fails the summary when a fake runner logs a transcript
- [x] 5.6 MT sweep: send `--dialect` variants to bn→ar only (ar→bn has no dialect slot), add `poc/bench/dialect-variants.json`, and add `--report-name` to write each sweep summary to `poc/reports/`; verify tests cover the direction guard and the variants file
- [x] 5.7 Write `poc/RUNBOOK.md`: the ordered VPS and people steps for sections 2–9 with exact commands; verify every command and path in it matches the scripts' arguments

## 6. Run evaluation on the VPS

- [ ] 6.1 Confirm the go/no-go criteria (design D8) with the owner and record them in `poc/reports/criteria.md` before any review starts
- [ ] 6.2 Run the STT sweep over all candidates; verify `poc/reports/stt-sweep.md` shows CER/WER per language, accent and noise, plus latency and peak RAM per model
- [ ] 6.3 Run the MT sweep on reference transcripts over all LLM candidates (and the prompt variants via `--dialect`); verify `poc/reports/mt-sweep.md` shows chrF, latency and peak RAM per model and prompt version
- [ ] 6.4 Run e2e for the top 1–2 combinations with both services loaded; verify `poc/reports/e2e.md` shows median/p95 total and per-stage latency, success rate, combined peak RAM against the D3 budget, and 0 external calls

## 7. Native-speaker review

- [ ] 7.1 Generate blinded, shuffled review CSVs per direction (e2e outputs and reference-transcript outputs) with a separate key file; verify the sheets contain no model or run identifiers
- [ ] 7.2 Collect the completed sheets from native Arabic reviewers (bn→ar) and Bangla reviewers (ar→bn), at least 2 per direction where possible
- [ ] 7.3 Write and run the import/aggregation script; verify `poc/reports/review.md` shows per-direction acceptable rate, mean adequacy/fluency, standard-Arabic share and reviewer disagreement
- [x] 7.4 Carry category/accent/noise into the review key (not the sheets) and report the end-to-end acceptable rate per slice (criteria C9, C10); verify a test checks per-category counts with failed turns counted as not acceptable, and that slice labels never appear on reviewer sheets

## 8. Device TTS check

- [ ] 8.1 Create the throwaway Expo app in `poc/tts-check` (expo-speech voice list filtered to `bn*`/`ar*`, speak bundled sample translations, text-only display when no voice exists); verify it runs in Expo Go without crashing on a device that has no Bangla voice
- [ ] 8.2 Run it on at least one Android and one iOS device with a native listener; verify `poc/reports/tts.md` records the device, OS, available voices/locales and the intelligibility/accent verdict

## 9. Decision

- [ ] 9.1 Write `poc/reports/go-no-go.md`: chosen STT and LLM models (license, quantization), quality/latency/RAM/reliability/cost against `criteria.md`, the TTS findings, a proposed latency target (not a promise), the verdict (go / go with conditions / no-go), follow-ups and the decision on keeping or deleting recordings; verify each criterion links to its source report
- [ ] 9.2 If go: record the final model choices and runner contract version in `docs/models.md` and `CLAUDE.md` for the Week 2 Laravel change; if no-go: tear down the stack with `docker compose down` and verify no inference containers remain
