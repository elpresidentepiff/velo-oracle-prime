# Core V0_OR — Promotion Report
Generated: 2026-05-25T22:15:33.679650Z

## Decision
**Core V0_OR is now the champion model.** Promoted from challenger status.

## Evidence
| Metric | Previous Champion (Core V0) | New Champion (Core V0_OR) | Delta |
|---|---|---|---|
| AUC   | 0.6735 | 0.6777 | +0.0042 |
| Brier | 0.0861 | 0.0859 | -0.0002 |
| SR    | 21.8% | 21.9% | +0.1% |
| Frame | 50.3% | 50.8% | +0.5% |

## Features Added
- `official_rating` — numeric OR (0 for unrated horses)
- `is_rated` — binary flag (1 if horse has a handicap mark)

## Rollback
Champion pkl: `data/new_build/models/core_v0/core_v0_model.pkl`
Previous champion features: see `data/new_build/models/core_v0/core_v0_metadata.json`

## Next
→ Horse Passport challenge (ablation: V0 / V0_OR / Passport-only / V0_OR+Passport)