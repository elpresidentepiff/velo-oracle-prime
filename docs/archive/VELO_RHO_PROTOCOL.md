# VÉLØ RHO PROTOCOL — Retrospective Harness Optimization

**Effective:** 2026-06-11 · Scope law: this formalizes what exists. It is not a new project, not a fourth harness runner, not a doctrine empire.

## 1. The Failure → Guardrail Escalation Law
| Trigger | Mandatory response |
|---|---|
| First occurrence | LOG (ledger entry + reasons) |
| Repeated occurrence | LOOP required (registered checker + artifact) |
| Live-truth impact | BLOCKER (gate that stops the chain) |
| Learning impact | QUARANTINE (admission gate status) |
| Public-claim impact | CLAIM DOWNGRADE (auto, per PERFORMANCE_CLAIM_POLICY §6) |
| Infrastructure impact | DECOMMISSION/REBUILD GATE (approval packet) |
| Secret impact | ROTATION GATE (operator checklist) |

**No failure is allowed to remain only a lesson.**

## 2. Converted failures (RHO already done by hand)
| Failure | Evidence | Guardrail created | Remaining risk | Owner loop |
|---|---|---|---|---|
| May 24 degraded features | doctrine V1 origin; HarnessGuard case `may24_rpdc_degraded` | source_truth_enforcer + Sentinel rule 3 + observability packet | pre-scoring PDF-intel check still manual | L1/L2 |
| June 9 RPDC attach failure | investigation doc; 632 candidates, 0 attached | attach preflight (exit-coded) + deterministic name fallback (122b1de) + integrity checker | 17 earlier attach days unrepairable | L3 |
| June 10 RPDC persist gap | hijack fda78d4; local 34 attached vs Supabase 0 | persist boundary fix (66d23a0) + persistence proof tool + 4 boundary tests | historical rows await approved repair (packet B) | L4 |
| Railway zombie topology | 502 endpoint; 50 failed fires/day | infra audit + decommission packet + schedules disabled + topology law | dashboard decommission pending operator | infra |
| 100-day evidence gap | 87 days, 0 signed-clean | truth ledger (rerunnable) + day classifications + ledger-gated claims | clean series starts June 11 | ledger |
| Sigma universe scope error | "595" was a 19-day slice of 2,528 | universe extractor + layer law (never blend) | CLV needs BSP capture | L12 |
| betting_ledger unknown | 1,050 rows, no sim marker | provenance audit → CONFIRMED_SIM, ROI-banned forever | none (quarantined) | L12 |
| Silent ingest batch drop | 250/381 printed "COMPLETE" | dedupe + fail-loud exit (91a8197) | none | L7 |

## 3. RHO operating rule
RHO may **select, replay, diagnose, propose**. RHO may **never auto-apply**. Operator approval required for: code changes · schema changes · historical repair · learning admission · Telegram re-enable · public-claim upgrade · live scoring change.

## 4. Wiring (existing assets, no new builds)
- **Hard-day selector** = the 100-day ledger → `data/current/rho_candidate_failures.json` (52 candidates, 18 HIGH-priority attach days, auto-generated).
- **Replay seed** = `hackathon/amd_harnessguard/demo_cases/` (3 historical incidents with baselines — recognized, to be folded in, not duplicated).
- **Replay engine path** = the golden-day replay test (RUN_PRIME_STRANGLER_PLAN step 1). One engine serves both strangler verification and RHO replay.
- **Guardrail owner map** = the loop registry (`loop_registry.json`).
- **Future evidence spine** = DuckDB truth store (DB-2+).
- **Scripts** (`select_hard_days_for_rho.py` etc.): **DEFERRED** — the selector is already the JSON above; replay waits for the golden-replay engine. No code until that lands.

## 5. Duplication warning — consolidate, never multiply
Three harness runners exist: `run_agent_harness.py`, `run_harness.py`, `velo_daily_harness.py`. Marked for consolidation into ONE during the run_prime strangler. **Creating a fourth harness runner is forbidden.** The harness code layer (`src/velo/harness/`: Sentinel, contracts, verifier, executor) and the ratified `VELO_AGENT_HARNESS_DOCTRINE_V1` remain the single foundation — RHO is a protocol on top of them, not beside them.
