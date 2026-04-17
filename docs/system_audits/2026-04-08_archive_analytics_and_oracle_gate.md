# System Audit — 2026-04-08 — 500-Race Analytics + Oracle Field Gate

## PART 1 — Archive Analytics (558 races)

**Archive:** 558 races, 674 runners, Jan 9 – Apr 8 2026, 55 tracks

### Core Rates
- Strike: 20.8% (140/674)
- Placed: 27.3% (184/674)
- Miss: 51.9% (350/674)
- Clean miss (excl. NR): 47.2% (318/674)

### Avg verdict_score
- Hits: 0.2542
- Misses: 0.2074
- Delta: +0.0468 — calibration direction correct

### Winner SP Distribution (n=139)
- <3.0: 69 (49.6%)
- 3.0-6.0: 47 (33.8%)
- 6.0-10.0: 16 (11.5%)
- 10.0-15.0: 4 (2.9%)
- >15.0: 3 (2.2%)

### Miss Classes (350 misses)
- mid_priced_won: 123 (35.1%) ★★★
- market_decoy_followed: 94 (26.9%)
- outsider_won: 38 (10.9%)
- non_runner_or_untracked: 32 (9.1%) ← not a model miss
- short_fav_won: 30 (8.6%)
- outsider_hedge_omitted: 29 (8.3%)
- high_confidence_miss: 2 (0.6%)

### Tier Performance
- Tier A: 36.1% strike (n=61) ← best
- Tier B: 22.7% strike (n=163)
- Tier C: 18.4% strike (n=228)
- Tier D: 12.3% strike (n=57)
- Tier X: 14.5% strike (n=83)

### Decile Performance
- 0.0-0.1: 61.5% (n=13, small)
- 0.1-0.2: 15.6% (n=135)
- 0.2-0.3: 21.4% (n=103)
- 0.3-0.4: 23.8% (n=42)
- 0.4-0.5: 26.3% (n=19)
- 0.5-0.7: 50.0% (n=12, small)

---

## PART 2 — Oracle Field Gate

### Field Availability

| Field | In src/ | In app/ | In Live Pipeline |
|-------|---------|---------|-----------------|
| n_arrative_disruption | NO | YES | NO |
| mpi | NO | YES | NO |
| chaos_bloom | NO | YES | NO |
| integrity_score | NO | YES | NO |
| story_anchor | NO | YES | NO |
| power_anchor | NO | YES | NO |
| threat_cluster | NO | YES | NO |
| vetp_patterns | NO | YES | NO |

### Architecture

- `src/` = live scoring core (velo_pipeline.py, velo_prime_ensemble.py) — self-contained
- `app/` = API layer + playbook orchestrator + intelligence modules
- `app/services/velo_prime_service.py` imports from `src/`
- `src/` does NOT import from `app/`
- `app/intelligence/` modules (narrative_disruption, market_manipulation) are NOT connected to `src/`

### Verdict

| Playbook | Status | Reason |
|----------|--------|--------|
| G | SAFE TO REVIVE IMMEDIATELY | No oracle_data needed. Load sentient_state.json. |
| E | BLOCKED | Needs oracle_data schema. Requires building intelligence layer into src/. |
| F | BLOCKED | Same as E. |

### G Revival Path

1. Load `data/sentient_state.json` at `velo_prime_ensemble.py` startup
2. Read `doctrine_firing_threshold`, `doctrine_strengths`, `structural_drift`
3. Apply as post-processing multiplier on `velo_prime_prob`
4. Shadow test, then deploy

### E/F Blocker

E and F require the oracle_data schema. The fields exist in `app/intelligence/` but that layer is not connected to `src/`. Three options:
- Option A: Port app/intelligence modules into src/
- Option B: Wire app/intelligence into src/ pipeline
- Option C: Build new oracle layer in src/

All are valid but all are separate projects.
