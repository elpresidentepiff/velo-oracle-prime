# PERFORMANCE AND MONEY REALITY AUDIT — VÉLØ ORACLE PRIME

**Date:** 2026-06-10 · Every number below is computed from stored artifacts, with its evidence class. No marketing numbers.

## A–B. Verified strike rate and frame rate — VERIFIED_FROM_SIGMA

Source: `data/sigma_results/sigma_results_*.json` (19 race days, 2026-05-21 → 2026-06-09).

| Metric | Value | Class |
|---|---|---|
| Wins / evaluated | 155 / 595 | VERIFIED_FROM_SIGMA |
| **Strike rate (19 days)** | **26.1%** | VERIFIED_FROM_SIGMA |
| Frames (placed-not-won field) | 145 / 595 = 24.4% | VERIFIED_FROM_SIGMA (field semantics: wins+frames = 300/595 = 50.4%, consistent with historical ~48% frame rate — confirm definition before publishing) |
| Daily range | 9.5% (May 31) to 38.7% (Jun 8); Jun 9 = 13.8% | VERIFIED_FROM_SIGMA |

Context: April 28 unified audit baseline was 20.6% SR over 49 days (n=1,391). Recent 19-day window at 26.1% is above that baseline but a smaller sample.

## C. Verified live ROI — NOT_FOUND
There is **no live staking ledger**. No bankroll. No live ROI exists, by design (NO live staking is a permanent rule). Any live-ROI claim is CLAIM_REQUIRES_PROOF.

## D. Shadow ROI — SHADOW_ONLY (flat 1pt paper stakes)

Source: `data/router_shadow_audit_latest.md` (2026-06-09 22:27 UTC, 1,248 rows / 764 with results).

| Lane | n | SR | Frame | Paper P&L | ROI | Class |
|---|---|---|---|---|---|---|
| V1_BASE | 51 | 45.1% | 80.4% | +£14.68 | **+28.8%** | SHADOW_ONLY |
| V2_CLASS4_ONLY | 41 | 48.8% | 78.0% | +£16.70 | **+40.7%** | SHADOW_ONLY |
| V6_GOLD_SEAM | 17 | 41.2% | 70.6% | +£8.25 | +48.5% | SHADOW_ONLY (low n) |

Ensemble-surgery control audit (2026-05-08, n≈340): LEGACY −3.1% → NEW +13.5% — SHADOW_ONLY (retrospective control, not staked).

## E. Best-performing lane
V2_CLASS4_ONLY: n=41, SR 48.8%, ROI +40.7%, drawdown −£5.75. Strongest combination of sample size and ROI. Still shadow.

## F. Worst-performing lane — POWER_ANCHOR paper ledger (EVIDENCE_INTEGRITY_SUSPECT)

Source: `data/velo_execution_bridge_paper_ledger.csv` (569 rows).

- POWER_ANCHOR_MODE: 52 directives, only **8 closed with results, 0 wins, paper P&L −9.75**.
- This contradicts the April first-audit memory (2/2 wins). Root cause of the closure gap: ledger rows carry **synthetic horse IDs** (`rp_SOUTHWELL_collanisi`) while results carry real RP numeric IDs — most rows can never reconcile. Additionally `rpdc_release_score=0.0` on every row (RPDC severance, see SUPABASE_REALITY_AUDIT finding 1).
- Classification: **EVIDENCE_INTEGRITY_SUSPECT** — the ledger needs ID-chain repair and re-audit before any conclusion about POWER_ANCHOR is drawn. The closed subset (0/8) is a warning sign, not a verdict.

## G. Contaminated / excluded days
- 2026-05-20: excluded from corpus — `SCORING_FLATLINE_CONTAMINATED` (mission control corpus governance).
- 14 degraded days on the truth watchdog (session check), including 2026-05-19, 2026-06-07, 2026-06-08, 2026-06-10.
- Learning-blocked days: 2026-05-02, 2026-05-04 (+ all degraded days by gate).
- DEGRADED_DAY_EXCLUDED handling is inconsistent: sigma aggregates above include degraded days — a clean-day-only SR series does not yet exist.

## H–J. Claims discipline

| Claim | Verdict |
|---|---|
| "Top-tier UK performance territory" | **NOT SUPPORTABLE today.** Supportable: 26.1% top-pick SR over 19 verified days, shadow router ROI +29–41% at n=41–51 flat paper stakes. No like-for-like public benchmark audit exists in the repo. |
| "Top 10 UK" | **NOT PUBLICLY CLAIMABLE.** No external benchmark, no third-party verification, no staked record. |
| What is needed to claim safely | (1) 90+ consecutive days of sigma-verified picks timestamped pre-race; (2) clean-day-only series with degraded days excluded; (3) comparison against a named public benchmark (e.g. RP Postdata/newspaper naps tables) over the same dates — `build_industry_comparison.py` already exists for this; (4) ledger ID-chain repaired so paper P&L closes; (5) independent re-computation from stored artifacts. |
