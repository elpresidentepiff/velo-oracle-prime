# System Audit — 2026-04-08

## 1. Closed-Loop Archive
- **sigma_audits**: 711 rows total
  - Race-level: 558 races (Jan 9 – Apr 8, 2026)
  - Horse-level: 674 runner verdicts
  - 55 unique tracks, 89 days, avg 6.3 races/day
- **learned_patterns**: 68 patterns (mostly empty — 0 occurrences)
- **fingerprint_signal_summary**: 507 rows (ALL from today — my local session)
- **race_fingerprint_analogs**: only today's data

## 2. Expanded Stats
- Horse-level strike: 140/674 = 20.8%
- Miss rate: 350/674 = 51.9% (clean: 47.2% excl. NR)
- Placed rate: 184/674 = 27.3%
- Winner SP: 49.6% short fav, 37.4% mid, 10.8% outsider, 2.2% longshot

### Miss Class (350 misses)
- mid_priced_won: 123 (35.1%) ← biggest bleed
- market_decoy_followed: 94 (26.9%)
- outsider_won: 38 (10.9%)
- non_runner_or_untracked: 32 (9.1%) ← NOT model error
- short_fav_won: 30 (8.6%)
- outsider_hedge_omitted: 29 (8.3%)

### Tier Performance
- Tier A: 36.1% strike (n=61)
- Tier B: 22.7% strike (n=163)
- Tier C: 18.4% strike (n=228)
- Tier D: 12.3% strike (n=57)
- Tier X: 14.5% strike (n=83)

### Decile (verdict_score)
- 0.0-0.1: 61.5% strike (n=13, small sample)
- 0.1-0.2: 15.6% strike (n=135)
- 0.2-0.3: 21.4% strike (n=103)
- 0.3-0.4: 23.8% strike (n=42)
- 0.4-0.5: 26.3% strike (n=19)
- 0.5-0.7: 50.0% strike (n=12, small sample)
- High-conf (>=0.25): 25.0% strike (n=112)

## 3. RPDC Tagging — DORMANT
- NOT persisted anywhere
- velo_pipeline.py _assign_rpd_tag() is runtime only
- rpd_tags table: 0 rows
- learned_patterns: 68 patterns with 0 occurrences
- verdict_score multipliers DO affect ranking at runtime
- KEY ISSUE: RPDC feedback loop never closed

## 4. Playbooks — NOT IMPLEMENTED
- No playbook files exist
- HorseStateEngine designed for playbook consumption — nothing consumes it
- Real decisioning: velo_prime_ensemble + tie_v3_gate + orchestrator

## 5. Railway Deployment — PARTIALLY LIVE
- velo_verdicts pipeline: ✅ LIVE on Railway (2026-03-15 → today)
- Sidecar (extended_shadow, sqpe_bridge, raceform_deriver): ❌ NOT DEPLOYED
  - src/v13/racing_analogs/ is UNTRACKED in git
  - 507 rows in fingerprint_signal_summary = my local session only
- Railway API: 403 Forbidden (token expired)
- CRON: No Hermes cron jobs registered

## 6. Actions Required
1. P0: Commit sidecar to git + deploy to Railway
2. P1: Create shadow_log table in Supabase
3. P2: Regenerate Railway token
4. P3: Set up sidecar cron on Railway
5. P4: Audit/fix learned_patterns — feedback loop is broken
