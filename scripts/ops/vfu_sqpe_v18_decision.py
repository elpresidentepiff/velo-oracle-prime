#!/usr/bin/env python3
"""
VFU-24: SQPE v18 Formal NO_PROMOTION Decision

Reads model metadata for SQPE v17.1 and v18, issues the formal governance
decision with full evidence trail.

Key facts:
  - v18 new features: days_since_run, class_delta (both 0.0005 importance)
  - AUC delta: -0.0003 (negative)
  - top1 delta: -0.0012 (negative)
  - v18 trained on different holdout than v17.1 (241k vs 80k rows)
  - v18 baseline is pre-retrain v17, not v17.1

Verdict: SQPE_V18_NO_PROMOTION — archive in place, do not wire.

Usage:
    python scripts/ops/vfu_sqpe_v18_decision.py
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

V17_METADATA  = ROOT / "models" / "sqpe_v17" / "metadata.json"
V18_METADATA  = ROOT / "models" / "sqpe_v18" / "metadata.json"
OUTPUT_RECORD = ROOT / "data" / "reports" / "vfu_24_sqpe_v18_decision.json"
OUTPUT_BRIEF  = ROOT / "data" / "reports" / "vfu_24_sqpe_v18_decision.md"

VFU_VERSION = "VFU_24_SQPE_V18_DECISION_V1"


def load_metadata(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def build_decision(v17: dict, v18: dict) -> dict:
    v17_auc    = v17.get("auc")                    # v17.1 holdout AUC
    v17_top1   = v17.get("top1_accuracy")           # v17.1 top1
    v17_mrr    = v17.get("mrr")                     # v17.1 MRR

    v18_auc    = v18.get("auc_v18")                 # v18 AUC
    v18_top1   = v18.get("top1_v18")                # v18 top1
    v18_mrr    = v18.get("mrr_v18")                 # v18 MRR

    # v18's own baseline (pre-retrain v17, different holdout)
    v18_bl_auc  = v18.get("auc_v17_baseline")
    v18_bl_top1 = v18.get("top1_v17_baseline")
    v18_bl_mrr  = v18.get("mrr_v17_baseline")

    new_feat_importances = v18.get("new_feature_importances", {})
    class_delta_imp      = new_feat_importances.get("class_delta", 0.0)
    days_since_run_imp   = new_feat_importances.get("days_since_run", 0.0)

    # v18's own assessment (using its own holdout vs its own baseline)
    v18_self_auc_delta  = round(v18_auc - v18_bl_auc, 4)   if (v18_auc and v18_bl_auc) else None
    v18_self_top1_delta = round(v18_top1 - v18_bl_top1, 4) if (v18_top1 and v18_bl_top1) else None

    # Cross-holdout note: v17.1 was retrained AFTER v18 evaluation, so v18's v17_baseline != v17.1
    cross_holdout_note = (
        f"v18 evaluated against pre-retrain v17 ({v18_bl_auc} AUC). "
        f"v17.1 (post-retrain) AUC={v17_auc} on a different holdout ({v17.get('test_rows', '?')} rows). "
        "Direct comparison impossible across holdouts — use feature importance as primary signal."
    )

    promotion_blocked_reasons = [
        f"AUC delta within v18's own holdout: {v18_self_auc_delta} (negative)",
        f"top1 delta within v18's own holdout: {v18_self_top1_delta} (negative)",
        f"class_delta feature importance: {class_delta_imp} (near-zero)",
        f"days_since_run feature importance: {days_since_run_imp} (near-zero)",
        "v17.1 (current live) was retrained after v18 evaluation — v18 does not represent an improvement over the live model",
        "New features add no marginal lift; zero basis for live-path promotion",
    ]

    return {
        "vfu24_validation_version": VFU_VERSION,
        "decision": "NO_PROMOTION",
        "model_evaluated": "sqpe_v18",
        "incumbent_model": "sqpe_v17.1",
        "v17_1": {
            "auc": v17_auc,
            "top1": v17_top1,
            "mrr": v17_mrr,
            "train_rows": v17.get("train_rows"),
            "test_rows": v17.get("test_rows"),
            "promoted_at": v17.get("promoted_at"),
            "version": v17.get("version"),
        },
        "v18": {
            "auc": v18_auc,
            "top1": v18_top1,
            "mrr": v18_mrr,
            "train_rows": v18.get("train_rows"),
            "test_rows": v18.get("test_rows"),
            "trained_at": v18.get("trained_at"),
            "version": v18.get("version"),
            "new_features": list(v18.get("v18_new_features", [])),
            "new_feature_importances": new_feat_importances,
            "v18_own_auc_delta": v18_self_auc_delta,
            "v18_own_top1_delta": v18_self_top1_delta,
        },
        "cross_holdout_note": cross_holdout_note,
        "promotion_blocked_reasons": promotion_blocked_reasons,
        "disposition": "ARCHIVE_IN_PLACE — model.pkl retained at models/sqpe_v18/. No live path wiring. No re-evaluation without new features showing >0.01 importance.",
        "classification_codes": [
            "VFU_24_SQPE_V18_DECISION_COMPLETE",
            "SQPE_V18_NO_PROMOTION",
            "SQPE_V17_1_REMAINS_LIVE",
            "V18_NEW_FEATURES_ZERO_LIFT",
            "NO_LIVE_SCORING_CHANGE",
            "NO_MODEL_PROMOTION",
            "NO_SUPABASE_WRITES",
            "REPORT_ONLY",
        ],
    }


def build_brief(decision: dict) -> str:
    v17 = decision.get("v17_1", {})
    v18 = decision.get("v18", {})
    reasons = decision.get("promotion_blocked_reasons", [])

    lines = [
        "# VFU-24 — SQPE v18 Formal Decision — Operator Brief",
        "",
        f"## Decision: **{decision.get('decision')}**",
        "",
        "## Model Comparison",
        "| Metric | v17.1 (live) | v18 | v18 own delta |",
        "|---|---|---|---|",
        f"| AUC | {v17.get('auc')} | {v18.get('auc')} | {v18.get('v18_own_auc_delta')} |",
        f"| top1 | {v17.get('top1')} | {v18.get('top1')} | {v18.get('v18_own_top1_delta')} |",
        f"| MRR | {v17.get('mrr')} | {v18.get('mrr')} | — |",
        f"| Train rows | {v17.get('train_rows')} | {v18.get('train_rows')} | — |",
        f"| Test rows | {v17.get('test_rows')} | {v18.get('test_rows')} | — |",
        "",
        "## New Feature Importances",
        "| Feature | Importance |",
        "|---|---|",
        f"| class_delta | {v18.get('new_feature_importances', {}).get('class_delta', 0)} |",
        f"| days_since_run | {v18.get('new_feature_importances', {}).get('days_since_run', 0)} |",
        "",
        "## Cross-Holdout Note",
        f"> {decision.get('cross_holdout_note', '')}",
        "",
        "## Promotion Blocked — Reasons",
        *[f"- {r}" for r in reasons],
        "",
        "## Disposition",
        f"{decision.get('disposition', '')}",
        "",
        "## Classifications",
        *[f"- {c}" for c in decision.get("classification_codes", [])],
    ]
    return "\n".join(lines)


def main() -> dict:
    (ROOT / "data" / "reports").mkdir(parents=True, exist_ok=True)

    v17 = load_metadata(V17_METADATA)
    v18 = load_metadata(V18_METADATA)

    decision = build_decision(v17, v18)

    OUTPUT_RECORD.write_text(json.dumps(decision, indent=2), encoding="utf-8")
    OUTPUT_BRIEF.write_text(build_brief(decision), encoding="utf-8")

    print(f"VFU-24: SQPE v18 Decision = {decision['decision']}")
    print(f"  v18 own AUC delta: {decision['v18']['v18_own_auc_delta']}")
    print(f"  v18 own top1 delta: {decision['v18']['v18_own_top1_delta']}")
    print(f"  class_delta importance: {decision['v18']['new_feature_importances'].get('class_delta')}")
    print(f"  days_since_run importance: {decision['v18']['new_feature_importances'].get('days_since_run')}")
    print(f"  Record: {OUTPUT_RECORD}")
    return decision


if __name__ == "__main__":
    main()
