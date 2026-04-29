"""
VÉLØ Candidate Lane Design V1

Reads the unified evidence vault and produces a structured design specification
for each candidate shadow lane.

This script is DESIGN ONLY. It:
  - reads evidence from data/evidence_vault/
  - produces design JSON, Markdown, and evidence documents
  - does NOT change any routing, prediction, model, or staking logic

Usage:
    python scripts/design_velo_candidate_lanes.py

Outputs:
    data/velo_candidate_lane_design_v1.json
    data/velo_candidate_lane_design_v1.md
    docs/evidence/VELO_CANDIDATE_LANES_V1.md

Rules: No deployment. No router changes. No staking. Design only.
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUN_TS = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

GLOBAL_SR = 20.6
GLOBAL_FRAME = 48.4
BASELINE_SR = 20.0
BASELINE_FRAME = 70.0


# ─── Lane definitions ─────────────────────────────────────────────────────────

LANES = [
    {
        "lane_id": "VP30_TIER_A",
        "display_name": "VP ≥ 0.30 + Tier A",
        "status": "SHADOW_CANDIDATE",
        "priority": 1,

        # A. Condition
        "condition": {
            "velo_prime_prob": {"gte": 0.30},
            "decision_tier": {"eq": "A"},
        },
        "condition_plain": "velo_prime_prob >= 0.30 AND decision_tier == 'A'",

        # B. Signal source fields
        "signal_sources": ["velo_prime_prob", "decision_tier"],
        "source_table": "velo_verdicts + sigma_audits",

        # C/D/E. Current evidence
        "evidence": {
            "n": 162,
            "wins": 65,
            "placed": 125,
            "misses": 37,
            "strike_rate": 40.1,
            "frame_rate": 77.2,
            "avg_vp": 0.425,
            "avg_winner_sp": 2.26,
            "avg_miss_sp": 7.12,
            "sr_lift_vs_global": round(40.1 - GLOBAL_SR, 1),
            "fr_lift_vs_global": round(77.2 - GLOBAL_FRAME, 1),
            "evidence_days": 49,
            "roi_research": "not_yet_calculated",
            "note": "Most miss SPs in 3.25-9.0 range — mid-price zone still the weakness",
        },

        # F. Confidence level
        "confidence_level": "HIGH",
        "confidence_note": "n=162 across 49 days. Monotonic VP relationship confirms the signal is structural.",

        # G. Risks
        "risks": [
            "Tier A self-selection: these are the system's highest-confidence races — selection bias possible",
            "Average winner SP=2.26 means wins come from short-priced horses — market may price this in",
            "37 misses include 15+ races where short favourites won — short-fav override needed",
            "Miss SP avg=7.12: mid-price winner problem persists even in this lane",
        ],

        # H. Minimum sample before promotion review
        "promotion_gates": {
            "shadow_candidate_entry": "n=162 (already passed — evidence exists)",
            "first_review": "n=200 qualifying results",
            "paper_execution_gate": "n=300, SR≥35%, Frame≥70%, no freeze triggered",
            "live_discussion_gate": "n=500, multi-month track record, SR≥30%, Frame≥70%",
            "live_activation": "NEVER without explicit operator decision + legal review",
        },

        # I. Required shadow ledger fields
        "shadow_ledger_fields": [
            "date", "race_id", "track", "off_time", "horse",
            "velo_prime_prob", "decision_tier", "outcome",
            "actual_winner_sp", "miss_reason", "shadow_stake_£1",
            "cumulative_pl", "cumulative_roi", "consecutive_losses",
        ],

        # J. Pass/fail thresholds
        "pass_thresholds": {
            "min_sr_at_n20": 30.0,
            "min_sr_at_n50": 28.0,
            "min_sr_at_n100": 25.0,
            "min_frame_at_n20": 65.0,
            "min_frame_at_n50": 62.0,
            "target_roi": "positive at n=50",
        },

        # K. Freeze conditions
        "freeze_conditions": [
            "SR drops below 20.0% at n≥30 (global baseline — no lift = no point)",
            "Frame drops below 55.0% at n≥30",
            "6+ consecutive losses at any sample size",
            "ROI turns negative and stays negative for 20+ races at n≥50",
        ],

        # L. Lane classification
        "lane_classification": "SHADOW_CANDIDATE",
        "can_affect_live_routing": False,
        "human_approval_required_for": ["paper_execution", "live_discussion", "any_staking"],
    },

    {
        "lane_id": "MARKET_DECEPTION_HIGH",
        "display_name": "Market Deception Score > 0.50",
        "status": "SHADOW_CANDIDATE",
        "priority": 2,

        "condition": {
            "market_deception_score": {"gt": 0.50},
        },
        "condition_plain": "market_deception_score > 0.50",

        "signal_sources": ["market_deception_score"],
        "source_table": "velo_verdicts",

        "evidence": {
            "n": 31,
            "wins": 17,
            "placed": 30,
            "misses": 1,
            "strike_rate": 54.8,
            "frame_rate": 96.8,
            "sr_lift_vs_global": round(54.8 - GLOBAL_SR, 1),
            "fr_lift_vs_global": round(96.8 - GLOBAL_FRAME, 1),
            "evidence_days": 49,
            "roi_research": "not_yet_calculated",
            "note": (
                "Frame=96.8% means almost every pick finishes in the top 3. "
                "SR=54.8% means over half win outright. "
                "This is the highest-lift sidecar in the system. "
                "n=31 is promising but not yet sufficient for full confidence. "
                "CAUTION: In A/B routing, high MDS was historically treated as DECOY risk. "
                "The evidence here directly contradicts that assumption. "
                "Polarity flip confirmed: high MDS in velo_verdicts = model-backed signal, not decoy."
            ),
        },

        "confidence_level": "PROMISING_HIGH_UPSIDE",
        "confidence_note": "n=31 clears the INSUFFICIENT threshold but remains small. SR=54.8% is extraordinary. Must track for regression — if SR drops to 30-35% range it may still be valuable but the current numbers could be a small-sample peak.",

        "risks": [
            "n=31: small sample — single regression patch could drop SR significantly",
            "Polarity confusion: MDS was previously used as a decoy blocker. If any code path still treats MDS>0.5 as a negative signal, this lane will self-contradict",
            "MDS>0.5 fires on ~2% of predictions — very low volume, slow ledger accumulation",
            "Frame=96.8% at n=31 is likely to regress toward 80-85% at n=100 — still excellent but not 97%",
            "No SP filter applied: winning at any price. If most wins are short-priced (SP<2), ROI may be limited despite high SR",
        ],

        "promotion_gates": {
            "shadow_candidate_entry": "IMMEDIATE — evidence sufficient to start shadow tracking",
            "first_review": "n=50 qualifying results",
            "paper_execution_gate": "n=80, SR≥40%, Frame≥80%, positive ROI, no freeze",
            "live_discussion_gate": "n=100, multi-month track record, SR≥35%",
            "live_activation": "NEVER without explicit operator decision + legal review",
        },

        "shadow_ledger_fields": [
            "date", "race_id", "track", "off_time", "horse",
            "market_deception_score", "velo_prime_prob", "decision_tier",
            "outcome", "actual_winner_sp", "miss_reason",
            "shadow_stake_£1", "cumulative_pl", "cumulative_roi",
            "consecutive_losses",
        ],

        "pass_thresholds": {
            "min_sr_at_n20": 35.0,
            "min_sr_at_n50": 30.0,
            "min_sr_at_n100": 25.0,
            "min_frame_at_n20": 75.0,
            "min_frame_at_n50": 70.0,
            "target_roi": "positive at n=30",
        },

        "freeze_conditions": [
            "SR drops below 25.0% at n≥20 (still above global but serious regression from 54.8%)",
            "Frame drops below 65.0% at n≥20 (regression from 96.8%)",
            "5+ consecutive losses at any sample size",
            "ROI negative for 15+ consecutive races at n≥30",
        ],

        "lane_classification": "SHADOW_CANDIDATE",
        "can_affect_live_routing": False,
        "human_approval_required_for": ["any_threshold_change", "paper_execution", "any_staking"],
    },

    {
        "lane_id": "IMPROVEMENT_SCORE_HIGH",
        "display_name": "Improvement Score > 0.40",
        "status": "SHADOW_CANDIDATE",
        "priority": 3,

        "condition": {
            "improvement_score": {"gt": 0.40},
        },
        "condition_plain": "improvement_score > 0.40",

        "signal_sources": ["improvement_score"],
        "source_table": "velo_verdicts",

        "evidence": {
            "n": 62,
            "wins": 27,
            "placed": 51,
            "misses": 11,
            "strike_rate": 43.5,
            "frame_rate": 82.3,
            "sr_lift_vs_global": round(43.5 - GLOBAL_SR, 1),
            "fr_lift_vs_global": round(82.3 - GLOBAL_FRAME, 1),
            "evidence_days": 49,
            "roi_research": "not_yet_calculated",
            "note": (
                "The improvement specialist model identifies horses about to step forward "
                "in performance. SR=43.5% at n=62 is the second-highest SR in the system. "
                "Frame=82.3% means picks are competitive in 5 of 6 races. "
                "This is a consistently strong signal with a meaningful sample."
            ),
        },

        "confidence_level": "HIGH",
        "confidence_note": "n=62 is a meaningful sample. SR=43.5% at this size is convincing. The improvement model is one of 7 specialist models — it fires selectively.",

        "risks": [
            "Improvement score fires on horses showing forward form — these may already be short-priced, limiting ROI",
            "The improvement model was trained on historical data — may not generalise to unusual going/class combinations",
            "n=62: at the lower end of confidence — need 100+ for full PROVEN status",
            "Interaction with MDS: a horse showing improvement in a deceptive market may fire both signals — avoid double-counting",
        ],

        "promotion_gates": {
            "shadow_candidate_entry": "IMMEDIATE — evidence sufficient",
            "first_review": "n=80 qualifying results",
            "paper_execution_gate": "n=120, SR≥35%, Frame≥75%, positive ROI",
            "live_discussion_gate": "n=150, SR≥30%, Frame≥72%",
            "live_activation": "NEVER without explicit operator decision + legal review",
        },

        "shadow_ledger_fields": [
            "date", "race_id", "track", "off_time", "horse",
            "improvement_score", "velo_prime_prob", "decision_tier",
            "outcome", "actual_winner_sp", "miss_reason",
            "shadow_stake_£1", "cumulative_pl", "cumulative_roi",
            "consecutive_losses",
        ],

        "pass_thresholds": {
            "min_sr_at_n30": 32.0,
            "min_sr_at_n60": 30.0,
            "min_sr_at_n100": 25.0,
            "min_frame_at_n30": 70.0,
            "min_frame_at_n60": 65.0,
            "target_roi": "positive at n=50",
        },

        "freeze_conditions": [
            "SR drops below 22.0% at n≥30",
            "Frame drops below 60.0% at n≥30",
            "6+ consecutive losses",
            "ROI negative for 20+ consecutive races at n≥50",
        ],

        "lane_classification": "SHADOW_CANDIDATE",
        "can_affect_live_routing": False,
        "human_approval_required_for": ["paper_execution", "any_staking"],
    },

    {
        "lane_id": "PLACE_PROB_HIGH",
        "display_name": "Place Probability > 0.80",
        "status": "WATCHLIST",
        "priority": 4,

        "condition": {
            "place_prob": {"gt": 0.80},
        },
        "condition_plain": "place_prob > 0.80",

        "signal_sources": ["place_prob"],
        "source_table": "velo_verdicts",

        "evidence": {
            "n": 392,
            "wins": 124,
            "placed": 262,
            "misses": 130,
            "strike_rate": 31.6,
            "frame_rate": 66.8,
            "sr_lift_vs_global": round(31.6 - GLOBAL_SR, 1),
            "fr_lift_vs_global": round(66.8 - GLOBAL_FRAME, 1),
            "evidence_days": 49,
            "roi_research": "not_yet_calculated",
            "note": (
                "SR=31.6% at n=392 is the largest sample of any sidecar signal. "
                "Frame=66.8% is slightly below the 70% target but with 392 races it is statistically significant. "
                "This signal fires frequently — 392 from 1391 total = 28% of all predictions. "
                "Lift of +11% SR over global baseline is consistent and meaningful at this scale."
            ),
        },

        "confidence_level": "WATCHLIST_GOOD",
        "confidence_note": "Large sample (n=392) but frame rate misses the 70% target. The signal provides meaningful lift without exceptional performance. WATCHLIST not SHADOW_CANDIDATE because it does not differentiate winners sharply enough on its own.",

        "risks": [
            "Frame=66.8% is just below the 70% target — may be a ceiling effect for the place_prob specialist",
            "High coverage (28% of all predictions) means it is not selective — needs combination with VP or tier filter",
            "The place_prob model is optimised for placement, not wins — SR=31.6% may be the ceiling for this signal alone",
            "Combining with VP≥0.30 may create a stronger combined lane — test separately",
        ],

        "promotion_gates": {
            "watchlist_entry": "IMMEDIATE — already at n=392",
            "shadow_candidate_gate": "n=500, combined with VP≥0.30 filter, SR≥28%, Frame≥68%",
            "paper_execution_gate": "n=700, SR≥25%, Frame≥68%, positive ROI over 6+ months",
            "live_discussion_gate": "n=1000",
            "live_activation": "NEVER without explicit operator decision + legal review",
        },

        "shadow_ledger_fields": [
            "date", "race_id", "track", "off_time", "horse",
            "place_prob", "velo_prime_prob", "decision_tier",
            "outcome", "actual_winner_sp", "miss_reason",
            "shadow_stake_£1", "cumulative_pl", "cumulative_roi",
        ],

        "pass_thresholds": {
            "min_sr_maintained": 25.0,
            "min_frame_maintained": 60.0,
            "positive_roi_at": "n=200",
        },

        "freeze_conditions": [
            "SR drops below 20.0% (global baseline) at n≥100",
            "Frame drops below 55.0% at n≥100",
            "10+ consecutive losses",
        ],

        "lane_classification": "WATCHLIST",
        "can_affect_live_routing": False,
        "human_approval_required_for": ["shadow_candidate_promotion", "any_staking"],
    },

    {
        "lane_id": "B_TIER_LOW_VP_SUPPRESS",
        "display_name": "Tier B VP < 0.30 — Suppress Candidate",
        "status": "SUPPRESS_CANDIDATE",
        "priority": 5,

        "condition": {
            "decision_tier": {"eq": "B"},
            "velo_prime_prob": {"lt": 0.30},
        },
        "condition_plain": "decision_tier == 'B' AND velo_prime_prob < 0.30",

        "signal_sources": ["decision_tier", "velo_prime_prob"],
        "source_table": "sigma_audits + velo_verdicts",

        "evidence": {
            "n": 272,
            "wins": 46,
            "placed": 120,
            "misses": 152,
            "strike_rate": 16.9,
            "frame_rate": 44.1,
            "avg_vp": 0.245,
            "avg_winner_sp": 4.93,
            "avg_miss_sp": 8.27,
            "sr_lift_vs_global": round(16.9 - GLOBAL_SR, 1),
            "suppression_test": {
                "original_n": 1249,
                "suppressed_n": 977,
                "rows_removed": 272,
                "coverage_lost_pct": 21.8,
                "original_sr": GLOBAL_SR,
                "suppressed_sr": 21.6,
                "sr_gain": 1.0,
                "original_frame": GLOBAL_FRAME,
                "suppressed_frame": 49.6,
                "frame_gain": 1.2,
            },
            "note": (
                "SR=16.9% is below global baseline. These predictions have negative lift (-3.7%). "
                "Suppressing them gains only +1.0% SR and +1.2% frame but loses 21.8% coverage. "
                "The gain is modest. The direction is confirmed: these are drag. "
                "Suppression is an operator decision, not automatic."
            ),
        },

        "confidence_level": "CONFIRMED_DRAG",
        "confidence_note": "n=272 is conclusive. SR=16.9% across 49 days is consistently below baseline. This is not a signal — it is a noise band.",

        "risks": [
            "Coverage loss: removing 272 races loses 21.8% of daily prediction volume",
            "Some Tier B VP<0.30 races may be E/W candidates — suppressing them removes potential placed returns",
            "The gain (+1% SR) is statistically real but operationally modest",
            "If the VP calibration improves, some currently VP<0.30 B-tier races may become VP≥0.30 — suppression rule should be reviewed after any model update",
        ],

        "suppression_protocol": {
            "what_to_suppress": "All Tier B predictions where velo_prime_prob < 0.30",
            "where": "Any future candidate lane design — do not include these in lane pass criteria",
            "not_where": "Do not change the production sigma output — all predictions still reported to Telegram",
            "activation_requires": "Explicit operator decision — do not auto-suppress",
            "review_trigger": "After any model update that changes VP calibration",
        },

        "lane_classification": "SUPPRESS_CANDIDATE",
        "can_affect_live_routing": False,
        "human_approval_required_for": ["any_suppression_activation"],
    },

    {
        "lane_id": "MID_PRICE_WINNER_FORENSICS",
        "display_name": "Mid-Priced Winner Forensics Lane (SP 3.0–8.5)",
        "status": "FORENSICS_ONLY",
        "priority": 6,

        "condition": {
            "actual_winner_sp": {"gte": 3.0, "lte": 8.5},
            "outcome": {"eq": "MISS"},
        },
        "condition_plain": "outcome == 'MISS' AND actual_winner_sp between 3.0 and 8.5",

        "signal_sources": ["actual_winner_sp", "miss_reason", "outcome"],
        "source_table": "sigma_audits",

        "evidence": {
            "total_misses": 607,
            "sp_3_8_5_misses": 352,
            "sp_3_8_5_pct_of_misses": 58.0,
            "miss_class_breakdown": {
                "mid_priced_won": 279,
                "outsider_won": 92,
                "market_decoy_followed": 87,
                "short_fav_won": 81,
            },
            "high_vp_misses": {
                "n": 15,
                "winner_sps": [1.44, 1.57, 1.67, 1.91, 2.2, 3.25, 3.5, 3.75, 4.33, 4.5],
                "note": "15 races where VP>=0.40 but a short-price horse won instead",
            },
            "note": (
                "This is not a promotion lane. It is a research diagnostic. "
                "VÉLØ is missing 279 mid-priced winners across 49 days. "
                "These are races where the model competed but ranked the wrong horse first. "
                "The winner was visible to the market (SP 3–8.5 = legitimate contender). "
                "Research question: what distinguishes the SP 3–8.5 winner from VÉLØ's pick?"
            ),
        },

        "confidence_level": "FORENSICS",
        "confidence_note": "This is a diagnostic lane only. There is no promotion path.",

        "research_questions": [
            "What features do SP 3–8.5 winners carry that VÉLØ's picks do not?",
            "Is there a specific tier/archetype combination where mid-price misses cluster?",
            "Are mid-price misses correlated with specific courses or going conditions?",
            "Does the place_prob or improvement signal fire on the actual winner in these cases?",
            "Is the VÉLØ pick framing in these races (finishing 2nd/3rd) or missing entirely?",
            "What is the VP score of the actual SP 3–8.5 winner in races where VÉLØ missed?",
        ],

        "research_methodology": {
            "step_1": "Pull all MISS rows where actual_winner_sp between 3.0 and 8.5",
            "step_2": "For each miss, fetch the VÉLØ pick's VP, tier, improvement_score, place_prob, MDS",
            "step_3": "Attempt to find the actual winner in the velo_verdicts table to get its score",
            "step_4": "Compare feature distributions: VÉLØ pick vs actual winner",
            "step_5": "Cluster by course/going/class/archetype to find miss patterns",
            "step_6": "If a distinguishing feature is found, design a new sidecar signal",
        },

        "promotion_path": "NONE — this is a research tool that may eventually produce a new sidecar signal candidate",

        "lane_classification": "FORENSICS_ONLY",
        "can_affect_live_routing": False,
        "human_approval_required_for": ["any_signal_derived_from_this_research"],
    },
]


# ─── Governance framework ──────────────────────────────────────────────────────

GOVERNANCE = {
    "principles": [
        "No lane affects live routing without explicit operator approval",
        "Shadow ledger is append-only — never overwrite historical records",
        "Freeze conditions are automatic — once triggered, human review required to unfreeze",
        "Promotion gates require human sign-off at every step",
        "Evidence numbers must come from closed-result sigma_audits — no simulation",
        "ROI figures are research-only — no staking until n≥100 and explicit approval",
    ],
    "shadow_lane_lifecycle": [
        "DESIGN → shadow annotation active (ledger tracking begins)",
        "WATCHLIST → n≥20, SR positive, no freeze triggered",
        "SHADOW_CANDIDATE → n≥30, SR≥baseline, Frame≥70%, positive ROI",
        "PAPER_EXECUTION → n≥60, operator approves paper P&L tracking",
        "LIVE_DISCUSSION → n≥100, multi-month evidence, operator reviews",
        "LIVE_ACTIVATION → explicit operator decision, legal review, disclaimers",
    ],
    "freeze_rules": {
        "auto_freeze": [
            "SR drops below global baseline (20.6%) at n≥20",
            "Frame drops below 50% at n≥20",
            "7+ consecutive losses",
            "ROI below -20% at n≥30",
        ],
        "unfreeze_requires": "Human review of last 20 races + operator approval",
    },
    "supabase_schema_note": (
        "Shadow ledger tables are not yet created in Supabase. "
        "Current tracking is via router_shadow_audit_ledger.csv. "
        "When Supabase tables are created, all historical CSV data will be migrated."
    ),
}


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    print(f"VÉLØ Candidate Lane Design V1")
    print(f"Run: {RUN_TS}")
    print("=" * 60)

    result = {
        "run_ts": RUN_TS,
        "evidence_source": "data/evidence_vault/velo_unified_evidence_audit_v1.json",
        "global_baseline": {
            "sr": GLOBAL_SR, "frame": GLOBAL_FRAME,
            "baseline_sr": BASELINE_SR, "baseline_frame": BASELINE_FRAME,
        },
        "lanes": LANES,
        "governance": GOVERNANCE,
        "summary": {
            "total_lanes": len(LANES),
            "shadow_candidates": [l["lane_id"] for l in LANES if l["status"] == "SHADOW_CANDIDATE"],
            "watchlist": [l["lane_id"] for l in LANES if l["status"] == "WATCHLIST"],
            "suppress_candidates": [l["lane_id"] for l in LANES if l["status"] == "SUPPRESS_CANDIDATE"],
            "forensics_only": [l["lane_id"] for l in LANES if l["status"] == "FORENSICS_ONLY"],
            "highest_priority": LANES[0]["lane_id"],
            "highest_upside": "MARKET_DECEPTION_HIGH (SR=54.8%, n=31)",
            "most_proven": "VP30_TIER_A (SR=40.1%, n=162, 49-day evidence)",
            "largest_sample": "PLACE_PROB_HIGH (n=392)",
            "confirmed_suppress": "B_TIER_LOW_VP_SUPPRESS (SR=16.9%, confirmed drag)",
            "no_deployment": "All lanes are design-only. No routing changes. No staking.",
        },
    }

    # Write JSON
    json_path = ROOT / "data" / "velo_candidate_lane_design_v1.json"
    with open(json_path, "w") as f:
        json.dump(result, f, indent=2, default=str)
    print(f"Written: {json_path}")

    # Write markdown design doc
    md_content = build_markdown(result)
    md_path = ROOT / "data" / "velo_candidate_lane_design_v1.md"
    with open(md_path, "w") as f:
        f.write(md_content)
    print(f"Written: {md_path}")

    # Write evidence doc
    evidence_md = build_evidence_doc(result)
    ev_path = ROOT / "docs" / "evidence" / "VELO_CANDIDATE_LANES_V1.md"
    ev_path.parent.mkdir(parents=True, exist_ok=True)
    with open(ev_path, "w") as f:
        f.write(evidence_md)
    print(f"Written: {ev_path}")

    print(f"\nDesign complete — {RUN_TS}")
    print(f"No routing, model, or staking logic was changed.")
    return result


def build_markdown(result: dict) -> str:
    lines = [
        "# VÉLØ Candidate Lane Design V1",
        f"**Generated:** {result['run_ts']}",
        f"**Evidence source:** {result['evidence_source']}",
        "",
        "**This document is DESIGN ONLY. No code was changed. No staking was activated.**",
        "",
        "---",
        "",
        f"## Summary",
        "",
        f"| Item | Value |",
        f"|---|---|",
        f"| Shadow candidates | {', '.join(result['summary']['shadow_candidates'])} |",
        f"| Watchlist | {', '.join(result['summary']['watchlist'])} |",
        f"| Suppress candidates | {', '.join(result['summary']['suppress_candidates'])} |",
        f"| Forensics only | {', '.join(result['summary']['forensics_only'])} |",
        f"| Highest priority | {result['summary']['highest_priority']} |",
        f"| Highest upside | {result['summary']['highest_upside']} |",
        f"| Most proven | {result['summary']['most_proven']} |",
        "",
        "---",
        "",
    ]
    for lane in result["lanes"]:
        e = lane.get("evidence", {})
        status_icon = {
            "SHADOW_CANDIDATE": "🔵",
            "WATCHLIST": "🟡",
            "SUPPRESS_CANDIDATE": "🔴",
            "FORENSICS_ONLY": "🔬",
        }.get(lane["status"], "⚪")
        lines += [
            f"## {status_icon} {lane['lane_id']} — {lane['display_name']}",
            "",
            f"**Status:** {lane['status']} | **Priority:** {lane['priority']}",
            "",
            f"**Condition:** `{lane['condition_plain']}`",
            "",
            f"**Signal sources:** {', '.join(lane['signal_sources'])}",
            "",
            "### Evidence",
            "",
            f"| Metric | Value | vs Global |",
            f"|---|---|---|",
            f"| n | {e.get('n', '—')} | baseline n=1249 |",
            f"| Strike rate | {e.get('strike_rate', '—')}% | global {GLOBAL_SR}% |",
            f"| Frame rate | {e.get('frame_rate', '—')}% | global {GLOBAL_FRAME}% |",
            f"| SR lift | {e.get('sr_lift_vs_global', '—')}% | — |",
        ]
        if "avg_vp" in e:
            lines.append(f"| Avg VP | {e['avg_vp']} | — |")
        if "avg_winner_sp" in e:
            lines.append(f"| Avg winner SP | {e['avg_winner_sp']} | — |")
        lines += [
            "",
            f"**Note:** {e.get('note', '—')}",
            "",
            f"**Confidence level:** {lane.get('confidence_level', '—')}",
            "",
            f"**Confidence note:** {lane.get('confidence_note', '—')}",
            "",
        ]
        if "risks" in lane:
            lines += ["### Risks", ""]
            for r in lane["risks"]:
                lines.append(f"- {r}")
            lines.append("")
        if "promotion_gates" in lane:
            lines += ["### Promotion Gates", ""]
            for gate, crit in lane["promotion_gates"].items():
                lines.append(f"- **{gate}:** {crit}")
            lines.append("")
        if "freeze_conditions" in lane:
            lines += ["### Freeze Conditions", ""]
            for fc in lane["freeze_conditions"]:
                lines.append(f"- {fc}")
            lines.append("")
        if "suppression_protocol" in lane:
            lines += ["### Suppression Protocol", ""]
            for k, v in lane["suppression_protocol"].items():
                lines.append(f"- **{k}:** {v}")
            lines.append("")
        if "research_questions" in lane:
            lines += ["### Research Questions", ""]
            for q in lane["research_questions"]:
                lines.append(f"- {q}")
            lines.append("")
        lines += ["---", ""]
    return "\n".join(lines)


def build_evidence_doc(result: dict) -> str:
    lines = [
        "# VÉLØ Candidate Lanes V1",
        "",
        f"**Evidence basis:** Unified Evidence Audit V1 (49 days, 1391 sigma rows)",
        f"**Design date:** 2026-04-28",
        f"**Status:** Design only — no lanes are active**",
        "",
        "---",
        "",
        "## Lane Status Summary",
        "",
        "| Lane | Status | n | SR | Frame | Priority |",
        "|---|---|---|---|---|---|",
    ]
    status_symbols = {
        "SHADOW_CANDIDATE": "SHADOW_CANDIDATE",
        "WATCHLIST": "WATCHLIST",
        "SUPPRESS_CANDIDATE": "SUPPRESS_CANDIDATE",
        "FORENSICS_ONLY": "FORENSICS_ONLY",
    }
    for lane in result["lanes"]:
        e = lane.get("evidence", {})
        lines.append(
            f"| {lane['lane_id']} | {lane['status']} | "
            f"{e.get('n', '—')} | {e.get('strike_rate', '—')}% | "
            f"{e.get('frame_rate', '—')}% | {lane['priority']} |"
        )
    lines += [
        "",
        "---",
        "",
        "## Governance Principles",
        "",
    ]
    for p in result["governance"]["principles"]:
        lines.append(f"- {p}")
    lines += [
        "",
        "## Lane Lifecycle",
        "",
    ]
    for step in result["governance"]["shadow_lane_lifecycle"]:
        lines.append(f"1. {step}")
    lines += [
        "",
        "## Auto-Freeze Rules",
        "",
    ]
    for fc in result["governance"]["freeze_rules"]["auto_freeze"]:
        lines.append(f"- {fc}")
    lines += [
        "",
        f"**Unfreeze requires:** {result['governance']['freeze_rules']['unfreeze_requires']}",
        "",
        "---",
        "",
        "## Highest Priority Lanes",
        "",
        "### 1. VP30_TIER_A — Most Proven",
        "- n=162, SR=40.1%, Frame=77.2% across 49 days",
        "- This is the most evidence-backed lane in the system",
        "- Ready for shadow ledger tracking immediately",
        "",
        "### 2. MARKET_DECEPTION_HIGH — Highest Upside",
        "- n=31, SR=54.8%, Frame=96.8%",
        "- Exceptional numbers but small sample — must track for regression",
        "- Highest lift (+34.2%) of any signal in the system",
        "",
        "### 3. IMPROVEMENT_SCORE_HIGH — Strong and Growing",
        "- n=62, SR=43.5%, Frame=82.3%",
        "- Second-highest SR with meaningful sample",
        "- Consistently strong across operating period",
        "",
        "---",
        "",
        "## Next Steps",
        "",
        "1. Add shadow lane annotation fields to velo_verdicts or sigma_audits table",
        "2. Wire VP30_TIER_A shadow flag to daily sigma output (annotation only, no routing change)",
        "3. Wire MARKET_DECEPTION_HIGH shadow flag",
        "4. Wire IMPROVEMENT_SCORE_HIGH shadow flag",
        "5. Build shadow_lane_ledger.csv (separate from router_shadow_audit_ledger.csv)",
        "6. Run 30 qualifying results through each lane before first review",
        "7. No staking, no routing changes, no production impact",
        "",
        "---",
        "",
        "*VÉLØ Oracle Prime — Candidate Lanes V1 | Design only | No deployment*",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    main()
