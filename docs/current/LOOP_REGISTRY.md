# LOOP REGISTRY — VÉLØ LOOPED OS

**Machine-readable source of truth:** `data/current/loop_registry.json` · **Health:** `PYTHONPATH=. python scripts/ops/check_loop_health.py` (read-only) → `data/current/loop_health_latest.json` + `data/reports/loop_health_latest.md`.
Architecture detail: `VELO_LOOPED_OS_ARCHITECTURE.md`. Statuses: `LOOP_OK / LOOP_PARTIAL / LOOP_MISSING_ARTIFACT / LOOP_FAILING / LOOP_NOT_IMPLEMENTED / LOOP_BLOCKED_OPERATOR`.

| Loop | Name | Status (2026-06-10) | Blocks learning | Blocks Telegram | Blocks clean claim | Next fix |
|---|---|---|---|---|---|---|
| L1 | Source Truth | PARTIAL | ✓ | ✓ | ✓ | pre-scoring PDF-intel check + source_truth_latest.json |
| L2 | Feature Health | PARTIAL | ✓ | ✓ | ✓ | standalone packet + improvement variance check |
| L3 | RPDC Integrity | **OK (checker live)** | ✓ | — | ✓ | historical repair (dry-run → approved apply) |
| L4 | Persistence Proof | **OK (checker live)** | ✓ | ✓ | ✓ | auto-run after every scoring run |
| L5 | Mission Control Truth | **OK (fixed bc28e2f)** | ✓ | ✓ | ✓ | consume L3/L4 artifacts as gate inputs |
| L6 | Race Day Execution | NOT_IMPLEMENTED | — | ✓ | — | dry-run skeleton after approval (spec exists) |
| L7 | Sigma | PARTIAL | ✓ | — | ✓ | four-status day classifier |
| L8 | Learning Admission | PARTIAL | ✓ | — | — | read-only checker + runner artifact-gating |
| L9 | Testing & CI | PARTIAL | — | — | — | daily-chain-contract.yml workflow |
| L10 | Docs Truth | PARTIAL | — | — | — | approved archive sweep |
| L11 | Telegram/Media Gate | BLOCKED_OPERATOR | — | ✓ | — | stays DISABLED until gate PASS + approval |
| L12 | Performance Truth | PARTIAL | — | — | ✓ | ledger ID-chain repair; named benchmark |

**Registry rules:** every new operational capability must register here with a checker and artifacts before it is considered production. A loop whose checker cannot run is `LOOP_MISSING_ARTIFACT`, not silently OK. `current_status` in the JSON is the declared state; `check_loop_health.py` may downgrade it from artifact evidence, never upgrade it.
