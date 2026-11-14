# Go/no-go criteria

**Status: DRAFT. The owner must confirm or change these before any review sheet goes out (task 6.1).** After that they are frozen. Results are judged against the criteria as confirmed, not adjusted to fit the numbers.

Source: design D8, plus additions marked *(new)*. Each line is checked in `go-no-go.md` against the linked report.

## Definitions

- **Acceptable**: a reviewer marks Y when a listener would understand the meaning correctly and act on it, even if the wording is awkward. A translation that is fluent but changes the meaning (wrong number, negation, person or place) is **not** acceptable.
- **Per-utterance verdict**: a majority of that utterance's reviewers must say Y. Ties count as not acceptable, and so do failed turns (no output). `import_reviews.py` already applies these rules.
- **End-to-end**: real recording → Whisper → LLM. The sheets built from reference transcripts isolate translation quality. They are diagnostic only, not a gate.
- **Sample size**: about 52 utterances per direction. An observed 80% has a 95% interval of roughly 67–89%, so results close to a threshold are weak evidence either way. The report states the interval next to each rate.

## Criteria

| # | Criterion | Threshold | Kind | Evidence |
|---|---|---|---|---|
| C1 | End-to-end acceptable, **bn→ar** | ≥ 80% | quality | `review.md` (bn2ar e2e) |
| C2 | End-to-end acceptable, **ar→bn** | ≥ 80% | quality | `review.md` (ar2bn e2e) |
| C3 | bn→ar outputs rated "standard Arabic" (MSA, no dialect forms or broken mix) | ≥ 85% | quality | `review.md` |
| C4 | Reliability: valid-audio turns that complete without a timeout or internal error | ≥ 98% | hard | `e2e.md` |
| C5 | Memory: OOM kills, and combined inference peak against the D3 budget (adjusted by `baseline.md`) | 0 OOM; within budget | hard | `e2e.md`, `baseline.md` |
| C6 | Cost: external API calls and estimated charges | 0 and 0 | hard | `e2e.md` |
| C7 | Latency: median and p95, total and per stage | No fixed threshold; owner judgement (see below) | judgement | `e2e.md` |
| C8 | Recovery: a crashed service restarts, and the affected turns fail with retryable codes | Pass | hard | `e2e.md` (fault injection) |
| C9 | *(new)* Numbers, prices and dates: end-to-end acceptable within the `numbers_prices_dates` category, per direction | ≥ 85% (7 of 8 at the current set size) | quality | `review.md` (per category) |
| C10 | *(new)* No weak slice: end-to-end acceptable for every category, every accent group with ≥ 5 utterances, and the noisy-clip group, per direction | ≥ 60% each | quality | `review.md`, `stt-sweep.md` |
| C11 | *(new)* Privacy: a scan of the runner logs from the e2e run finds none of the transcripts or translations | 0 matches | hard | `e2e.md` |

Why the new criteria:
- **C9**: a wrong price or date is the most harmful kind of error in everyday use, and an average across all categories can hide it.
- **C10**: a passing overall rate can still hide one accent or noisy speech failing badly.
- **C11**: the unit test already checks this. C11 confirms it holds on real data.

### C7: owner's latency judgement

Fill this in **before** seeing results. It is a "too slow to be useful" line, not a promise to users:

> A p95 end-to-end time above **____ s** for a ~10 s clip would make conversation impractical.

After the run, the report proposes a backend-phase target based on the measured p95.

## Decision rule

- **Go**: every criterion passes, and the owner accepts C7.
- **Go with conditions**: every **hard** criterion (C4, C5, C6, C8, C11) passes, and each miss is small and comes with a named fix:
  - C1, C2 or C3 is no more than 5 points below its threshold.
  - C9 or C10 misses by at most one utterance in the failing group.
  - C7 is judged too slow, but a stated change fixes it (shorter max clip, smaller model, fewer tokens).

  Each condition must be re-measured on the same sheets or runs before the Week 3 app work depends on it.
- **No-go**: any hard criterion fails and cannot be fixed within the PoC, or any quality miss is larger than the limits above. The report lists the options considered (other models, shorter clips, a separate host). **A paid provider is never an automatic fallback.** Enabling one is a separate decision the owner makes explicitly.

## Not gates

These are recorded to inform later weeks, but they don't decide go/no-go:
- **STT CER/WER**: used to diagnose whether failures come from speech recognition or translation.
- **Reference-transcript sheets**: diagnostic, as above.
- **Device TTS**: a missing Arabic or Bangla voice is handled by always showing the text (PRD). The findings feed the Week 3 app.
- **Reviewer disagreement rate**: reported, and above ~25% it means "acceptable" needs clarifying with the reviewers.

---

Confirmed by: ______  Date: ______  Changes from draft: ______
