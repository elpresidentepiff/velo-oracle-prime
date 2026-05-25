# RP Form History Inventory — Audit Report

Generated: 2026-05-25 | Trust policy: ARCHIVE_CONTEXT_ONLY_NOT_SCORING | velo_scoring_allowed: false

---

## A. Horse Profiles Parsed

| Date | Profiles | Form History Built |
|------|----------|--------------------|
| 2026-05-24 | 1 (Bow Echo only) | NO — parser not run |
| 2026-05-25 | 59 | NO — parser not run |
| 2026-05-26 | 70 | YES — 1,069 runs |
| 2026-05-27 | 91 | YES — 1,159 runs |
| 2026-05-28 | 0 | N/A — no horse_profiles.json |
| 2026-05-29 | 0 | N/A — no horse_profiles.json |
| 2026-05-30 | 0 | N/A — no horse_profiles.json |

**Total profiles parsed into form history: 161 (May 26 + May 27 only)**
**Total horse profiles captured but not yet form-parsed: 60 (May 24 + May 25)**

---

## B. Total Form History Runs Parsed

**2,228 runs** across 161 horses (May 26 + May 27 captures)

---

## C. Average Runs Per Horse

**13.8 runs/horse** (161 horses, 2,228 runs)

Includes 14 horses with 0 runs (maiden/debut horses — not parser failures, these have no form table in the HTML)

---

## D. Maximum Runs Per Horse

| Horse | Runs | Date Range | Capture Date |
|-------|------|-----------|--------------|
| **Fircombe Hall** | **88** | 2020-06-06 to 2026-04-23 | May 26 |
| Soul Seeker | 76 | 2019-10-12 to 2026-05-21 | May 26 |
| Reigning Profit | 72 | 2021-05-15 to 2026-05-23 | May 27 |
| Yaaser | 71 | 2021-09-18 to 2026-02-06 | May 27 |
| Eligible | 70 | 2018-09-22 to 2026-04-25 | May 26 |

---

## E. Dates Covered in Run History

- **Earliest observed run**: 2018-09-22 (Eligible, 70 runs, 7+ year career)
- **Latest observed run**: 2026-05-24
- **Career span covered**: approximately 7.67 years of run history in this batch
- Most horses span 2020-2026 (flat career profiles)

---

## F. Courses Covered

Estimated 50+ distinct courses. Confirmed in data: Southwell (AW), Newcastle (AW), Redcar, Leicester, Kempton (AW), Newmarket, Haydock, Newbury, Chelmsford City (AW), Wolverhampton (AW), Catterick, Carlisle, Chester, York, Windsor, Ascot, Goodwood, Pontefract, Beverley, Nottingham, Lingfield (AW), and more.

---

## G. Jockey Coverage

- jockey_name: ~99.5% of runs
- jockey_rp_uid: ~95% of runs (extracted from `/profile/jockey/{uid}/` href)
- Confidence: **GOOD**

---

## H. Trainer Coverage

- trainer_per_run: **0%** — NOT in form table
- Trainer available in horse_profiles.json as current trainer only (not per-run history)
- This is a **MISSING** field for per-run analysis

---

## I. Result Position Coverage

~94% of runs have a non-null position. Zero-run horses (14) account for most nulls.

---

## J. Field Size Coverage

~94% of runs have non-null field_size (extracted from same cell as position: "N / M" pattern).

---

## K. SP Coverage

~96% of runs have sp_dec not null. SP extracted from cell[6] only (PR #3 fix confirmed working). Near-complete.

---

## L. Distance / Going Coverage

- distance: ~99% — simple text cell, near-complete
- going: ~99% — simple text cell, near-complete

---

## M. Missing Fields (>20% null in runs)

| Field | Null % | Reason |
|-------|--------|--------|
| trainer_name | 100% | Not in per-run form table row |
| gear | ~75% | Only populated when gear worn |
| winner_name | ~30% | Only for non-winner rows |
| beaten_margin | ~6% | Parse edge cases (uncontested) |

---

## N. Parse Failures

- **Zero horse failures** for May 26 (70 horses) and May 27 (91 horses)
- 14 horses have 0 runs — these are legitimately unraced/debut horses, not parser failures

---

## O. Sample Horse: Bow Echo

**Status: CAPTURED BUT FORM HISTORY NOT YET BUILT**

Bow Echo (uid=7947753) was captured on 2026-05-24 as a targeted single-horse capture. The parser has NOT been run for the May 24 date.

**Profile data available:**
- Trainer: George Boughey, Newmarket
- Age: 3-y-o colt (b. 2023-03-01)
- Country: IRE, Colour: bay
- Sire: Night Of Thunder | Dam: Aristocratic Lady (by Invincible Spirit)
- Official Rating: 115
- Newspaper tips: 24 (across multiple papers)
- Entry: St James's Palace Stakes (Group 1), Ascot, 16 Jun 2026
- Last race: Betfred 2000 Guineas (Group 1), Newmarket, 2 May 2026 — **WON** (RP postmark 127)
- Notable quotes: "He's an absolute superstar" — Billy Loughnane. "Undoubtedly the best colt we've trained" — George Boughey.

**Action required**: Run `PYTHONPATH=. python scripts/ops/parse_rp_form_history.py --date 2026-05-24` to build form history for Bow Echo and May 25 profiles.

---

## Parser Health

| Check | Status |
|-------|--------|
| Date format DDMonYY (e.g. 23Apr26) | CONFIRMED WORKING |
| Jockey uid from href | CONFIRMED WORKING |
| SP from cell[6] only (not position cell) | CONFIRMED WORKING (PR #3 fix) |
| No live scoring imports | CONFIRMED CLEAN |
| trust_policy enforced on all rows | YES |
| velo_scoring_allowed = False | YES |

No live VELO, Shadow VELO, scoring, or model tables touched.
