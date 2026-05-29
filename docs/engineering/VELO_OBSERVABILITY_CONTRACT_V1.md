# VÉLØ OBSERVABILITY CONTRACT (V1)
**Author:** Manus AI | **Status:** RATIFIED | **Date:** May 28, 2026 | **Version:** 1.0.0

---

## 1. Introduction
Every pipeline run must explain itself. "Black-box" execution is unacceptable. This contract mandates that every execution of the VÉLØ Prime pipeline must produce a structured, auditable **Run Observability Packet** to ensure absolute transparency of source data, features, code versions, and learning eligibility.

---

## 2. Mandatory Run Output Schema

Every run must record and persist the following 11 observability metrics:

| Metric Name | Type | Description | Verification Source |
|---|---|---|---|
| `source_truth` | `string` | The declared input source label (e.g., `RP_MERGED_CLEAN`). | `racecard_loader.py` [1] |
| `feature_health` | `string` | Status of feature standard deviations (`HEALTHY` or `DEGRADED`). | `feature_audit.py` [2] |
| `active_formula` | `string` | The exact scoring formula and weight profile active. | `weight_policy_registry.py` |
| `excluded_live_components`| `array` | List of features excluded due to missing inputs. | `run_prime_today.py` |
| `rpdc_coverage` | `float` | Percentage of runners with complete RPDC data. | `complete_pdf_parser.py` |
| `ratings_source_status` | `string` | Health of OFR, RPR, and TS ratings (`OK` or `MISSING`). | `racecard_loader.py` [1] |
| `supabase_write_proof` | `boolean`| Whether verdicts successfully persisted to Supabase. | `run_prime_today.py` [3] |
| `decision_tier_status` | `string` | Status of decision synthesis (`PASS`, `DEGRADED`, `FAIL`). | `run_prime_today.py` [3] |
| `git_commit_sha` | `string` | The exact 40-character git commit hash of the run. | `runtime_truth_support.py` |
| `learning_gate` | `string` | Learning status (`ELIGIBLE` or `BLOCKED_DEGRADED`). | `feature_audit.py` [2] |
| `next_safe_command` | `string` | The recommended next operator command. | Operator Protocol |

---

## 3. Observability File Artifacts

### A. Run Snapshot JSON (`data/velo_run_observability_{date}_{run_id}.json`)
At the completion of STEP 7 in the pipeline [3], the system must output a comprehensive JSON file containing the full run state:

```json
{
  "run_id": "2026_05_28_a33c5bd9_1779907858",
  "timestamp": "2026-05-28T12:00:00Z",
  "git_commit_sha": "a33c5bd99153c4e6abc8cd31283aa5d46bcbaa22",
  "source_truth": "RP_MERGED_CLEAN",
  "feature_health": "HEALTHY",
  "active_formula": "VELO_PRIME_V10_1_SQR",
  "metrics": {
    "races_processed": 33,
    "runners_processed": 269,
    "rpdc_coverage_pct": 100.0,
    "supabase_write_success": true
  },
  "gates": {
    "gate_2_flatline_fires": false,
    "gate_5_rpdc_warn_fires": false,
    "gate_6_learning_blocked": false
  }
}
```

### B. Daily Truth Watchdog Markdown (`data/velo_daily_run_truth_{date}.md`)
The watchdog system must automatically parse the run snapshot and compile the daily human-readable markdown report to verify database writes and alert status [4].

---

## References
* [1] `src/velo/racecard_loader.py` - Ingestion source classification and verification.
* [2] `src/velo/feature_audit.py` - Scoring feature audits and flatline detection.
* [3] `scripts/ops/run_prime_today.py` - Pipeline run metrics and DB persistence step.
* [4] `velo_daily_run_truth_watchdog.py` - Automated watchdog report generator.
