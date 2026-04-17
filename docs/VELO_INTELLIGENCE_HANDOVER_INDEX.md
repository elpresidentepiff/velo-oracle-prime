# VÉLØ INTELLIGENCE HANDOVER INDEX
**Last updated:** 2026-03-21

This document is the single reference for the state of the intelligence stack.
Updated after every major build phase.

---

## INTELLIGENCE SCHEMA — TABLE REGISTRY

### intelligence schema (5-layer stack)

| Table | Rows (2025) | Rows (2024) | Purpose |
|---|---|---|---|
| `intelligence.plot_candidate_flags_2025` | 84,049 | — | Master flag layer. Source of truth for RPD-C inputs. |
| `intelligence.plot_candidate_flags_2024` | — | 169,702 | Same, 2024 season. |
| `intelligence.handicap_trajectory_2025` | 84,049 | — | OR trajectory, peak OR, compression flags. |
| `intelligence.handicap_trajectory_2024` | — | 169,702 | Same, 2024. |
| `intelligence.setup_restore_events_2025` | 84,049 | — | Trip/course/surface restore signals. |
| `intelligence.setup_restore_events_2024` | — | 169,702 | Same, 2024. |
| `intelligence.horse_run_history_2025` | 84,049 | — | Run-by-run history, win flags, run numbers. |
| `intelligence.horse_run_history_2024` | — | 169,702 | Same, 2024. |
| `intelligence.rpdc_tags_2025` | 84,049 | — | **RPD-C tags — 2025 full season. LIVE.** |
| `intelligence.rpdc_tags_2024` | — | 169,702 | **RPD-C tags — 2024 full season. LIVE.** |

### public schema — production tables

| Table | Rows | Status | Purpose |
|---|---|---|---|
| `public.runner_race_facts` | 243 | LIVE | Per-runner derived facts. Includes rpdc_tag_base (live, low-confidence). |
| `public.horse_profiles` | 243 | LIVE | Horse profiles. |
| `public.trainer_profiles` | 132 | LIVE | Trainer profiles. |
| `public.jockey_profiles` | 118 | LIVE | Jockey profiles. |
| `public.horse_comments` | 1,765 | LIVE | NLP spotlight flags. |
| `public.gear_medical_events` | 440 | LIVE | Gear/medical event log. |
| `public.rpd_tags` | 0 | **DEPRECATED** | Never populated. Use `intelligence.rpdc_tags_*` instead. |
| `public.velo_verdicts` | 22 | LIVE | Final betting verdicts. |
| `public.plot_memory_spine` | 0 | EMPTY | PJI scoring — not yet populated. |

### BHA macro tables

| Table | Rows | Purpose |
|---|---|---|
| `public.bha_industry_stats` | 246 | Atomic BHA metrics 2012–2024 |
| `public.bha_yearly_summary` | 13 | One row per year — fixtures, field sizes |
| `public.bha_macro_specialty_metrics` | 132 | Going distribution, HIT breakdown |

---

## RPD-C ENGINE

| Component | Location | Status |
|---|---|---|
| Live engine | `src/rpd/rpdc_rules.py` | ✅ LIVE — single source of truth |
| Original engine | `src/rpd/rpd_v2.py.deprecated` | ❌ ARCHIVED — do not use |
| Backfill script | `scripts/build_rpdc_intelligence_stack.py` | ✅ Complete. Idempotent. |
| Schema migration | `scripts/add_rpdc_columns.py` | ✅ Run. `runner_race_facts` has rpdc columns. |

### RPD-C Tag Distribution (verified 2026-03-21)

| Tag | 2025 | 2025 % | 2024 | 2024 % |
|---|---|---|---|---|
| T (Target) | 5,255 | 6.3% | 16,778 | 9.9% |
| H (Honest) | 18,937 | 22.5% | 38,248 | 22.5% |
| S (Speculative) | 56,935 | 67.7% | 102,329 | 60.3% |
| P (Prep) | 2,880 | 3.4% | 12,167 | 7.2% |
| E (Exhausted) | 42 | 0.1% | 180 | 0.1% |

**S dominance is expected and correct.** Most runners in any season lack a within-year win reference — S is the honest classification.

---

## VOX AGENT

| Component | Location | Status |
|---|---|---|
| OpenRouter adapter | `workers/velo_vox/providers/openrouter_client.py` | ✅ LIVE |
| Agent loop | `workers/velo_vox/agent_loop.py` | ✅ LIVE — Python-first, full intent detection |
| Evidence builder | `workers/velo_vox/evidence_builder.py` | ✅ LIVE |
| Tool layer | `workers/velo_vox/agent_tools.py` | ✅ LIVE |
| Telegram bot | `workers/velo_vox/telegram_bot.py` | ✅ LIVE — @Velovoxbot |
| System prompt | `workers/velo_vox/templates/vox_agent_system.txt` | ✅ LIVE |
| Model | MiniMax (minimax-m2.7) via OpenRouter | ✅ CONNECTED |

---

## DAILY PIPELINE

| Component | Location | Status |
|---|---|---|
| Main pipeline | `workers/daily_pipeline.py` | ✅ LIVE |
| RPD-C live tagger | `src/rpd/rpdc_rules.tag_from_live_runner()` | ✅ WIRED — runs on every upsert |
| rpd_tag field | `runner_race_facts.rpd_tag` | BLANK — not populated (correct) |
| rpdc_tag_base | `runner_race_facts.rpdc_tag_base` | ✅ Populated by live tagger (low-confidence) |

---

## OUTSTANDING ACTIONS (priority order)

| # | Action | Script | Status |
|---|---|---|---|
| 1 | Add `rpdc_override_tag` / `rpdc_override_reason` to both years | `scripts/add_rpdc_override_fields.py` | ❌ TODO |
| 2 | Create retrieval views for TEXT[] → JSONB convenience | `scripts/create_rpdc_views.py` | ❌ TODO |
| 3 | Annotate `public.rpd_tags` as deprecated | SQL one-liner | ❌ TODO |
| 4 | Archive `rpd_v2.py` | `mv src/rpd/rpd_v2.py src/rpd/rpd_v2.py.deprecated` | ❌ TODO |
| 5 | Verify backfill integrity | `scripts/verify_rpdc_backfill.py` | ❌ TODO |
| 6 | Wire `intelligence.rpdc_tags_*` into VOX evidence (historical > live) | `workers/velo_vox/evidence_builder.py` | ❌ TODO |
| 7 | Deploy VOX bot to Railway (persistent) | Railway service config | ❌ DEFERRED |
| 8 | SIGMA forensic loop | new module | ❌ DEFERRED |

---

## REPORT ARCHIVE

| Date | Report | Contents |
|---|---|---|
| 2026-03-21 | `reports/daily/rpdc_2025_2024_state_audit_2026-03-21.md` | Full state audit |
| 2026-03-21 | `reports/daily/rpdc_2025_2024_derivation_map_2026-03-21.md` | Tag derivation rules |
| 2026-03-21 | `reports/daily/rpdc_2025_2024_backfill_plan_2026-03-21.md` | Backfill status + verification |
| 2026-03-21 | `reports/daily/rpdc_2025_2024_claude_prep_2026-03-21.md` | Claude execution brief |

---

## KEY PRINCIPLES (never violate)

1. LLM never classifies RPD-C base tags. Deterministic rules only.
2. Supabase is the system of record. No SQLite persistence.
3. `run_style` is never used as a proxy for `rpd_tag` or `rpdc_tag_base`.
4. `public.rpd_tags` is dead. Do not query or populate it.
5. `intelligence.rpdc_tags_*` are the canonical historical RPD-C store.
6. No Railway changes without explicit instruction.
7. No live scoring changes without explicit instruction.
