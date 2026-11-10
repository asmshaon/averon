# Go/no-go criteria

**Status: PROPOSED. The owner must confirm or change these before any review starts (task 6.1).**
Source: design D8. Every line is checked in `go-no-go.md` against the linked report.

| # | Criterion | Threshold | Evidence |
|---|---|---|---|
| C1 | End-to-end translations acceptable to native reviewers, **bn→ar** | ≥ 80% (failed turns count as not acceptable) | `review.md` (bn2ar__e2e) |
| C2 | End-to-end translations acceptable to native reviewers, **ar→bn** | ≥ 80% | `review.md` (ar2bn__e2e) |
| C3 | bn→ar outputs rated "sounds Saudi" | ≥ 70% | `review.md` |
| C4 | Reliability: valid-audio turns completing without timeout or internal error | ≥ 98% | `e2e.md` |
| C5 | Memory: zero OOM kills; combined inference peak within the D3 budget | 0 OOM; within budget | `e2e.md`, `baseline.md` |
| C6 | Cost: external API calls and estimated charges | 0 and 0 | `e2e.md` |
| C7 | Latency | **No fixed threshold.** The owner judges median/p95 for conversational use, and the report proposes a target | `e2e.md` |
| C8 | Recovery: crashed service restarts; affected turns fail with retryable codes | Pass | `e2e.md` (fault injection) |

Confirmed by: ______  Date: ______  Changes from proposal: ______
