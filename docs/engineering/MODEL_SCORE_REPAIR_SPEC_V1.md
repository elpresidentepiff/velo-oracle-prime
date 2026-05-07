# VÉLØ Model Score Repair Specification V1

## Objective
Remediate probability drift and selection leakage identified in the 1,046-race Genesis replay. These repairs focus on stabilizing high-confidence predictions and bridging the "Chalk Blindness" gap while maintaining absolute production safety.

## 1. Calibration Drift Repair (Priority: 1)
- **Problem**: Model overstates probability in the >45% range, leading to high-confidence losses.
- **Evidence**: 132 `CALIBRATION_ERROR` outcomes; 59 high-confidence implosions.
- **Affected Races**: 132 documented calibration errors.
- **Expected Impact**: Stabilize Strike category ROI.
- **Safe to Implement Now**: True (Shadow Mode).
- **Blocked by HFS**: False.
- **Proposed Files**: `app/services/scoring/recalibration_overlay.py`.
- **Required Tests**: Strike Rate vs implied prob on >45% range.
- **Rollback Plan**: Disable recalibration overlay flag.
- **Promotion Gate**: 7-day shadow replay pass.

## 2. Chalk Blindness Repair (Priority: 2)
- **Problem**: VÉLØ fails to identify "Easy Winners" where the market favorite wins and the model diverges without doctrine cause.
- **Evidence**: 59 `FAVOURITE_MISSED` leakage events.
- **Affected Races**: ~15% of historical losses.
- **Expected Impact**: Higher strike rate by capturing market-obvious outcomes.
- **Safe to Implement Now**: False (Requires Betfair Truth).
- **Blocked by HFS**: False.
- **Proposed Files**: `app/services/scoring/chalk_sanity_gate.py`.
- **Required Tests**: Match model rank to market rank.
- **Rollback Plan**: Revert to static selection rank.
- **Promotion Gate**: Live market truth integration.

## 3. Environmental Volatility Dampener (Priority: 3)
- **Problem**: High-uncertainty fields (Chaos) cause model confidence to remain artificially high.
- **Evidence**: High density of losses in races with >14 runners and high MPI proxy.
- **Affected Races**: ~10% of total volume.
- **Expected Impact**: ROI protection in volatile environments.
- **Safe to Implement Now**: False (Requires HFS Repair).
- **Blocked by HFS**: True.
- **Proposed Files**: `app/services/scoring/chaos_cap_modifier.py`.
- **Required Tests**: Variance check on prob in fields > 16.
- **Rollback Plan**: Remove chaos multiplier.
- **Promotion Gate**: HFS_TRAINING_SAFE=TRUE.

## 4. Top-3 Containment Repair (Priority: 4)
- **Problem**: Successful winners are frequently ranked outside the model's Top 3 selections.
- **Evidence**: Winners identified at Model Rank 4-5 in "leaky" races.
- **Affected Races**: ~5% of miss volume.
- **Expected Impact**: Rescue overlooked winners.
- **Safe to Implement Now**: True (Shadow Analysis).
- **Blocked by HFS**: False.
- **Proposed Files**: `app/services/study/rescue_audit_engine.py`.
- **Required Tests**: Rank stability check.
- **Rollback Plan**: Disable rescue audit layer.
- **Promotion Gate**: Verified 20% rescue rate.

## 5. Loss-Type Feedback Weighting (Priority: 5)
- **Problem**: All misses treated too similarly; model does not adapt to failure classes.
- **Evidence**: `WRONG_HORSE` dominant pattern (713 cases).
- **Affected Races**: Entire historical lifecycle.
- **Expected Impact**: Context-aware selection tuning.
- **Safe to Implement Now**: True (Shadow State).
- **Blocked by HFS**: False.
- **Proposed Files**: `app/playbooks/sentient_feedback_bridge.py`.
- **Required Tests**: Weight adjustment audit.
- **Rollback Plan**: Freeze sentient state influence.
- **Promotion Gate**: 30-day shadow stability.

## 6. HFS-Dependent Feature Repair (Priority: 6)
- **Problem**: Advanced feature learning is blocked by unsafe data.
- **Evidence**: `HFS_TRAINING_SAFE` = FALSE.
- **Affected Races**: 100% of training rows.
- **Expected Impact**: Unlock V17 deep signals (MPI/Chaos Bloom).
- **Safe to Implement Now**: False (Maintenance only).
- **Blocked by HFS**: True.
- **Proposed Files**: `scripts/backfill_historical_feature_store.py`.
- **Required Tests**: HFS Schema and Value consistency.
- **Rollback Plan**: Revert to HFS_BLOCK_001.
- **Promotion Gate**: Successful full-history dry-run.

---
*Authorized by VÉLØ Command Authority | Engineering Division*
