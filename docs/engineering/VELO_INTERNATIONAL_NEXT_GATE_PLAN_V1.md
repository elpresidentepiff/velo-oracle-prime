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
2. **Market timestamp provenance gate** — all market features used in any live deployment must be classified PRE_RACE_MORNING_SAFE. Arena V2 features (sp_dec derivatives) are CLOSING_MARKET_ONLY — NOT morning-safe. See `ARENA_V2_MARKET_PROVENANCE_AUDIT.md`.
3. **Assess morning odds path** — HKJC tote pool (public, pre-race) for HK; PMU morning prices for FR. Source legality must be confirmed before ingestion. No scraping without confirmed rights.
4. **Arena V3 (morning odds arena) — required per pack** — Form + morning market proxy. Same gate criteria: AUC ≥ 0.75 AND SR > FavSR. Must pass for each pack independently. No cross-pack credit. This is the missing arena between V1 (form-only, all fail) and V2 (closing-market, all gate-reopened).
5. **FR penetrometer** — numeric going proxy from France Galop (better than bucket codes)
6. **FR Quinté+ flag** — PMU race designation (prize-race dynamics differ)
7. **FR class proxy** — France Galop Valeur rating
8. **Rerun safety audit** — any new features must pass provenance audit before arena
9. **Worker activation legality** — HKJC and PMU data sourcing legality must be confirmed before any worker is built. Workers NOT BUILT until: (a) sign-off granted AND (b) source legality confirmed AND (c) timestamp safety confirmed (morning odds, not SP).
10. **Migration** — only after sign-off on at least one pack AND Arena V3 pass for that pack

---

## Three-Arena Requirement Per Pack

Each pack must pass all three arenas independently before any live deployment discussion:

| Arena | Features | Timing | Status |
|---|---|---|---|
| Arena V1 | Lagged form only | PRE_RACE_MORNING_SAFE | All 5 packs FAIL |
| Arena V2 | Form + SP (race-off) | CLOSING_MARKET_ONLY | All 5 packs GATE_REOPENED |
| Arena V3 | Form + morning odds | PRE_RACE_MORNING_SAFE | NOT YET BUILT |

Arena V3 is required before any pack can be considered for morning deployment.  
Arena V2 evidence is valid for closing-market strategy research only.

---

## Provenance Doctrine (Permanent)

```
Same-race RPR/TS for FR: POST_RACE_LEAKAGE_CONFIRMED — BANNED permanently
Same-race RPR/OR for HK: PRE_RACE_SAFE (winner_max 42–46%) — ALLOWED
Lagged features only: mandatory for all international packs
SP (sp_dec) derivatives: CLOSING_MARKET_ONLY — banned from morning prediction features
Morning odds (HKJC tote pool / PMU morning price): PRE_RACE_MORNING_SAFE — required for Arena V3
Arena gate criteria: AUC ≥ 0.75 AND SR > FavSR (strictly greater)
Each pack closes gate independently
No cross-pack promotion
Market timestamp safety: must be confirmed for every feature before arena inclusion
```

---

```
INTERNATIONAL_NEXT_GATE_PLAN_V1_STATUS: UPDATED_2026-05-23
GATE: STILL_ACTIVE — operator sign-off required
MIGRATION: NOT_APPLIED
WORKERS: NOT_BUILT — legality confirmation required before build
PROMOTION: BLOCKED
ARENA_V3_MORNING_ODDS: NOT_YET_BUILT — required for all 5 packs
MARKET_TIMESTAMP_GATE: ACTIVE — SP derivatives banned from morning features
FIRST_ELIGIBLE_PACK: HK_SHA_TIN (largest gap) — after sign-off AND Arena V3 pass
```
