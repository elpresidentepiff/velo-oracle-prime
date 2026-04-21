# VÉLØ Audit: What Already Exists (Complete Inventory)

## Racing API Standard Plan — Fields Already Ingested

The `daily_pipeline.py` already ingests ALL of these into `runner_race_facts`:

| Field | API Key | Supabase Column | Status |
|---|---|---|---|
| Official Rating | `ofr` | `official_rating` | LIVE |
| RPR | `rpr` | `rpr` | LIVE |
| Topspeed | `ts` | `topspeed` | LIVE |
| Headgear code | `headgear` | `headgear` | LIVE |
| Headgear run count | `headgear_run` | `headgear_run` | LIVE |
| Wind surgery | `wind_surgery` | `wind_surgery` | LIVE |
| Wind surgery run | `wind_surgery_run` | `wind_surgery_run` | LIVE |
| Medical flags | `medical` | `medical_flags` | LIVE |
| Form string | `form` | `form_string` | LIVE |
| Last run days | `last_run` | `last_run_days` | LIVE |
| Spotlight text | `spotlight` | `spotlight_text` | LIVE |
| Stable tour | `stable_tour` | `stable_tour_text` | LIVE |
| Quotes | `quotes` | `quotes_text` | LIVE |
| Previous trainers | `prev_trainers` | (in runners table) | LIVE |
| Trainer 14-day form | `trainer_14_days` | `trainer_14_day_wins/runs` | LIVE |
| Trainer RTF | `trainer_rtf` | `trainer_rtf` | LIVE |
| Betting forecast | `betting_forecast` | `betting_forecast` | LIVE |

**Coverage from API exploration (today's cards):**
- Spotlight: 57% of runners (215/372)
- Headgear: 29% (110/372)
- Wind surgery: 1% (5/372)
- Medical: 10% (39/372)
- Previous trainers: 41% (155/372)

## Spotlight Parser — Already Built (workers/spotlight_parser.py)

767 lines. Fully implemented with:
- 15 flag categories (intent, excuse, stamina, behaviour, jockey, trainer, ground, trip, peak timing, danger, setup run, market, course form, PJI signal)
- Sentiment scoring (-2 to +2)
- PJI modifiers (concealed_effort_bonus, setup_mismatch_bonus, release_day_bonus)
- Stamina modifiers
- Day type push (CASH/SETUP/DISGUISE/NEUTRAL)
- Survivability modifier
- SpotlightGate class (structural qualification before modifiers apply)
- Supabase write to `horse_comments` table

## Spotlight Ingestion Worker — Already Built (workers/spotlight_ingestion_worker.py)

Full pipeline worker with:
- Comment extraction from raw text (3 regex patterns)
- NLP parsing pass
- Supabase write with upsert
- Null pathway contract (never blocks engine)

## Daily Pipeline — Already Wires Spotlight (workers/daily_pipeline.py)

Lines 458-792: The daily pipeline ALREADY:
1. Extracts spotlight text from Racing API `runner.spotlight`
2. Parses it through `parse_spotlight()` (simplified version)
3. Writes to `horse_comments` table in Supabase
4. Also writes headgear, headgear_run, wind_surgery, wind_surgery_run to `runner_race_facts`

## TIE v3 Gate — Already Built (src/intelligence/tie_v3_gate.py)

224 lines. Rule-based gate with 6 signals:
1. `rested_and_fit` — 14-42 days since last run
2. `class_drop_or_same` — class_delta <= 0
3. `win_withheld` — 6-15 runs since last win
4. `in_form_placed_recently` — placed within last 4 runs
5. `trainer_timing_pattern` — trainer_timing_score >= 0.5
6. `market_mid_range_support` — not fav but top-4 market

Already wired into `velo_prime_service.py` (lines 394-430).

## RPDC Rules — Already Detect First-Time Headgear (src/rpd/rpdc_rules.py)

Line 383: `first_headgear = (headgear_run == 1 and headgear)`
Line 394: Adds `live_first_time_headgear` as a T-signal (trainer intent)
Also detects: `live_wind_surgery_first_back`, `live_trainer_in_form`, `live_market_shortening`

## Playbook Orchestrator — Spotlight Already Integrated

`app/playbooks/playbook_orchestrator.py` already:
- Accepts `spotlight_records` parameter
- Runs SpotlightGate
- Applies modifiers to qualified runners
- Records spotlight_layer status in output

## WHAT IS MISSING / BROKEN

1. **The daily pipeline uses a SIMPLIFIED spotlight parser** (lines 460-483) with only 10 flags, NOT the full 767-line `spotlight_parser.py` with 15 flags + SpotlightGate
2. **No handicap plot detection** — no `or_delta_to_win` or `near_winning_mark` feature
3. **TIE v3 gate has NO spotlight signals** — it only uses v17 features, not the spotlight flags
4. **No gear intent signal in TIE** — first-time headgear is in RPDC but NOT in TIE v3
5. **No wind surgery signal in TIE** — wind_surgery_run is ingested but not used by TIE
6. **No education run detection** — setup_run_flag exists in v17 but isn't connected to TIE
7. **Spotlight text from API only covers 57%** — the PDF Spotlight covers 100% of runners
8. **The full spotlight_parser.py and spotlight_ingestion_worker.py are NOT called by daily_pipeline.py** — they exist but are disconnected
