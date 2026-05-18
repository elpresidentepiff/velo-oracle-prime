# MAY 18 SYNTHETIC ID REGRESSION PROOF

**Commit:** `1dc8d5b`  
**File:** `scripts/run_prime_today.py` lines 236-237  
**Function:** `_load_rp_profile_as_racecards()`

---

## Failing Code

```python
# BAD — preserves spaces from horse_norm column
horse_norm_val = str(row.get("horse_norm") or row.get("horse") or "").lower()
raw_hid = f"RP_{horse_norm_val}" if horse_norm_val else None
```

`horse_norm` column format in `rp_runner_profile_latest.parquet`:
```
'IMPERIAL GUARD'   (ALL CAPS, SPACES PRESERVED)
```

After `.lower()`:
```
'imperial guard'   (lowercase, SPACES STILL PRESERVED)
```

Synthetic ID produced:
```
'RP_imperial guard'   ← SPACE IN ID
```

---

## Fixed Code

```python
# GOOD — strips all non-alphanumeric including spaces
horse_norm_val = _norm_horse_name(row.get("horse_norm") or row.get("horse") or "")
raw_hid = f"RP_{horse_norm_val}" if horse_norm_val else None
```

`_norm_horse_name` (line 808, same file):
```python
def _norm_horse_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(name or "").lower())
```

Synthetic ID produced:
```
'RP_imperialguard'   ← NO SPACE
```

---

## Proof Table

| Horse Name | prediction_id BEFORE | result_id | match | prediction_id AFTER | match |
|---|---|---|---|---|---|
| Imperial Guard | `RP_imperial guard` | `RP_imperialguard` | **FAIL** | `RP_imperialguard` | PASS |
| Ride The Thunder | `RP_ride the thunder` | `RP_ridethethunder` | **FAIL** | `RP_ridethethunder` | PASS |
| Trojan Soldier | `RP_trojan soldier` | `RP_trojansoldier` | **FAIL** | `RP_trojansoldier` | PASS |
| Cooley's Mist | `RP_cooley's mist` | `RP_cooleysmist` | **FAIL** | `RP_cooleysmist` | PASS |
| Billy No Mates | `RP_billy no mates` | `RP_billynomates` | **FAIL** | `RP_billynomates` | PASS |
| Dontwaste A Moment | `RP_dontwaste a moment` | `RP_dontwasteamoment` | **FAIL** | `RP_dontwasteamoment` | PASS |
| Plaid *(control)* | `RP_plaid` | `RP_plaid` | PASS | `RP_plaid` | PASS |
| Adalida *(control)* | `RP_adalida` | `RP_adalida` | PASS | `RP_adalida` | PASS |
| Letmeseethecolts *(control)* | `RP_letmeseethecolts` | `RP_letmeseethecolts` | PASS | `RP_letmeseethecolts` | PASS |

**Before fix:** 6 FAIL, 3 PASS  
**After fix:** 0 FAIL, 9 PASS

---

## Why Single-Word Names Passed (Control Group)

Sigma evaluated exactly these single-word horses on May 18:
- Adalida → WIN
- Lequinto → WIN  
- Wipeawayyourtears → PLACED
- Detective → MISS
- Letmeseethecolts → MISS
- Profiteer → MISS
- Powernap → MISS

`'ADALIDA'.lower()` = `'adalida'`. No spaces to strip. Both paths produce `RP_adalida`.  
Strict equality passes. This is why sigma found exactly 7 matched races — the 7 single-word names that had a result in the file.
