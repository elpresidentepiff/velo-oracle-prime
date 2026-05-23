# Mid-Price Top-vs-Winner Delta Audit

**Generated:** 2026-05-23T01:24:10.756658+00:00

## Summary
| Metric | Value |
|---|---|
| Total races | 80 |
| Total misses (top != winner) | 58 |
| Mid-price zone misses (SP 3.0–8.5) | 39 |
| Winner visible in snapshots | 56 |
| Rescuable by sidecar signal | 2 |
| Rescue rate | 3.4% |
| Mid-price miss rate | 67.2% |

## Rescue Signal Breakdown

Rescue threshold: MDS>0.5, improvement>0.40, place_prob>0.80
- place_prob: 2 races

## Operating Notes
- READ-ONLY audit. No scoring changes, no routing changes, no execution changes.
- Inputs: runner snapshot JSONL + results JSON from SL scraper
- Only clean post-fix snapshots (excluding run_ids ['32cc27f9', '847964a6'])