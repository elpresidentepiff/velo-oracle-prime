# PRODUCTION READINESS SCORECARD — VÉLØ ORACLE PRIME

**Date:** 2026-06-10 · Scale 0–5 · Every score <4 carries the smallest fix that raises it.

| Dimension | Score | Evidence | Smallest fix to raise |
|---|---|---|---|
| Reproducibility | 4 | Verdicts carry `git_commit_sha`, `engine_version`, run_id; observability schema v1.1.0; profile logged per race | — |
| Source clarity | 3 | `source_truth_enforcer.py` is solid, but PDF-intel coverage decides CLEAN/DEGRADED and June 10 ran DEGRADED with no pre-scoring warning stage | Add a ratings-source check to pre-flight: fail loudly BEFORE scoring if >50% runners lack `pdf_intel` |
| Race-day run safety | 3 | Hard gates exist (`validate_rp_injection`, SOURCE_UNKNOWN_BLOCK) but the day is 20 manual steps with hand-copied labels | One wrapper that threads `FINAL_CAPTURE_LABEL` automatically through stages 3–6 (orchestration only, zero logic change) |
| Feature health detection | 4 | Degradation detection, flatline detection, spotlight timing audit all live in observability | — |
| Degraded-state handling | 2 | Degraded runs proceed and learning blocks correctly, but Mission Control re-labels the day CLEAN; `send_degraded_run_notice.py` exists but is not wired into the chain | Fix `_detect_source_truth` to read the observability JSON; call degraded notice from `run_prime_today` |
| Learning safety | 5 | Multi-gate: source, council, pipeline truth, contamination list, shadow-only state, idempotency proof | — |
| Persistence reliability | 4 | June 10: 34/34 persisted, persist_fail 0, local backup + readback fields exist (readback null — wire it) | — |
| Dashboard reliability | 2 | Three-script manual chain; no delivery truth artifact; uncommitted drift in `app/static/dashboard/index.html` | Emit a `dashboard_publish_truth_{date}.json` like the Telegram truth file |
| Telegram reliability | 3 | Delivery truth file exists and is honest (DISABLED state recorded); but alerts have been off since the recovery period with no re-enable criteria | Write the re-enable condition into ONE_TRUTH and flip `--no-notify` once met |
| Test coverage | 2 | 911 tests collect, including harness-enforcement tests — but 3 modules have import drift against live code | Fix/delete the 3 drifted test modules (`test_racecard_loader`, `test_hfs_*`) |
| CI confidence | 1 | CI tests ONLY `workers/ingestion_spine` (legacy); no workflow runs the daily-chain tests; local pytest cannot even start (pytest 6.2.5 vs pytest-asyncio 1.3.0) | Pin compatible pytest (≥8) + pytest-asyncio, add a `ci.yml` job running `tests/` |
| Observability | 4 | Run truth, telegram truth, timing audit, observability packet, mission control — rich and mostly honest | — |
| Rollback ability | 4 | Env-var profile rollback; rollback runbook + manifest in docs/stabilization; models immutable on disk | — |
| Operator clarity | 2 | Three competing truth docs at root + 133 flat docs; the truthful doc (THE_ONE_TRUTH) buried among stale rivals | Adopt `docs/current/ONE_TRUTH.md` as index; archive the rivals (this audit) |
| Code simplicity | 2 | `run_prime_today.py` is a 112KB monolith; 260 scripts; duplicated doc/system layers | No rewrite now — freeze: new code only via the 20-step contract; archive dead scripts |

**Overall: NOT sign-off ready.** The scoring core and learning gates are genuinely strong (4–5). The wrapper around them — CI, tests, Mission Control truthfulness, doc sprawl, manual fragility — is where race-day mistakes repeat.
