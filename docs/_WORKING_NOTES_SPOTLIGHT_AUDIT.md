# Working Notes: Spotlight PDF Analysis & Trainer Intent Code Audit

## Spotlight PDF Structure (Pontefract 21.04.26)
- **Format:** Racing Post Spotlight daily racecard
- **7 pages, 6 races** covering a full meeting
- **Per race:** Race title, class/band, prize money, distance, going, weight conditions, penalties
- **Per runner:** Horse name, age, weight (with gear codes like p/t/b/h/v/w), trainer, jockey, SP, OR, TS, RPR
- **Per runner:** Free-text Spotlight comment (1-3 sentences) — THIS IS THE GOLD
- **Per race:** SPOTLIGHT VERDICT paragraph naming the selection + danger(s)

## Key Data Fields Available Per Runner
1. Horse name
2. Age (e.g., "3" or "4")
3. Weight (e.g., "9-9" = 9st 9lb)
4. Gear codes: p=first-time blinkers, t=tongue tie, b=blinkers, h=hood, v=visor, w=wind op, 1=first-time cheekpieces
5. Trainer name
6. Jockey name
7. SP (starting price)
8. OR (Official Rating) — CRITICAL for handicap plot detection
9. TS (Topspeed rating)
10. RPR (Racing Post Rating)
11. Spotlight comment text — contains education/plot/intent signals in natural language

## Handicap Plot Signals Visible in Spotlight Comments
- "dropped down the weights" → class drop / weight drop
- "3lb below that winning mark" → near_winning_mark / release signal
- "could prove to be ahead of the handicapper" → OR underestimate
- "first-time cheekpieces" / "blinkers go on now" → gear change = intent signal
- "changed hands" → new trainer = fresh start
- "gelded since" → physical intervention = intent
- "returns having been gelded" → deliberate prep for release
- "wears first-time cheekpieces" → gear intent
- "hood added" → gear intent
- "tongue tie" → gear intent
- "breathing surgery" → physical intervention
- "could be sharper for that experience" → education run completed
- "open to improvement" → upward trajectory
- "won this race 12 months ago" → course specialist returning
- "2lb out of the handicap" → weight penalty context

## What the Current Trainer Intent Code Does (BROKEN)
### feature_engineering.py — trainer_intent_factor()
- **STUB.** Returns 0.5 default.
- Only checks: gear_change (bool) and jockey_upgrade (hardcoded to 2 Australian jockeys!)
- No OR analysis, no class drop, no weight movement, no comment parsing
- Weight: 0.13 in v9pm ensemble

### v9pm.py — _layer_3_trainer_intent()
- **STUB.** Returns trainer ROI / 20.0
- No actual intent detection

### oracle_analyzer.py — handicap_plot_risk
- Binary "high" if handicap, "low" if not
- No nuance, no OR comparison, no winning mark analysis

### horse_state_engine.py — release_state
- Actually decent architecture! Has release_candidate / hidden / conditioning
- Uses: class_delta, rest_pattern, runs_since_win, trainer_timing_score, quiet_run_score
- BUT: class_delta comes from Racing API (limited), not from OR vs winning mark comparison
- Missing: OR relative to last winning OR (the "winning mark" concept)
- Missing: gear change signals
- Missing: Spotlight comment intelligence

### TIE v3 Gate
- Rule-based, 6 signals: rested_and_fit, class_drop_or_same, win_withheld, in_form_placed_recently, trainer_timing_pattern, market_mid_range_support
- Fires for tier upgrade (C→B, D→C) when ≥4 signals
- Missing: OR vs winning mark, gear changes, physical interventions, comment intel

## What Needs Building (Handicap Plot Engine)
1. **OR vs Last Winning OR comparison** — the "winning mark" concept
   - If current OR ≤ last winning OR: release_candidate signal
   - If current OR is 1-3lb below last winning OR: near_winning_mark
   - If current OR is 4+ below: below_winning_mark (strong signal)
2. **Gear Change Detection** — first-time blinkers/cheekpieces/tongue tie/visor/hood
3. **Physical Intervention Detection** — gelded, wind op, breathing surgery
4. **Education Run Pattern** — 2-3 run sequence where horse is being "schooled"
5. **Spotlight Comment NLP** — parse the free text for intent signals
6. **Weight Movement Tracking** — OR trajectory over last 3-5 runs
7. **Trainer Pattern Detection** — specific trainers known for plot sequences
