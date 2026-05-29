# VÉLØ RECOVERY LOOP (V1)
**Author:** Manus AI | **Status:** RATIFIED | **Date:** May 28, 2026 | **Version:** 1.0.0

---

## 1. Introduction
The Recovery Loop is VÉLØ’s active defense mechanism. It monitors the execution of the pipeline, detects anomalies in features, credentials, or scoring outputs, and executes deterministic fallbacks to prevent silent failures, database pollution, or incorrect execution.

---

## 2. Recovery Matrix

The following matrix defines the exact recovery behavior for all ten core failure modes.

| Failure Mode | Detection | Severity | Fallback Behavior | Operator Notice | Learning Status |
|---|---|---|---|---|---|
| **1. RPDC Zero** | `rpdc_coverage == 0` | **CRITICAL** | Abort scoring; fallback to `VISION_ONLY` static card. | Urgent Telegram & Dashboard banner. | **BLOCKED** |
| **2. Improvement Constant** | `std(improvement_score) == 0` | **DEGRADED** | Fall back to default model weights; suppress `improvement_score` signal. | Dashboard warning: `FEATURE_DEGRADED`. | **BLOCKED** |
| **3. OFR/RPR/Age Missing** | `null_count(ofr, rpr) > 0.5 * n` | **DEGRADED** | Hydrate missing values using running course means. | Log warning in `run_prime_today.py`. | **ALLOWED** (degraded) |
| **4. Supabase Missing** | HTTP connection timeout or 401 | **CRITICAL** | Write to local JSON archive (`data/velo_prime_verdicts_{date}.json`). | Urgent Telegram: `SUPABASE_WRITE_FAIL`. | **BLOCKED** |
| **5. decision_tier NULL** | `decision_tier is None` after scoring | **CRITICAL** | Abort run; execute persistence rollback. | Urgent Telegram: `DECISION_SYNTH_FAIL`. | **BLOCKED** |
| **6. git_commit_sha Missing** | `get_commit_sha() == ""` | **CRITICAL** | Refuse database write; default to dry-run mode. | Log error: `UNFINGERPRINTED_RUN`. | **BLOCKED** |
| **7. Identity Mismatch** | `loaded_date != requested_date` | **CRITICAL** | Hard abort; do not score. | Log error: `DATE_MISMATCH_ABORT`. | **BLOCKED** |
| **8. Flatline Score Collapse** | `len(set(vps)) <= 2` or top group > 60% | **CRITICAL** | Flag race `SCORING_COLLAPSED`; block execution. | Dashboard banner: `⚠ RP_FEATURE_FLATLINE`. | **BLOCKED** |
| **9. Stale Council Verdict** | `council_verdict_age > 48h` | **DEGRADED** | Bypass Council weight overrides; fall back to baseline. | Telegram warning: `STALE_COUNCIL_OVERRIDE`. | **ALLOWED** |
| **10. Source Truth Unknown** | `source_label == "unknown"` | **CRITICAL** | Hard abort; block normalization. | Urgent Telegram: `UNKNOWN_SOURCE_BLOCK`. | **BLOCKED** |

---

## 3. Recovery Workflows

### Workflow A: Flatline Score Collapse (Gate 2)
When `src/velo/feature_audit.py` detects a flatline condition where probabilities do not differentiate:
1. Assign `rp_flatline_warning` to the race payload.
2. Store warning inside `full_analysis.governance` in Supabase [1].
3. Set `decision_tier = "X"` and `execution_allowed = False`.
4. Trigger the `⚠ RP_FEATURE_FLATLINE` banner on the operator dashboard [1].

### Workflow B: Supabase Credential Loss
When the pipeline cannot reach Supabase:
1. Intercept exception in `run_prime_today.py` [2].
2. Divert all scored race verdicts to `/home/ubuntu/velo-oracle-prime/data/velo_prime_verdicts_{date}.json` [2].
3. Format and send emergency Telegram alert to the operator containing the local backup path.
4. Set exit code to `1` (FAIL) but preserve the local JSON artifacts for manual recovery [2].

### Workflow C: Learning Eligibility Block (Gate 6)
When any degraded feature, constant value, or flatline condition is detected during the run:
1. Append the run to `data/nightly_eod_learning_failures_{date}.json`.
2. Set `learning_eligible = False` in the run's metadata.
3. The Sigma backtesting and training engine must read this flag and strictly exclude the date from walk-forward optimization to prevent model contamination.

---

## References
* [1] Git Commit `9670e90` - Wiring of `RP_FEATURE_FLATLINE` warning into dashboard.
* [2] `scripts/ops/run_prime_today.py` - Local fallback and pipeline run recovery handlers.
