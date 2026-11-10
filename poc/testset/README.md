# PoC test set

`manifest.jsonl` has one JSON object per utterance. The manifest is versioned. The **audio is not**: it lives on the VPS at
`/opt/averon/poc-data/audio/` (recordings are personal data, collected with consent, see design D10).

## Entry fields

| Field | Type | Notes |
|---|---|---|
| `id` | string | Unique, e.g. `bn2ar-001`, `ar2bn-001` |
| `direction` | `bn-BD>ar-SA` \| `ar-SA>bn-BD` | Source language is the spoken one |
| `category` | one of `greetings`, `directions`, `shopping`, `food_ordering`, `workplace`, `numbers_prices_dates`, `general` | PRD §11 categories |
| `tags` | list | `formal`, `informal` (Bangla register), `saudi_colloquial`, `question`, … |
| `speaker` | string | Pseudonymous speaker ID, e.g. `spk03`, never a real name |
| `accent` | string | e.g. `dhaka`, `chittagong`, `sylhet`, `najdi`, `hijazi` |
| `noise` | bool | Recorded with background noise |
| `audio` | string | File name inside the audio dir (`.m4a` from a phone preferred) |
| `reference_transcript` | string | Exactly what the speaker said, in the source script |
| `reference_translation` | string | Written or approved by a **native speaker of the target language** (Saudi colloquial for ar-SA) |

## Coverage rules (`validate_manifest.py`)

- At least 100 entries, and at least 50 per direction.
- Every category appears in each direction.
- bn→ar has both `formal` and `informal` Bangla. ar→bn has `saudi_colloquial`.
- At least 2 accents and at least 1 noisy clip per direction.
- Unique IDs, with non-empty references.
- With `--audio-dir`: every file exists, decodes, and is 30 s or shorter (checked with ffprobe from the content).

```bash
python3 validate_manifest.py manifest.jsonl                       # task 4.1 (no audio yet)
python3 validate_manifest.py manifest.jsonl --audio-dir /opt/averon/poc-data/audio   # task 4.3
```
