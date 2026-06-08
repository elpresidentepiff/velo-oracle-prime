# International Worker Replacement Plan V1

**Date:** 2026-05-23  
**Status:** DESIGN — Racing API unavailable, archived workers are BLOCKED  
**Classification:** Engineering decision document

---

## Problem Statement

Both archived ingest workers (`fr_daily_ingest.py`, `hk_daily_ingest.py`) depend on The Racing API as their sole data source. Racing API access has been removed. The workers cannot be activated in their current form.

Options for replacing the data source are evaluated below.

---

## Option 1 — Revive Archived Workers With Racing API (When Access Restored)

**Description:** If Racing API access is restored, patch both archived workers and move them to `workers/`. Minor bugs to fix (FR worker: `resp.status` bug).

| Property | Assessment |
|---|---|
| Legality | CLEAR — Racing API is a licensed commercial product |
| Engineering effort | LOW — 1-2 days of bug fixes and testing |
| Data quality | HIGH — full racecards, RPR, form, horse history, trainer/jockey IDs |
| Governance risk | LOW — existing architecture, known schema |
| Dependency risk | HIGH — single external dependency. Removal happened once, could happen again. |
| Recommendation | BUILD AS FALLBACK — do not rely on as sole source |

**Status: BLOCKED until Racing API access is restored**

---

## Option 2 — New HK Worker: HKJC Official Site (Free)

**Description:** Build a new `workers/hk_hkjc_collector.py` that scrapes HKJC's official website for race cards, results, and sectionals. All data is public and free.

| Property | Assessment |
|---|---|
| Legality | CLEAR — HKJC publishes race data publicly for betting reference. Scraping public pages is standard practice. No ToS violation for personal use. |
| Engineering effort | MEDIUM — 3-5 days. HKJC HTML structure is complex but well-documented by HK community. |
| Data quality | GOOD — results, draw, class, going, form. Missing: RPR (not on HKJC site). |
| Governance risk | LOW — isolated to hk_research schema only |
| RPR gap | CRITICAL — HKJC does not publish RPR. Need to source RPR separately (Racing Post or paid service) |
| Sectional times | HIGH VALUE — HKJC sectionals URL is confirmed free and structured |
| Draw stats | HIGH VALUE — HKJC draw statistics page is free and well-structured |

**Data fields available from HKJC:**
- Race card: date, course, race number, distance, class, going, field size, draw, weight, form string, trainer name, jockey name
- Results: finish position, beaten distance, race time, dividends
- Sectionals: 400m splits, pace ranks
- Draw stats: win/place % by draw position per course and distance
- Horse profiles: basic career summary, barrier trial results
- NOT available: RPR, TS, OR (horse's official rating is on HKJC but different scale and format)

**Recommendation: BUILD HK HKJC WORKER FIRST — highest value for lowest legal risk.**

```
hk_hkjc_collector.py priority:
  Phase A: Race cards + results (draw, class, going, form)
  Phase B: Sectional times (400m splits)
  Phase C: Draw bias stats (historical)
  Phase D: Horse history (career summary)
```

---

## Option 3 — New FR Worker: PMU API (Free, Unofficial)

**Description:** Build a new `workers/fr_pmu_collector.py` using the community-documented PMU turfinfo API.

| Property | Assessment |
|---|---|
| Legality | GREY AREA — API is unofficial (not documented by PMU). Community-discovered. Used widely by French racing data enthusiasts. No explicit prohibition. Treat as public data access, not scraping. Rate limit to 1 req/5s. |
| Engineering effort | MEDIUM — 3-5 days. API returns JSON, well-structured. |
| Data quality | GOOD — race programme, runners, going (including penetrometer), odds (PMU morning pool). Missing: RPR (not on PMU). |
| Governance risk | LOW — isolated to fr_research schema only |
| RPR gap | CRITICAL — PMU does not publish RPR. Need Racing Post or commercial source. |
| Going penetrometer | HIGH VALUE — PMU terrain.libelle field includes penetrometer numeric value. This is the key FR-specific feature not available elsewhere for free. |
| Quinté+ flag | HIGH VALUE — PMU explicitly marks Quinté+ races in programme endpoint |

**PMU API endpoints (confirmed community-documented):**
- Programme: `https://online.turfinfo.api.pmu.fr/rest/client/61/programme/{DDMMYYYY}`
- Runners (partants): `https://online.turfinfo.api.pmu.fr/rest/client/61/programme/{DDMMYYYY}/partants/{raceNum}`
- Results: Various `/rapports` endpoints

**Data fields available from PMU:**
- Race card: date, meeting, race number, distance, going (text + penetrometer), prize, race type, field size
- Runners: horse name, jockey, trainer, weight, draw, form, age, sex
- Results: finish positions, PMU dividends (win/place/show)
- NOT available: RPR, TS, OR

**Recommendation: BUILD PMU FR WORKER SECOND — legality grey area requires care, but penetrometer going is uniquely available here.**

---

## Option 4 — France Galop Supplement (Free Scrape)

**Description:** Supplement PMU data with France Galop website for Valeur ratings and Group/Listed classification.

| Property | Assessment |
|---|---|
| Legality | CLEAR — public website, no API terms |
| Engineering effort | LOW-MEDIUM — HTML scraping, fragile, update-prone |
| Data quality | PARTIAL — Valeur rating, Group/Listed classification |
| Governance risk | LOW |
| Recommendation | PHASE 2 SUPPLEMENT — add after PMU worker is stable |

---

## Option 5 — Manual Parquet-Only Offline Training (Current Default)

**Description:** Use existing parquet (255,862 rows) for offline model development only. No live ingestion. No Supabase. No workers.

| Property | Assessment |
|---|---|
| Legality | CLEAR — data already owned |
| Engineering effort | ZERO — data already exists |
| Data quality | HIGH — 2015-2025 historical substrate |
| Governance risk | ZERO — no live pipeline changes |
| Limitation | No live scoring possible. Historical only. |
| Recommendation | CURRENT PHASE — Phase 1A offline baseline arena |

---

## Option 6 — Renavon (HK Commercial, $99+/month)

**Description:** Commercial HK-specific database with odds time-series going back to 1970s.

| Property | Assessment |
|---|---|
| Legality | CLEAR — licensed commercial product |
| Engineering effort | LOW — API access |
| Data quality | VERY HIGH — odds time-series uniquely available |
| Governance risk | LOW — paid service with clear ToS |
| Cost | $99+/month |
| Key value | HKJC tote odds time-series — essential for Benter model market calibration |
| Recommendation | PHASE 3 — when Benter overlay requires live market priors |

---

## Decision Matrix

| Source | Legality | Effort | RPR? | Penetrometer? | Phase | Priority |
|---|---|---|---|---|---|---|
| Racing API (when restored) | CLEAR | LOW | YES | NO | Fallback | P4 |
| HKJC Official (HK) | CLEAR | MEDIUM | NO | N/A | 1C | **P1** |
| PMU API (FR) | GREY | MEDIUM | NO | YES | 1C | **P2** |
| France Galop (FR) | CLEAR | LOW-MED | NO | NO | 2 | P3 |
| Parquet offline (current) | CLEAR | ZERO | YES | NO | 1A | **P0 done** |
| Renavon (HK) | CLEAR | LOW | NO | N/A | 3 | P4 |

---

## RPR Gap — Critical Issue

**Neither HKJC nor PMU publishes RPR.** RPR is the primary cross-jurisdiction signal (corr=0.326-0.394). Without RPR in the live ingestion pipeline, the live-scoring model will be significantly weaker than the offline models trained on historical parquet.

**Solutions for RPR:**
1. **Racing Post API** — if RP subscription can be obtained separately from Racing API. Check availability.
2. **Racing Post PDF parsing** — existing ingestion_spine can parse FR PDFs for RP ratings. Check if RP PDFs cover FR/HK races. (UK PDFs F_0010 confirmed. FR/HK PDFs not confirmed.)
3. **Racing API restored** — provides RPR as primary field.
4. **Proxy approach** — train without RPR, use OR (HK) and local going/class features as substitutes.

**Verdict:** RPR gap is the single largest blocker to live scoring quality. Investigate Racing Post PDF coverage for FR/HK races before building workers.

---

## Recommended Sequence

```
Phase 1A (NOW):    Offline baseline arena using existing parquet
Phase 1B:          Apply schema migration after operator approval
Phase 1C-HK:       Build hk_hkjc_collector.py — HKJC official scraper
Phase 1C-FR:       Build fr_pmu_collector.py — PMU API collector
Phase 1D:          Investigate RPR source for live pipeline (RP PDF or restored API)
Phase 2:           Train jurisdiction models on parquet substrate
Phase 2-live:      Start live cold archive collection using new workers
Phase 3:           Renavon integration for Benter HK model
Phase 4:           Shadow scoring with verdict output
Phase 5:           Evidence accumulation to Gate 1 (n=150)
Phase 6:           Gate 1 review — operator decision

WORKERS_STATUS:     ARCHIVE_ONLY_NOT_ACTIVATED
NEW_WORKERS:        NOT_BUILT_YET
RACING_API:         UNAVAILABLE
RPR_GAP:            UNRESOLVED
```

---

## Governance

```
No worker activation until Phase 1B (migration applied)
No new worker deployment until Phase 1C review
Archived workers stay in archive/dead_workers/
No UK pipeline modification
No Telegram changes
No live scoring until Phase 4
```
