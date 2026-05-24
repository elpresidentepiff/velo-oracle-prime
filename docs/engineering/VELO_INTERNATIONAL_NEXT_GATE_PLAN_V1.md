# VÉLØ International Next Gate Plan V1

**Status:** GATE_BLOCKED — El Presidente sign-off required  
**Phase:** 11 — International Continuation  
**Classification:** `INTERNATIONAL_STILL_GATED` / `NO_MIGRATION` / `NO_WORKERS` / `NO_PROMOTION`

---

## Current State (2026-05-23)

| Gate | Status |
|---|---|
| INTERNATIONAL_RATING_PROVENANCE_GATE | ACTIVE (locked `589b428`) |
| Arena V1 (form-only) | All 5 packs FAILS_FAVOURITE_BASELINE |
| Arena V2 (market signal) | All 5 packs GATE_REOPENED_SAFE_SHADOW_CANDIDATE |
| Migration (`intl_schemas_v1.sql`) | NOT APPLIED |
| Workers (HKJC / PMU ingest) | NOT BUILT |
| International training/promotion | BLOCKED |

**Provenance gate remains ACTIVE until El Presidente explicit sign-off.** The arena V2 result is evidence. Gate closure requires operator decision.

---

## Arena V2 Results

| Pack | AUC | SR | FavSR | Gap | Verdict |
|---|---|---|---|---|---|
| HK_SHA_TIN_V2 | 0.8870 | 52.04% | 34.70% | +17.3pp | GATE_REOPENED |
| HK_HAPPY_VALLEY_V2 | 0.8606 | 42.99% | 26.87% | +16.1pp | GATE_REOPENED |
| FR_CHANTILLY_V2 | 0.8359 | 32.30% | 29.42% | +2.9pp | GATE_REOPENED |
| FR_FLAT_CORE_V2 | 0.8530 | 34.98% | 29.69% | +5.3pp | GATE_REOPENED |
| FR_AUTEUIL_JUMPS_V2 | 0.7816 | 27.58% | 27.58% | 0pp | GATE_REOPENED* |

*Auteuil: AUC ≥ 0.75 technically passes gate but SR ties FavSR exactly. Marginal. Treat as lowest priority.

**Key insight:** Market signal (SP at race off) is dominant. Market-only model achieves AUC 0.79–0.90. Form adds modest incremental signal. The favourite baseline is beaten by following market consensus, not by superior form analysis alone.

**Implication for live deployment:** SP is available at race start (not morning). For morning selections, morning odds (HKJC tote pool, PMU morning price) are needed as a proxy.

---

## Priority Packs for Gate Close

| Priority | Pack | Gap to Fav | Notes |
|---|---|---|---|
| 1 | HK_SHA_TIN_V2 | +17.3pp | Largest gap. Strong market signal. Primary target. |
| 2 | HK_HAPPY_VALLEY_V2 | +16.1pp | Strong gap. Good class signal. |
| 3 | FR_FLAT_CORE_V2 | +5.3pp | Core FR pack. Largest sample. |
| 4 | FR_CHANTILLY_V2 | +2.9pp | Speciality pack. |
| 5 | FR_AUTEUIL_JUMPS_V2 | 0pp | Tied. Lowest priority. Morning odds needed. |

---

## Required Next Work (Gate-Blocked Until Sign-off)

1. **El Presidente sign-off** — explicit approval to proceed with any of the below
2. **Assess morning odds path** — HKJC tote pool (public, pre-race) for HK; PMU morning prices for FR
3. **FR penetrometer** — numeric going proxy from France Galop (better than bucket codes)
4. **FR Quinté+ flag** — PMU race designation (prize-race dynamics differ)
5. **FR class proxy** — France Galop Valeur rating
6. **Rerun safety audit** — any new features must pass provenance audit before arena
7. **Migration** — only after sign-off on at least one pack

---

## Provenance Doctrine (Permanent)

```
Same-race RPR/TS for FR: POST_RACE_LEAKAGE_CONFIRMED — BANNED permanently
Same-race RPR/OR for HK: PRE_RACE_SAFE (winner_max 42–46%) — ALLOWED
Lagged features only: mandatory for all international packs
Arena gate criteria: AUC ≥ 0.75 AND SR > FavSR (strictly greater)
Each pack closes gate independently
No cross-pack promotion
```

---

```
INTERNATIONAL_NEXT_GATE_PLAN_V1_STATUS: DEFINED
GATE: STILL_ACTIVE — operator sign-off required
MIGRATION: NOT_APPLIED
WORKERS: NOT_BUILT
PROMOTION: BLOCKED
FIRST_ELIGIBLE_PACK: HK_SHA_TIN (largest gap) — after sign-off
```
