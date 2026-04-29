# VÉLØ Signal Rankings V1

**Evidence basis:** 49 race days | 1391 sigma rows | 1604 verdicts
**Last updated:** 2026-04-28
**Audit source:** `data/evidence_vault/velo_unified_evidence_audit_v1.json`

Signal ranks are derived from live closed-result data only.
No simulated, backtested, or hypothetical results are included.
Rankings will be updated as evidence accumulates.

---

## PROVEN_SIGNAL
*n ≥ 30, SR consistently above global baseline, Frame ≥ 70%, reproducible across multiple days*

### VP ≥ 0.30 + Tier A
- **n:** 162 | **SR:** 40.1% | **Frame:** 77.2% | **Avg VP:** 0.425
- **Basis:** 49-day live read, consistent across venues and race types
- **Interpretation:** The intersection of VÉLØ's highest-tier classification and VP ≥ 0.30 is the sharpest proven live signal. These are races where the model's confidence and tier alignment converge. SR is 2× global baseline.
- **Candidate action:** Shadow candidate lane — track under VP_30_TIER_A shadow annotation. No staking until n ≥ 100.
- **Risk:** Sample is drawn from A-tier races which are inherently self-selective. Requires ongoing monitoring for regression.

### VP ≥ 0.40
- **n:** 100 | **SR:** 44.0% | **Frame:** 85.0% | **Avg VP:** 0.487
- **Basis:** Monotonic VP relationship proven across all 49 days
- **Interpretation:** VP ≥ 0.40 is the highest-probability band. 85% frame rate means these picks are landing in the top 3 almost every time.
- **Candidate action:** Include in VP_30_TIER_A shadow lane (VP ≥ 0.40 is a strict subset).

### Market Deception Score > 0.5
- **n:** 31 | **SR:** 54.8% | **Frame:** 96.8% | **Lift:** +34.2% over global baseline
- **Basis:** Sidecar signal from velo_verdicts.market_deception_score
- **Interpretation:** When VÉLØ fires with high MDS, it is identifying a race where market structure supports the pick. This is the highest-lift live signal in the entire system. Note: in A/B-tier routing, high MDS was historically treated as a decoy risk. The 49-day evidence contradicts that assumption — high MDS predicts winners.
- **Candidate action:** PRIORITY — design MDS_GT_0.5 candidate lane immediately. Combine with VP ≥ 0.30 for the tightest gate.
- **Caution:** n=31 is above the INSUFFICIENT threshold but below full confidence. Treat as PROVEN_SIGNAL but track for regression.

### Improvement Score > 0.40
- **n:** 62 | **SR:** 43.5% | **Frame:** 82.3% | **Lift:** +22.9%
- **Basis:** Specialist model score from sidecar ensemble
- **Interpretation:** When the improvement specialist model fires above 0.40, the pick is consistently winning. This signal adds significant lift at meaningful sample size (n=62).
- **Candidate action:** Design IMPROVEMENT_GT_0.4 candidate lane. Track alongside MDS lane.

---

## PROMISING_SIGNAL
*Positive SR lift, positive frame contribution, n ≥ 30, not yet fully proven at scale*

### VP ≥ 0.30 (combined, all tiers)
- **n:** 345 | **SR:** 32.2% | **Frame:** 69.3% | **Avg VP:** 0.383
- **Interpretation:** Consistent outperformance. Crosses the 70% frame baseline. The primary live gate for any future action. Not yet at PROVEN level because it includes B/C tier dilution.
- **Action:** Use as minimum gate for any candidate lane design.

### Place Probability > 0.80
- **n:** 392 | **SR:** 31.6% | **Frame:** 66.8% | **Lift:** +11.0%
- **Interpretation:** The place_prob specialist model provides significant lift at scale. 392 qualifying races is the largest sidecar sample in the system. Consistent positive lift across the full operating period.
- **Action:** Combine with VP ≥ 0.30 to create a two-factor gate. Do not use alone.

---

## WATCHLIST_SIGNAL
*Positive direction, under-sampled or not yet consistent across enough days*

### Tier B VP ≥ 0.30
- **n:** 130 | **SR:** 30.0% | **Frame:** 62.3%
- **Interpretation:** B-tier picks at VP ≥ 0.30 perform meaningfully better than B-tier overall. This is the "rescue filter" for B-tier — applying a VP floor transforms noisy volume into a watchlist candidate.
- **Action:** Monitor. If SR holds above 28% at n=200, promote to PROMISING.

### V1_BASE (Router Lane)
- **n:** 27 | **SR:** 37.0% | **Frame:** 85.2% | **ROI:** +11.5%
- **Status:** WATCHLIST — needs n ≥ 50 for SHADOW_CANDIDATE promotion
- **Action:** Evidence accumulation only. +23 qualifying results needed.

### V2_CLASS4_ONLY (Router Lane)
- **n:** 17 | **SR:** 41.2% | **Frame:** 82.4% | **ROI:** +30.2%
- **Status:** LANE_ACTIVE — needs n ≥ 20 for WATCHLIST, n ≥ 30 for SHADOW_CANDIDATE
- **Action:** +3 qualifying results → WATCHLIST gate.

### RPDC Release Score > 0.5
- **n:** 54 | **SR:** 24.1% | **Lift:** +3.5%
- **Interpretation:** Modest but positive lift. RPDC signals are early-stage. Trainer/headgear evidence layer may strengthen over time.
- **Action:** Continue accumulation. Re-evaluate at n=100.

---

## NOISY_SIGNAL
*Minimal lift, not worth active tracking — monitor passively*

### Tier B (All VP)
- **n:** 402 | **SR:** 21.1% | **Frame:** 50.0%
- **Interpretation:** At the global baseline for SR, but frame rate (50%) is well below the 70% target. B-tier volume with no VP filter provides almost no signal above random.

### Archetype = Structure
- **n:** 270 | **SR:** 21.1% | **Lift:** +0.5%
- **Interpretation:** Structure archetype provides essentially no lift over global baseline. It may be useful in combination with other signals but is not a standalone predictor.

### Archetype = Compression
- **n:** 40 | **SR:** 20.0% | **Lift:** -0.6%
- **Interpretation:** Compression archetype is at or slightly below global baseline. No lift. Candidate for SUPPRESS at next evidence review.

---

## SUPPRESS_SIGNAL
*Confirmed drag. Removing these picks improves system performance.*

### Tier B VP < 0.30
- **n:** 272 | **SR:** 16.9% | **Frame:** 44.1%
- **Suppression test:** Removing 272 rows (-21.8% coverage) improves SR from 20.6% → 21.6%, Frame 48.4% → 49.6%
- **Interpretation:** These picks are below random at SR=16.9%. They have high volume (272 races) but produce no edge. The coverage cost of suppression is real (-21.8%) but the drag direction is confirmed.
- **Action:** Flag for B-tier VP<0.30 suppression rule. Do not suppress immediately — document threshold for operator decision.

---

## INSUFFICIENT_SAMPLE
*Too few results for any conclusion*

### V6_GOLD_SEAM (Router Lane)
- **n:** 5 | **SR:** 60.0% | **Frame:** 100.0%
- **Note:** Numbers look exceptional but n=5 has no statistical meaning. Must reach n=20 before any assessment.

### G Shadow Multiplier > 1.0
- **n:** 0 — signal exists in code but not wiring through to sigma_audits join. **BROKEN_OR_UNWIRED.**
- **Action:** Investigate wiring path before next audit.

### RPDC Cash Window Flag
- **n:** 1 — near-zero coverage. **INSUFFICIENT_SAMPLE.**

### Macro Chaos Mode
- **n:** 0 — not firing in current data pipeline. **BROKEN_OR_UNWIRED.**

### Playbook G V3 Core
- **Status:** OFFLINE_RESEARCH_CANDIDATE_ONLY
- **Note:** Offline candidate exists from Phase 2B segmentation. Has not yet run on live data. Cannot be ranked until shadow validation produces closed results.

---

## Market-Aware Variants
- **Status:** SUPPRESS — rejected due to market recrowding risk
- **Note:** Any variant that incorporates live market odds as a primary input risks recrowding the market signal back into itself. These are excluded from candidate lane design until a clean separation methodology is designed.

---

## Ranking Summary Table

| Signal | n | SR | Frame | Rank |
|---|---|---|---|---|
| VP ≥ 0.30 + Tier A | 162 | 40.1% | 77.2% | PROVEN_SIGNAL |
| VP ≥ 0.40 | 100 | 44.0% | 85.0% | PROVEN_SIGNAL |
| Market deception score >0.5 | 31 | 54.8% | 96.8% | PROVEN_SIGNAL |
| Improvement score >0.40 | 62 | 43.5% | 82.3% | PROVEN_SIGNAL |
| VP ≥ 0.30 combined | 345 | 32.2% | 69.3% | PROMISING_SIGNAL |
| Place prob >0.80 | 392 | 31.6% | 66.8% | PROMISING_SIGNAL |
| Tier B VP ≥ 0.30 | 130 | 30.0% | 62.3% | WATCHLIST_SIGNAL |
| V1_BASE router | 27 | 37.0% | 85.2% | WATCHLIST_SIGNAL |
| V2_CLASS4_ONLY router | 17 | 41.2% | 82.4% | WATCHLIST_SIGNAL |
| RPDC release score >0.5 | 54 | 24.1% | 48.1% | WATCHLIST_SIGNAL |
| Tier B all VP | 402 | 21.1% | 50.0% | NOISY_SIGNAL |
| Archetype=Structure | 270 | 21.1% | 53.7% | NOISY_SIGNAL |
| Archetype=Compression | 40 | 20.0% | 47.5% | NOISY_SIGNAL |
| **Tier B VP < 0.30** | **272** | **16.9%** | **44.1%** | **SUPPRESS_SIGNAL** |
| V6_GOLD_SEAM router | 5 | 60.0% | 100.0% | INSUFFICIENT_SAMPLE |
| G Shadow multiplier | 0 | — | — | BROKEN_OR_UNWIRED |
| Playbook G V3 core | — | — | — | OFFLINE_RESEARCH_ONLY |

---

*VÉLØ Oracle Prime — Signal Rankings V1 | Evidence-only, no simulation*
*Next review: when global n crosses 1500 matched outcomes or V2 reaches WATCHLIST gate*
