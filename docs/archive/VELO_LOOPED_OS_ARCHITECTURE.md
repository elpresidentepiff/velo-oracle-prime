# VÉLØ LOOPED OS — ARCHITECTURE

**Effective:** 2026-06-10 · Operator law: `EVERY_STAGE_REQUIRES_A_LOOP`.
**The pattern:** `DETECT → DECIDE → ACT → VERIFY → LOG → LEARN OR BLOCK`.
A stage that cannot verify itself is not production. A stage that cannot log proof is not trusted. A stage that cannot fail loud is dangerous. A stage that does not feed Mission Control is not part of the OS.

Machine-readable registry: `data/current/loop_registry.json` · health: `scripts/ops/check_loop_health.py` (read-only).
Convention: every loop writes a `data/current/*_latest.json` status artifact and a dated `data/reports/*_{date}.md` evidence report.

---

## LOOP 1 — Source Truth Loop
| Element | Definition |
|---|---|
| Trigger | Race-day morning, before any scoring |
| Input | RP HTML captures, racecard injection, merged build, PDF intel coverage |
| Validator | `validate_rp_injection.py` + `source_truth_enforcer.py` (>50% pdf_intel rule) |
| Action | Classify day: `SOURCE_CLEAN / SOURCE_DEGRADED / SOURCE_UNKNOWN / SOURCE_BLOCKED` |
| Verifier | Observability packet carries the label; Mission Control re-reads it (never infers) |
| Artifact | `data/velo_run_observability_{date}_*.json` → `data/current/source_truth_latest.json` (planned) |
| MC field | `source_truth` |
| Failure state | `SOURCE_UNKNOWN_BLOCK` → scoring refuses (SourceTruthBlockError) |
| Fallback | Re-capture / re-login; never substitute a non-RP source (Racing API forbidden) |
| Learning impact | Non-CLEAN blocks learning (GATE_SOURCE_DEGRADED / GATE_SOURCE_UNKNOWN) |
| Operator approval | Required to proceed scoring on a known-degraded day |

## LOOP 2 — Feature Health Loop
Trigger: every scoring run · Input: per-runner features, ensemble components · Validator: active_components vs `_WEIGHTS` profile; improvement_score variance; flatline detector · Action: label CLEAN/DEGRADED · Verifier: observability packet `feature_health` + flatline_summary · Artifact: `data/current/feature_health_latest.json` (planned; today inside observability packet) · MC field: `flatline_count`, gate reasons · Failure: live-weighted component excluded or flat ⇒ DEGRADED · Fallback: none — declare loudly · Learning: DEGRADED blocks · Approval: operator may not override in code.

## LOOP 3 — RPDC Integrity Loop *(priority — implemented 2026-06-10)*
| Element | Definition |
|---|---|
| Trigger | After every scoring run; on demand for any historical date |
| Input | Local backup verdicts (`rpdc_lookup_status`, rpdc fields) + Supabase `velo_verdicts` rows + `runner_release_candidates` |
| Validator | Field-level compare: primary tag, tags, release score, cash window, tag count |
| Action | Classify: `RPDC_OK / RPDC_LOCAL_ONLY / RPDC_PERSIST_GAP / RPDC_CORRUPTED / RPDC_UNKNOWN` |
| Verifier | `scripts/ops/check_rpdc_integrity.py` (read-only) |
| Artifact | `data/current/rpdc_integrity_latest.json` + `data/reports/rpdc_integrity_{date}.md` |
| MC field | `rpdc_integrity_status` (column proposed in pending migration) |
| Failure state | PERSIST_GAP (attach worked, persistence dropped it) or CORRUPTED (foreign data in RPDC columns — the fda78d4 hijack signature) |
| Fallback | Historical repair tool (dry-run first, apply only with explicit operator flag) |
| Learning impact | Non-OK blocks learning (`LEARNING_BLOCKED_RPDC_CORRUPTED`) |
| Operator approval | Required for any historical repair write |

## LOOP 4 — Persistence Proof Loop *(priority — implemented 2026-06-10)*
Trigger: after every scoring run · Input: Supabase `velo_verdicts` + local backup · Validator: count match, null tier/sha, RPDC presence, active_components, schema gaps · Action: PASS/FAIL/CANNOT_CHECK · Verifier: `scripts/ops/prove_supabase_persistence.py` (GET-only, exit-coded) · Artifacts: `data/current/persistence_proof_latest.json` + `data/reports/supabase_persistence_proof_{date}.{json,md}` · MC field: `persistence_proof_status` (column proposed) · Failure: FAIL blocks learning (`LEARNING_BLOCKED_PERSISTENCE_UNPROVEN`) · Fallback: investigate before evening chain · Approval: none to run (read-only); required to fix schema.

## LOOP 5 — Mission Control Truth Loop *(priority — implemented 2026-06-10, bc28e2f)*
Trigger: evening chain + after fixes · Input: observability packet, sigma artifact, council artifacts, run truth · Validator: `_detect_source_truth` reads packet — missing⇒UNKNOWN, malformed⇒UNKNOWN, degraded⇒DEGRADED, **never defaults clean** · Action: gate learning/promotion with reasons · Verifier: `tests/test_mission_control_source_truth.py` (11 tests) + cross-check vs packet · Artifact: `data/mission_control/{date}_mission_control.json` + `latest.json` · MC field: is MC · Failure: UNKNOWN blocks all gates · Fallback: none — UNKNOWN is the honest answer · Learning: BLOCKED on DEGRADED/UNKNOWN/CONTAMINATED/flatline · Approval: contamination list changes.

## LOOP 6 — Race Day Execution Loop *(spec committed; build pending approval)*
Pattern: preflight → Loop 1 → Loop 2 → Loop 3 → scoring (dry-run first) → Loop 4 → Loop 5 → Telegram/dashboard gate. Command: `run_race_day.py --date D --mode dry-run` (live mode raises until operator approves). Spec: `ONE_RACE_DAY_COMMAND_SPEC.md`. Artifacts: `data/current/race_day_status_{date}.json` + `data/reports/race_day_{date}.md`.

## LOOP 7 — Sigma Loop
Pattern: results capture → parse → reconcile → classify `SIGMA_CLOSED_CLEAN / SIGMA_CLOSED_DEGRADED / SIGMA_INCOMPLETE / SIGMA_BLOCKED` → MC. Exists today as `run_results_sigma.py` (locked format) + MC sigma_artifact section; the explicit four-status classifier and `data/current/sigma_status_latest.json` are the wiring gap. Learning: non-CLOSED blocks (`LEARNING_BLOCKED_SIGMA_MISSING`).

## LOOP 8 — Learning Admission Loop
Pattern: consume Loops 1–5 + 7 + horse_runs ingest + contamination list → status → **operator approval always required**. Statuses per `LEARNING_ADMISSION_GATE.md` (8 statuses incl. `LEARNING_READY_PENDING_OPERATOR_APPROVAL`). Checker `check_learning_admission.py` is read-only and **cannot execute learning** — it only reports eligibility. Enforcement fix queued: learning runner refuses without artifacts.

## LOOP 9 — Testing & CI Loop *(local half implemented 2026-06-10, ee3fcc6)*
Pattern: bug found → test written → fix applied → local pass → CI contract protects it. Local: 947 collected/0 errors; truth-boundary suites green; quarantine policy in `tests/README.md`. CI gap: workflow must run MC source-truth tests, RPDC boundary tests, proof script offline mode, Racing-API-not-live check, ONE_TRUTH/runbook existence. Until CI lands, this loop is LOOP_PARTIAL.

## LOOP 10 — Docs Truth Loop
Pattern: new truth → update ONE_TRUTH → mark stale → archive after approval. Rules: `docs/current` = living truth; `data/reports` = daily evidence; `docs/archive` = history; no numbered doctrine files; anything contradicting ONE_TRUTH is stale by definition. Maps: `DOCS_CONSOLIDATION_MAP.md` (+ approval packet pending). Blocks nothing mechanically; blocks operator sanity when broken.

## LOOP 11 — Telegram / Media Gate Loop
Pattern: race day status → MC truth → persistence proof → feature health → **operator approval** → send → delivery-truth verification. Statuses: `TELEGRAM_DISABLED / TELEGRAM_READY_PENDING_OPERATOR / TELEGRAM_BLOCKED_DEGRADED / TELEGRAM_BLOCKED_SOURCE_UNKNOWN / TELEGRAM_SENT_VERIFIED`. Current status: `TELEGRAM_DISABLED`. Gate doc: `TELEGRAM_REENABLE_GATE.md`. The delivery-truth file must record SUPPRESSED, never silently skip.

## LOOP 12 — Performance / Money Truth Loop
Pattern: sigma → ledger → contaminated-day exclusion → benchmark → claim level. Claim levels: `INTERNAL_ONLY / SHADOW_ONLY / VERIFIED_INTERNAL / PUBLIC_SAFE / PUBLIC_BENCHMARKED`. Policy: `PERFORMANCE_CLAIM_POLICY.md`. Current ceiling: VERIFIED_INTERNAL (19-day sigma SR) and SHADOW_ONLY (router lanes); no public claim until benchmarked against named public competitors. Known evidence defect: paper ledger ID chain prevents result closure — ledger claims are EVIDENCE_INTEGRITY_SUSPECT until repaired.

---

## Loop interaction spine
```
L1 source ─┐
L2 feature ─┼─► L5 Mission Control ─► L8 learning admission ─► (operator) ─► learning
L3 rpdc ───┤            │
L4 persist ─┘            ├─► L11 telegram gate ─► (operator) ─► public output
L7 sigma ───────────────┘
L6 race-day command orchestrates L1→L5 in order; L9 CI defends the code of every loop;
L10 docs keep one truth; L12 caps what may be claimed publicly.
```
