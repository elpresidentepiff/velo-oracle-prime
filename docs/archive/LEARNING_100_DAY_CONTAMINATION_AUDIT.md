# LEARNING — 100-DAY CONTAMINATION AUDIT

**Date:** 2026-06-10 · Evidence: nightly learning status files, Playbook G audits, ledger classifications, artifact mtimes.

## Headline
Learning ran on **23 days** (2026-04-29 → 2026-06-08). Under the ledger's strict rules, **zero of those days were SIGNED_CLEAN**, so all 23 carry `LEARNING_CONTAMINATION_RISK`. The decisive mitigation: **every one of the 23 runs recorded `live_sentient_state_touched: false`** — learning was shadow-only throughout. Live weights, the live ensemble profile, and live scoring behaviour were never trained on contaminated days.

## Per-day classification of the 23 learning days

| Learning-day class | Days | Meaning |
|---|---|---|
| `LEARNING_ADMITTED_DEGRADED_RISK` (RPDC_PERSIST_CORRUPTED window) | 16 | Shadow learning consumed days whose RPDC evidence labels were corrupted |
| `LEARNING_ADMITTED_DEGRADED_RISK` (RPDC_ATTACH_FAILURE) | 5 (Apr 29, May 2–5) | Shadow learning consumed days where RPDC never attached |
| `LEARNING_UNKNOWN` (HISTORICAL_OUTPUT_ONLY) | 1 (Apr 29-era) | Insufficient evidence to classify the day |
| `LEARNING_ADMITTED_DEGRADED_RISK` (PERSISTENCE_UNPROVEN) | 1 (May 29) | Local output without Supabase proof |
| `LEARNING_ADMITTED_CLEAN` | **0** | — |
| `LEARNING_CONTAMINATION_CONFIRMED` (live state) | **0** | live state untouched on all runs |

## What the contaminated shadow learning touched

| Artifact | Status | Quarantine proposal |
|---|---|---|
| `data/sentient_state_shadow.json` (Playbook G shadow state, mtime 2026-06-09) | Evolved from 23 risk days | Freeze: rename-copy to `quarantine/` namespace conceptually — i.e. mark in ledger; **do not promote shadow→live until rebuilt from a clean window** |
| `data/sigma_memory/sigma_retrieval_corpus_v1.jsonl` (retrieval memory) | Rebuilt through Jun 9; corpus governance already excluded May 20 | Acceptable for retrieval (it stores results, not RPDC labels); flag RPDC-tag fields inside it as unreliable for the window |
| `data/velo_innovation_protocol_1k_deduped.csv` (router evidence) | Includes `rpdc_release_score` columns from the corrupted window | Router lane SR/ROI stats unaffected (driven by results+SP); any RPDC-conditioned analysis void for the window |
| `data/sentient_state.json` (LIVE state, mtime 2026-05-02 12:37) | Changed once, on the Playbook G training day (2026-05-02, HFS_TRAINING_READY — operator-sanctioned event per project records) | **Operator confirm:** that May 2 change was the sanctioned training event and not a nightly leak. All nightly runs report false for live-touch, including May 2's. |
| Supabase `learned_patterns` (344 rows) | Not dated in this audit | Include in repair packet review |

## Council admissions
Council artifacts exist from May 1; recent verdicts were `WATCH_ONLY` (learning gates BLOCKED at MC level on the recent days). The nightly runner nonetheless produced shadow learning artifacts on blocked days — confirming the known gap: **the learning runner does not read the Council verdict before running** (it writes its own audit with a default verdict). That gap is queued as the L8 enforcement fix and is why gate-bypass was possible.

## Proposed quarantine (NO action taken — approval required)
1. **Do not promote** `sentient_state_shadow.json` or any Playbook G shadow doctrine to live until re-derived from post-fix clean days (earliest clean candidate: 2026-06-11 onward).
2. Label the 23 learning days `LEARNING_ADMITTED_DEGRADED_RISK` in the ledger (done — read-only label).
3. Void RPDC-conditioned learning conclusions from the window (e.g. any doctrine weighted on rpdc_release_score).
4. L8 enforcement fix: learning runner refuses to start without Council `PASS_TO_LEARNING` + MC gate OPEN + persistence proof PASS (queued, NEXT_10).
5. Nothing deleted. Nothing mutated. All artifacts remain for review.
