# VÉLØ HK LANE — Contamination Safeguards & UK Protection
**Date:** 2026-03-23
**Purpose:** Hard rules to prevent HK/FR research data from touching UK production

---

## The One Rule That Cannot Be Broken

**hk_research.* is a completely separate island.**
No row from `hk_research` may enter any `public.` table.
No row from `hk_research` may enter any `velo_*` table.
No HK result, runner, or stat may influence UK doctrine, sigma, or phase gate.

---

## Concrete Safeguards

### 1. Database Level — Hard Schema Separation

```
Production:  public.velo_*  public.races  public.runners  public.sigma_audits
Research:    hk_research.hk_*  hk_research.hk_*

Rule: hk_research never touches public. Nothing from public enters hk_research.
```

### 2. Ingestion Script Rules

```python
# ✅ CORRECT — writes ONLY to hk_research
db.table("hk_research.hk_races").upsert(...)

# ❌ WRONG — will fail or be blocked, but never wire this
db.table("velo_verdicts").upsert(...)
db.table("races").upsert(...)          # public.races, not hk_races
db.table("sigma_audits").upsert(...)
```

### 3. Supabase RLS — hk_research

- `service_role`: full read/write
- `anon`: SELECT only (no writes from client apps)
- No RLS policy ever grants hk_research write to public tables

### 4. UK Production Filter — The One Line That Protects Everything

```python
# In velo_prime_service.py and run_prime_today.py:
UK_ALLOWED = {"GB", "IRE"}

def is_uk_race(race: dict) -> bool:
    return race.get("region", "") in UK_ALLOWED
```

This filter lives **only** in the UK production scoring path. It has no knowledge of `hk_research` and cannot affect it.

### 5. Sigma Closure — UK Only

```python
# In close_sigma_loops.py:
# Only UK/IRE races get sigma reviews written
if race.get("region") not in UK_ALLOWED:
    continue  # skip HK, FR, etc.
```

### 6. Phase Gate — UK Only

The 5 clean runs for Phase 1→2A activation count **only** UK races. HK races are excluded from:
- Clean run counting
- T1.1–T1.5 gate verification
- Doctrine mutation triggers

### 7. VOX Reporting Desk — UK Only

All daily reports (`reports/daily/operator_brief_*`, `sigma_forensic_*`, etc.) cover **UK/IRE races only**. HK is tracked separately in `hk_research` and reported only when explicitly requested.

### 8. Code Review Rule

Before merging any PR to `main`:
```
Ask: Does this change touch velo_verdicts, sigma_audits, velo_post_race_reviews, learned_patterns?
If YES: Does it have an explicit UK_ALLOWED or region filter?
If NO: BLOCK. Cannot merge without region filter.
```

### 9. GitHub PAT — VOX Access

VOX has write access to `hk_research` migration files and `workers/hk_daily_ingest.py` — **these are the ONLY files VOX may write to HK data**.

VOX may NOT write to:
- `velo_verdicts`
- `sigma_audits`
- `velo_post_race_reviews`
- `learned_patterns`
- `public.races`, `public.runners`

---

## What HK Can Contaminate (Safe Zones)

These are safe — HK data in them does not affect UK production:

| Table | Safe? | Reason |
|---|---|---|
| `hk_research.hk_*` | ✅ | Research lane only |
| `public.courses` | ⚠️ | Read-only enrichment, no scoring authority |
| `public.horse_racecard_history` | ⚠️ | Historical only, not in live scoring |
| `public.trainer_course_analysis` | ⚠️ | Read-only enrichment |

---

## What HK Must Never Touch (Forbidden Zones)

| Table | Forbidden Because |
|---|---|
| `velo_verdicts` | Production verdict authority |
| `sigma_audits` | UK doctrine feedback loop |
| `velo_post_race_reviews` | Miss taxonomy + learning spine |
| `learned_patterns` | Sigma-loop pattern accumulation |
| `public.races` (UK section) | UK production race list |
| `public.runners` (UK section) | UK production runner list |

---

## Fast Contamination Check Query

Run this before any major deployment:

```sql
-- Contamination check: any non-UK race_ids in velo_verdicts?
SELECT race_id, generated_at
FROM velo_verdicts
WHERE race_id NOT IN (
    SELECT race_id FROM races WHERE region IN ('GB', 'IRE')
)
LIMIT 10;
-- Should return ZERO rows. If non-zero → contamination event.
```
