"""
VÉLØ Telegram Signal Attribution Panel Design V1

Produces the design specification for the VÉLØ SIGNAL STACK panel —
a signal attribution block that appears at the top of each Telegram prediction report.

This is a design document generator. It does NOT modify the Telegram output scripts,
the run_prime_today.py pipeline, or any production system. Production integration
requires explicit operator approval.

Usage:
    python scripts/design_telegram_signal_attribution_panel.py

Outputs:
    data/telegram_signal_attribution_design_v1.json
    data/telegram_signal_attribution_design_v1.md
    docs/evidence/VELO_TELEGRAM_SIGNAL_ATTRIBUTION_PANEL_V1.md

Rules: No model changes. No router changes. No staking. Design documentation only.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUN_TS = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

# ─────────────────────────────────────────────────────────────────────────────
# PANEL FIELD SPEC
# ─────────────────────────────────────────────────────────────────────────────

PANEL_FIELDS = [
    {
        "field": "pick",
        "label": "Pick",
        "source": "velo_verdicts.top.horse",
        "required": True,
        "note": "The VÉLØ top pick for this race",
    },
    {
        "field": "velo_prime_prob",
        "label": "VP",
        "source": "velo_verdicts.velo_prime_prob",
        "required": True,
        "format": "0.XX",
        "note": "Velo Prime probability — primary confidence signal",
    },
    {
        "field": "decision_tier",
        "label": "Tier",
        "source": "velo_verdicts.decision_tier",
        "required": True,
        "note": "A/B/C/D/X — A is highest confidence",
    },
    {
        "field": "lane_badges",
        "label": "Candidate Lanes",
        "source": "computed from candidate lane conditions",
        "required": False,
        "note": "One badge per lane that qualifies. Empty section if no lanes fire.",
    },
    {
        "field": "sidecar_values",
        "label": "Sidecar",
        "source": "velo_verdicts.market_deception_score, improvement_score, place_prob",
        "required": False,
        "note": "Show values only if above threshold. Suppressed if all below threshold.",
    },
    {
        "field": "suppress_warnings",
        "label": "Suppress Warnings",
        "source": "decision_tier + velo_prime_prob",
        "required": False,
        "note": "Shown only if suppression signal active",
    },
    {
        "field": "forensics_warnings",
        "label": "Risk Flags",
        "source": "computed from SP zone and tier",
        "required": False,
        "note": "Mid-price danger zone, short-fav override risk",
    },
    {
        "field": "router_status",
        "label": "Router",
        "source": "router_shadow_audit_latest.csv",
        "required": True,
        "note": "Always shown — confirms shadow-only status",
    },
    {
        "field": "operator_note",
        "label": "Status",
        "source": "hardcoded constant",
        "required": True,
        "note": "SHADOW EVIDENCE ONLY — NO STAKING AUTOMATION. Always shown.",
    },
]

# ─────────────────────────────────────────────────────────────────────────────
# BADGE LOGIC
# ─────────────────────────────────────────────────────────────────────────────

BADGE_LOGIC = [
    {
        "lane_id": "MARKET_DECEPTION_HIGH",
        "badge": "🔥 MDS_HIGH",
        "badge_label": "elite shadow signal",
        "emoji": "🔥",
        "condition": "market_deception_score > 0.50",
        "evidence_line": "n=31 | SR 54.8% | Frame 96.8%",
        "priority": 1,
        "status": "SHADOW_CANDIDATE",
        "show_if": "market_deception_score > 0.50",
        "tone": "elite — highest-lift signal in the system",
        "polarity_note": "Polarity confirmed: MDS > 0.5 predicts winners, not decoys.",
    },
    {
        "lane_id": "VP30_TIER_A",
        "badge": "✅ VP30_TIER_A",
        "badge_label": "proven shadow signal",
        "emoji": "✅",
        "condition": "velo_prime_prob >= 0.30 AND decision_tier == 'A'",
        "evidence_line": "n=162 | SR 40.1% | Frame 77.2%",
        "priority": 2,
        "status": "SHADOW_CANDIDATE",
        "show_if": "velo_prime_prob >= 0.30 AND decision_tier == 'A'",
        "tone": "proven — most robust signal in the system by sample size",
    },
    {
        "lane_id": "IMPROVEMENT_SCORE_HIGH",
        "badge": "📈 IMPROVE_HIGH",
        "badge_label": "proven shadow signal",
        "emoji": "📈",
        "condition": "improvement_score > 0.40",
        "evidence_line": "n=62 | SR 43.5% | Frame 82.3%",
        "priority": 3,
        "status": "SHADOW_CANDIDATE",
        "show_if": "improvement_score > 0.40",
        "tone": "proven — progressive form improvement signal",
    },
    {
        "lane_id": "PLACE_PROB_HIGH",
        "badge": "🟡 PLACE_HIGH",
        "badge_label": "watchlist signal",
        "emoji": "🟡",
        "condition": "place_prob > 0.80",
        "evidence_line": "n=392 | SR 31.6% | Frame 66.8%",
        "priority": 4,
        "status": "WATCHLIST",
        "show_if": "place_prob > 0.80",
        "tone": "watchlist — requires VP or Tier A overlay to matter",
        "caveat": "Shown only when VP >= 0.30 or Tier A also present, else suppressed from panel.",
    },
    {
        "lane_id": "B_TIER_LOW_VP_SUPPRESS",
        "badge": "⚠️ B_LOW_VP",
        "badge_label": "suppress candidate — drag signal",
        "emoji": "⚠️",
        "condition": "decision_tier == 'B' AND velo_prime_prob < 0.30",
        "evidence_line": "n=272 | SR 16.9% | Frame 44.1% — below baseline",
        "priority": 5,
        "status": "SUPPRESS_CANDIDATE",
        "show_if": "decision_tier == 'B' AND velo_prime_prob < 0.30",
        "tone": "suppress warning — this pick is in the confirmed drag zone",
        "warning": "This pick is in the Tier B VP<0.30 suppress zone. Historical SR=16.9%.",
    },
    {
        "lane_id": "MID_PRICE_WINNER_FORENSICS",
        "badge": "🔬 MID_PRICE_RISK",
        "badge_label": "forensics — known miss zone",
        "emoji": "🔬",
        "condition": "opponent_sp_range_3_to_8.5_possible",
        "evidence_line": "352 misses = 58% of all misses in SP 3.0–8.5 zone",
        "priority": 6,
        "status": "FORENSICS_ONLY",
        "show_if": "race_archetype contains mid-price contenders OR VP 0.25-0.35 range",
        "tone": "risk flag — mid-price winner zone. VÉLØ historically misses here.",
        "note": "Cannot be computed cleanly pre-race without SP info. Show as risk flag when VP is marginal.",
    },
]

# ─────────────────────────────────────────────────────────────────────────────
# SIDECAR DISPLAY THRESHOLDS
# ─────────────────────────────────────────────────────────────────────────────

SIDECAR_THRESHOLDS = {
    "market_deception_score": {
        "show_threshold": 0.40,
        "elite_threshold": 0.50,
        "format": "MDS={value:.2f}",
        "elite_label": "⚡ ELITE",
        "note": "Show if > 0.40. Mark ELITE if > 0.50.",
    },
    "improvement_score": {
        "show_threshold": 0.30,
        "strong_threshold": 0.40,
        "format": "Improve={value:.2f}",
        "strong_label": "↑ STRONG",
        "note": "Show if > 0.30. Mark STRONG if > 0.40.",
    },
    "place_prob": {
        "show_threshold": 0.70,
        "high_threshold": 0.80,
        "format": "PlaceProb={value:.2f}",
        "high_label": "📍 HIGH",
        "note": "Show if > 0.70. Mark HIGH if > 0.80.",
    },
    "rpdc_release_score": {
        "show_threshold": 0.50,
        "format": "RPDC={value:.2f}",
        "note": "Show if > 0.50. Watchlist signal only.",
    },
}

# ─────────────────────────────────────────────────────────────────────────────
# EXAMPLE PANELS
# ─────────────────────────────────────────────────────────────────────────────

EXAMPLE_PANELS = [
    {
        "scenario": "Elite multi-signal race — MDS + VP30_TIER_A + IMPROVE",
        "panel": """\
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🏇 VÉLØ SIGNAL STACK
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Pick: Example Horse
VP: 0.42 | Tier: A

Candidate Lanes:
🔥 MDS_HIGH — elite shadow signal
   n=31 | SR 54.8% | Frame 96.8%
✅ VP30_TIER_A — proven shadow signal
   n=162 | SR 40.1% | Frame 77.2%
📈 IMPROVE_HIGH — proven shadow signal
   n=62 | SR 43.5% | Frame 82.3%

Sidecar: MDS=0.63 ⚡ ELITE | Improve=0.47 ↑ STRONG | PlaceProb=0.84 📍 HIGH

Router: SHADOW ONLY — unchanged
Status: SHADOW EVIDENCE ONLY — NO STAKING AUTOMATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━""",
        "signal_count": 3,
        "tier": "A",
        "vp": 0.42,
        "mds": 0.63,
        "improvement": 0.47,
        "place_prob": 0.84,
    },
    {
        "scenario": "Single proven signal — VP30_TIER_A only",
        "panel": """\
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🏇 VÉLØ SIGNAL STACK
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Pick: Example Horse
VP: 0.33 | Tier: A

Candidate Lanes:
✅ VP30_TIER_A — proven shadow signal
   n=162 | SR 40.1% | Frame 77.2%

Sidecar: MDS=0.31 | Improve=0.28 | PlaceProb=0.76

Router: SHADOW ONLY — unchanged
Status: SHADOW EVIDENCE ONLY — NO STAKING AUTOMATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━""",
        "signal_count": 1,
        "tier": "A",
        "vp": 0.33,
        "mds": 0.31,
        "improvement": 0.28,
        "place_prob": 0.76,
    },
    {
        "scenario": "Suppress warning — Tier B VP<0.30 drag zone",
        "panel": """\
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🏇 VÉLØ SIGNAL STACK
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Pick: Example Horse
VP: 0.24 | Tier: B

Candidate Lanes:
⚠️ B_LOW_VP — suppress candidate
   n=272 | SR 16.9% | Frame 44.1% — DRAG ZONE

Sidecar: MDS=0.18 | Improve=0.15 | PlaceProb=0.61

⚠️ RISK: Tier B + VP<0.30 — confirmed drag zone
   Suppress candidate. Historical SR well below baseline.

Router: SHADOW ONLY — unchanged
Status: SHADOW EVIDENCE ONLY — NO STAKING AUTOMATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━""",
        "signal_count": 0,
        "tier": "B",
        "vp": 0.24,
        "suppress_warning": True,
    },
    {
        "scenario": "MDS elite signal — maximum interest",
        "panel": """\
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🏇 VÉLØ SIGNAL STACK
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Pick: Example Horse
VP: 0.38 | Tier: A

Candidate Lanes:
🔥 MDS_HIGH — ELITE SHADOW SIGNAL
   n=31 | SR 54.8% | Frame 96.8%
   ⚡ Highest-lift signal in system. n=31 — discipline required.
✅ VP30_TIER_A — proven shadow signal
   n=162 | SR 40.1% | Frame 77.2%

Sidecar: MDS=0.71 ⚡ ELITE | Improve=0.22 | PlaceProb=0.81 📍 HIGH

Router: SHADOW ONLY — unchanged
Status: SHADOW EVIDENCE ONLY — NO STAKING AUTOMATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━""",
        "signal_count": 2,
        "tier": "A",
        "vp": 0.38,
        "mds": 0.71,
        "place_prob": 0.81,
        "notes": "MDS > 0.70 should include the n=31 caution note explicitly.",
    },
]

# ─────────────────────────────────────────────────────────────────────────────
# OPERATOR VISIBILITY GAP ANALYSIS
# ─────────────────────────────────────────────────────────────────────────────

VISIBILITY_GAP = {
    "current_state": (
        "Current Telegram output shows: horse name, VP score, tier, and a narrative summary. "
        "It does NOT surface candidate lane badges, sidecar signal values, or suppress warnings. "
        "The operator cannot distinguish a VP=0.38/Tier A/MDS=0.71 pick from a VP=0.38/Tier A/MDS=0.10 pick."
    ),
    "gap_severity": "HIGH",
    "example": (
        "On 2026-04-28, MARKET_DECEPTION_HIGH would have fired on a subset of picks. "
        "The operator received the standard Telegram output with no indication of MDS elevation. "
        "A 54.8% SR signal was invisible at the operator layer."
    ),
    "fix_required": (
        "Add the VÉLØ SIGNAL STACK panel near the top of each race report. "
        "This does not change predictions. It surfaces what the engine already knows."
    ),
    "production_integration_path": {
        "file_to_modify": "scripts/run_prime_today.py (Telegram output section)",
        "function_to_update": "format_telegram_message() or equivalent",
        "requires_operator_approval": True,
        "status": "DESIGN_ONLY — production integration NOT yet approved",
        "next_step": "Operator reviews this design doc, approves panel format, then integration is built",
    },
}

# ─────────────────────────────────────────────────────────────────────────────
# GOVERNANCE
# ─────────────────────────────────────────────────────────────────────────────

GOVERNANCE = {
    "panel_name": "VÉLØ SIGNAL STACK",
    "panel_position": "top of each race prediction block in Telegram",
    "display_logic": "Always show VP, Tier, Router status, and operator note. Show lane badges, sidecar values, and warnings only when relevant.",
    "production_status": "DESIGN_ONLY — not yet in production Telegram output",
    "approval_required_for_production": True,
    "hard_rules": [
        "The panel is informational only. It does not change the prediction or decision.",
        "The SHADOW EVIDENCE ONLY note must always appear — never remove it.",
        "No badge implies staking approval. Badges are shadow evidence signals only.",
        "MDS_HIGH badge must always include the n=31 caution note when n is still below 75.",
        "B_LOW_VP warning must always include the SR=16.9% figure.",
        "Panel content must be derived from velo_verdicts and candidate lane design — no recalculation.",
    ],
}


# ─────────────────────────────────────────────────────────────────────────────
# OUTPUT BUILDERS
# ─────────────────────────────────────────────────────────────────────────────

def build_json() -> dict:
    return {
        "design_version": 1,
        "created": RUN_TS,
        "status": "DESIGN_ONLY_NOT_YET_IN_PRODUCTION",
        "baseline_commits": {
            "candidate_lane_design": "3a007eb",
            "shadow_ledger_design": "pending",
            "evidence_vault": "63f37e9",
        },
        "panel_fields": PANEL_FIELDS,
        "badge_logic": BADGE_LOGIC,
        "sidecar_thresholds": SIDECAR_THRESHOLDS,
        "example_panels": EXAMPLE_PANELS,
        "visibility_gap": VISIBILITY_GAP,
        "governance": GOVERNANCE,
    }


def build_markdown(data: dict) -> str:
    lines = [
        "# VÉLØ Telegram Signal Attribution Panel Design V1",
        "",
        f"**Created:** {data['created']}",
        "**Status:** DESIGN ONLY — not yet in production",
        "",
        "---",
        "",
        "## The Operator Visibility Problem",
        "",
        data["visibility_gap"]["current_state"],
        "",
        f"**Gap severity:** {data['visibility_gap']['gap_severity']}",
        "",
        f"> {data['visibility_gap']['example']}",
        "",
        f"**Fix required:** {data['visibility_gap']['fix_required']}",
        "",
        "---",
        "",
        "## Panel Design: VÉLØ SIGNAL STACK",
        "",
        f"**Panel name:** {data['governance']['panel_name']}",
        f"**Position:** {data['governance']['panel_position']}",
        f"**Display logic:** {data['governance']['display_logic']}",
        "",
        "---",
        "",
        "## Panel Fields",
        "",
        "| Field | Label | Source | Required |",
        "|---|---|---|---|",
    ]
    for f in data["panel_fields"]:
        lines.append(
            f"| `{f['field']}` | {f['label']} | {f['source']} | {'✅' if f['required'] else '—'} |"
        )
    lines += [
        "",
        "---",
        "",
        "## Badge Logic",
        "",
        "| # | Badge | Condition | Evidence | Priority |",
        "|---|---|---|---|---|",
    ]
    for b in data["badge_logic"]:
        lines.append(
            f"| {b['priority']} | {b['badge']} | `{b['condition']}` | {b['evidence_line']} | {b['priority']} |"
        )
    lines += [
        "",
        "---",
        "",
        "## Sidecar Display Thresholds",
        "",
        "| Signal | Show if | Elite/Strong if | Format |",
        "|---|---|---|---|",
    ]
    for sig, cfg in data["sidecar_thresholds"].items():
        show = cfg.get("show_threshold", "—")
        elite = cfg.get("elite_threshold", cfg.get("strong_threshold", cfg.get("high_threshold", "—")))
        fmt = cfg.get("format", "—")
        lines.append(f"| {sig} | > {show} | > {elite} | `{fmt}` |")
    lines += [
        "",
        "---",
        "",
        "## Example Panels",
        "",
    ]
    for ex in data["example_panels"]:
        lines += [
            f"### {ex['scenario']}",
            "",
            "```",
            ex["panel"],
            "```",
            "",
        ]
        if ex.get("notes"):
            lines.append(f"*{ex['notes']}*")
            lines.append("")
    lines += [
        "---",
        "",
        "## Production Integration Path",
        "",
        f"**File to modify:** `{data['visibility_gap']['production_integration_path']['file_to_modify']}`",
        f"**Function:** `{data['visibility_gap']['production_integration_path']['function_to_update']}`",
        f"**Requires operator approval:** {data['visibility_gap']['production_integration_path']['requires_operator_approval']}",
        f"**Status:** {data['visibility_gap']['production_integration_path']['status']}",
        f"**Next step:** {data['visibility_gap']['production_integration_path']['next_step']}",
        "",
        "---",
        "",
        "## Hard Rules",
        "",
    ]
    for r in data["governance"]["hard_rules"]:
        lines.append(f"- {r}")
    lines += [
        "",
        "---",
        f"*VÉLØ Telegram Signal Attribution Panel Design V1 | {data['created']}*",
    ]
    return "\n".join(lines)


def build_evidence_doc(data: dict) -> str:
    lines = [
        "# VÉLØ Telegram Signal Attribution Panel V1",
        "",
        f"**Version:** 1",
        f"**Created:** {data['created']}",
        "**Status:** DESIGN ONLY",
        "",
        "---",
        "",
        "## Why This Exists",
        "",
        "VÉLØ has discovered signals that predict race outcomes at elite levels:",
        "",
        "| Signal | SR | Frame | n |",
        "|---|---|---|---|",
        "| Market Deception Score > 0.50 | **54.8%** | **96.8%** | 31 |",
        "| VP≥0.30 + Tier A | 40.1% | 77.2% | 162 |",
        "| Improvement Score > 0.40 | 43.5% | 82.3% | 62 |",
        "",
        "These signals are currently invisible at the operator layer.",
        "The Telegram output shows VP and Tier but does not surface which candidate",
        "lanes fired, what the sidecar values are, or whether the pick is in a",
        "drag or suppress zone.",
        "",
        "This panel design fixes that without changing any prediction logic.",
        "",
        "---",
        "",
        "## What the Panel Shows",
        "",
        "For every VÉLØ pick in the Telegram report:",
        "",
        "1. **VP and Tier** — always shown (already present, format standardised)",
        "2. **Candidate Lane Badges** — which of the 6 shadow lanes fired",
        "3. **Sidecar Values** — MDS, improvement score, place prob if above threshold",
        "4. **Suppress Warnings** — if the pick is in a confirmed drag zone",
        "5. **Risk Flags** — mid-price winner danger zone, short-fav override risk",
        "6. **Router Status** — always confirms shadow-only state",
        "7. **Operator Note** — SHADOW EVIDENCE ONLY — NO STAKING AUTOMATION",
        "",
        "---",
        "",
        "## What the Panel Does NOT Do",
        "",
        "- Does not change predictions",
        "- Does not change routing logic",
        "- Does not imply staking approval for any badge",
        "- Does not override the human operator's decision",
        "- Does not produce or modify any model outputs",
        "",
        "---",
        "",
        "## The Company Case",
        "",
        "> VÉLØ does not merely output predictions.",
        "> VÉLØ audits its own confidence, identifies which signal families are working,",
        "> and refuses to promote them until a shadow ledger proves durability.",
        "> The Signal Attribution Panel makes this legible to the operator in real time.",
        "",
        "A horse with VP=0.34, Tier A, MDS=0.71, Improvement=0.47 is not the same",
        "as a horse with VP=0.34, Tier A, MDS=0.10, Improvement=0.12.",
        "The prediction layer must expose that difference.",
        "",
        "---",
        f"*VÉLØ Telegram Signal Attribution Panel V1 | {data['created']}*",
    ]
    return "\n".join(lines)


def main():
    print("VÉLØ Telegram Signal Attribution Panel Design V1")
    print(f"Run: {RUN_TS}")
    print("=" * 60)

    data = build_json()

    json_path = ROOT / "data" / "telegram_signal_attribution_design_v1.json"
    with open(json_path, "w") as f:
        json.dump(data, f, indent=2, default=str)
    print(f"Written: {json_path}")

    md_path = ROOT / "data" / "telegram_signal_attribution_design_v1.md"
    with open(md_path, "w") as f:
        f.write(build_markdown(data))
    print(f"Written: {md_path}")

    ev_path = ROOT / "docs" / "evidence" / "VELO_TELEGRAM_SIGNAL_ATTRIBUTION_PANEL_V1.md"
    ev_path.parent.mkdir(parents=True, exist_ok=True)
    with open(ev_path, "w") as f:
        f.write(build_evidence_doc(data))
    print(f"Written: {ev_path}")

    print()
    print("Design complete — no production Telegram code was changed.")
    print("No routing, model, or staking logic was changed.")
    print(f"\nOperator visibility gap: HIGH severity")
    print(f"Next step: operator approves panel format → production integration")


if __name__ == "__main__":
    main()
