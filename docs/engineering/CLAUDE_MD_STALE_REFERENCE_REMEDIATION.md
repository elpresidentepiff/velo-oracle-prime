# CLAUDE.md Stale Model Reference Remediation

**Status:** STALE_REFS_DOCUMENTED — CLAUDE.md update required  
**Classification:** `DOCS_REMEDIATION_REQUIRED` / `NO_RUNTIME_IMPACT`  
**Date authored:** 2026-05-23  
**Authority:** El Presidente

---

## Purpose

The ML Models table in `CLAUDE.md` contains four stale references that overstate what actually exists on disk. This document records the gap for Council awareness and specifies the required correction.

No runtime code is affected — all four references are documentation-only claims.

---

## Stale References Found

### CLAUDE.md Claims (current, incorrect)

```
| SQPE v14   | models/sqpe_v14/sqpe_v14.pkl   | EXISTS on disk |
| SQPE v15   | models/sqpe_v15/sqpe_v15.pkl   | EXISTS on disk |
| Longshot v6| models/longshot_v6/longshot_v6.pkl | EXISTS on disk |
| Overlay v5 | models/overlay_v5/overlay_v5.pkl   | EXISTS on disk |
```

### Verified Actual State (2026-05-23)

| Model | Directory | PKL file | Actual status |
|---|---|---|---|
| SQPE v14 | `models/sqpe_v14/` — EXISTS | `sqpe_v14.pkl` — ABSENT | METADATA_ONLY |
| SQPE v15 | `models/sqpe_v15/` — MISSING | N/A | DIRECTORY_MISSING |
| Longshot v6 | `models/longshot_v6/` — EXISTS | `longshot_v6.pkl` — ABSENT | METADATA_ONLY |
| Overlay v5 | `models/overlay_v5/` — EXISTS | `overlay_v5.pkl` — ABSENT | METADATA_ONLY |

---

## Per-Reference Detail

### SQPE v14

**Claimed:** `models/sqpe_v14/sqpe_v14.pkl` EXISTS on disk  
**Actual:** Directory exists, contains only `metadata.json`. No pkl file present.  
**Classification:** `METADATA_ONLY` / `NOT_LOADABLE` / `NO_RUNTIME_MODEL_PRESENT`  
**Runtime impact:** NONE — no code path references `sqpe_v14.pkl` in `src/` or `scripts/`  
**V14 architecture note:** Referenced in `VELO_V14_ARCHITECTURE_TRUTH_MAP.md` with correct status `METADATA_ONLY / NOT_LOADABLE`

---

### SQPE v15

**Claimed:** `models/sqpe_v15/sqpe_v15.pkl` EXISTS on disk  
**Actual:** Directory `models/sqpe_v15/` does NOT exist. Nothing present.  
**Classification:** `STALE_REFERENCE_IN_CLAUDE_MD` / `DIRECTORY_MISSING` / `NO_RUNTIME_IMPACT_CONFIRMED`  
**Runtime impact:** NONE — no code path references `sqpe_v15.pkl`  
**V14 architecture note:** Referenced in `VELO_V14_ARCHITECTURE_TRUTH_MAP.md` with correct status `STALE_REFERENCE_IN_CLAUDE_MD / DOCS_REMEDIATION_REQUIRED`

---

### Longshot v6

**Claimed:** `models/longshot_v6/longshot_v6.pkl` EXISTS on disk  
**Actual:** Directory exists, contains only `metadata.json`. No pkl file present.  
**Classification:** `METADATA_ONLY` / `NOT_LOADABLE` / `NO_RUNTIME_MODEL_PRESENT`  
**Runtime impact:** NONE — the live specialist model in use is `models/specialist/longshot_model/` (trained 2026-03-16, AUC=0.936, gated SP≥10)  
**Note:** longshot_v6 appears to be a superseded version. The metadata-only directory should not be confused with the live specialist model.

---

### Overlay v5

**Claimed:** `models/overlay_v5/overlay_v5.pkl` EXISTS on disk  
**Actual:** Directory exists, contains only `metadata.json`. No pkl file present.  
**Classification:** `METADATA_ONLY` / `NOT_LOADABLE` / `NO_RUNTIME_MODEL_PRESENT`  
**Runtime impact:** NONE — no code path references `overlay_v5.pkl` in current live scoring path

---

## What Is Correctly Referenced

| Model | File | Status | CLAUDE.md claim |
|---|---|---|---|
| SQPE v1_real | `models/v1_real/sqpe/sqpe_model.pkl` | CONFIRMED PRESENT | Correct |
| TIE v9 | `models/tie_v9/tie_v9.pkl` | CONFIRMED PRESENT | Correct |
| SQPE v17 | `models/sqpe_v17/sqpe_v17.pkl` | CONFIRMED PRESENT | Not in table |
| SQPE v18 | `models/sqpe_v18/sqpe_v18.pkl` | CONFIRMED PRESENT (unclassified) | Not in table |

---

## Runtime Impact Assessment

**Confirmed zero runtime impact.** The stale CLAUDE.md entries are documentation artifacts from an earlier development phase. None of the four stale models are imported by:

- `scripts/run_prime_today.py` (LIVE_RUNTIME)
- `src/intelligence/velo_prime_ensemble.py` (LIVE_SUPPORT)
- `src/intelligence/sqpe.py` (LIVE_SUPPORT)
- `src/intelligence/specialist_models/loader.py` (LIVE_SUPPORT)
- Any app/ path

---

## Required CLAUDE.md Correction

The ML Models table in `CLAUDE.md` must be updated to reflect verified actual state:

```markdown
| Model | File | Status |
|---|---|---|
| SQPE v1_real | models/v1_real/sqpe/sqpe_model.pkl | REAL — trained, loadable |
| SQPE v14 | models/sqpe_v14/ | METADATA_ONLY — pkl absent, not loadable |
| SQPE v15 | models/sqpe_v15/ | MISSING — directory does not exist |
| SQPE v17 | models/sqpe_v17/sqpe_v17.pkl | LIVE MODEL — trained 2026-03-16, AUC=0.94 |
| SQPE v18 | models/sqpe_v18/sqpe_v18.pkl | UNCLASSIFIED LAB MODEL — NO LIFT verdict |
| TIE v9 | models/tie_v9/tie_v9.pkl | EXISTS on disk |
| Longshot v6 | models/longshot_v6/ | METADATA_ONLY — pkl absent, not loadable |
| Overlay v5 | models/overlay_v5/ | METADATA_ONLY — pkl absent, not loadable |
```

---

## Hard Rules

```
DO NOT attempt to load sqpe_v14.pkl, sqpe_v15.pkl, longshot_v6.pkl, overlay_v5.pkl
DO NOT delete metadata.json files from model directories without Council decision
DO NOT infer that metadata_only directories are loadable
DO NOT promote any metadata-only model without a present, verified pkl
```

---

```
CLAUDE_MD_STALE_REFERENCE_REMEDIATION_STATUS: DOCUMENTED
STALE_REFS_FOUND: 4 (sqpe_v14 METADATA_ONLY, sqpe_v15 MISSING, longshot_v6 METADATA_ONLY, overlay_v5 METADATA_ONLY)
RUNTIME_IMPACT: NONE
CLAUDE_MD_UPDATE_REQUIRED: YES
NO_MODEL_DELETION: DO NOT DELETE metadata directories without Council decision
```
