# VELO Recovery Protocol

If interrupted:

1. Check `git status`.
2. Check [C:\Users\puror\velo-oracle-prime\data\velo_current_state.json](C:\Users\puror\velo-oracle-prime\data\velo_current_state.json).
3. Check the latest manifest.
4. Check accepted DB counts.
5. Check for partial rows by manifest event keys.
6. Roll back failed block by manifest scope only.
7. Never resume from memory alone.

## Detailed Recovery Notes
- Use the canonical state file as the first source of truth for mission phase.
- Use the latest accepted audit to confirm doctrine, provenance, and parity expectations.
- If a block failed, verify:
  - `race_results` scoped rows
  - `runner_results` scoped rows
  - `historical_feature_store` scoped rows
  - `races` scoped rows
- Recovery is complete only when scoped residual rows are confirmed at `0`.

## Hard Constraints
- Do not broaden rollback scope.
- Do not patch model logic mid-recovery unless the approved mission is specifically remediation.
- Do not proceed to training from a recovered state without a fresh accepted audit.
