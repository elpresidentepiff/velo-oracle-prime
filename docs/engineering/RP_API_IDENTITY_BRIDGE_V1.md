# RP / RACING API IDENTITY BRIDGE V1

**Effective:** 2026-05-18 (drafted post-incident)  
**Status:** PENDING OPERATOR APPROVAL — not yet enforced in code  
**Trigger:** May 18 SYNTHETIC_ID_NORMALISATION_DRIFT incident

---

## Core Rule

> Racing API `race_id` and `horse_id` are the canonical identity keys for VÉLØ.  
> Racing Post features must attach to those canonical keys.  
> Synthetic RP IDs are temporary ingestion handles only — never final Sigma keys.

---

## Identity Hierarchy

```
Level 1 (canonical): Racing API race_id / horse_id
                      race_id: rac_11944101
                      horse_id: hrs_64780492
                      Source: /v1/racecards/free or /v1/racecards/standard

Level 2 (derived): Synthetic RP ID
                   Format: RP_{canonical_norm(horse_name)}
                   Scope: TEMPORARY — valid only within a single day's pipeline
                   Promotion: must resolve to Level 1 via alias table

Level 3 (forbidden as sigma key): Raw horse_norm column values
                                   Format: horse_norm with spaces
                                   e.g. 'imperial guard' → NEVER use as ID suffix
```

---

## Canonical Synthetic ID Format

When Racing API horse_id is unavailable, a synthetic ID is generated as:

```python
import re

def canonical_synthetic_id(horse_name: str) -> str:
    """
    Canonical synthetic horse ID from horse name.
    Strips ALL non-alphanumeric characters including spaces and apostrophes.
    Result is always lowercase alphanumeric only.
    """
    norm = re.sub(r"[^a-z0-9]", "", horse_name.lower())
    return f"RP_{norm}"

# Examples:
# 'Imperial Guard'   → 'RP_imperialguard'
# "Cooley's Mist"    → 'RP_cooleysmist'
# 'Billy No Mates'   → 'RP_billynnomates'
# 'Adalida'          → 'RP_adalida'
# "Don't Wait"       → 'RP_dontwait'
```

**This function must be used identically in ALL components that generate or consume synthetic IDs:**

| Component | File | Status |
|---|---|---|
| Scoring/racecard loader | `scripts/run_prime_today.py` `_load_rp_profile_as_racecards()` | NEEDS PATCH |
| Result scraper | `scripts/scrape_results_atr.py` `load_racecard_from_rp_profile()` | CORRECT |
| Synthetic ID audit | `scripts/audit_rp_synthetic_horse_ids.py` `_norm()` | CORRECT |
| Sigma result matcher | `scripts/run_results_sigma.py` | CORRECT (strict match works when IDs consistent) |

---

## Identity Resolution Chain

When attaching Racing Post features to canonical IDs:

```
Step 1: Racing API canonical ID available?
    YES → use it directly (hrs_XXXXXXXX / rac_XXXXXXXX)
    NO  → proceed to Step 2

Step 2: Generate synthetic ID
    synthetic_id = canonical_synthetic_id(horse_name)
    Mark as temporary: requires alias table resolution

Step 3: Alias table lookup (build_rp_horse_alias_table.py — pending)
    RP_{norm} → Racing API horse_id
    Enables long-term cross-source join

Step 4: Sigma fallback (if IDs still inconsistent)
    Normalised name match: re.sub(r"[^a-z0-9]", "", horse_name.lower())
    course match
    off_time window (±5 min)
    Must be logged as NAME_MATCH_FALLBACK, not marked as NR-ABSENT
```

---

## Race ID Format

When Racing API race_id is unavailable:

```python
def canonical_race_id(date: str, course_code: str, off_time: str) -> str:
    """
    e.g. '2026-05-18', 'Carlisle', '2:30' → '2026-05-18_Carlisle_230'
    Time must be HHMM or HMM without colon.
    """
    t = off_time.replace(":", "")  # '2:30' → '230'
    return f"{date}_{course_code}_{t}"
```

The course segment uses the RP profile course value as-is (may be abbreviated: CRL, ROS, etc.). This is acceptable since race_id is only used within the RP-sourced pipeline, never compared to Racing API race_ids.

---

## Sigma Matching Rules

### Primary match (canonical IDs available)
```python
if runner.get("horse_id") == predicted_horse_id:
    found_in_result = True
```
Strict equality. Correct and sufficient when IDs are canonical and consistent.

### Fallback match (when primary fails — RP synthetic IDs)
When primary match fails and `predicted_horse_id.startswith("RP_")`:

```python
# Attempt 1: normalise both sides
norm_pred = re.sub(r"[^a-z0-9]", "", predicted_horse_id.lower())
for runner in full_runners:
    norm_result = re.sub(r"[^a-z0-9]", "", (runner.get("horse_id") or "").lower())
    if norm_pred == norm_result:
        found_in_result = True
        status = "MATCH_VIA_NORMALISED_ID"
        break

# Attempt 2: horse name normalisation
if not found_in_result:
    horse_name_norm = norm_pred[2:]  # strip 'rp' prefix
    for runner in full_runners:
        runner_norm = re.sub(r"[^a-z0-9]", "", (runner.get("horse") or "").lower())
        if horse_name_norm == runner_norm:
            found_in_result = True
            status = "MATCH_VIA_NAME_NORM"
            break
```

### Exclusion taxonomy (NR-ABSENT must never be used for identity failures)

| Old label | New label | Condition |
|---|---|---|
| `[NR-ABSENT]` | `[TRUE_NON_RUNNER]` | Horse in result with DNF position |
| `[NR-ABSENT]` | `[RESULT_RACE_MISSING]` | race_id not in result file |
| `[NR-ABSENT]` | `[SYNTHETIC_ID_DRIFT]` | ID mismatch resolved by normalisation |
| `[NR-ABSENT]` | `[RESULT_JOIN_FAILED]` | No match by any method |

Only `TRUE_NON_RUNNER` and `RESULT_RACE_MISSING` are legitimately excluded from sigma stats.  
`SYNTHETIC_ID_DRIFT` and `RESULT_JOIN_FAILED` must be counted as sigma coverage failures and flagged for operator review.

---

## Alias Table (Future — Pending Racing API auth)

When Racing API auth is restored, build `scripts/build_rp_horse_alias_table.py`:

```
table: rp_horse_alias
  rp_norm         TEXT    -- canonical_synthetic_id(horse_name)[3:]  e.g. 'imperialguard'
  racing_api_id   TEXT    -- hrs_XXXXXXXX
  horse_name      TEXT    -- original horse name
  first_seen      DATE
  last_seen       DATE
```

This resolves `RP_imperialguard` → `hrs_64780492` permanently, enabling:
- Cross-source result matching
- Historical model training continuity
- Long-term horse form spine

---

## What Racing API Gives (and must remain canonical)

| Field | Value | Why canonical |
|---|---|---|
| `race_id` | `rac_11944101` | Unique, stable, cross-referenced by all result sources |
| `horse_id` | `hrs_64780492` | Unique, stable, used in form history and results |
| `course` | `Carlisle` | Full name, no abbreviation |
| `off_time` | `2:30` | Consistent format |
| `trainer_id` | `trn_205551` | Links to trainer profile |
| `jockey_id` | `jky_246693` | Links to jockey profile |

Racing API free plan provides these fields via `/v1/racecards/free` (confirmed working 2026-05-18).

---

## What Racing Post Gives (intelligence layer)

| Field | Source | Role |
|---|---|---|
| `current_or` | RP form | Scoring feature |
| `current_ts` | RP form | Scoring feature |
| `current_rpr` | RP form | Scoring feature |
| `trainer` | RP form | TJ combo lookup |
| `jockey` | RP form | TJ combo lookup |
| OR/TS/RPR slope trends | RP history | Scoring features |
| Spotlight comment | RP PDF | NLP flags |
| Postdata | RP PDF | Intelligence layer |

RP features must attach to **canonical Racing API horse_id** as the primary key.  
When canonical ID is unavailable, attach to synthetic `RP_{canonical_norm}` as temporary key.

---

## Governance Locks

```
CANONICAL_ID_IS_RACING_API          — permanent
RP_SYNTHETIC_ID_FORMAT_LOCKED       — strip all non-alphanumeric, lowercase
RP_SYNTHETIC_ID_IS_TEMPORARY        — must resolve via alias table
SIGMA_MUST_NEVER_LABEL_ID_FAIL_AS_NR — permanent
NAME_FALLBACK_MANDATORY_FOR_RP_DAYS  — required when canonical IDs absent
```

---

## Incident Reference

This spec was written in response to the May 18 `SYNTHETIC_ID_NORMALISATION_DRIFT` incident.  
See: `docs/engineering/MAY18_FULL_PIPELINE_INCIDENT_REPORT.md`
