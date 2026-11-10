## Purpose

Defines how the AI proof of concept is measured on the real VPS and with native speakers, so the go/no-go decision before backend and app work rests on recorded evidence, not assumptions.

## ADDED Requirements

### Requirement: Representative test set
The test set SHALL contain at least 100 real recorded utterances, with at least 50 in each direction (bn-BD→ar-SA and ar-SA→bn-BD). Each clip SHALL be 30 seconds or shorter. The set SHALL cover greetings, directions, shopping, food ordering, workplace phrases, numbers, prices and dates, formal and informal Bangla, multiple speaker accents, Saudi colloquialisms and background noise. Each utterance SHALL have a manifest entry with ID, direction, category, accent/speaker label, noise flag, reference transcript and reference translation.

#### Scenario: Coverage check
- **WHEN** the manifest validator runs
- **THEN** it confirms at least 100 entries, at least 50 per direction, at least one entry per required category, no clip over 30 seconds, and a reference transcript and translation for every entry

#### Scenario: Recordings kept out of git
- **WHEN** the repository is inspected
- **THEN** the manifest is versioned, but the audio recordings are stored outside version control

### Requirement: Benchmark on the target VPS
The benchmark SHALL run every test utterance through the AI runner on the actual VPS, once for each candidate model combination, one inference at a time. It SHALL record per utterance: transcription, translation, per-stage and total latency, success or error code. It SHALL also record per run: peak memory of each inference service, CPU utilization and disk use of the models.

#### Scenario: Benchmark run output
- **WHEN** the benchmark finishes for a candidate combination
- **THEN** a results file exists with one row per utterance and a summary with median and p95 total latency, per-stage latency, success rate, failure counts by error code, and peak RAM per service

#### Scenario: Headroom check under combined load
- **WHEN** the selected combination is benchmarked
- **THEN** peak memory is recorded while both services are loaded together, and the run reports whether the documented reserve for OS, MySQL, PHP-FPM and the queue worker stayed available

### Requirement: Speech recognition quality per language
The benchmark SHALL compute character error rate (and word error rate) of model transcripts against reference transcripts after a documented text normalization. It SHALL report results separately for Bangla and Saudi Arabic and broken down by accent and noise condition.

#### Scenario: Per-language STT report
- **WHEN** the STT metrics are computed
- **THEN** the report shows CER/WER for Bangla and for Arabic separately, with breakdowns by accent label and noise flag

### Requirement: Translation quality judged by native speakers
Translation quality SHALL be judged by native speakers: Saudi Arabic speakers for bn→ar outputs and Bangla speakers for ar→bn outputs. Each reviewed output SHALL be scored for adequacy and fluency on a 1–5 scale and marked acceptable or not acceptable for everyday use. bn→ar outputs SHALL also be marked as sounding Saudi or not. Automatic metrics (such as chrF) MAY be reported, but they SHALL NOT replace the human verdict. To separate translation quality from STT errors, the reviewers SHALL also judge translations of the reference transcripts.

#### Scenario: Review sheet generated
- **WHEN** the benchmark finishes
- **THEN** a review sheet is produced per direction with source text, model translation and blank scoring columns, with no model or run identity shown to the reviewer

#### Scenario: Review results aggregated
- **WHEN** completed review sheets are imported
- **THEN** the report shows per-direction acceptable rate, mean adequacy and fluency, and (for bn→ar) the share rated as sounding Saudi

### Requirement: Device TTS availability check
On at least one Android device and one iOS device, the PoC SHALL record which installed text-to-speech voices are available for Bangla and Arabic (including any Saudi-locale voice). It SHALL record whether sample translated outputs are spoken intelligibly, as judged by a native speaker.

#### Scenario: Voice inventory recorded
- **WHEN** the TTS check app runs on a device
- **THEN** it lists the available voices whose language matches `bn` or `ar`, with their identifiers and locales, and that list is recorded in the report

#### Scenario: Missing voice
- **WHEN** a device has no Bangla or no Arabic voice installed
- **THEN** the check shows the text without speech and records the missing voice, without crashing

### Requirement: Cost is zero and verified
The PoC SHALL make no calls to paid or external AI services, and the report SHALL state the external API call count and estimated charges, both of which SHALL be zero.

#### Scenario: Cost line in report
- **WHEN** the go/no-go report is produced
- **THEN** it shows 0 external API calls and 0 estimated charges, taken from the runner usage records

### Requirement: Go/no-go decision record
The PoC SHALL end with a written decision report. The report SHALL name the chosen STT model and translation model (with license and quantization), summarize the measured quality, latency, memory and reliability, compare them with the decision criteria agreed before the review, and state "go", "go with conditions" or "no-go" with reasons and any follow-up actions. The report SHALL NOT commit to a fixed production latency promise. Instead, it SHALL propose a latency target based on the measurements.

#### Scenario: Go decision
- **WHEN** the selected models meet the agreed criteria
- **THEN** the report records "go", the chosen models, the observed median/p95 latency and peak RAM, and the proposed latency target for the backend phase

#### Scenario: No-go decision
- **WHEN** no candidate combination meets the agreed quality or resource criteria
- **THEN** the report records "no-go" or "go with conditions", lists which criteria failed, and lists the options considered (smaller or shorter clips, other models, separate host), without enabling any paid provider
