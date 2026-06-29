# HISTORICAL REPAIR — APPROVAL PACKET

**Date:** 2026-06-10 · **Nothing in this packet has been applied.** Each item needs the operator's explicit approval. Old verdict *predictions* are immutable in every scenario — repairs touch evidence labels and metadata only.

| ID | Repair | Target | Reason | Method | Rollback | Approve |
|---|---|---|---|---|---|---|
| A | Safe local metadata repair | Ledger labels (`data/current/velo_100_day_truth_ledger.json`) | Keep classifications current as new evidence lands | Re-run `build_100_day_truth_ledger.py` (read-only rebuild) | Regenerate from artifacts any time | ☐ (low risk — recommend standing approval) |
| B | Supabase historical RPDC field repair | `velo_verdicts` rows 2026-04-21→2026-06-10 **where the local backup carries genuine attached RPDC** (June 10: 34 rows proven; tool will enumerate the rest) | Persist boundary erased genuine RPDC evidence | Build `repair_historical_rpdc_verdict_fields.py`: `--dry-run` default producing before/after samples + repairable/blocked counts; writes only with `--apply-historical-rpdc-repair-I-understand` | Pre-repair row snapshot saved to `data/reports/` before any write; restore from snapshot | ☐ |
| C | Schema migration | `velo_verdicts` + `source_truth`, `feature_degraded`, `degraded_reason`, `observability_packet_path`, `rpdc_integrity_status`, `persistence_proof_status` columns | Day health must be queryable on-row | Migration file in `supabase/migrations/` (to be written); apply via operator's Supabase access | Columns are additive/nullable — rollback = drop columns | ☐ |
| D | Learning quarantine | `sentient_state_shadow.json` + Playbook G shadow doctrines from the 23 risk days | Shadow state evolved on degraded/corrupted evidence | No deletion: freeze promotion; rebuild shadow state from post-fix clean days (2026-06-11+) before any shadow→live discussion | Frozen artifact retained untouched | ☐ |
| E | Performance restatement adoption | All public-facing materials (whitepaper, dashboards, Telegram templates) | Old claims exceed the evidence | Replace numbers with PERFORMANCE_RESTATEMENT buckets + claim levels | Git history preserves prior text | ☐ |
| F | Docs correction | Stale docs asserting RPDC sidecar stats / Racing API / unclassified strike rates | Contradict the ledger | Archive sweep per DOCS_CONSOLIDATION_MAP.md | `git mv` is reversible | ☐ |
| G | Public claim correction | Any external statement of "top-tier/top-10 UK" | Ceiling is VERIFIED_INTERNAL | Withdraw/caveat per PERFORMANCE_CLAIM_POLICY.md | n/a | ☐ |

**Sequencing if all approved:** C (schema) → B (RPDC repair, dry-run first) → A (ledger rebuild) → D (quarantine policy) → E/F/G (docs and claims).

**Explicitly not repairs:** the 18 attach-failure days (nothing genuine to restore at the verdict level — permanent `RPDC_ATTACH_FAILURE` label); the 18 cron-era days without local backups (no source of truth); anything touching predictions, tiers, or probabilities.
