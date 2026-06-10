# VÉLØ EXECUTION ROADMAP — LOCKED ORDER

**Effective:** 2026-06-11 (operator-decided). This supersedes all scattered next-fix lists. Work proceeds top-down; nothing below starts while its gate above is red.

| # | Step | Status | Trigger / gate | Owner |
|---|---|---|---|---|
| 1 | **June 11 clean-chain, local** | READY — morning | capture →… → attach preflight READY → dry-run → operator go → real run → integrity RPDC_OK → proof PASS | Fable + operator go |
| 2 | **Rotate dangerous keys** (service-role, DB URL first) | checklist ready | operator hands; rotate Telegram AFTER tonight's closeout window | Operator |
| 3 | **Park Railway zombies** (dashboard) | steps ready; volume export FIRST | 48h soak across Jun 11–12 | Operator |
| 4 | **Finish Sigma ROI/CLV** | layers A–G live; remaining: clean-chain bucket E fills from #1; runner-level = declared NOT_FOUND; odds provenance done; CLV needs BSP capture (#4b: one nightly fetch — build after first clean day) | Fable | 
| 5 | **DuckDB = daily truth spine** | DB-1 prototype live | DB-2: loop checkers read DB; DB-3 dual-write needs approval; identity_aliases mandatory; 100-day ledger becomes a SQL view | Fable, phased |
| 6 | **GitHub Actions closeout workflow** | hosting decision committed | build AFTER #2 (secrets must be rotated before entering GH vault); closeout first, capture stays local | Fable |
| 7 | **run_prime_today strangler** | plan committed | golden replay test (June 10 artifacts) FIRST; June 11 replay added once clean; CI replay job; dead code + API paths removed in own commits | Fable |
| 8 | **JTC-D sidecar wiring** | JTC_D_PARTIAL, plan committed | badge-only attach; 30-day evidence loop; never weighted without gates | Fable |
| 9 | **Dashboard + Telegram approval bot** | L11 gate defined | only after Telegram re-enable conditions PASS + operator approval | later |
| 10 | **Betfair automation thinking** | FORBIDDEN until 1–9 stand | — | — |

## Model-truth track (parallel, evaluation only — no retrain without harness)
walk-forward harness spec → **leakage audit of sqpe_v17** (SP-as-input + in-sample, already proven — formal doc) → new_build champion validation on unseen clean days → shadow arena promotion rules → ONLY THEN any retrain discussion. **Tier-A-not-leakage proof:** live Tier-A (+4.3%, n=365) uses realized results vs SP — not model-circular; the decade proxy (+4.78%, 11/11 years) corroborates structurally; final proof = walk-forward by year/course/class/odds-band on pre-race-only features.

## Tomorrow morning, exact commands (Fable runs)
```
PYTHONPATH=. python scripts/ops/velo_session_start_check.py
# THE_ONE_TRUTH Steps 1–4 (capture/parse, label chosen once)
PYTHONPATH=. python scripts/ops/validate_rp_injection.py --injection-path <label>/racecard_injection.json
PYTHONPATH=. python scripts/ops/build_racecard_merged_from_injection.py --date 2026-06-11 --injection-path <same>
# PDF-intel coverage check (>50% or declare DEGRADED before scoring)
PYTHONPATH=. python scripts/ops/build_rpdc_daily.py --date 2026-06-11 --injection-path <same>
PYTHONPATH=. python scripts/ops/check_rpdc_attach_preflight.py --date 2026-06-11   # must exit 0
PYTHONIOENCODING=utf-8 PYTHONPATH=. python scripts/ops/run_prime_today.py --date 2026-06-11 --source rp --dry-run
# OPERATOR GO →
PYTHONIOENCODING=utf-8 PYTHONPATH=. python scripts/ops/run_prime_today.py --date 2026-06-11 --source rp --no-notify
PYTHONPATH=. python scripts/ops/prove_supabase_persistence.py --date 2026-06-11    # first expected PASS
PYTHONPATH=. python scripts/ops/check_rpdc_integrity.py --date 2026-06-11          # first expected RPDC_OK
```
