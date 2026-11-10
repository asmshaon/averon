# Go/no-go decision: AI proof of concept

**Verdict:** _go / go with conditions / no-go_ · **Date:** … · **Decided by:** …

## Chosen models

| Stage | Model ID | File / quantization | License | Prompt version |
|---|---|---|---|---|
| STT | … | … | … | n/a |
| Translation | … | … | … | … |

## Results against criteria ([criteria.md](criteria.md))

| # | Criterion | Threshold | Measured | Pass? | Source |
|---|---|---|---|---|---|
| C1 | Acceptable bn→ar | ≥ 80% | … | … | [review.md](review.md) |
| C2 | Acceptable ar→bn | ≥ 80% | … | … | [review.md](review.md) |
| C3 | Sounds Saudi | ≥ 70% | … | … | [review.md](review.md) |
| C4 | Reliability | ≥ 98% | … | … | [e2e.md](e2e.md) |
| C5 | Memory | 0 OOM, within budget | … | … | [e2e.md](e2e.md), [baseline.md](baseline.md) |
| C6 | Cost | 0 / 0 | … | … | [e2e.md](e2e.md) |
| C7 | Latency (median / p95) | owner judgement | … | … | [e2e.md](e2e.md) |
| C8 | Recovery | pass | … | … | [e2e.md](e2e.md) |
| C9 | Numbers/prices/dates acceptable, per direction | ≥ 85% | … | … | [review.md](review.md) |
| C10 | Weakest category / accent / noisy group, per direction | ≥ 60% each | … | … | [review.md](review.md), [stt-sweep.md](stt-sweep.md) |
| C11 | Transcript/translation text in runner logs | 0 matches | … | … | [e2e.md](e2e.md) |

STT quality per language, accent and noise: see [stt-sweep.md](stt-sweep.md). MT comparison: see [mt-sweep.md](mt-sweep.md).

## Device TTS ([tts.md](tts.md))

…

## Proposed latency target for the backend phase

… (based on the measured p95; this is a target, not a promise)

## Conditions / follow-ups

- …

## Recordings

Keep as regression set / delete on … (owner decision)
