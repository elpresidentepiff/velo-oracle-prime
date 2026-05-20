# VÉLØ Known Issues and Blockers V1

## High Priority (P0)

1. **HFS Signal Flatness (Block 001):** `mpi` and `chaos_bloom` signals are flat or null in the `historical_feature_store`. This means Playbook G is training on unsafe/proxy data. The sentient loop is unsafe for live promotion.
2. **Missing `supabase` Python Package:** Pipeline scripts fail in some execution environments because the `supabase` dependency is missing. Fallbacks trigger (like local JSON dashboard publishing).

## Medium Priority (P1)

1. **Python Command Alias:** Execution environments often lack the `python` alias and require `python3` explicitly. Standardize Makefile and documentation to use `python3`.
2. **Racing API Rate Limits:** The Racing API is on the Standard plan, strictly limited to 3 requests per second. Aggressive batch fetching without delays will result in 429 Too Many Requests errors.

## Low Priority (P2)

1. **Documentation Fragmentation:** Key research documents (e.g., `VELO_TRUTH_THESIS_V1.md`) are sometimes located outside the repository root.
2. **Dead Scripts:** The `archive/dead_scripts` folder contains outdated scripts like `close_sigma_loops.py` which can confuse agents.
