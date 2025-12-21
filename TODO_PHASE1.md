# V12 Phase 1: Live-Only Functionality Patches

## Status: IN PROGRESS

### Patch 1: Race Context Propagation FIX
- [x] Pass race_ctx into Decision Policy
- [x] Pass race_ctx into ADLG
- [ ] Verify logs show real race_id (not "unknown")

### Patch 2: Market Role Classifier v1 (odds-based)
- [x] Implement Anchor (lowest odds)
- [x] Implement SecondFav (2nd lowest odds)
- [x] Implement MidBand (middle odds range)
- [x] Implement Outsider (highest odds)
- [x] Rule: lowest odds runner NEVER Noise

### Patch 3: Chaos v1 from odds concentration
- [x] Implement HHI (Herfindahl-Hirschman Index) calculation
- [x] Implement Gini coefficient calculation
- [x] Factor in field size
- [x] Ensure chaos varies across races (not constant 0.45)

### Patch 4: Top-4 Ranking score-based
- [ ] Combine odds-derived signals
- [ ] Add feature stability scoring
- [ ] Rank by composite score
- [ ] Verify Top-4 not always R01-R04

## Acceptance Tests (Non-Negotiable)
1. [ ] Any race with 1.44 fav: runner cannot be Noise
2. [ ] Chaos cannot be constant across races
3. [ ] Decision/ADLG cannot say "race: unknown"
4. [ ] Top-4 cannot be first four IDs by list order
