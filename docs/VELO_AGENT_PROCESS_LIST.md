# VELO Agent Process List

## Mandatory Startup Sequence For Any New Agent
A. Read [C:\Users\puror\velo-oracle-prime\data\velo_current_state.json](C:\Users\puror\velo-oracle-prime\data\velo_current_state.json).  
B. Read [C:\Users\puror\velo-oracle-prime\docs\VELO_AGENT_HANDOFF.md](C:\Users\puror\velo-oracle-prime\docs\VELO_AGENT_HANDOFF.md).  
C. Read [C:\Users\puror\velo-oracle-prime\docs\VELO_OASIS_RUNBOOK.md](C:\Users\puror\velo-oracle-prime\docs\VELO_OASIS_RUNBOOK.md).  
D. Inspect the latest global audit artifacts before touching logic or data.  
E. Confirm no rejected block remains partially inserted.  
F. Confirm current DB counts match the accepted spine.  
G. Only then continue the next approved mission.  

## Mandatory Startup Checks
- Confirm `training_status = paused`.
- Confirm `playbook_e_status = paused`.
- Confirm latest failed block is fully rolled back if one exists.
- Confirm no active mission is resumed from memory alone.

## Mission Progression Rules
- Discovery must be accepted before bridge.
- Bridge must be accepted before any new window is opened.
- Global audit must pass before any training gate can even be discussed.
- Any macro-year mismatch is a hard stop.

## Current Next Approved Mission
- `ETCSLV Framework Audit`

## Forbidden Shortcuts
- No top-up from other windows.
- No filter relaxation.
- No unstated retraining.
- No cross-window mixing.
- No speculative mutation of provenance or doctrine without an explicit remediation mission.
