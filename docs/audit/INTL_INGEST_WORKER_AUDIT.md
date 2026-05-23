# International Ingest Worker Audit

**Date:** 2026-05-23  
**Files audited:**
- `archive/dead_workers/fr_daily_ingest.py`
- `archive/dead_workers/hk_daily_ingest.py`

**Final status: ARCHIVE_ONLY_NOT_ACTIVATED**

---

## Critical Blocker — Racing API Access Removed

**As of 2026-05-23, Racing API access has been revoked.**

Both workers use The Racing API (`api.theracingapi.com`) as their sole data source. Without API access, neither worker can fetch data. The workers are **BLOCKED** regardless of code quality.

This changes the international data source strategy. Alternative sources must be identified before any worker can be activated. See architecture document for revised source priority.

---

## Worker 1 — `archive/dead_workers/fr_daily_ingest.py`

| Property | Value |
|---|---|
| Path | `archive/dead_workers/fr_daily_ingest.py` |
| Syntax | PASS (after os import patch 2026-05-23) |
| Import: `os` | WAS MISSING — patched |
| Import: `requests` | Present |
| Import: `supabase` | Present |
| Env vars required | `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `RACING_API_USERNAME`, `RACING_API_PASSWORD` |
| Network requirement | Racing API at `api.theracingapi.com` — **UNAVAILABLE** |
| Schema target | `fr_research.*` ONLY |
| UK table writes | NONE — explicit region filter `region == "FR"` |
| Live state writes | NONE |
| Dry-run support | NO — runs immediately on call |
| Write-mode | Upsert only — idempotent on `race_id`, `(race_id, horse_id)` |
| Archive-only safety | YES — fr_research schema only, no production impact |
| Racing API dependency | `GET /v1/racecards?date=` and `GET /v1/results?date=` |
| Decommission reason | Racing API access removed |
| Classification | **ARCHIVE_ONLY_NOT_ACTIVATED** |
| Reactivation path | Replace API calls with alternative source (PMU API, France Galop scrape) |

**Code quality issues (non-blocking, fix before reactivation):**
1. `os` import was missing (patched 2026-05-23)
2. `fetch_fr_results`: `resp.status` should be `resp.status_code` (line 180) — will raise AttributeError at results fetch
3. No timeout on results fetch with 422 check path (minor)
4. `raw_payload` logged as full racecards JSON — may be large

---

## Worker 2 — `archive/dead_workers/hk_daily_ingest.py`

| Property | Value |
|---|---|
| Path | `archive/dead_workers/hk_daily_ingest.py` |
| Syntax | PASS (after os import patch 2026-05-23) |
| Import: `os` | WAS MISSING — patched |
| Import: `requests` | Present |
| Import: `supabase` | Present |
| Env vars required | `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `RACING_API_USERNAME`, `RACING_API_PASSWORD` |
| Network requirement | Racing API at `api.theracingapi.com` — **UNAVAILABLE** |
| Schema target | `hk_research.*` ONLY |
| UK table writes | NONE — `HK_COURSES = {"Happy Valley", "Sha Tin"}` allowlist enforced |
| Live state writes | NONE |
| Dry-run support | NO |
| Write-mode | Upsert only — idempotent |
| Archive-only safety | YES — hk_research schema only |
| Racing API dependency | `GET /v1/racecards?date=` and `/horses/{id}/results` |
| Decommission reason | Racing API access removed |
| Classification | **ARCHIVE_ONLY_NOT_ACTIVATED** |
| Reactivation path | Replace API calls with HKJC official site + alternative sources |

**Code quality issues (non-blocking, fix before reactivation):**
1. `os` import was missing (patched 2026-05-23)
2. Horse history calls `GET /horses/{horse_id}/results` — requires Racing API subscription
3. No rate limiting between horse history calls — risk of 429 errors when API available

---

## Alternative Data Sources (No Racing API)

Since Racing API is unavailable, both workers need new data sources before activation.

**France alternatives (ordered by quality):**
1. **PMU API (unofficial, free):** `online.turfinfo.api.pmu.fr/rest/client/61/programme/{DDMMYYYY}` — runners, race metadata, going, odds
2. **France Galop scrape:** `france-galop.com` — Valeur ratings, race classification
3. **Racing and Sports AU (subscription):** Full form, trainer/jockey stats

**HK alternatives (ordered by quality):**
1. **HKJC official site (free):** Race cards at `racing.hkjc.com` — draw, class, going, odds
2. **HKJC sectionals (free):** `racing.hkjc.com/en-us/local/information/displaysectionaltime` — official splits
3. **Renavon ($99/month):** Historical odds time-series, HK-specific database
4. **Apify HKJC scraper:** Maintained actor, $10-30/month

---

## Worker Status Summary

| Worker | Path | Syntax | API Dependency | UK Contamination | Final Status |
|---|---|---|---|---|---|
| fr_daily_ingest.py | archive/dead_workers/ | PASS | Racing API — UNAVAILABLE | NONE | **ARCHIVE_ONLY_NOT_ACTIVATED** |
| hk_daily_ingest.py | archive/dead_workers/ | PASS | Racing API — UNAVAILABLE | NONE | **ARCHIVE_ONLY_NOT_ACTIVATED** |

**Do NOT move workers from archive until:**
1. Alternative data source is confirmed and tested
2. New worker code is written (or existing workers updated for new source)
3. Supabase schemas created (`migrations/intl_schemas_v1.sql` applied)
4. Phase 1 approval from operator

---

## Governance

```
Workers remain in archive/dead_workers/
No deployment to Railway
No Supabase migration (schemas not created)
No live state mutation
Racing API dependency must be replaced before reactivation
```
