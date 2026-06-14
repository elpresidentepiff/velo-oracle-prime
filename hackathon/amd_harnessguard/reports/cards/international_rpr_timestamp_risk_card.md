# Incident Report Card: Incident C: International RPR Leakage Risk
- **ID:** `international_rpr_timestamp_risk`
- **Severity:** `CRITICAL`
- **Status:** BLOCKED

## Executive Summary
BLOCK_LEARNING / OPERATOR_REVIEW

## Mathematical Proof
- TEMPORAL_LEAKAGE: Detected 50 records with RETROSPECTIVE_SIGNAL_TEST_WITH_LEAKAGE_RISK.

## Affected Features
leakage_status

## Operator Recovery
```bash
python scripts/ops/verify_ts_coverage.py --audit-rpr
```
