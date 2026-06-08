# Race Day Two-Lane Readiness: 2026-05-29
Generated: 2026-05-29T03:51:20.032303Z

**Overall Status:** `READY`
**Operational Lane:** `LANE_A_CORE_PASSPORT`

## Quality Gates
| Gate | Pass |
|---|---|
| rpr_clean | ✓ |
| sp_clean | ✓ |
| passport_coverage_above_50pct | ✓ |
| no_leakage_violations | ✓ |

## Intent Coverage
- Coverage: **0.0%** (gate: 80.0%) — `UNAVAILABLE_BELOW_GATE`
- Intent features are historical (race_id, horse) pairs. Current-card rows never match → 0% is expected for morning reads.

## Lane Selection
- **LANE_A_CORE_PASSPORT** — Intent coverage 0.0% < 80.0% gate. Lane B is PAPER_ONLY_NO_INTENT. Lane A (Core+Passport) is operational read.

## Lane A: Core V0_OR + Passport (30 features) — Operational
- Model: `C:\Users\puror\velo-oracle-prime\data\new_build\models\core_v0_or_passport\core_v0_or_passport_model.pkl`

## Lane B: Challenger V1 Core+Passport+Intent (45 features)
- Status: `PAPER_ONLY_NO_INTENT`
- Intent coverage: 0.0%

## Race Day Scorecards — 2026-05-29
_7 races, 109 runners_

### 14:00 Chepstow — DragonBet Proud Sponsors Of Chepstow Racecourse Ap
- Runners: 12 | Passport: 12/12
- **Lane A (operational):** Oasis Sunrise (0.191), Beaune (0.165), Electric Bass (0.152)
- **Lane B (paper):** Oasis Sunrise (0.107), Beaune (0.134), Electric Bass (0.116) ⚠ PAPER_ONLY_NO_INTENT

### 14:30 Chepstow — DragonBet - Oncourse And Online Handicap
- Runners: 22 | Passport: 22/22
- **Lane A (operational):** Worlington (0.086), Thomas Picton (0.072), Action Reaction (0.071)
- **Lane B (paper):** Shirakawa (0.065), Heart Sign (0.060), Bumaan (0.052) ⚠ PAPER_ONLY_NO_INTENT

### 15:00 Chepstow — Pricing By Real Bookmakers At DragonBet Novice Sta
- Runners: 19 | Passport: 15/19 ⚠ WEAK_DATA
- **Lane A (operational):** Glory Road (0.130), Gone By (0.101), El Nay (0.097)
- **Lane B (paper):** Glory Road (0.085), Gone By (0.090), El Nay (0.090) ⚠ PAPER_ONLY_NO_INTENT

### 15:30 Chepstow — DragonBet Born From The Betting Ring Handicap
- Runners: 9 | Passport: 9/9
- **Lane A (operational):** So Smart (0.213), Cayman Tai (0.199), Tuscan Point (0.188)
- **Lane B (paper):** So Smart (0.138), Cayman Tai (0.143), In The City (0.155) ⚠ PAPER_ONLY_NO_INTENT

### 16:05 Chepstow — Best Odds Guaranteed On dragonbet.co.uk Handicap (
- Runners: 17 | Passport: 17/17
- **Lane A (operational):** Thanos (0.121), Smoker Bellamy (0.089), Mooj (0.086)
- **Lane B (paper):** Thanos (0.069), Smoker Bellamy (0.069), Mooj (0.073) ⚠ PAPER_ONLY_NO_INTENT

### 16:40 Chepstow — DragonBet: Supporting British Racing Maiden Stakes
- Runners: 17 | Passport: 13/17 ⚠ WEAK_DATA
- **Lane A (operational):** Erudition (0.140), Distant Moon (0.133), Law Court (0.085)
- **Lane B (paper):** Erudition (0.088), Distant Moon (0.088), Watercraft (0.070) ⚠ PAPER_ONLY_NO_INTENT

### 17:10 Chepstow — DragonBet, Top Prices On Top Markets Handicap
- Runners: 13 | Passport: 13/13
- **Lane A (operational):** Too Much Trevor (0.152), Romanovich (0.150), Sub Thirteen (0.119)
- **Lane B (paper):** Too Much Trevor (0.110), Romanovich (0.107), Sub Thirteen (0.096) ⚠ PAPER_ONLY_NO_INTENT

## Boundaries
- Paper-only intelligence. No betting instruction.
- No Telegram, staking, live scoring table writes, or official-pick override.
- Old Live VÉLØ and Shadow VÉLØ untouched.
- RPR archive-only. No SP in morning model. No JTC-D all-time sidecar.