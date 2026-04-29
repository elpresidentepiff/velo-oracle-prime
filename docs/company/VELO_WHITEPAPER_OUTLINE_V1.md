# VÉLØ Whitepaper Outline V1

**Title:** VÉLØ: An Auditable Intelligence Operating System for Horse Racing Prediction

**Subtitle:** Evidence-Grade Race Intelligence from Machine Learning, Market Analysis, and Structured Audit

**Date:** 2026-04-28 (draft outline)
**Target audience:** Technical investors, data science community, racing analytics market, potential partners

---

## Abstract (target: 200 words)

VÉLØ Oracle Prime is an auditable intelligence operating system designed for horse racing prediction. Unlike existing racing services, VÉLØ commits every prediction to an immutable evidence vault, reconciles all predictions against closed results, and produces structured signal rankings from live data. This paper describes the system architecture, evidence methodology, 49-day performance results, and the company's research roadmap for improving winner conversion in the mid-priced zone (SP 3.0–8.5).

---

## Section 1: The Problem

**1.1 Racing intelligence is largely unauditable**
- Most tipster services provide picks with no methodology disclosure
- No traceable chain from model input to prediction to result
- Historical performance claims are selectively curated
- Post-race miss analysis is absent or superficial

**1.2 The market inefficiency**
- Horse racing markets are semi-efficient
- Mid-priced winners (SP 3.0–8.5) are systematically underidentified
- Favourite-following produces negative expected value
- Machine learning on structured data can find edge in specific bands

**1.3 Why auditability changes everything**
- Auditable predictions are defensible, fundable, and trustworthy
- Evidence accumulation enables governed signal promotion
- Transparent miss analysis is more valuable than curated win lists

---

## Section 2: System Architecture

**2.1 Overview**
- VeloPrimeEnsemble: SQPE v17 + 7 specialist models
- Sigma audit layer: daily closed-result reconciliation
- Router Evidence Engine: shadow lane accumulation
- Evidence Vault: Git-committed immutable archive

**2.2 The prediction pipeline**
```
Racing API data → Feature engineering → VeloPrimeEnsemble
    → VP score + Tier classification + Sidecar signals
    → Product routing → Telegram intelligence report
    → Sigma audit (post-race) → Evidence Vault
```

**2.3 The VeloPrimeEnsemble**
- SQPE v17: gradient boosting trained on 50k row backtest
- 7 specialist models: improvement, market_deception, release_window,
  comment_intelligence, draw_bias, place, longshot
- Ensemble fusion: weighted probability with specialist overlays

**2.4 Race archetype classification**
- Structure / Compression / Chaos archetypes
- Each archetype produces different routing and signal behaviour
- Structure archetype is the primary attack lane (router V2)

**2.5 The sigma audit layer**
- Every prediction reconciled against Racing API closed results
- Outcomes: WIN / PLACED / MISS (classified) / X-tier excluded
- Miss classes: mid_priced_won, short_fav_won, outsider_won, market_decoy_followed
- 176 learned patterns accumulated from closed results

**2.6 The Router Evidence Engine**
- Innovation Protocol: 713-row deduped dataset of router-qualified races
- Three shadow lanes: V1_BASE, V2_CLASS4_ONLY, V6_GOLD_SEAM
- Append-only ledger with timestamped snapshots
- Freeze rules: ROI<0 at n≥20 OR Frame<70% at n≥20

---

## Section 3: Evidence Methodology

**3.1 Data collection**
- Predictions generated pre-race from Racing API data
- Results fetched post-race from Racing API results endpoint
- No hindsight, no retroactive adjustment

**3.2 Prediction reconciliation**
- Exact course/time matching with 4-level fallback
- Non-runners excluded (not counted as misses)
- X-tier predictions excluded from SR/frame calculations (honest)

**3.3 Signal ranking methodology**
- Signals ranked by: n, SR vs baseline, frame vs target, lift
- Minimum n for PROVEN status: 30+
- Rankings updated with each Unified Evidence Audit

**3.4 The VP scale**
- VP (Velo Prime probability) is the ensemble's winner probability estimate
- Range: 0.00–1.00
- Proven monotonic: VP<0.20=14.5% SR → VP≥0.40=44.0% SR

---

## Section 4: 49-Day Results

**4.1 Global performance**
- 49 race days (2026-01-09 to 2026-04-28)
- 1,391 sigma-audited predictions
- SR=20.6% (baseline 20%), Frame=48.4%

**4.2 VP band analysis**
- [Table: VP band performance]
- VP monotonic relationship proven across all 49 days

**4.3 Tier analysis**
- [Table: Tier A/B/C/D/X performance]
- Tier A: SR=40.1%, Frame=77.2%, n=162 — proven

**4.4 Sidecar signal analysis**
- Market deception score >0.5: SR=54.8%, Frame=96.8%, n=31
- Improvement score >0.40: SR=43.5%, Frame=82.3%, n=62
- Place probability >0.80: SR=31.6%, Frame=66.8%, n=392

**4.5 Router lane evidence**
- V1_BASE: n=27, SR=37%, ROI=+11.5%
- V2_CLASS4_ONLY: n=17, SR=41%, ROI=+30.2%
- V6_GOLD_SEAM: n=5, SR=60%, ROI=+115% (small sample)

**4.6 Miss class analysis**
- [Table: miss class breakdown]
- 58% of misses in SP 3.0–8.5 zone

**4.7 Modification impact timeline**
- VeloPrimeEnsemble (Mar 16): foundational
- Race archetype classification (Apr 10): +3.9% SR, +6.7% frame
- [Full timeline table]

---

## Section 5: Known Weaknesses

**5.1 Mid-priced winner conversion (primary)**
- SP 3.0–8.5 zone = 58% of all misses
- VÉLØ frames these races but cannot separate the winner
- Research target: what feature distinguishes winners in this zone?

**5.2 B-tier low-confidence drag**
- 272 B-tier VP<0.30 predictions, SR=16.9%
- These picks dilute the global frame rate from 70%+ to 48.4%
- Suppression would lose 22% coverage for ~1% SR gain

**5.3 Short-favourite override**
- 81 misses where a short favourite (<3.0 SP) won despite VÉLØ backing another horse
- Market signal should override model ranking in these cases

---

## Section 6: Research Roadmap

**6.1 Candidate lane design**
- VP≥0.30 + Tier A lane (evidence: n=162, PROVEN)
- MDS>0.5 + VP≥0.30 lane (evidence: n=31, PROVEN lift)
- Improvement score + VP≥0.30 lane (evidence: n=62, PROVEN lift)

**6.2 Mid-priced winner forensics**
- Feature analysis of SP 3–8.5 winners vs VÉLØ picks
- Hypothesis: VÉLØ underweights recent form in this zone
- Method: isolation forest + feature importance on miss cases

**6.3 Router lane promotion path**
- V2 → WATCHLIST at n=20 (3 more qualifying results)
- V2 → SHADOW_CANDIDATE at n=30
- Any lane → LIVE_DISCUSSION at n=100

---

## Section 7: Commercial Applications

**7.1 Consumer intelligence app** — daily race analytics with transparency dashboard
**7.2 Professional dashboard** — full sidecar detail, router lane status, API
**7.3 Data API** — VP scores, archetypes, sidecar signals for B2B
**7.4 Stable/trainer/owner tools** — intelligence for racing professionals
**7.5 Media/content** — provably accurate race analytics for editorial

---

## Section 8: Risk Controls

- No automated staking
- No router promotion without evidence gates
- No claims beyond what the evidence proves
- Responsible gambling disclaimers on all consumer-facing content
- Audit dossier publicly accessible (transparency)

---

## Appendix

- A: Evidence vault contents
- B: Full signal rankings table
- C: Modification impact timeline
- D: Glossary (VP, Tier, MDS, SR, Frame, Router Lane)
- E: Data sources and methodology

---

*VÉLØ Oracle Prime — Whitepaper Outline V1 | 2026-04-28*
*Full whitepaper to be written after Unified Evidence Audit V2*
