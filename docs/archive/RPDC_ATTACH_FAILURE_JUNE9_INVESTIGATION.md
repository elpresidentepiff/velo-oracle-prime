# RPDC ATTACH FAILURE — JUNE 9 INVESTIGATION

**Date:** 2026-06-10 · Trigger: Loop 3 (`check_rpdc_integrity.py`) reported `RPDC_UNKNOWN / ATTACH_FAILURE_SUSPECTED` for 2026-06-09.

## Verdict: ROOT CAUSE PROVEN — synthetic-vs-real ID mismatch on the PDF-bypass path

| Layer | June 9 (bypass day) | June 10 (normal day) |
|---|---|---|
| RPDC candidates (`runner_release_candidates`) | **632 rows, REAL IDs** — race_id `919911`, horse_id `2753137` (built from the real injection JSON at 03:40 UTC) | 381 rows, real IDs |
| Scoring race_ids (local verdict backup) | **SYNTHETIC** — `rp_BRIGHTON_20260609_6.21` | real — `919917` |
| Scoring horse_ids | **SYNTHETIC** — `rp_BRIGHTON_banksman` | real — `7441070` |
| Attach result | `no_data` × 33 (all races) | `attached` × 34 |

**Proof by example:** Banksman ran June 9. Candidates table has him as horse_id `6350106` in race `920127` with tags `["PLACE_FORM"]`. Scoring looked him up as `rp_BRIGHTON_banksman` in race `rp_BRIGHTON_20260609_6.21`. Zero rows joined. RPDC data was present and correct the entire time.

## Exact mechanism
1. June 9 used the **June 9 Override** (THE_NEW_TRUTH): capture problems forced high-integrity PDFs (Brighton, Carlisle, Salisbury, Sligo, Southwell) to be converted into `rp_merged` JSON. That converter has no access to RP numeric IDs, so it minted synthetic `rp_{VENUE}_{...}` race and horse IDs.
2. `build_rpdc_daily.py` ran from the **real injection JSON** → wrote candidates under real IDs.
3. `scripts/ops/run_prime_today.py:1341` `_fetch_race_rpdc(race_id)` queries `runner_release_candidates?race_id=eq.{race_id}` with the **synthetic** race_id → `[]` → `_attach_rpdc_from_row(top, None)` → `no_data`.
4. Silence mechanism: the per-race "RPDC zero-runner warning" goes to the log only; observability `gate_5_rpdc_warn_fires` is computed from `len(scored) < len(normalized)` (`run_prime_today.py:2313`) — i.e. it measures *scoring* coverage, not RPDC coverage. All races scored, so the gate stayed green.

## Last known healthy comparison
June 10 (real-ID day): attach 34/34 locally. The attach code is correct when the ID universes agree; the bug lives at the **boundary between the bypass card builder and the RPDC build**, exactly the class of boundary failure that hit Mission Control and persistence.

## Can June 11 repeat this?
**Yes, conditionally.** The normal RP HTML path produces real IDs and attaches fine. The failure recurs if and only if a capture/session failure forces the PDF bypass again — which is precisely the situation where nobody is watching details. Hence two defenses, both shipped with this investigation:
1. **Pre-score preflight** (`check_rpdc_attach_preflight.py`) — proves candidates can join today's card BEFORE scoring; gates the day per the go/no-go rules.
2. **Deterministic attach fallback** — when the exact race_id join returns nothing, attach by `run_date` + normalized horse name, unique-match-only; ambiguity returns `no_data` (never invented data); `attach_method` recorded per pick.

## Answers required by the command
- Candidate count (June 9): 632 · local runners scored: 33 races (~380 runners) · attached: **0**
- Candidate race_id examples: `919911`, `920127` · scoring race_id examples: `rp_BRIGHTON_20260609_6.21`, `rp_SOUTHWELL_20260609_4.30`
- Mismatch type: **synthetic vs real identifier universes** (race_id AND horse_id)
- Function: `_fetch_race_rpdc` (`scripts/ops/run_prime_today.py:1341`) — not wrong itself; starved by upstream bypass IDs
- June 11 at risk: only on bypass; preflight now gates it
- Recommended safe fix: deterministic name fallback + preflight gate (Tasks 2–3) — **no historical backfill, no old-verdict mutation**
