# VELO Agent Sandbox Policy V1

## Principle
Agents default to read-only. Write access is granted per role, per path, and per command.

## Sandbox Levels

### Read-Only
Allowed:
- inspect artifacts
- read Supabase tables
- compute summaries
- write local status reports only

Blocked:
- verdict writes
- learning writes
- state mutation
- backups

### Shadow-Write
Allowed:
- write to approved shadow targets
- write local forensic artifacts
- write learning events when Sigma truth is ready

Blocked:
- live state writes
- contaminated target writes
- cloud backup mutation
- consumed_live promotion

### Live-Write
Reserved for explicitly approved official scoring only.

Blocked by default for:
- Learning Agent
- Mission Control
- Safety Sentinel
- Red Team Agent

## Forbidden Paths
- `data/sentient_state.json`
- `data/sentient_state_shadow_full_train_v1.json`
- `.env`
- any secrets file

## Stop Conditions
- wrong target state
- `consumed_live > 0`
- Sigma truth unavailable for learning
- official prediction overwrite risk
- cloud backup changed unexpectedly
- forbidden file drift in scoring/model/router/staking/Telegram layers
