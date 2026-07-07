# VFU_INDEX.md — VÉLØ Forensics Unit Index (VFU-01 to VFU-25)

Source material: `docs/current/VELO_VFU_TIMELINE_APPENDIX.md` (VFU-01 to VFU-12
narrative), `docs/current/ONE_TRUTH.md` VFU Sign-Off Log (VFU-13 onward), and
`docs/current/VFU_FAILURE_TAXONOMY_V1.md`. This index does not add facts beyond
those two sources — where detail is thin, that is stated rather than invented.

The VFU program moves VÉLØ beyond simple outcome scoring into governed
behavioural/forensic analysis: doctrine, autopsy, pattern detection, identity
integrity, and time-safety review — always dry-run/report-only unless explicitly
promoted by the operator.

| VFU | Title | Purpose | Main outcome | Safety status | Next dependency |
|---|---|---|---|---|---|
| VFU-01 | Doctrine + schemas | Establish foundational rules, DB schemas, operational boundaries for forensic investigation | Read-only, non-mutating start | COMPLETE | VFU-02 |
| VFU-02 | 20-race autopsy dry-run | Controlled test of the autopsy mechanism on a small dataset | Validated extraction/classification of failure modes | COMPLETE, dry-run | VFU-03 |
| VFU-03 | pick_sp enrichment audit | Align price data with predictions for market context | `vfu_pick_sp_enrichment_report.{json,md}`, ambiguous/unmatched row lists | COMPLETE | VFU-04 |
| VFU-04 | Full current-era autopsy pass | First comprehensive sweep of recent data | Baseline error distribution, miss categorization | COMPLETE | VFU-05 |
| VFU-05 | Pattern Prosecutor | Identify recurring themes across autopsies | Move from isolated failures to structural weaknesses; `vfu_pattern_prosecutor_*` reports | COMPLETE, dry-run watchlist only | VFU-06 |
| VFU-06 | Horse Identity Bridge | Link legacy name-based records to stable immutable horse IDs | Namespace-preserving identity infrastructure | COMPLETE | VFU-07 |
| VFU-07 | Identity-confirmed repeated-horse review | Use VFU-06 identity bridge to analyze repeatedly-selected/repeatedly-missed horses | `vfu_repeated_horse_truth_table.json`, blind-spot exposure | COMPLETE | VFU-08 |
| VFU-08 | Passport Review Queue | Workflow for proposing Horse Passport updates from forensic evidence | Dry-run gated proposal queue; `vfu_passport_review_rejected.json` shows rejections enforced | COMPLETE, dry-run gate | VFU-09 |
| VFU-09 | VP Suppression Investigation | Investigate whether high VP was masking underlying profile weaknesses | `vfu_vp_suppression_investigation.{json,md}`, human review queue | COMPLETE | VFU-10 |
| VFU-10 | Time-Safe Passport Override Validation | Temporal-discipline check; investigated 'Kakirra' anomaly | Kakirra proven temporally contaminated, correctly rejected for promotion. Related: MiK = PARTIAL (per `project_vfu_state` — sp_shortening safe, win_rate not confirmed at claimed rate) | COMPLETE — contamination catch enforced | VFU-11 |
| VFU-11 | 6,019-row Sigma Master Ledger | Assemble definitive era-separated dataset for structural investigation | Quarantined older/unsafe data; foundation for Pattern Tribunal | COMPLETE | VFU-12 |
| VFU-12 | Sigma Pattern Tribunal + Human Review Triage | Prosecute pattern candidates, generate human review queue | 7 patterns prosecuted, Top 25 human review queue, 3 patterns (VP suppression, SP shortening, Passport Override) promoted to **dry-run watchlist only** — no live doctrine promoted without operator approval | COMPLETE, dry-run watchlist only | VFU-13 |
| VFU-13 to VFU-19 | Contamination catches, Sigma master ledger, pattern tribunal (grouped in `ONE_TRUTH.md`; no further per-VFU breakdown documented) | Extend VFU-11/12 lineage | Kakirra confirmed CONTAMINATED, MiK confirmed PARTIAL (per `ONE_TRUTH.md` VFU Sign-Off Log) | **COMPLETE — no pending operator gates** (per `ONE_TRUTH.md` line 100) | VFU-20 |
| VFU-20 | Field-size remediation | Recover missing field-size data across historical corpus | 1,989 missing → 152 remaining (92.36% recovery accepted); 749 EW label changes accepted; EW profitability ruled `PARTIAL_EW_SIGNAL_NOT_PROFIT_PROOF` — no profitability claim authorised | **OPERATOR SIGN-OFF GRANTED 2026-06-29.** No VP change, no model promotion, no Supabase write. Output: `data/reports/vfu_20_operator_brief.md` | VFU-21 |
| VFU-21 | (not yet started per `ONE_TRUTH.md`: "VFU-21 NOT started — awaiting VCP-00 truth lock completion") | — | — | NOT STARTED | VCP-00 Truth Lock completion (VCP-00 was IN PROGRESS as of 2026-06-29 per `ONE_TRUTH.md` VCP State section) |
| VFU-22 | False-GREEN Feature Autopsy (formerly proposed as VFU-13 before DOCS-01 index reconciliation) | Investigate days where the VP Gatekeeper classified GREEN but strike rate was poor (confirmed precedent: 2026-06-09, VP_avg=0.358, 9 picks VP>=0.40, SR=13.8% — see `docs/current/VP_GATEKEEPER_PROMOTION_V1.md` "MANDATORY CAVEAT — FALSE GREEN RISK"). Identify false-green feature classes, feature push/pull effects, and latent warning gaps the gate missed. | **COMPLETE, merged PR #137 (`4f789b1`).** 6 of 16 GREEN days (37.5%) confirmed false-green; `CONFIDENCE_FLOOD_FALSE_GREEN` class identified (~3x smaller VP hit/miss discrimination gap than true-green days; 2/6 inverted) | DRY_RUN / REPORT_ONLY — no live scoring, no Supabase write, no Telegram send, no model promotion | VFU-23 |
| VFU-23 | Confidence Flood Retrospective Diagnostic | Build a reusable, tested post-Sigma diagnostic (`scripts/ops/build_confidence_flood_diagnostic.py`) that measures the VFU-22 `CONFIDENCE_FLOOD_FALSE_GREEN` pattern every time Sigma closes — instrument, not cure | **COMPLETE, merged PR #138 (`797cdef`).** Reproduced the VFU-22 false-green set 6/6 with zero extras; 21 tests pass; `confidence_flood_flag` disclosed as an imperfect SR-independent proxy (4/6 caught, 1 false alarm) | DRY_RUN / RETROSPECTIVE_ONLY — no pre-race gate change, no live scoring, no Supabase write, no Telegram send, no model promotion | VFU-24 |
| VFU-24 | Confidence Flood Root-Cause Split | Split the six confirmed false-green days into root-cause subtypes; explain why 2026-06-18 and 2026-06-19 were false-green despite a HEALTHY VP discrimination gap | **COMPLETE, merged PR #139 (`ad1a4aa`).** All 6 classified: 4 `GAP_COLLAPSE_FALSE_GREEN`, 2 `HEALTHY_GAP_FALSE_GREEN` (both also `THRESHOLD_FLOOD_FALSE_GREEN`); 29 tests pass. | DRY_RUN / PATHOLOGY_CLASSIFICATION_ONLY — no cure proposed, no pre-race gate change, no live scoring, no Supabase write, no Telegram send, no model promotion | VFU-25 |
| VFU-25 | Confidence Flood Cure Design Sandbox | Design (not implement) candidate mitigations for both VFU-24 variants | IN PROGRESS (opened 2026-07-07 per operator formal dispatch). 5 candidates designed: Gap-Collapse Guard, Threshold-Flood Guard, Green-Day Risk Overlay, Same-Day Post-Sigma Reporting Enhancement, Promotion/Rejection Criteria. All rated `DESIGN_ONLY`/`NEEDS_MORE_EVIDENCE`/`SHADOW_TEST_NEXT` — none ready to leave the sandbox. | DRY_RUN / REPORT_ONLY / CURE_DESIGN_SANDBOX — no cure implemented, no pre-race gate change, no live scoring, no Supabase write, no Telegram send, no model promotion | Task contract `ops/task_contracts/VFU-25.json`; see `docs/current/CONFIDENCE_FLOOD_CURE_DESIGN_SANDBOX.md` |

## Numbering ruling (resolved 2026-07-06 — do not reopen)

The DOCS-01 mission spec that produced this index originally named the *next*
piece of work as **"VFU-13 — False-GREEN Feature Autopsy."** That number was
already assigned in `ONE_TRUTH.md` to the completed contamination-catch group
(VFU-13 to VFU-19, COMPLETE). Operator ruling issued 2026-07-06:
**VFU-13 is retired and must never be reused.** The work is **VFU-22 — False-GREEN
Feature Autopsy** (formerly proposed as VFU-13 before DOCS-01 index reconciliation).
Any reference to "VFU-13 — False-GREEN Feature Autopsy" in older mission text is
stale — that number is dead.

## Cross-references

- Failure taxonomy used across autopsy VFUs: `docs/current/VFU_FAILURE_TAXONOMY_V1.md`
- Race-level autopsy schema: `docs/current/VFU_RACE_AUTOPSY_SCHEMA_V1.md`
- VCP (Coherence Protocol, downstream of VFU-20/21): `docs/current/ONE_TRUTH.md` §"VÉLØ Coherence Protocol (VCP) State"
