# VFU-05 — Pattern Prosecutor Summary (Current Era Only)

**Generated:** 2026-06-14T20:52:08.567460+00:00
**Source scope:** Current era only (May 08–Jun 13 2026)
**Canonical Passport mutated:** NO
**Supabase written:** NO

---

## VFU-04 Tier-Count Reconciliation

| Tier | Count | % |
|---|---|---|
| TIER_A_FULL | 107 | 8.5% |
| TIER_B_GOOD_NO_PICK_SP | 800 | 63.3% |
| TIER_C_LIMITED_IDENTITY | 62 | 4.9% |
| TIER_D_EVENT_ONLY | 294 | 23.3% |

**Total: 1263 / 1,263 rows — RECONCILED.**

> ERRATA NOTE: The operator's final report text omitted TIER_D_EVENT_ONLY (294 rows). The underlying JSON and JSONL files were correct at all times. This summary reconciles the count.

---

## Pattern Verdicts

| Pattern ID | Belief | Verdict | n | SR |
|---|---|---|---|---|
| VP_BELIEF_01 | VP >= 0.40 is a valid opportunity signal | PROMOTE_TO_WATCHLIST | 213 | 43.2% |
| VP_BELIEF_02 | VP >= 0.45 improves confidence over 0.40 | PROMOTE_TO_WATCHLIST | 154 | 46.1% |
| VP_BELIEF_03 | VP >= 0.50 does not meaningfully improve over | KEEP_OBSERVING | 105 | 48.6% |
| VP_BELIEF_04 | VP false positives are concentrated in specif | HUMAN_REVIEW_REQUIRED | 56 | 0.0% |
| VP_BELIEF_05 | VP false negatives are recoverable through co | NEEDS_MORE_DATA | 244 | 0.0% |
| GATE_BELIEF_06 | GREEN days (avg VP>=0.35) outperform RED days | PROMOTE_TO_WATCHLIST | 306 | 38.6% |
| GATE_BELIEF_07 | RED days protect against weak cards | KEEP_OBSERVING | 412 | 18.2% |
| GATE_BELIEF_08 | False GREEN days require warning logic | HUMAN_REVIEW_REQUIRED | 0 | N/A |
| GATE_BELIEF_09 | Jun 09 remains a known false-GREEN caveat | PROMOTE_TO_WATCHLIST | 0 | N/A |
| PRICE_BELIEF_10 | SP >= 6.0 is a dead zone | NEEDS_MORE_DATA | 43 | 16.3% |
| PRICE_BELIEF_11 | SP 4.0–6.0 is a mid-price wall | NEEDS_MORE_DATA | 15 | 20.0% |
| PRICE_BELIEF_12 | SP 1.5–4.0 with VP>=0.40 is the operating win | PROMOTE_TO_WATCHLIST | 10 | 40.0% |
| COURSE_BELIEF_13 | Musselburgh is excelling | PROMOTE_TO_WATCHLIST | 20 | 55.0% |
| COURSE_BELIEF_14 | Worcester is excelling | PROMOTE_TO_WATCHLIST | 21 | 47.6% |
| COURSE_BELIEF_15 | Uttoxeter is excelling | PROMOTE_TO_WATCHLIST | 27 | 44.4% |
| COURSE_BELIEF_16 | Yarmouth is a drain | PROMOTE_TO_WATCHLIST | 20 | 10.0% |
| COURSE_BELIEF_17 | Beverley is a drain | NEEDS_MORE_DATA | 14 | 7.1% |
| COURSE_BELIEF_18 | Hamilton is caution | KEEP_OBSERVING | 26 | 19.2% |
| COURSE_BELIEF_19 | Nottingham is caution | NEEDS_MORE_DATA | 19 | 15.8% |
| HORSE_BELIEF_20 | Repeated horses show exploitable profile chan | HUMAN_REVIEW_REQUIRED | 0 | N/A |
| HORSE_BELIEF_21 | Some misses are due to missing repeat-horse m | NEEDS_MORE_DATA | 244 | 0.0% |
| HORSE_BELIEF_22 | Horse Passport candidates are useful but not  | DATA_BLOCKED | 0 | N/A |
| DATA_BELIEF_23 | LOCAL_ONLY rows are useful only for aggregate | PROMOTE_TO_WATCHLIST | 0 | N/A |
| DATA_BELIEF_24 | Lack of horse_id blocks Passport automation | DATA_BLOCKED | 0 | N/A |
| DATA_BELIEF_25 | Lack of pick_sp blocks ROI claims | DATA_BLOCKED | 0 | N/A |
| DATA_BELIEF_26 | winner_in_frame unavailable blocks frame-qual | DATA_BLOCKED | 0 | N/A |

---

## Promoted to Watchlist

- **VP_BELIEF_01** — VP >= 0.40 is a valid opportunity signal
  - Evidence: n=213, SR=0.432, confidence=HIGH
  - Confirms: SR>=35% sustained over 14-day dry-run
  - Kills it: SR falls below 28% for 5+ consecutive days

- **VP_BELIEF_02** — VP >= 0.45 improves confidence over 0.40
  - Evidence: n=154, SR=0.461, confidence=HIGH
  - Confirms: SR remains above VP>=0.40 SR
  - Kills it: VP>=0.45 converges to VP>=0.40 over 50+ new rows

- **GATE_BELIEF_06** — GREEN days (avg VP>=0.35) outperform RED days (VP<0.25)
  - Evidence: n=306, SR=0.386, confidence=HIGH
  - Confirms: HIGH-VP pool SR >= 30% day-on-day
  - Kills it: Multiple GREEN days with 0 wins

- **GATE_BELIEF_09** — Jun 09 remains a known false-GREEN caveat
  - Evidence: n=0, SR=None, confidence=INSUFFICIENT
  - Confirms: FALSE_GREEN_POSSIBLE logged on every GREEN label
  - Kills it: Any GREEN day without caveat

- **PRICE_BELIEF_12** — SP 1.5–4.0 with VP>=0.40 is the operating window
  - Evidence: n=10, SR=0.4, confidence=INSUFFICIENT
  - Confirms: SR>=36% on SP 1.5-4.0 + VP>=0.40 with n>=50
  - Kills it: SR below baseline on 30+ rows

- **COURSE_BELIEF_13** — Musselburgh is excelling
  - Evidence: n=20, SR=0.55, confidence=LOW
  - Confirms: SR>=38% on 20+ Musselburgh rows
  - Kills it: SR falls below baseline on 10+ more rows

- **COURSE_BELIEF_14** — Worcester is excelling
  - Evidence: n=21, SR=0.476, confidence=LOW
  - Confirms: SR>=38% on 20+ Worcester rows
  - Kills it: SR falls below baseline

- **COURSE_BELIEF_15** — Uttoxeter is excelling
  - Evidence: n=27, SR=0.444, confidence=LOW
  - Confirms: SR>=38% on 20+ Uttoxeter rows
  - Kills it: SR falls below baseline

- **COURSE_BELIEF_16** — Yarmouth is a drain
  - Evidence: n=20, SR=0.1, confidence=LOW
  - Confirms: SR<=15% on 20+ Yarmouth rows
  - Kills it: SR climbs above baseline

- **DATA_BELIEF_23** — LOCAL_ONLY rows are useful only for aggregate pattern evidence
  - Evidence: n=0, SR=None, confidence=INSUFFICIENT
  - Confirms: TIER_D stays excluded from named conclusions
  - Kills it: TIER_D rows incorrectly merged

---

## Data-Blocked / Rejected

- **HORSE_BELIEF_22** — Horse Passport candidates are useful but not merge-ready
  - Reason: NAME_ONLY_CONFIDENCE: horse_id=None for all 1,263 rows. Name-based matching only.

- **DATA_BELIEF_24** — Lack of horse_id blocks Passport automation
  - Reason: Insufficient evidence or data gap

- **DATA_BELIEF_25** — Lack of pick_sp blocks ROI claims
  - Reason: Insufficient evidence or data gap

- **DATA_BELIEF_26** — winner_in_frame unavailable blocks frame-quality prosecution
  - Reason: Insufficient evidence or data gap

---

## Summary Answers

1. PROMOTE_TO_WATCHLIST: 10 beliefs — VP>=0.40, VP>=0.45, VP Gatekeeper GREEN/RED, Jun-09-caveat, operating SP window, TIER_D aggregate separation, and some course tiers.
2. DATA_BLOCKED: 4 — horse_id automation, full ROI, winner_in_frame, Passport merge.
3. NEEDS_MORE_DATA: 6 — SP dead-zone (n=107), VP false negative recovery.
4. KEEP_OBSERVING: 3 — RED-day protection, VP>=0.50 marginal lift.
5. Not safe for live use: all 26 patterns are blocked_from_live_use=True. No automatic staking.
6. Top 5 investigation priorities: (1) horse_id bridge; (2) pick_sp expansion; (3) day-level gate log; (4) winner_in_frame archive; (5) false-GREEN day enumeration.
7. Data gaps most restricting prosecution: horse_id=0%, pick_sp=8.5%, winner_in_frame=0%, day-level gate log absent.
8. Before Passport automation: horse_id bridge must be built from racecard injection files. All 69 passport candidates remain do_not_merge=True.
9. Before ROI claims: pick_sp must expand beyond innovation CSV. Current ceiling: 107 rows.
10. VFU-06 recommendation: PROCEED on identity bridge (horse_id join). Do NOT open Mar–Apr. Do NOT advance Passport automation until horse_id bridge proven.

---

## Hard Rule Confirmations

| Check | Status |
|---|---|
| Canonical Horse Passport NOT mutated | CONFIRMED |
| No Supabase writes | CONFIRMED |
| No live scoring change | CONFIRMED |
| No model promotion | CONFIRMED |
| No hard course bans | CONFIRMED |
| No Telegram send | CONFIRMED |
| No Racing API restoration | CONFIRMED |
| No Mar–Apr extraction | CONFIRMED |
| ROI limited to pick_sp rows | CONFIRMED |
| Repeated-horse NAME_ONLY_CONFIDENCE | CONFIRMED |
| Passport automation blocked | CONFIRMED |

## Final Classifications

- `VFU_05_PATTERN_PROSECUTOR_COMPLETE`
- `VFU_04_TIER_COUNTS_RECONCILED`
- `PATTERN_WATCHLIST_CREATED`
- `DATA_BLOCKED_PATTERNS_DECLARED`
- `HUMAN_REVIEW_QUEUE_CREATED`
- `ROI_LIMITED_TO_PICK_SP_ROWS`
- `REPEATED_HORSE_NAME_ONLY_CONFIDENCE`
- `PASSPORT_AUTOMATION_BLOCKED_PENDING_HORSE_ID`
- `NO_HARD_COURSE_BANS`
- `NO_LIVE_DOCTRINE_PROMOTION_WITHOUT_OPERATOR`
- `NO_MAR_APR_EXTRACTION`
- `CANONICAL_HORSE_PASSPORT_NOT_MUTATED`
- `NO_LIVE_SCORING_CHANGE`
- `NO_SUPABASE_WRITES`
- `NO_MODEL_PROMOTION`
- `NO_TELEGRAM_SEND`
- `NO_RACING_API_RESTORATION`