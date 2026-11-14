# Week 1 PoC runbook

These are the steps to finish change `ai-inference-poc` on the VPS, in order. Each step names its task in `openspec/changes/ai-inference-poc/tasks.md`. Tick the task there once its check passes.

Paths assume the repo is checked out on the VPS, for example at `/opt/averon/app`. Models go in `/opt/averon/models` and recordings in `/opt/averon/poc-data/audio`. Neither ever goes into git.

## 0. Start the people work now (it takes longest)

| Task | What | Who |
|---|---|---|
| 6.1 | Fill in the latency line, confirm the thresholds and sign `poc/reports/criteria.md`. Do this **before** any sheet goes out | Owner |
| 3.5 | Check the 5 few-shot examples in `ai/averon_ai/prompts/bn-BD__ar.json`, then set `review_status` to `approved` | Native Arabic speaker |
| 4.1 | In `poc/testset/prompts.draft.jsonl`, write or correct each `reference_translation` and set `review_status: "approved"`. The ar→bn source sentences also need checking: MSA ones for correctness, dialect ones by a speaker of that dialect | Arabic (Gulf, Egyptian, Levantine) + Bangla speakers |
| 4.3 | Record every prompt on a phone (m4a), with several speakers and accents and some noisy clips. Get consent | Speakers |

Make the recording sheet:
```bash
python3 poc/testset/build_manifest.py --plan /opt/averon/poc-data/recordings.csv --speakers bn:spk01,bn:spk02,ar:spk03,ar:spk04
```
Speaker IDs are pseudonyms. Keep the name ↔ ID list off the server and out of git.

## 1. VPS baseline (2.1)

Run this before starting anything:
```bash
deploy/baseline.sh > poc/reports/baseline.md
```
Fill in the conclusion at the bottom. If other apps are using memory, lower `LLAMA_MEM_LIMIT` (and the LLM candidates) and pass the measured reserve to `run_bench.py --reserve-mib`.

## 2. Models (2.3)

```bash
sudo mkdir -p /opt/averon/{models,poc-data/audio} && sudo chown -R "$USER" /opt/averon
cp deploy/.env.example deploy/.env          # then edit the limits from step 1
MODELS_DIR=/opt/averon/models deploy/download-models.sh all
```
Confirm each GGUF URL on its model page first, because upstream file names change. Gemma needs a manual download after you accept its terms. Then:
```bash
cp /opt/averon/models/SHA256SUMS docs/models.sha256
(cd /opt/averon/models && sha256sum -c "$OLDPWD/docs/models.sha256")
```
Copy each sha256 into `docs/models.md`.

## 3. Stack up, isolation and recovery (2.4, 2.5, 3.9)

```bash
cd deploy && docker compose up -d --build --wait && docker compose ps     # both healthy
docker compose config | grep -n 'ports:' || echo "no published ports"
```
Then from **another machine**: `nmap -Pn -p 1-65535 <vps-public-ip>`. Neither the whisper port nor the llama port may be open.

```bash
./crash-service.sh whisper && ./crash-service.sh llama   # 2.5: restart count rises, healthy again
```

For 3.9, copy one real Bangla clip and one real Arabic clip into `/opt/averon/poc-data/audio`, then run:
```bash
docker compose exec -T ai-runner python run_turn.py --turn-id t1 --audio /data/audio/<bn>.m4a --source bn-BD --target ar; echo "exit=$?"
docker compose exec -T ai-runner python run_turn.py --turn-id t2 --audio /data/audio/<ar>.m4a --source ar --target bn-BD; echo "exit=$?"
```
Both must give `status: completed` and `exit=0`.

## 4. Manifest (4.1, 4.3)

```bash
python3 poc/testset/build_manifest.py --recordings /opt/averon/poc-data/recordings.csv
python3 poc/testset/validate_manifest.py poc/testset/manifest.jsonl --audio-dir /opt/averon/poc-data/audio
```
The build refuses any prompt without an approved native-speaker reference.

## 5. Sweeps (6.2–6.4)

Set up once with `python3 -m venv poc/.venv && poc/.venv/bin/pip install -r poc/bench/requirements.txt`. Run the sweeps off-peak, one at a time. Start with a dry run using `--limit 5`.

```bash
B="poc/.venv/bin/python poc/bench/run_bench.py"
# 6.2: every STT candidate
$B stt --report-name stt-sweep \
  --model whisper-base=ggml-base.bin --model whisper-base-q5_1=ggml-base-q5_1.bin --model whisper-base-q8_0=ggml-base-q8_0.bin \
  --model whisper-small=ggml-small.bin --model whisper-small-q5_1=ggml-small-q5_1.bin --model whisper-small-q8_0=ggml-small-q8_0.bin \
  --model whisper-large-v3-turbo-q5_0=ggml-large-v3-turbo-q5_0.bin
# 6.3: every LLM candidate × prompt variant (variants apply to bn→ar only)
$B mt --report-name mt-sweep --dialect-variants poc/bench/dialect-variants.json \
  --model qwen3-1.7b-q8=Qwen3-1.7B-Q8_0.gguf --model qwen3-4b-q4km=Qwen3-4B-Q4_K_M.gguf \
  --model qwen2.5-1.5b-q4km=qwen2.5-1.5b-instruct-q4_k_m.gguf --model gemma3-4b-q4km=<gemma file>.gguf
# 6.4: top 1–2 combinations, with fault injection (repeat with a new --report-name for the second)
$B e2e --report-name e2e --stt <id>=<file> --llm <id>=<file> --reserve-mib <from baseline> \
  --fault llama@10 --fault whisper@20
```
If one variant clearly wins in the MT sweep, set it as the prompt's `default_dialect`, bump the prompt `version`, and use that for e2e.

Before step 6, check that `poc/reports/e2e.md` shows combined peak RAM within budget (C5), 0 external calls (C6), a fault-injection result of OK (C8) and 0 log leaks (C11).

## 6. Native review (7.1–7.3)

```bash
python3 poc/review/make_sheets.py --e2e poc/bench/results/<e2e-run>/results.jsonl --mt poc/bench/results/<mt-run>/results.jsonl
```
Send `bn2ar__*.csv` to native Arabic reviewers and `ar2bn__*.csv` to Bangla reviewers, at least 2 per direction. Never send `poc/review/keys/`. Save each completed sheet as `<sheet>__<reviewer>.csv`, then:
```bash
python3 poc/review/import_reviews.py completed/*.csv
```
This writes `poc/reports/review.md`, with the rates per direction and per slice (C1–C3, C9, C10).

## 7. Device TTS (8.1, 8.2)

```bash
python3 poc/tts-check/scripts/export_samples.py poc/bench/results/<e2e-run>/results.jsonl
cd poc/tts-check && npm ci && npx expo start
```
Run it in Expo Go on one Android phone and one iPhone, ideally one without a Bangla voice, with a native listener present. Record the results in `poc/reports/tts.md`.

## 8. Decision (9.1, 9.2)

Fill in `poc/reports/go-no-go.md` against `criteria.md`, linking each line to its report.
- **Go:** record the chosen models in `docs/models.md` ("Selected for MVP") and in `CLAUDE.md`.
- **No-go:** run `docker compose down` and confirm that `docker ps` shows no inference containers.

Then record whether the recordings are kept or deleted.
