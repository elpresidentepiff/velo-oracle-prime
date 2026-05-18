# RP PRIMARY RACE-DAY POLICY V1

**Effective:** 2026-05-18  
**Commit:** 1dc8d5b  
**Status:** LOCKED — operator change required to override

---

## Core Rule

> Racing Post runner profile is the primary race-day information source.  
> Racing API is optional enrichment only.  
> A 401 from Racing API must not block a VÉLØ race-day run when the RP runner profile exists for the requested date.

**Before this policy:**
```
Racing API 401 = VÉLØ day broken
```

**After this policy:**
```
RP profile available = VÉLØ can complete the day
Racing API = enrichment only
```

---

## Racecard Priority Chain (locked)

```
Priority 1: cached racecard JSON
            data/racecards_{date_tag}_standard.json
            Source label: CACHE

Priority 2: RP runner profile fallback
            data/features/rp_runner_profile_latest.parquet
            Source label: RP_PROFILE_FALLBACK
            Condition: cache absent AND RP profile has rows for date

Priority 3: live Racing API
            https://api.theracingapi.com/v1/racecards/standard
            Source label: LIVE_API
            Condition: priorities 1 and 2 both unavailable
```

The Racing API is **never contacted** if either a cached racecard or an RP profile exists for the requested date.

---

## Terminal States (exactly 4, no others permitted)

| State | Meaning |
|---|---|
| `FULL_ENGINE_RUN` | VP scored via live API or cache. Full Model C active. |
| `FULL_ENGINE_RUN_RP_SOURCED` | VP scored via RP profile fallback. Full Model C active. Racing API was 401 or absent — WARN_ONLY. |
| `PARTIAL_SHADOW_CONTEXT` | VP scoring failed. No cache, no RP profile, API blocked. RP/TJ/last-6 shadow context only. Not full Model C. |
| `FAILED_RUN_REQUIRES_OPERATOR` | Hard failure at a non-VP step. Operator intervention required. |

No other terminal states exist. A run that ends without one of these four is an orchestrator defect.

---

## Racing API Auth Gate

When the RP profile covers the requested date:

- `AUTH_OK` → proceed normally (API may be used for enrichment if available)
- `AUTH_FAIL_401` → `AUTH_FAIL_401_WARN_ONLY` — logged in manifest, run continues
- `AUTH_FAIL_OTHER` → logged in manifest, run continues on RP profile

When no cache and no RP profile:

- `AUTH_OK` → proceed with live API fetch
- Any auth failure → `FAILED_RUN_REQUIRES_OPERATOR`

---

## Manifest Requirements

Every race day must produce exactly one manifest at:
```
data/runs/velo_race_day_manifest_YYYY-MM-DD.json
```

Required fields:

| Field | Type | Description |
|---|---|---|
| `date` | string | YYYY-MM-DD |
| `final_status` | string | One of the 4 terminal states |
| `racecard_source` | string | `cache` / `rp_profile` / `api` |
| `rp_primary` | bool | True when RP profile was the source |
| `racing_api_required` | bool | False when RP profile covers the date |
| `racing_api_auth` | string | Auth check result |
| `vp_available` | bool | Whether VP scoring produced scores |
| `vp_source` | string | `RP_PROFILE_FALLBACK` / `CACHE` / `LIVE_API` / `NONE` |
| `vp_coverage` | float | Count of scored races (null if VP unavailable) |
| `full_model_c` | bool | Whether Model C shadow ran with VP scores |
| `telegram_sent` | bool | Whether Telegram was sent |
| `telegram_message_id` | int/null | Message ID if sent |
| `governance` | string | Governance locks in force |

---

## Telegram and Dashboard Labels

When `rp_primary = true`:
- Dashboard `status` field must show `FULL_ENGINE_RUN_RP_SOURCED` (not `FULL_ENGINE_RUN`)
- Dashboard must include `rp_primary: true`, `racing_api_required: false`, `vp_source: RP_PROFILE_FALLBACK`
- Telegram must label source as `RP PRIMARY` and auth as `AUTH_FAIL_401_WARN_ONLY`

Operator must never receive a Telegram or dashboard update that hides the racecard source.

---

## Synthetic Horse ID Rule

When using RP profile fallback, `horse_id` from the Racing API is absent (None).

A synthetic ID is generated as:
```
RP_{horse_norm_lowercase}
```
where `horse_norm` is the normalised horse name from the RP profile.

Properties:
- **Deterministic:** same horse on different dates always produces the same ID prefix
- **Auditable:** `RP_` prefix marks it as synthetic, distinguishable from real Racing API IDs
- **Temporary:** an alias table will map `RP_{horse_norm}` → real `horse_id` as enrichment

A future alias table must resolve:
```
Racing API horse_id  →  RP profile horse_norm  →  RP_{horse_norm} synthetic ID
```
This is required for long-term model integrity across data sources.

---

## Daily Execution

Standard race-day command (no manual chains):
```bash
PYTHONPATH=. python scripts/velo_race_day_orchestrator.py --date YYYY-MM-DD
```

Validation after each run:
```bash
PYTHONPATH=. python scripts/validate_race_day_manifest.py --date YYYY-MM-DD
```

Credential smoke test (run if API auth suspected):
```bash
PYTHONPATH=. python scripts/check_racing_api_auth.py
```

---

## Governance Locks (permanent)

```
NO_SCORING_CHANGE
NO_ROUTER_CHANGE
NO_STAKING_CHANGE
NO_TELEGRAM_CHANGE
NO_LIVE_STATE_MUTATION
RP_PRIMARY_API_OPTIONAL
NO_MISSING_DAYS
```

No race day may end without a manifest.  
No race day may end without a recorded terminal state.  
No terminal state may be invented outside the approved four.
