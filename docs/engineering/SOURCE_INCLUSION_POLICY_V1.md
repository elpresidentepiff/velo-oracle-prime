# Source Inclusion Policy V1

## Purpose

VÉLØ uses multiple racing data sources, but it does not blindly merge them. Every source has a lane.

## Source Roles

| Source | Role | Live Scoring |
| --- | --- | --- |
| Racing Post account archive | Deep context, dossiers, comments, pedigree, entries, quotes, notes, newspaper/tip heat. | No |
| Racing API | Identity, race/result structure, IDs, fallback/cross-check. | Only existing approved structured fields |
| VÉLØ | Independent probability, tiers, MDS, improvement, router outputs. | Yes |
| Sigma | Outcome truth and miss taxonomy. | Post-race only |
| RPDC | Memory and historical horse behaviour. | Shadow/research unless already approved |

## Explicit Field Policy

| Field / Group | Policy |
| --- | --- |
| RPR | `ARCHIVE_ONLY` for all models built after 2026-06-19 (New Build, Champion Intent Shadow, SQPE No-RPR Shadow) — banned from those models' features, verified via `BANNED_LEAKAGE_FIELDS`/feature-list checks in their respective builders. **Old VELO (`MAIN_VELO_PRIME`, `sqpe_v17.pkl`) is grandfathered and genuinely uses RPR** (`rpr_num`+`rpr_vs_field` = ~50% of its base model's real feature importance, confirmed 2026-07-26 via direct pickle inspection). This was a deliberate 2026-06-19 decision (commit `61a4789`/`3667d39`): Old VELO was kept as the RPR-inclusive incumbent specifically so a doctrine-clean challenger (No-RPR) could be honestly benchmarked against it, not a doc/code mismatch. Empirically (1,442-race ledger, 2026-07-26): RPR genuinely helps Old VELO identify short-favourites (51.2% SR vs No-RPR's 38.4%) and makes no difference in the mid-price band (both tie at 24.0% SR) — so the grandfather status is earning its keep in the band it covers, not present by oversight. |
| RP comments / Spotlight / Newspaper Form | Archive/context only; useful for explanation, watchlists, and contradiction intelligence. |
| Tip count | Archive/context/hype warning only; not a truth signal. |
| Trainer / jockey / owner / sire / dam | Archive/context; shadow research only until proven and approved. |
| Headgear / wind surgery | Archive/context; shadow research candidate. |
| Racing API IDs/results | Identity/truth layer. |
| VÉLØ scores | Independent decision layer. |
| Sigma result | Post-race truth only. |

## Promotion Gates

No archive field can enter live scoring without:

1. Evidence from archive context value tests.
2. Leakage audit.
3. Shadow-only trial.
4. Operator/Council approval.
5. Explicit code review confirming no RPR or RP opinion leakage.

## Current Decision

Racing Post archive data prepares, challenges, and explains VÉLØ. It does not steer the engine.
