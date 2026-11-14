# PoC test set

`manifest.jsonl` has one JSON object per utterance. The manifest is versioned. The **audio is not**: it lives on the VPS at
`/opt/averon/poc-data/audio/` (recordings are personal data, collected with consent, see design D10).

## Draft prompt list (`prompts.draft.jsonl`)

There are 104 scripted prompts: 52 per direction, 8 per required category plus 4 `general`. bn→ar mixes formal and informal Bangla, and ar→bn is half Modern Standard Arabic (tag `msa`) and half everyday dialect (tag `dialect`, plus `gulf`, `egyptian` or `levantine`). `reference_transcript` is the text the speaker reads aloud.

`draft_translation` was **written by an AI and is not a reference**. `reference_translation` stays empty until a native speaker of the target language writes or approves it. Then set `review_status` to `approved`. Reviewers should rewrite freely rather than just accept the draft, because references from an AI would bias chrF toward the LLM output being scored. The dialect prompts also need a speaker of that dialect to confirm they sound natural before anyone records them. Draft Arabic translations are in Modern Standard Arabic.

Once recordings exist, `build_manifest.py` turns the prompt list plus a recordings sheet (`prompt_id, speaker, accent, noise, audio`) into `manifest.jsonl`. `build_manifest.py --plan FILE --speakers bn:spk01,ar:spk02` writes a blank sheet. Each recording becomes one entry in `manifest.jsonl`. It copies the prompt's text fields and adds `speaker`, `accent`, `noise` and `audio`. The builder adds the speaker to the ID (`bn2ar-001-spk03`), so several speakers can read the same prompt.

## Entry fields

| Field | Type | Notes |
|---|---|---|
| `id` | string | Unique, e.g. `bn2ar-001`, `ar2bn-001` |
| `direction` | `bn-BD>ar` \| `ar>bn-BD` | Source language is the spoken one |
| `category` | one of `greetings`, `directions`, `shopping`, `food_ordering`, `workplace`, `numbers_prices_dates`, `general` | PRD §11 categories |
| `tags` | list | `formal`, `informal` (Bangla register), `msa`, `dialect`, `gulf`, `egyptian`, `levantine`, `question`, … |
| `speaker` | string | Pseudonymous speaker ID, e.g. `spk03`, never a real name |
| `accent` | string | e.g. `dhaka`, `chittagong`, `sylhet`, `gulf`, `egyptian`, `levantine` |
| `noise` | bool | Recorded with background noise |
| `audio` | string | File name inside the audio dir (`.m4a` from a phone preferred) |
| `reference_transcript` | string | Exactly what the speaker said, in the source script |
| `reference_translation` | string | Written or approved by a **native speaker of the target language** (Modern Standard Arabic for ar) |

## Coverage rules (`validate_manifest.py`)

- At least 100 entries, and at least 50 per direction.
- Every category appears in each direction.
- bn→ar has both `formal` and `informal` Bangla. ar→bn has both `msa` and `dialect`.
- At least 2 accents and at least 1 noisy clip per direction.
- Unique IDs, with non-empty references.
- With `--audio-dir`: every file exists, decodes, and is 30 s or shorter (checked with ffprobe from the content).

```bash
python3 validate_manifest.py manifest.jsonl                       # task 4.1 (no audio yet)
python3 validate_manifest.py manifest.jsonl --audio-dir /opt/averon/poc-data/audio   # task 4.3
```
