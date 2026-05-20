"""
sidecar_role_decision_board.py
================================
Synthesizes from live_sidecar_ablation_audit + sqpe_alone_control_audit
to classify each sidecar into a definitive role category.

Input files:
  data/live_sidecar_ablation_audit_latest.json
  data/sqpe_alone_control_audit_latest.json

Output:
  data/sidecar_role_decision_board_latest.json
  data/sidecar_role_decision_board_latest.md

AUDIT ONLY — no model changes, no weight changes.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

INPUT_ABLATION = ROOT / "data" / "live_sidecar_ablation_audit_latest.json"
INPUT_SQPE = ROOT / "data" / "sqpe_alone_control_audit_latest.json"
OUTPUT_JSON = ROOT / "data" / "sidecar_role_decision_board_latest.json"
OUTPUT_MD = ROOT / "data" / "sidecar_role_decision_board_latest.md"

# Role categories
ROLES = {
    "LIVE_WEIGHT_KEEP": "Live-weighted, value positive — keep as-is",
    "LIVE_WEIGHT_REDUCE_CANDIDATE": "Live but shrink weight — pending audit gate",
    "BADGE_ONLY_CANDIDATE": "Remove from probability weighting; keep as operator flag",
    "FRAME_SUPPORT_BADGE": "Helps frame/coverage but not value — badge only",
    "SUPPRESS_BADGE": "Negative signal for suppressing short-priced horses",
    "SHADOW_ONLY": "Not ready for live use — shadow / operator visibility only",
    "FREEZE_CANDIDATE": "Actively hurts — freeze weight at 0",
}

# Sidecars to classify (with current live weight)
SIDECARS = {
    "improvement_score": {
        "current_live_weight": 0.12,
        "ablation_key": "improvement_score",
        "sqpe_config": "SQPE_PLUS_IMPROVEMENT",
        "notes": "Disabled from ensemble by _DISABLED_COMPONENTS but weight declared as 0.12",
    },
    "release_day_prob": {
        "current_live_weight": 0.00,
        "ablation_key": "release_window_score",
        "sqpe_config": None,
        "notes": "Weight=0.00 confirmed, disabled from live ensemble",
    },
    "market_deception_score": {
        "current_live_weight": 0.10,
        "ablation_key": "market_deception_score",
        "sqpe_config": "SQPE_PLUS_MDS",
        "notes": "Live weighted. Highest-lift signal in system (SR=54.8% at MDS>0.5)",
    },
    "place_prob": {
        "current_live_weight": 0.08,
        "ablation_key": "place_prob",
        "sqpe_config": "SQPE_PLUS_PLACE",
        "notes": "Live weighted. place_prob>0.80 SR=31.6% (SQPE evidence)",
    },
    "comment_intel_score": {
        "current_live_weight": 0.00,
        "ablation_key": "comment_intel_score",
        "sqpe_config": None,
        "notes": "Weight=0.00 confirmed, disabled from live ensemble",
    },
    "longshot_score": {
        "current_live_weight": 0.07,
        "ablation_key": "longshot_score",
        "sqpe_config": "SQPE_PLUS_LONGSHOT",
        "notes": "Live weighted. Only fires at SP>=10.",
    },
    "Racing_API_enrichment": {
        "current_live_weight": 0.00,
        "ablation_key": None,
        "sqpe_config": None,
        "notes": "Shadow/operator only. No live weight. Connection/course/distance scores.",
    },
    "CASHRUN": {
        "current_live_weight": 0.00,
        "ablation_key": None,
        "sqpe_config": None,
        "notes": "Pending. Not yet wired. RPDC cash_run_flag — insufficient sample.",
    },
}


def _safe_float(v: Any) -> Optional[float]:
    try:
        if v is None:
            return None
        return float(v)
    except (ValueError, TypeError):
        return None


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"  WARNING: Could not load {path.name}: {e}", file=sys.stderr)
        return {}


def _get_ablation_row(ablation_data: dict, key: str) -> dict:
    for row in ablation_data.get("sidecars", []):
        if row.get("component") == key:
            return row
    return {}


def _get_sqpe_classification(sqpe_data: dict, config_name: str) -> dict:
    for c in sqpe_data.get("classifications", []):
        if c.get("config") == config_name:
            return c
    return {}


def _decide_role(
    sidecar_key: str,
    meta: dict,
    ablation_row: dict,
    sqpe_cls: dict,
) -> tuple[str, str, str]:
    """
    Returns (role, reason, next_gate).
    """
    weight = meta["current_live_weight"]

    # Racing API and CASHRUN — always shadow/operator only
    if sidecar_key in ("Racing_API_enrichment", "CASHRUN"):
        return (
            "SHADOW_ONLY",
            "No live weight. Operator/shadow visibility only. No evidence gate cleared.",
            "Build prospective sample before any promotion discussion",
        )

    # Weight=0 sidecars with confirmed disabled
    if weight == 0.0 and sidecar_key in ("release_day_prob", "comment_intel_score"):
        return (
            "SHADOW_ONLY",
            "Weight=0.00 confirmed. Disabled from live ensemble. Required features not wired.",
            "Wire required features, then run ablation audit with n>=50 before reconsideration",
        )

    # No ablation data
    ablation_class = ablation_row.get("classification") or "UNKNOWN"
    ablation_action = ablation_row.get("action") or "UNKNOWN"
    ablation_roi = _safe_float(ablation_row.get("roi_high"))
    ablation_sr = _safe_float(ablation_row.get("strike_rate_high"))
    ablation_frame = _safe_float(ablation_row.get("frame_rate_high"))
    ablation_sp = _safe_float(ablation_row.get("average_sp_high"))
    ablation_n = ablation_row.get("matched_high_sample_size") or 0

    sqpe_classification = sqpe_cls.get("classification") or "UNKNOWN"
    sqpe_roi = _safe_float(sqpe_cls.get("flat_roi"))

    # Special case: improvement_score — disabled from ensemble but weight declared 0.12
    if sidecar_key == "improvement_score":
        if ablation_class == "OVERBET_RISK" and (ablation_roi is None or ablation_roi < 0):
            return (
                "BADGE_ONLY_CANDIDATE",
                "SR improves at high values (ablation: OVERBET_RISK, ROI negative). "
                "Ablation 2026-04-04 shows it hurts top-1. Weight=0.12 declared but disabled in ensemble. "
                "Evidence: improvement_score>0.40 SR=43.5% — may work as operator badge, not probability weight.",
                "Maintain at DISABLED in _DISABLED_COMPONENTS. Re-enable only if retrained model shows positive ROI",
            )
        return (
            "LIVE_WEIGHT_REDUCE_CANDIDATE",
            f"Ablation class={ablation_class}. Weight declared 0.12 but runtime-disabled. Under audit.",
            "n>=100 with positive ROI required before re-enabling",
        )

    # market_deception_score — live weight 0.10
    if sidecar_key == "market_deception_score":
        if ablation_class == "OVERBET_RISK":
            return (
                "LIVE_WEIGHT_REDUCE_CANDIDATE",
                f"Live weight=0.10. Ablation=OVERBET_RISK (SR={ablation_sr}, ROI={ablation_roi}). "
                "CRITICAL: MDS>0.5 is highest-lift signal SR=54.8%. Risk is in ensemble weight not signal itself. "
                "Recommended: keep in ensemble at reduced weight, maintain as operator badge at MDS>0.5.",
                "Build n>=50 prospective results at MDS>0.5 threshold before weight change",
            )
        if ablation_class == "HELPS_VALUE":
            return (
                "LIVE_WEIGHT_KEEP",
                f"Ablation=HELPS_VALUE. MDS is proven high-lift signal. Keep live at current weight.",
                "Continue monitoring ROI at monthly audit",
            )
        return (
            "LIVE_WEIGHT_REDUCE_CANDIDATE",
            f"Ablation={ablation_class}. Audit pending.",
            "Build n>=50 prospective results",
        )

    # place_prob — live weight 0.08
    if sidecar_key == "place_prob":
        if ablation_class == "OVERBET_RISK":
            return (
                "BADGE_ONLY_CANDIDATE",
                f"Live weight=0.08. Ablation=OVERBET_RISK (SR={ablation_sr}, ROI={ablation_roi}). "
                "Frame improves but ROI is negative. place_prob>0.80 SR=31.6% in unified audit. "
                "Best used as operator coverage badge, not ensemble weight.",
                "Monitor at n>=100. If ROI remains negative, reclassify to FRAME_SUPPORT_BADGE",
            )
        return (
            "LIVE_WEIGHT_REDUCE_CANDIDATE",
            f"Ablation={ablation_class}. Audit pending.",
            "n>=50 prospective results required",
        )

    # longshot_score — live weight 0.07
    if sidecar_key == "longshot_score":
        if ablation_class == "OVERBET_RISK":
            return (
                "BADGE_ONLY_CANDIDATE",
                f"Live weight=0.07. Ablation=OVERBET_RISK (SR={ablation_sr}, ROI={ablation_roi}). "
                "Only fires at SP>=10 — small n. Frame may improve but ROI negative.",
                "Isolate to SP>=10 candidates only. Monitor at n>=30 in that band.",
            )
        if ablation_class in ("HOLDS", "HOLD"):
            return (
                "SHADOW_ONLY",
                "Ablation=HOLD. Insufficient evidence for live weighting.",
                "Build SP>=10 candidate lane, n>=20 before reconsideration",
            )
        return (
            "LIVE_WEIGHT_REDUCE_CANDIDATE",
            f"Ablation={ablation_class}. Limited evidence — SP>=10 sub-population.",
            "Build dedicated SP>=10 sample n>=30",
        )

    # Fallback
    return (
        "SHADOW_ONLY",
        f"Insufficient evidence (ablation={ablation_class}). Default to shadow.",
        "Build evidence gate n>=20 with results",
    )


def run_board() -> dict[str, Any]:
    generated_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    print(f"[sidecar_role_decision_board] Starting at {generated_at}")

    ablation_data = _load_json(INPUT_ABLATION)
    sqpe_data = _load_json(INPUT_SQPE)

    if not ablation_data:
        print(f"  WARNING: {INPUT_ABLATION.name} not found or empty. Run live_sidecar_ablation_audit.py first.")
    if not sqpe_data:
        print(f"  WARNING: {INPUT_SQPE.name} not found or empty. Run sqpe_alone_control_audit.py first.")

    # Baseline context
    sqpe_only_result = next(
        (r for r in sqpe_data.get("configurations", []) if r.get("config") == "SQPE_ONLY"),
        {},
    )

    decisions: list[dict] = []
    for sidecar_key, meta in SIDECARS.items():
        ablation_key = meta.get("ablation_key")
        sqpe_config = meta.get("sqpe_config")

        ablation_row = _get_ablation_row(ablation_data, ablation_key) if ablation_key else {}
        sqpe_cls = _get_sqpe_classification(sqpe_data, sqpe_config) if sqpe_config else {}

        role, reason, next_gate = _decide_role(sidecar_key, meta, ablation_row, sqpe_cls)

        decisions.append({
            "sidecar": sidecar_key,
            "current_live_weight": meta["current_live_weight"],
            "notes": meta["notes"],
            "ablation_classification": ablation_row.get("classification") or "NO_DATA",
            "ablation_roi_high": ablation_row.get("roi_high"),
            "ablation_sr_high": ablation_row.get("strike_rate_high"),
            "ablation_frame_high": ablation_row.get("frame_rate_high"),
            "ablation_avg_sp": ablation_row.get("average_sp_high"),
            "ablation_matched_n": ablation_row.get("matched_high_sample_size") or 0,
            "sqpe_classification": sqpe_cls.get("classification") or "NO_DATA",
            "sqpe_roi": sqpe_cls.get("flat_roi"),
            "recommended_role": role,
            "reason": reason,
            "next_gate": next_gate,
            "evidence_status": (
                "MULTI_SIGNAL" if ablation_row and sqpe_cls else
                "ABLATION_ONLY" if ablation_row else
                "SQPE_ONLY" if sqpe_cls else
                "NO_EVIDENCE"
            ),
        })

    # Role summary
    role_counts: dict[str, int] = {}
    for d in decisions:
        r = d["recommended_role"]
        role_counts[r] = role_counts.get(r, 0) + 1

    return {
        "generated_at": generated_at,
        "ablation_source": str(INPUT_ABLATION.name),
        "sqpe_source": str(INPUT_SQPE.name),
        "ablation_loaded": bool(ablation_data),
        "sqpe_loaded": bool(sqpe_data),
        "sqpe_only_roi": sqpe_only_result.get("flat_roi"),
        "sqpe_only_sr": sqpe_only_result.get("strike_rate"),
        "decisions": decisions,
        "role_summary": role_counts,
    }


def write_outputs(payload: dict[str, Any]) -> None:
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines = [
        "# Sidecar Role Decision Board",
        "",
        f"- Generated: `{payload['generated_at']}`",
        f"- Ablation source: `{payload['ablation_source']}` (loaded: {payload['ablation_loaded']})",
        f"- SQPE source: `{payload['sqpe_source']}` (loaded: {payload['sqpe_loaded']})",
        f"- SQPE-only ROI: `{payload['sqpe_only_roi']}` | SR: `{payload['sqpe_only_sr']}`",
        "",
        "## Decision Board",
        "",
        "| Sidecar | Live Weight | Ablation | Ablation ROI | SQPE Cls | Recommended Role |",
        "|---|---:|---|---:|---|---|",
    ]
    for d in payload["decisions"]:
        def _f(v): return f"{float(v):.4f}" if v is not None else "—"
        lines.append(
            f"| {d['sidecar']} | {d['current_live_weight']:.2f} | "
            f"{d['ablation_classification']} | {_f(d['ablation_roi_high'])} | "
            f"{d['sqpe_classification']} | **{d['recommended_role']}** |"
        )
    lines.append("")

    for d in payload["decisions"]:
        lines += [
            f"### {d['sidecar']}",
            "",
            f"- **Recommended role:** `{d['recommended_role']}`",
            f"- **Current live weight:** `{d['current_live_weight']:.2f}`",
            f"- **Evidence status:** `{d['evidence_status']}`",
            f"- **Ablation classification:** `{d['ablation_classification']}`",
            f"- **Ablation n (matched high):** `{d['ablation_matched_n']}`",
            f"- **Ablation SR/Frame/ROI:** `{d['ablation_sr_high']} / {d['ablation_frame_high']} / {d['ablation_roi_high']}`",
            f"- **SQPE control classification:** `{d['sqpe_classification']}`",
            f"- **Reason:** {d['reason']}",
            f"- **Next gate:** {d['next_gate']}",
            f"- *Notes:* {d['notes']}",
            "",
        ]

    lines += [
        "## Role Summary",
        "",
        "| Role | Count |",
        "|---|---|",
    ]
    for role, count in sorted(payload["role_summary"].items()):
        lines.append(f"| {role} | {count} |")

    lines += [
        "",
        "## Role Definitions",
        "",
    ]
    for role, desc in ROLES.items():
        lines.append(f"- **{role}** — {desc}")

    lines += [
        "",
        "---",
        "*Audit only. No weight changes applied. All recommendations require operator review and evidence gate passage.*",
    ]
    OUTPUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"  Written: {OUTPUT_JSON.name}")
    print(f"  Written: {OUTPUT_MD.name}")


def main() -> int:
    payload = run_board()
    write_outputs(payload)

    print()
    print("=" * 70)
    print("SIDECAR ROLE DECISION BOARD — SUMMARY")
    print("=" * 70)
    print(f"{'Sidecar':<28} {'Weight':>7} {'Role'}")
    print(f"{'-'*28} {'-'*7} {'-'*35}")
    for d in payload["decisions"]:
        print(f"{d['sidecar']:<28} {d['current_live_weight']:>7.2f} {d['recommended_role']}")
    print()
    print("Role counts:")
    for role, count in sorted(payload["role_summary"].items()):
        print(f"  {role}: {count}")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
