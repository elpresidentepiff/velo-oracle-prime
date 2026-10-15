# Racing Post vs FormFav — what each feeds, how each is processed (V1, 2026-10-15)

Measured on 2026-10-14 GB/IE: 39 FormFav races matched to 39 RP races, **351 runners on both sides, 0 unmatched either way**.
Canonical truth stays `docs/current/ONE_TRUTH.md`. This page is analysis, not law.

## 1. The two feeds side by side

| | Racing Post (RP) | FormFav |
|---|---|---|
| Role | **Canonical.** Only live source Prime scores (hard law 1) | **Second source**, shadow only |
| How it arrives | Logged-in browser capture, **local**, once, manual: index → URL list → one HTML per race → parse | REST API, **cloud**, continuous: `velo-formfav-live` worker, 60 s tick |
| Cadence | One morning snapshot; **perishable** (RP drops a course from its index after it runs) | Meetings every 10 min, form every 30 min, predictions every 6 h, results after the off |
| Stored as | `data/racecards_*_standard.json` → merged files → Supabase `races.raw` | `formfav_races`, `formfav_runner_form`, `formfav_predictions`, `formfav_results` |
| Identity | Numeric `horse_id` / `trainer_id` / `jockey_id`, `race_id` | **Names only** (runner name + number); race key = country/date/track/race no. |
| Enriched by | PDF "Newspaper Form" sheets (OR/TS/postdata), passports (New Build), RPDC | Nothing; stored as received |
| Consumed by Prime | **Yes** (`run_prime_today.py --source rp`) | **No.** Shadow features only |

## 2. Processing path

**RP → VELO:** capture (Steps 1–3) → parse to injection JSON + standard cache (4) → validate (5) → New Build passport feed (6–7) → PDF ingest (8, hard gate) → RPDC (8.5) → merged cards → `run_prime_today.py` (9) → `velo_verdicts`, `runner_prediction_snapshots`, `pipeline_runs`.

**FormFav → shadow:** API → worker → `formfav_*` tables → `CachedFormFavClient` (cache first, live API on miss/stale) → `enrich_existing_racecards` (attaches `_formfav` to a **copy** of the RP card; fills only missing fields; never overwrites; Prime's cache is never enriched) → `build_race_shadow_packet` (`FORMFAV_UK_SHADOW_V1`: pace, form, class, track-bias, sample-size shrinkage, identity and draw checks, quality score) → `velo_report_artifacts` (`formfav_uk_shadow_features`) → dashboard `/api/formfav-shadow` (coverage only).

**Where they meet:** only inside the enrichment step, matched by normalised course + UK off time, then runner name. Nowhere else.

## 3. What each one uniquely holds

**RP only:** numeric IDs; official rating, TopSpeed, RPR (archive-only policy); sire / dam / damsire / owner; headgear and first-time flags; wind surgery; days since last run; trainer RTF and new-trainer runs; jockey first-time; newspaper tips and Spotlight / Diomed comments; forecast and morning price; going and stalls; plus PDF intel, passports and RPDC layered on top.

**FormFav only:** speed map (running style, early-speed index, settling position); pace scenario; class profile and race-class fit; stats split by overall / track / distance / track+distance / conditions / first-up / second-up; last-20 starts; decorators; career prize money; exact-distance 90-day barrier bias; its own win/place probabilities; (Premium) live prices.

FormFav coverage on 2026-10-14 GB/IE runners: stats 325/351 (93%), class profile and class fit 304 (87%), speed map 259 (74%). Distance-scoped stats are thinner (plan doc: 36% distance, 21% track+distance).

## 4. Where they overlap — measured agreement (351 runners)

| Field | Comparable | Agree |
|---|---|---|
| Runner identity (name join) | 351 | **351 (100%)** |
| Draw / barrier | 181 (flat; jumps have none) | **181 (100%)** |
| Age | 351 | **351 (100%)** |
| Weight (±1.5 lb after kg→lb) | 351 | **351 (100%)** |
| Trainer | 351 | **351 (100%)** |
| Jockey | 351 | 324 (92%) |
| Form string, exact | 318 | 70 (22%) |
| Non-runner flag | 351 | 348 (99%) |

So FormFav adds almost nothing to RP's *basic* fields (nothing to backfill). Its value is the lanes in section 3.

## 5. Disagreements worth knowing

- **Late changes.** FormFav marked 3 horses scratched that the morning RP card still listed as runners (Babatunde, Cospicua, Aleppo Pepper). Of 8 jockey mismatches reviewed (of 27), 6 were amateur titles ("Mr", "Miss"), and 2 were real booking changes (River Ore: RP Donagh Meyler vs FormFav Ross Sugrue; It's All About You: RP Callum Rodriguez vs FormFav Tom Marquand). RP is one snapshot; FormFav keeps moving.
- **Form strings are not comparable.** Same horses, different encoding and window (e.g. RP `25` vs FormFav `25X`; RP `21P471` vs `10471`). Never use string equality as a conflict test; use structured runs (`last20Starts`).
- **Names are the only FormFav key.** Suffixes ("(IRE)"), punctuation and same-name horses are the failure modes. The join strips them; a conflict is logged, not guessed.

## 6. Risks in how they are fed

1. **Single FormFav key, two consumers** (worker and shadow job) → HTTP 429 → empty enrichment on 10-13 and 10-14. Fixed: shadow job reads the worker's stored rows.
2. **Race-day order.** RP is local and slow; FormFav is cloud and fast. Check FormFav first (Step 0 below) so a FormFav fault is found before the perishable capture is spent.
3. **Shadow output is a per-day blob**, not per-runner rows with a snapshot time. An ablation needs queryable pre-race features joined to results. Not built yet.
4. **No lift measured.** `velo_vs_formfav` gives the side-by-side; promotion still needs the chronological ablation in `FORMFAV_UK_ENHANCED_VELO_PLAN_V1.md`.
5. **Prices are Premium-only** (trial = 403), so the market lane is empty.

## 7. Race-day order (FormFav first)

0. `formfav_readiness.py` — FormFav stored and fresh for the day (races with form ≥95%, predictions ≥90%, runner stats ≥80%, newest update <3 h). Fails the run before RP capture.
1–5. RP capture, parse, validate (ONE_TRUTH Steps 1–5).
5.6. FormFav shadow enrichment from the stored rows — must reach ≥80% of in-scope GB/IE races or scoring does not start.
6–9. Passports, PDFs, RPDC, scoring.
