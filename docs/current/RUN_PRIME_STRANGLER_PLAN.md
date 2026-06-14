# RUN_PRIME_TODAY — STRANGLER PLAN

**Date:** 2026-06-10 · Target: `scripts/ops/run_prime_today.py` (112KB, ~2,400 lines). Method: **extract, never rewrite.** Zero scoring-logic change, zero weight change, zero behaviour change per stage — proven by the golden-day replay after every extraction.

## Why strangler, not rewrite
The persist hijack lived 7 weeks inside this file because no human can hold it in their head; we also found an entire `full_analysis` dict that is built and then discarded (dead code on the hot path). A rewrite risks the exact silent behaviour changes we just spent a week eradicating. Extraction with replay-diff proof risks nothing.

## Target shape — `src/velo/pipeline/`

| # | Module | Extracted responsibility | Boundary test |
|---|---|---|---|
| 1 | `load_card.py` | racecard_loader call + source selection | source label fixture tests (exist) |
| 2 | `validate_sources.py` | source_truth_enforcer wiring | exist (`test_harness_wiring`) |
| 3 | `build_features.py` | pdf_intel attach, feature assembly | golden-runner fixture |
| 4 | `score_runners.py` | `score_race_velo_prime` call only — **weights frozen, untouched** | replay diff |
| 5 | `attach_rpdc.py` | `_fetch_race_rpdc` + `rpdc_attach` resolver (already pure) | exist (8 tests) |
| 6 | `attach_pdf_intel.py` | BHA badges + spotlight passthrough | timing-audit counts |
| 7 | `build_verdict_payload.py` | the persist row builder (move OUT of velo_prime_service monolith too) | exist (4 boundary tests) |
| 8 | `persist_verdicts.py` | Supabase upsert + local backup | mock-upsert capture |
| 9 | `write_observability.py` | packet + timing + telegram truth | schema tests (exist) |
| 10 | `prove_persistence.py` | call the proof script, attach status | exist (proof tool) |

`run_prime_today.py` ends as a ~100-line orchestrator calling 1→10. Same CLI, same flags, same outputs, byte-comparable artifacts.

## The golden-day replay test (the keystone — build FIRST)
June 10's complete inputs exist on disk (injection, merged files, RPDC rows snapshot-able, BHA CSVs). A CI-runnable test:
1. Replays the full scoring chain offline (Supabase mocked from recorded responses).
2. Asserts: 34 verdicts, identical tiers, identical VP values (4dp), identical `active_components`, RPDC attach 34/34, payload RPDC fields genuine.
3. Runs on every PR. Any silent behaviour change = red build.

Extraction order: replay test → 7/8 (persist, highest risk history) → 5 (attach) → 2 (validate) → the rest, one module per PR, replay green between each.

## Rules
- One module per commit/PR; replay diff attached to each.
- No formula edits, no weight edits, no new features during extraction.
- Dead code found during extraction is deleted only in its own commit with the replay proving no effect.
- Live race days take precedence: extraction never lands on a race-day morning.

**Approval needed:** plan approval to begin; per-PR review thereafter. Estimated: 2–3 weeks at one module every other day, fully interruptible.
