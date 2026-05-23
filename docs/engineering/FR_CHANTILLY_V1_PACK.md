# FR Flat Racing — Jurisdiction Pack V1
## Venues: Chantilly, Deauville, Longchamp, Saint-Cloud

**Date:** 2026-05-23  
**Status:** DESIGN — no training, no scoring, no live deployment  
**Classification:** SHADOW/RESEARCH ONLY

---

## Pack Scope

This pack covers all four French flat racing venues in the training substrate.

| Venue | Rows | Races | Date Range | Fav SR |
|---|---|---|---|---|
| Chantilly (FR) | 47,568 | 4,043 | 2015-01-23 → 2025-06-28 | 28.8% |
| Deauville (FR) | 46,926 | 3,907 | 2015-01-03 → 2025-07-05 | 27.8% |
| Longchamp (FR) | 20,127 | 1,868 | 2015-04-06 → 2025-07-03 | 29.1% |
| Saint-Cloud (FR) | 27,731 | 2,499 | 2015-03-07 → 2025-07-04 | 27.8% |
| **FR Flat Total** | **142,352** | **12,317** | **2015-01-03 → 2025-07-05** | **~28.4%** |

**Auteuil is NOT in this pack.** Auteuil is 97% jumps (Hurdle/Chase). It requires a separate FR_JUMPS pack.

---

## Source Priority (Racing API Unavailable)

| Priority | Source | URL | Auth | Status | Data |
|---|---|---|---|---|---|
| P1 | PMU API (unofficial) | `online.turfinfo.api.pmu.fr/rest/client/61/programme/{DDMMYYYY}` | None | FREE | Race programme, runners, morning odds, penetrometer going |
| P2 | France Galop | `france-galop.com/fr/programme-et-resultats` | None (scrape) | FREE | Valeur ratings, Group/Listed classification, patterns |
| P3 | Racing and Sports AU | `racingandports.com.au` | Subscription ~$40/mo | OPTIONAL | Form figures, trainer/jockey stats |
| BLOCKED | Racing API | `api.theracingapi.com` | Was Basic Auth | UNAVAILABLE | Full racecards, RPR, form |

**Primary data collection path:** PMU API → France Galop supplement → Verify with Racing and Sports if needed

---

## Canonical Course Codes

| Venue | VÉLØ Code | PMU Code | France Galop Code | Timezone |
|---|---|---|---|---|
| Chantilly | `CHN` | `CHANTILLY` | `chantilly` | Europe/Paris (UTC+1/+2) |
| Deauville | `DEV` | `DEAUVILLE` | `deauville` | Europe/Paris |
| Longchamp | `LGC` | `LONGCHAMP` | `paris-longchamp` | Europe/Paris |
| Saint-Cloud | `SCL` | `SAINT-CLOUD` | `saint-cloud` | Europe/Paris |

---

## Identity Rules

- **Horse identity:** Use RPR horsename + DOB where available. French horse names often include accents — normalise to ASCII for matching (é→e, è→e, ê→e, etc.).
- **Trainer identity:** French trainer names are stable. Match on normalised name.
- **Race identity:** PMU API provides a `numCourse` per meeting. Generate `race_id` as `{date}_{venue_code}_{numCourse}`.
- **Duplicate detection:** Upsert on `(race_id, horse_name_normalised)`.

---

## Class / Rating Mapping

French racing does NOT use UK Official Rating (OR). OR coverage in parquet: 0.0%.

| UK Concept | FR Equivalent | Notes |
|---|---|---|
| OR (Official Rating) | Valeur rating (20-62 scale) | Not directly equivalent. Valeur 62 = elite. Only available from France Galop. |
| RPR (Racing Post Rating) | RPR — same scale | **Primary FR rating signal. RPR correlation = 0.31-0.33 with win.** |
| TS (Timeform Speed) | TS — partially available | 51-88% coverage at flat venues. Use where available. |
| Race Class 1-7 | Group 1/2/3, Listed, Conditions, Handicap, Claiming | Map to tier: G1=1, G2=2, G3=3, Listed=4, Conditions=5, Handicap=6, Claiming=7 |
| Handicap mark | Not equivalent | French handicap marks are separate from UK marks. Do not transfer. |

**FR Rating Priority:** RPR → TS → Valeur (if available). OR must NOT be used as FR feature.

---

## Going Calibration (Critical)

French going text labels are NOT equivalent to UK labels. A horse that prefers UK "Good to Firm" may run on French "Bon" — which is systematically firmer.

**Penetrometer → UK Going Mapping:**
```
Penetrometer < 2.5          → Firm (UK)
Penetrometer 2.5 – 3.4     → Good to Firm (UK)
Penetrometer 3.5 – 4.4     → Good (UK)
Penetrometer 4.5 – 5.5     → Good to Soft (UK)
Penetrometer 5.6 – 6.5     → Soft (UK)
Penetrometer > 6.5          → Heavy (UK)
```

**Source:** PMU API `terrain.libelle` field includes penetrometer value (e.g. "Souple (3.5)").

**Current parquet:** going_code field is present but based on text label only — penetrometer value not stored. Add `going_penetrometer FLOAT` to `fr_research.fr_races` (already in migration).

---

## Result Reconciliation Rule

French race results use decimal SP (PMU dividend / 100). No exchange price available. SP reconciliation:
- PMU win dividend ÷ 10 = approximate decimal SP (e.g. PMU dividend 25.50 → SP 2.55)
- Use as-is for Brier score calibration
- No Betfair equivalent — tote-only market

---

## Feature Availability

| Feature | Available | Source | Notes |
|---|---|---|---|
| RPR | YES (92-95%) | PMU API / RP | Primary rating |
| TS | YES (51-88%) | RP | Variable coverage |
| OR | NO (0%) | — | Do not use |
| Valeur | PARTIAL | France Galop scrape | Phase 3 addition |
| Going (text) | YES | PMU API | Map to penetrometer |
| Going (penetrometer) | YES | PMU API terrain field | Highest-value going signal |
| Quinté+ flag | YES | PMU API | Binary flag — highest-quality race |
| Draw | YES (parquet) | racecards | Draw matters less in FR than UK/HK |
| Distance (furlongs) | YES (convert) | metres / 201.168 | Parquet uses dist_f |
| Class tier | YES | France Galop | 1-7 tier mapping |
| PMU morning odds | PARTIAL | PMU API odds endpoint | Pre-race pool snapshot |
| Trainer strike rate | NO (FR-specific) | Needs FR-specific computation | Cannot use UK trainer profiles |
| Jockey strike rate | NO (FR-specific) | Needs FR-specific computation | Cannot use UK jockey profiles |

---

## Flatline Gate

The FR scoring pipeline must monitor for improvement_score flatline (same symptom as UK). Define:
- `fr_improvement_score_flatline_alert`: if stddev of `velo_prime_prob` across all runners in a day < 0.005
- Response: WARN, do not score, flag for investigation

---

## Learning Gate

FR shadow brain operates independently of UK Playbook G. No cross-jurisdiction pattern transfer.

FR-specific patterns to track:
- `FR_QUINTET_PLUS_SIGNAL` — Quinté+ race, top-rated RPR runner
- `FR_GOING_VULNERABILITY` — penetrometer going mismatch vs horse preference
- `FR_SHORT_SEASON` — Longchamp/Chantilly flat season April-October only

---

## Shadow Brain Target

No scoring or pattern learning until Phase 2 model training is complete. When shadow scoring begins:
- Output: `fr_research.fr_verdicts` only
- No Telegram output
- No UK verdict table writes
- Model tag: `FR_V1_SHADOW`

---

## Promotion Gates

| Gate | Threshold | Action |
|---|---|---|
| Gate 1 | 150 top-pick decisions with outcomes | First review: SR, Brier, RPR calibration |
| Gate 2 | 300 top-pick decisions with outcomes | Full evidence review |
| Live promotion | OPERATOR DECISION ONLY | Never automatic |

---

## Legal / Source Restrictions

- PMU API is unofficial — community-documented, no SLA, use respectfully
- France Galop scraping: public data, no auth wall. Rate limit to 1 req/5s.
- No PMU betting account required for data access
- No Betfair France access — PMU tote is the only betting market

---

## First Shadow Backtest Plan

When model training is approved (Phase 2):
1. Train `sqpe_v1_fr.pkl` on 2015-2022 data (n≈116K rows)
2. Validate on 2023-2024 data (n≈26K rows)
3. Report: VP band monotonicity, Brier score, top-decile SR
4. Holdout: 2025 data (n≈8K rows) — untouched until evidence gate
5. Compare favourite SR calibration: model fav vs actual fav SR (28.4% baseline)

---

## No Live Deployment Rule

```
FR_V1_SHADOW outputs go to fr_research.fr_verdicts ONLY
No Telegram messages for FR racing
No betting, no staking, no Betfair
No UK pipeline integration
No mixing with velo_verdicts table
Operator decision required at every gate
```
