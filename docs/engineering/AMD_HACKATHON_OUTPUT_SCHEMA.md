# HarnessGuard Output Schema — Incident Report Card

## 1. Purpose
This schema defines the structured JSON artifact emitted by the HarnessGuard agent after auditing a prediction pipeline. It provides a standardized "handshake" between the detection layer and the policy enforcement layer.

## 2. JSON Schema Definition
```json
{
  "incident_id": "STRING (e.g. RPDC_2026-05-24)",
  "detection_time": "ISO_TIMESTAMP",
  "severity": "CRITICAL | HIGH | MEDIUM | LOW",
  "evidence_source": "STRING (Path to artifact)",
  "feature_health": {
    "FEATURE_NAME": {
      "status": "HEALTHY | DEGRADED | FAILED",
      "reason": "STRING (e.g. constant_value_detected | high_null_ratio)",
      "metrics": {
        "expected_variance": "FLOAT",
        "observed_variance": "FLOAT",
        "null_ratio": "FLOAT",
        "drift_score": "FLOAT"
      }
    }
  },
  "policy_evaluation": {
    "learning_eligibility": "ALLOWED | BLOCKED",
    "execution_eligibility": "ALLOWED | BLOCKED",
    "violations": ["STRING (Policy codes)"]
  },
  "recovery_plan": {
    "recommended_action": "STRING (High-level directive)",
    "operator_message": "STRING (Plain English explanation)",
    "safe_next_command": "STRING (Exact CLI command to run)"
  },
  "amd_benchmark": {
    "inference_device": "AMD Instinct MI300X",
    "latency_ms": "FLOAT",
    "throughput_signals_per_sec": "FLOAT"
  }
}
```

## 3. Example Instance (Incident A)
```json
{
  "incident_id": "RPDC_FLATLINE_2026-05-24",
  "detection_time": "2026-06-05T11:45:00Z",
  "severity": "CRITICAL",
  "feature_health": {
    "improvement_score": {
      "status": "DEGRADED",
      "reason": "constant_value_detected",
      "metrics": {
        "expected_variance": 0.12,
        "observed_variance": 0.0,
        "fallback_value": 0.0872
      }
    }
  },
  "policy_evaluation": {
    "learning_eligibility": "BLOCKED",
    "violations": ["POLICY_ZERO_VARIANCE_CRITICAL"]
  },
  "recovery_plan": {
    "recommended_action": "HALT_PIPELINE_AND_REINDEX_SOURCE",
    "operator_message": "The 'improvement_score' feature has flatlined across 100% of runners. This typically indicates an upstream API change or fallback trigger. Learning is disabled to prevent weight poisoning.",
    "safe_next_command": "PYTHONPATH=. python scripts/ops/reindex_feature_source.py --feature improvement_score"
  }
}
```
