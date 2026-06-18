# VFU-12 — Sigma Pattern Tribunal + Human Review Triage
**Version:** VFU_12_SIGMA_PATTERN_TRIBUNAL_V1  
**Timestamp:** 2026-06-18T01:32:09.486219+00:00  
**VP Threshold:** 0.4 (UNCHANGED)  

---

## VFU-10 Law (carried forward permanently)

> *No evidence becomes doctrine unless it was knowable before the race.*

---

## Pattern Tribunal Verdicts

| Pattern | n (total) | n (current) | Verdict | Contamination Risk |
|---------|-----------|-------------|---------|-------------------|
| DATA_QUALITY_DEBT_CANDIDATE | 2,516 | 1,265 | **DATA_BLOCKED** | MEDIUM — mix of current-era and quarantine rows; field gaps prevent era assignment in some |
| ERA_CONTAMINATION_CANDIDATE | 2,165 | 0 | **KEEP_QUARANTINED** | CRITICAL — all rows PRE_SURGERY_ARCHIVE_QUARANTINE |
| FALSE_GREEN_CANDIDATE | 366 | 258 | **NEEDS_TIME_SAFE_VALIDATION** | LOW — all current-era TIME_SAFE |
| IDENTITY_RESOLUTION_NEEDED | 2,822 | 2,112 | **DATA_BLOCKED** | LOW — rows exist, identity is absent; contamination risk is identity-provenance risk, not temporal |
| PASSPORT_OVERRIDE_CANDIDATE | 258 | 235 | **PROMOTE_TO_DRY_RUN_WATCHLIST** | LOW — current-era TIME_SAFE rows only |
| SP_SHORTENING_CANDIDATE | 501 | 316 | **PROMOTE_TO_DRY_RUN_WATCHLIST** | LOW — current-era TIME_SAFE; VFU-10 validated time-safety |
| VP_SUPPRESSION_CANDIDATE | 582 | 342 | **PROMOTE_TO_DRY_RUN_WATCHLIST** | LOW — all current-era TIME_SAFE rows |

All patterns: `blocked_from_live_use=True`, `human_approval_required=True`, `do_not_promote=True`

---

## Detailed Pattern Verdicts

### DATA_QUALITY_DEBT_CANDIDATE
**Verdict:** DATA_BLOCKED  
**Evidence count (total):** 2,516  
**Current-era (TIME_SAFE):** 1,265  
**Archive quarantine:** 663  
**RP_UID confirmed (current):** 0  
**Avg VP (current):** 0.3707  
**Avg SP (current):** 5.495  
**Contamination risk:** MEDIUM — mix of current-era and quarantine rows; field gaps prevent era assignment in some  
**Sample warning:** Data quality prevents signal extraction. Not a pattern — a repair task.  

**Reason:** n=2516 rows with ≥3 data gaps (n_current=1265 current-era). Gaps include VP_MISSING, HORSE_ID_MISSING, SP_MISSING, COURSE_MISSING, DATE_MISSING. Cannot run meaningful pattern analysis on rows with critical field absences. Data quality repair required before this cohort can be investigated.

**Next required evidence:** Prioritise: (1) horse_id resolution for NAME_ONLY rows, (2) SP backfill from sigma_audits_dump where actual_winner_sp is available, (3) off_time population from sigma_results EOD files. Target: reduce 3+-gap rows by ≥50% before re-running pattern tribunal.

### ERA_CONTAMINATION_CANDIDATE
**Verdict:** KEEP_QUARANTINED  
**Evidence count (total):** 2,165  
**Current-era (TIME_SAFE):** 0  
**Archive quarantine:** 2,165  
**RP_UID confirmed (current):** 0  
**Avg VP (current):** None  
**Avg SP (current):** None  
**Contamination risk:** CRITICAL — all rows PRE_SURGERY_ARCHIVE_QUARANTINE  
**Sample warning:** n=2165 is large but entirely contaminated — quantity does not overcome contamination.  

**Reason:** n=2165 rows, all PRE_SURGERY_ARCHIVE_QUARANTINE (Mar–Apr 2026). n_current=0 — zero time-safe rows in this pattern. Mar–Apr may be inspected as quarantined evidence only. VFU-10 law prohibits any of these becoming doctrine.

**Next required evidence:** No doctrine pathway for Mar–Apr data. Archive for historical completeness only. Any signal from this era requires prospective validation from 2026-05-08+.

### FALSE_GREEN_CANDIDATE
**Verdict:** NEEDS_TIME_SAFE_VALIDATION  
**Evidence count (total):** 366  
**Current-era (TIME_SAFE):** 258  
**Archive quarantine:** 63  
**RP_UID confirmed (current):** 78  
**Avg VP (current):** 0.5102  
**Avg SP (current):** 5.3283  
**Contamination risk:** LOW — all current-era TIME_SAFE  
**SR Note:** SR=0.0 IS A DEFINITIONAL ARTIFACT — all rows are non-winners by flag definition.  
**Sample warning:** n=258 is sufficient but pattern source (which feature?) is unknown.  

**Reason:** n=258 current-era TIME_SAFE VP≥0.40 non-winners. Avg VP=0.510. SR=0.0 is a definitional artifact (all these horses lost by definition). Real question: what features drove VP>=0.40 in losing cases? Need feature-level audit to distinguish systemic miss vs. legitimate race risk.

**Next required evidence:** Feature-level attribution: which Ensemble components drove VP high in losing cases? Is this market_deception_score, improvement_score, or SQPE-driven? Requires VFU-13 feature autopsy, not watchlist promotion yet.

### IDENTITY_RESOLUTION_NEEDED
**Verdict:** DATA_BLOCKED  
**Evidence count (total):** 2,822  
**Current-era (TIME_SAFE):** 2,112  
**Archive quarantine:** 453  
**RP_UID confirmed (current):** 0  
**Avg VP (current):** 0.3122  
**Avg SP (current):** 5.8943  
**Contamination risk:** LOW — rows exist, identity is absent; contamination risk is identity-provenance risk, not temporal  
**Sample warning:** n=2112 current-era NAME_ONLY is a major gap — 69% of current-era rows lack RP_UID.  

**Reason:** n=2822 rows without RP_UID namespace (n_current=2112 current-era). Without confirmed horse identity, cannot build Passport evidence, cross-reference VFU-10 time-safe snapshots, or track repeat-horse patterns. Identity resolution is a prerequisite for any Passport doctrine pathway.

**Next required evidence:** Run Horse ID Bridge (VFU-06 method) over current-era NAME_ONLY rows. Specifically target sigma_audits_dump rows (source of most nulls) and sigma_results rows. Priority: current-era NAME_ONLY with VP_SUPPRESSION or FALSE_GREEN flags.

### PASSPORT_OVERRIDE_CANDIDATE
**Verdict:** PROMOTE_TO_DRY_RUN_WATCHLIST  
**Evidence count (total):** 258  
**Current-era (TIME_SAFE):** 235  
**Archive quarantine:** 0  
**RP_UID confirmed (current):** 137  
**Avg VP (current):** 0.4244  
**Avg SP (current):** 7.532  
**Contamination risk:** LOW — current-era TIME_SAFE rows only  

**Reason:** n=235 current-era TIME_SAFE rows with existing Passport/pattern update candidates. Already on VFU-10 dry-run watchlist (N/A VFU-10 candidates). VFU-08/VFU-10 context gives time-safe Passport snapshot for subset. Linked to VP_SUPPRESSION and SP_SHORTENING signals — consistent oversight.

**Next required evidence:** Prioritise the Top 25 human review entries that have PASSPORT_OVERRIDE_CANDIDATE flag. Cross-link with VFU-10 watchlist by horse_id. Merge only after n>=50 confirmed + operator authorisation.

### SP_SHORTENING_CANDIDATE
**Verdict:** PROMOTE_TO_DRY_RUN_WATCHLIST  
**Evidence count (total):** 501  
**Current-era (TIME_SAFE):** 316  
**Archive quarantine:** 140  
**RP_UID confirmed (current):** 23  
**Avg VP (current):** 0.3505  
**Avg SP (current):** 2.4487  
**Contamination risk:** LOW — current-era TIME_SAFE; VFU-10 validated time-safety  
**SR Note:** SR=1.0 IS A DEFINITIONAL ARTIFACT — all rows are winners by flag definition.  

**Reason:** n=316 current-era TIME_SAFE SP<20 winners, avg VP=0.350. VFU-10 confirmed SP shortening is time-safe (pre-era observable). VFU-10 Group A: 67% SP-shortened vs Group C: 60% — directional but not conclusive. Avg VP=0.351 places these near the threshold — SP shortening may partially explain VP suppression.

**Next required evidence:** Build per-horse SP trajectory from core_v0 historical dataset (VFU-10 method). Validate that SP shortening is pre-race-day observable (not same-day move). Minimum n=50 RP_UID confirmed before Passport entry consideration.

### VP_SUPPRESSION_CANDIDATE
**Verdict:** PROMOTE_TO_DRY_RUN_WATCHLIST  
**Evidence count (total):** 582  
**Current-era (TIME_SAFE):** 342  
**Archive quarantine:** 172  
**RP_UID confirmed (current):** 102  
**Avg VP (current):** 0.259  
**Avg SP (current):** 3.6447  
**Contamination risk:** LOW — all current-era TIME_SAFE rows  
**SR Note:** SR=1.0 IS A DEFINITIONAL ARTIFACT — all rows are winners by flag definition.  

**Reason:** n=342 current-era TIME_SAFE VP<0.40 winners. Avg VP=0.259, avg SP=3.6. Short-priced winners (avg SP=4.3) indicate structural VP under-rating of confident market. n_rp_uid=102 — directional signal, needs identity enrichment before Passport doctrine.

**Next required evidence:** Increase RP_UID confirmed from 102 to 150+. Cross-reference with pre-era SP trajectory (VFU-10 time-safe method). n>=50 RP_UID confirmed before Passport watchlist entry.

---

## Human Review Queue Triage

**Total entries triaged:** 200  
**Priority band distribution:**  
- P0_CRITICAL: 41
- P4_ARCHIVE_ONLY: 159

### Top 25 Human Review Cases

| Rank | Priority | Horse | Era | VP | Outcome | Flags |
|------|----------|-------|-----|----|---------|-------|
| 1 | P0_CRITICAL | Saucy Jane | CURRENT_ERA_VALIDATE | 0.4318 | MISS | FALSE_GREEN, PASSPORT_OVE |
| 2 | P0_CRITICAL | Food For Thought | CURRENT_ERA_VALIDATE | 0.5035 | MISS | FALSE_GREEN, PASSPORT_OVE |
| 3 | P0_CRITICAL | Martymill | CURRENT_ERA_VALIDATE | 0.4187 | MISS | FALSE_GREEN, PASSPORT_OVE |
| 4 | P0_CRITICAL | African Spirit | CURRENT_ERA_VALIDATE | 0.4444 | MISS | FALSE_GREEN, PASSPORT_OVE |
| 5 | P0_CRITICAL | Letmeseethecolts | CURRENT_ERA_VALIDATE | 0.4299 | MISS | FALSE_GREEN, PASSPORT_OVE |
| 6 | P0_CRITICAL | Bearish | CURRENT_ERA_VALIDATE | 0.4057 | MISS | FALSE_GREEN, PASSPORT_OVE |
| 7 | P0_CRITICAL | Saxophonist | CURRENT_ERA_VALIDATE | 0.4057 | MISS | FALSE_GREEN, PASSPORT_OVE |
| 8 | P0_CRITICAL | Lemmy Caution | CURRENT_ERA_VALIDATE | 0.525 | MISS | FALSE_GREEN, PASSPORT_OVE |
| 9 | P0_CRITICAL | Thickthorn Tom | CURRENT_ERA_VALIDATE | 0.4195 | MISS | FALSE_GREEN, PASSPORT_OVE |
| 10 | P0_CRITICAL | Flying Ace | CURRENT_ERA_VALIDATE | 0.4906 | MISS | FALSE_GREEN, PASSPORT_OVE |
| 11 | P0_CRITICAL | High Storm | CURRENT_ERA_VALIDATE | 0.4815 | MISS | FALSE_GREEN, PASSPORT_OVE |
| 12 | P0_CRITICAL | Stellar Sunrise | CURRENT_ERA_VALIDATE | 0.4135 | MISS | FALSE_GREEN, PASSPORT_OVE |
| 13 | P0_CRITICAL | Sandy Craic | CURRENT_ERA_VALIDATE | 0.4547 | MISS | FALSE_GREEN, PASSPORT_OVE |
| 14 | P0_CRITICAL | Jazz Queen | CURRENT_ERA_VALIDATE | 0.6759 | MISS | FALSE_GREEN, PASSPORT_OVE |
| 15 | P0_CRITICAL | Never So Brave | CURRENT_ERA_VALIDATE | 0.4358 | MISS | FALSE_GREEN, PASSPORT_OVE |
| 16 | P0_CRITICAL | Calandagan | CURRENT_ERA_VALIDATE | 0.4909 | MISS | FALSE_GREEN, PASSPORT_OVE |
| 17 | P0_CRITICAL | Conquer The Breeze | CURRENT_ERA_VALIDATE | 0.4543 | MISS | FALSE_GREEN, PASSPORT_OVE |
| 18 | P0_CRITICAL | Sovereign Bay | CURRENT_ERA_VALIDATE | 0.5037 | MISS | FALSE_GREEN, PASSPORT_OVE |
| 19 | P0_CRITICAL | Pixie Diva | CURRENT_ERA_VALIDATE | 0.4473 | MISS | FALSE_GREEN, PASSPORT_OVE |
| 20 | P0_CRITICAL | Magical Merlot | CURRENT_ERA_VALIDATE | 0.4098 | MISS | FALSE_GREEN, PASSPORT_OVE |
| 21 | P0_CRITICAL | My A'Ali Baba | CURRENT_ERA_VALIDATE | 0.5704 | MISS | FALSE_GREEN, PASSPORT_OVE |
| 22 | P0_CRITICAL | Wemightakedlongway | CURRENT_ERA_VALIDATE | 0.4346 | MISS | FALSE_GREEN, PASSPORT_OVE |
| 23 | P0_CRITICAL | Hypotenus | CURRENT_ERA_VALIDATE | 0.4142 | MISS | FALSE_GREEN, PASSPORT_OVE |
| 24 | P0_CRITICAL | Deputy Vice | CURRENT_ERA_VALIDATE | 0.6136 | MISS | FALSE_GREEN, PASSPORT_OVE |
| 25 | P0_CRITICAL | Charlie Boyo | CURRENT_ERA_VALIDATE | 0.4665 | MISS | FALSE_GREEN, PASSPORT_OVE |

---

## Required Report Answers

**Q1 — Dry-run watchlist patterns:** PASSPORT_OVERRIDE_CANDIDATE, SP_SHORTENING_CANDIDATE, VP_SUPPRESSION_CANDIDATE
**Q2 — Data-blocked patterns:** DATA_QUALITY_DEBT_CANDIDATE, IDENTITY_RESOLUTION_NEEDED
**Q3 — Quarantine-only patterns:** ERA_CONTAMINATION_CANDIDATE
**Q4 — Needs time-safe validation:** FALSE_GREEN_CANDIDATE
**Q5 — Rejected patterns:** None
**Q6 — Top 25 generated:** YES

**Q7 — Biggest contamination risks:**
  - ERA_CONTAMINATION_CANDIDATE: n=2,165 Mar–Apr rows, zero time-safe (CRITICAL)
  - SKELETON_OR_NULL_DATE_EXCLUDED: 331 rows with null/invalid dates — temporal provenance unknown
  - DATA_QUALITY_DEBT_CANDIDATE overlap: 159 of 200 review queue entries are archive-quarantine rows

**Q8 — Biggest data-quality blockers:**
  - IDENTITY_RESOLUTION_NEEDED: 2,822 rows without RP_UID (2,112 current-era)
  - DATA_QUALITY_DEBT_CANDIDATE: 2,516 rows with 3+ data gaps
  - VP_MISSING: 969 current-era rows

**Q9 — SP shortening status:** SP shortening REMAINS the strongest time-safe Passport signal. VFU-10 validated: pre-era SP trajectory is observable before race. Current-era n=316, avg VP=0.3505. Verdict: PROMOTE_TO_DRY_RUN_WATCHLIST — watchlist, not doctrine.

**Q10 — VP threshold recommendation:** VP threshold remains 0.4. NO CHANGE RECOMMENDED. Evidence from current-era confirms monotonic VP signal strength. FALSE_GREEN pattern (n=258) requires feature attribution before any threshold review.

**Q11 — Doctrine promotion recommendation:** NO DOCTRINE PROMOTION RECOMMENDED. VFU-10 law: no evidence becomes doctrine unless it was knowable before the race. Watchlist patterns require n>=50 RP_UID confirmed + operator review. FALSE_GREEN requires feature attribution. Quarantine patterns (Mar–Apr) permanently excluded from doctrine pathway.

**Q12 — VFU-13 recommendation:** VFU-13 recommended. Suggested focus (operator decision required): OPTION A — False-GREEN Feature Autopsy: identify which Ensemble component drove VP≥0.40 in 258 current-era losing cases. Requires feature-level ledger from VFU-11 identity-enriched autopsy. OPTION B — SP Shortening Deep Dive: build per-horse SP trajectory from core_v0 for the 316 current-era SP<20 winners (VFU-10 extension). OPTION C — Identity Repair Sprint: resolve 2,112 current-era NAME_ONLY rows to unlock VP_SUPPRESSION and SP_SHORTENING for Passport analysis. Operator to choose one focus area.

---

## Hard Rules — Confirmed

- VP threshold: 0.40 — UNCHANGED
- Canonical Horse Passport: NOT MUTATED
- Supabase: NOT WRITTEN
- Live scoring: NOT CHANGED
- Model: NOT PROMOTED
- Telegram: NOT SENT
- Racing API: NOT RESTORED
- Mar–Apr: QUARANTINE ONLY — no doctrine, no Passport, no live use
- All patterns: blocked_from_live_use=True, human_approval_required=True

---

## Final Classifications

```
VFU_12_SIGMA_PATTERN_TRIBUNAL_COMPLETE
PATTERN_VERDICTS_CREATED
HUMAN_REVIEW_TOP25_CREATED
MAR_APR_QUARANTINE_MAINTAINED
NO_LIVE_DOCTRINE_PROMOTION
NO_VP_THRESHOLD_CHANGE
PATTERN_CANDIDATES_DRY_RUN_ONLY
HUMAN_APPROVAL_REQUIRED_FOR_ALL_PATTERNS
CANONICAL_HORSE_PASSPORT_NOT_MUTATED
NO_LIVE_SCORING_CHANGE
NO_SUPABASE_WRITES
NO_MODEL_PROMOTION
NO_TELEGRAM_SEND
NO_RACING_API_RESTORATION
```