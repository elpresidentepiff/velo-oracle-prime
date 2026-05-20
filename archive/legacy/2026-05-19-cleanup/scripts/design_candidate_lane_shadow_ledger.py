"""
VÉLØ Candidate Lane Shadow Ledger Design V1

Produces the design specification for per-lane append ledgers across all 6 candidate lanes.
This is a design document generator — it does NOT create live ledger files or write any
prediction data. The ledger implementation (append script) is a separate future mission.

Usage:
    python scripts/design_candidate_lane_shadow_ledger.py

Outputs:
    data/candidate_lane_shadow_ledger_design_v1.json
    data/candidate_lane_shadow_ledger_design_v1.md
    docs/evidence/VELO_CANDIDATE_LANE_SHADOW_LEDGER_PROTOCOL.md

Rules: No model changes. No router changes. No staking. Design documentation only.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUN_TS = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

# ─────────────────────────────────────────────────────────────────────────────
# ROW SCHEMA
# Every row appended to any lane ledger must contain these fields.
# ─────────────────────────────────────────────────────────────────────────────

ROW_SCHEMA = {
    "description": (
        "One row per qualifying race per lane. Append-only. "
        "Primary key: lane_id + race_id."
    ),
    "fields": [
        {"name": "row_id",             "type": "uuid",    "note": "auto-generated"},
        {"name": "lane_id",            "type": "text",    "note": "VP30_TIER_A | MARKET_DECEPTION_HIGH | etc"},
        {"name": "date",               "type": "date",    "note": "race date YYYY-MM-DD"},
        {"name": "race_id",            "type": "text",    "note": "from sigma_audits.race_id"},
        {"name": "race_time",          "type": "text",    "note": "off_time HH:MM"},
        {"name": "course",             "type": "text",    "note": "track/course name"},
        {"name": "horse",              "type": "text",    "note": "predicted pick name"},
        {"name": "velo_prime_prob",    "type": "float",   "note": "VP score 0-1"},
        {"name": "decision_tier",      "type": "text",    "note": "A/B/C/D/X"},
        {"name": "lane_condition",     "type": "text",    "note": "human-readable condition that qualified this row"},
        {"name": "signal_value",       "type": "float",   "note": "the key signal value that triggered the lane (MDS, improve_score, VP, etc)"},
        {"name": "market_deception_score", "type": "float", "note": "null if not relevant"},
        {"name": "improvement_score",  "type": "float",   "note": "null if not relevant"},
        {"name": "place_prob",         "type": "float",   "note": "null if not relevant"},
        {"name": "sp_decimal",         "type": "float",   "note": "starting price decimal at race time"},
        {"name": "result_position",    "type": "int",     "note": "1=winner, 2=placed, null=unranked"},
        {"name": "won",                "type": "boolean", "note": "true if outcome=WIN"},
        {"name": "framed",             "type": "boolean", "note": "true if outcome=WIN or PLACED"},
        {"name": "missed_winner",      "type": "boolean", "note": "true if outcome=MISS"},
        {"name": "missed_winner_sp",   "type": "float",   "note": "SP of actual winner if missed"},
        {"name": "miss_class",         "type": "text",    "note": "mid_priced_won | outsider_won | short_fav_won | market_decoy_followed | null"},
        {"name": "router_source",      "type": "text",    "note": "V1_BASE | V2_CLASS4_ONLY | V6_GOLD_SEAM | NONE"},
        {"name": "sidecar_sources",    "type": "text[]",  "note": "list of sidecars that also fired: MDS_HIGH | IMPROVE_HIGH | PLACE_HIGH"},
        {"name": "race_archetype",     "type": "text",    "note": "Structure | Compression | Null"},
        {"name": "audit_status",       "type": "text",    "note": "COMPLETE | PENDING | UNRESOLVABLE"},
        {"name": "created_at",         "type": "timestamptz", "note": "UTC timestamp of row creation"},
        {"name": "sigma_audit_id",     "type": "uuid",    "note": "FK to sigma_audits.id"},
        {"name": "verdict_id",         "type": "uuid",    "note": "FK to velo_verdicts.id if available"},
    ],
    "primary_key": ["lane_id", "race_id"],
    "append_only": True,
    "dedup_rule": "If race_id already exists for a lane_id, skip — do not overwrite.",
}

# ─────────────────────────────────────────────────────────────────────────────
# RUNNING STATS SCHEMA
# These aggregates are recomputed after each append batch.
# ─────────────────────────────────────────────────────────────────────────────

RUNNING_STATS_SCHEMA = {
    "description": "Per-lane running stats, recomputed after every append batch.",
    "fields": [
        {"name": "lane_id",                   "type": "text"},
        {"name": "n",                          "type": "int",   "note": "total qualifying rows appended"},
        {"name": "wins",                       "type": "int"},
        {"name": "frames",                     "type": "int",   "note": "wins + placed"},
        {"name": "misses",                     "type": "int"},
        {"name": "strike_rate",                "type": "float", "note": "wins / n"},
        {"name": "frame_rate",                 "type": "float", "note": "frames / n"},
        {"name": "roi_research",               "type": "float", "note": "level-stake ROI at SP — research only, not operational"},
        {"name": "avg_velo_prime_prob",        "type": "float"},
        {"name": "avg_sp",                     "type": "float"},
        {"name": "avg_signal_value",           "type": "float", "note": "avg of the lane trigger value"},
        {"name": "first_date",                 "type": "date"},
        {"name": "last_date",                  "type": "date"},
        {"name": "operating_days_covered",     "type": "int"},
        {"name": "day_contributions",          "type": "dict", "note": "date → qualifying rows that day"},
        {"name": "consecutive_weak_days",      "type": "int",   "note": "days with SR=0 in a row"},
        {"name": "promotion_progress",         "type": "dict",  "note": "n_pct, sr_ok, frame_ok, ready_for_review"},
        {"name": "freeze_status",              "type": "text",  "note": "ACTIVE | FROZEN | FROZEN_PENDING_REVIEW"},
        {"name": "freeze_reason",              "type": "text",  "note": "null if ACTIVE"},
        {"name": "last_computed_at",           "type": "timestamptz"},
    ],
}

# ─────────────────────────────────────────────────────────────────────────────
# LANE SPECIFICATIONS
# One entry per candidate lane — conditions, promotion gates, freeze rules.
# ─────────────────────────────────────────────────────────────────────────────

LANES = [
    {
        "lane_id": "VP30_TIER_A",
        "display_name": "VP≥0.30 + Tier A",
        "status": "SHADOW_CANDIDATE",
        "lane_classification": "PROVEN_SIGNAL_SHADOW_TRACK",
        "description": "Races where velo_prime_prob >= 0.30 AND decision_tier == 'A'. The primary live signal gate.",
        "condition": "velo_prime_prob >= 0.30 AND decision_tier == 'A'",
        "trigger_field": "velo_prime_prob",
        "trigger_threshold": 0.30,
        "secondary_condition": "decision_tier == 'A'",
        "baseline_evidence": {
            "n": 162, "sr": 0.401, "frame": 0.772,
            "source": "velo_unified_evidence_audit_v1 (49 days)"
        },
        "promotion_gates": {
            "minimum_n": 250,
            "sr_floor": 0.35,
            "frame_floor": 0.70,
            "multi_week_required": True,
            "human_review_required": True,
            "next_stage": "WATCHLIST",
            "notes": "n=250 gives statistical stability. SR floor is set below current 40.1% to allow for natural variance."
        },
        "freeze_rules": {
            "auto_freeze_if": "SR < 0.20 at n >= 50 OR frame_rate < 0.55 at n >= 50",
            "review_freeze_if": "consecutive_weak_days >= 10",
            "unfreeze_condition": "operator review + SR recovery above floor",
        },
        "ledger_file": "data/shadow_ledgers/vp30_tier_a_shadow_ledger.csv",
        "priority": 2,
    },
    {
        "lane_id": "MARKET_DECEPTION_HIGH",
        "display_name": "Market Deception Score > 0.50",
        "status": "SHADOW_CANDIDATE",
        "lane_classification": "ELITE_SIGNAL_SHADOW_TRACK",
        "description": (
            "Races where market_deception_score > 0.50. "
            "POLARITY FLIP CONFIRMED: previously used as a decoy blocker. "
            "49-day audit shows SR=54.8%, Frame=96.8% — this signal identifies live contenders "
            "the market shape is disguising. Highest upside signal in the system."
        ),
        "condition": "market_deception_score > 0.50",
        "trigger_field": "market_deception_score",
        "trigger_threshold": 0.50,
        "secondary_condition": None,
        "baseline_evidence": {
            "n": 31, "sr": 0.548, "frame": 0.968,
            "lift": "+34.2%",
            "source": "velo_unified_evidence_audit_v1 (49 days)",
            "warning": "n=31 — elite signal but small sample. Treat with discipline."
        },
        "promotion_gates": {
            "minimum_n": 75,
            "sr_floor": 0.40,
            "frame_floor": 0.80,
            "multi_week_required": True,
            "human_review_required": True,
            "next_stage": "WATCHLIST",
            "notes": (
                "Lower n gate (75 vs 250) because the signal is extreme. "
                "If SR holds above 40% at n=75 this warrants urgent human review. "
                "Extra caution: if SR drops below 30% at n=50, freeze immediately — "
                "extreme signals that regress can indicate overfitting."
            )
        },
        "freeze_rules": {
            "auto_freeze_if": "SR < 0.25 at n >= 40 OR frame_rate < 0.65 at n >= 40",
            "review_freeze_if": "consecutive_weak_days >= 7",
            "polarity_watch": "If SR falls below global baseline (20.6%), the polarity flip hypothesis fails — escalate immediately.",
            "unfreeze_condition": "operator review — do not auto-unfreeze this lane",
        },
        "ledger_file": "data/shadow_ledgers/market_deception_high_shadow_ledger.csv",
        "priority": 1,
    },
    {
        "lane_id": "IMPROVEMENT_SCORE_HIGH",
        "display_name": "Improvement Score > 0.40",
        "status": "SHADOW_CANDIDATE",
        "lane_classification": "PROVEN_SIGNAL_SHADOW_TRACK",
        "description": "Races where improvement_score > 0.40. Captures horses showing progressive form improvement.",
        "condition": "improvement_score > 0.40",
        "trigger_field": "improvement_score",
        "trigger_threshold": 0.40,
        "secondary_condition": None,
        "baseline_evidence": {
            "n": 62, "sr": 0.435, "frame": 0.823,
            "lift": "+22.9%",
            "source": "velo_unified_evidence_audit_v1 (49 days)"
        },
        "promotion_gates": {
            "minimum_n": 100,
            "sr_floor": 0.35,
            "frame_floor": 0.75,
            "multi_week_required": True,
            "human_review_required": True,
            "next_stage": "WATCHLIST",
            "notes": "n=62 at baseline. Need 100 to confirm. SR floor set below current 43.5% to allow variance."
        },
        "freeze_rules": {
            "auto_freeze_if": "SR < 0.22 at n >= 60 OR frame_rate < 0.60 at n >= 60",
            "review_freeze_if": "consecutive_weak_days >= 10",
            "unfreeze_condition": "operator review + SR recovery above floor",
        },
        "ledger_file": "data/shadow_ledgers/improvement_score_high_shadow_ledger.csv",
        "priority": 3,
    },
    {
        "lane_id": "PLACE_PROB_HIGH",
        "display_name": "Place Probability > 0.80",
        "status": "WATCHLIST",
        "lane_classification": "PROMISING_SIGNAL_WATCHLIST",
        "description": (
            "Races where place_prob > 0.80. Large sample signal (n=392). "
            "SR=31.6% is meaningful but requires VP or Tier A overlay before candidate promotion. "
            "Currently WATCHLIST — not yet a shadow candidate."
        ),
        "condition": "place_prob > 0.80",
        "trigger_field": "place_prob",
        "trigger_threshold": 0.80,
        "secondary_condition": None,
        "baseline_evidence": {
            "n": 392, "sr": 0.316, "frame": 0.668,
            "lift": "+11.0%",
            "source": "velo_unified_evidence_audit_v1 (49 days)"
        },
        "promotion_gates": {
            "minimum_n": 500,
            "sr_floor": 0.28,
            "frame_floor": 0.65,
            "overlay_required": "VP >= 0.30 OR decision_tier == 'A' required before SHADOW_CANDIDATE promotion",
            "human_review_required": True,
            "next_stage": "SHADOW_CANDIDATE (with VP/Tier overlay requirement)",
            "notes": (
                "Place probability alone is not enough — it is measuring a different dimension than VP. "
                "Only valid as a shadow candidate when combined with VP≥0.30 or Tier A. "
                "Track volume at n=392 is the highest in the system — watch for sample dilution."
            )
        },
        "freeze_rules": {
            "auto_freeze_if": "SR < 0.18 at n >= 200 OR frame_rate < 0.50 at n >= 200",
            "review_freeze_if": "consecutive_weak_days >= 14",
            "unfreeze_condition": "operator review",
        },
        "ledger_file": "data/shadow_ledgers/place_prob_high_shadow_ledger.csv",
        "priority": 4,
    },
    {
        "lane_id": "B_TIER_LOW_VP_SUPPRESS",
        "display_name": "Tier B + VP < 0.30 (SUPPRESS CANDIDATE)",
        "status": "SUPPRESS_CANDIDATE",
        "lane_classification": "SUPPRESS_CANDIDATE",
        "description": (
            "Races where decision_tier == 'B' AND velo_prime_prob < 0.30. "
            "SR=16.9%, Frame=44.1% — confirmed drag on global metrics. "
            "Suppression test: removing these 272 races improves global SR from 20.6% → 21.6% "
            "at a coverage cost of -21.8%. Tracking to confirm drag persists before suppression protocol."
        ),
        "condition": "decision_tier == 'B' AND velo_prime_prob < 0.30",
        "trigger_field": "decision_tier",
        "trigger_threshold": None,
        "secondary_condition": "velo_prime_prob < 0.30",
        "baseline_evidence": {
            "n": 272, "sr": 0.169, "frame": 0.441,
            "suppression_gain": "+1.0% global SR, +1.2% global frame at -21.8% coverage",
            "source": "velo_unified_evidence_audit_v1 (49 days)"
        },
        "suppression_review_gates": {
            "minimum_n": 350,
            "sr_ceiling": 0.18,
            "frame_ceiling": 0.50,
            "notes": (
                "If SR remains below 18% and frame below 50% at n=350, "
                "suppression protocol is warranted. Present evidence to operator for decision. "
                "Do NOT auto-suppress — this is a coverage reduction and requires explicit approval."
            )
        },
        "recovery_gates": {
            "recovery_if": "SR climbs above 22% at n >= 300",
            "notes": "If SR recovers, re-classify as WATCHLIST and hold suppression."
        },
        "freeze_rules": {
            "not_applicable": True,
            "notes": "Suppress candidates do not freeze — they accumulate evidence towards a suppression decision.",
        },
        "ledger_file": "data/shadow_ledgers/b_tier_low_vp_suppress_ledger.csv",
        "priority": 5,
    },
    {
        "lane_id": "MID_PRICE_WINNER_FORENSICS",
        "display_name": "Mid-Price Winner Forensics (SP 3.0–8.5 Miss Zone)",
        "status": "FORENSICS_ONLY",
        "lane_classification": "FORENSICS_ONLY",
        "description": (
            "Races where VÉLØ missed and the actual winner had SP between 3.0 and 8.5. "
            "352 misses = 58% of all misses across 49 days. This is the primary unsolved problem. "
            "No scoring function. No execution target. Research only."
        ),
        "condition": "outcome == 'MISS' AND actual_winner_sp >= 3.0 AND actual_winner_sp <= 8.5",
        "trigger_field": "actual_winner_sp",
        "trigger_threshold": None,
        "secondary_condition": "outcome == 'MISS'",
        "baseline_evidence": {
            "miss_count": 352,
            "pct_of_all_misses": 0.58,
            "sp_zone": "3.0 to 8.5",
            "source": "velo_unified_evidence_audit_v1 (49 days)"
        },
        "research_questions": [
            "1. SP clustering — where within 3.0–8.5 do misses concentrate? (3.0–4.5 vs 5.0–8.5?)",
            "2. VP distribution — what VP score did VÉLØ assign to these races when it missed?",
            "3. Tier distribution — are mid-price winner misses concentrated in Tier B/C?",
            "4. Race type distribution — flat vs jump? Class 3/4/5 split?",
            "5. Course/distance pattern — do certain tracks produce more mid-price winner misses?",
            "6. Time of meeting — do mid-price winner misses cluster in later races?",
        ],
        "forensics_goal": (
            "Determine whether VÉLØ is systematically underweighting mid-price contenders, "
            "or whether this is irreducible noise at 3.0–8.5 SP. If systematic, identify "
            "which feature or model component is responsible."
        ),
        "promotion_path": "NONE — forensics only. Cannot be promoted to a shadow candidate.",
        "ledger_file": "data/shadow_ledgers/mid_price_winner_forensics_ledger.csv",
        "ledger_note": (
            "Forensics ledger captures MISS rows in SP 3.0–8.5 zone. "
            "Each row has the full miss context for pattern analysis."
        ),
        "priority": 6,
    },
]

# ─────────────────────────────────────────────────────────────────────────────
# GOVERNANCE
# ─────────────────────────────────────────────────────────────────────────────

GOVERNANCE = {
    "principles": [
        "All ledgers are append-only. No row is ever deleted or modified after writing.",
        "A race qualifies for a lane when it meets the lane condition at the time of prediction.",
        "Lane qualification is determined from sigma_audit rows (post-result), not from racecard.",
        "Signal values (MDS, improve_score, VP) come from velo_verdicts or verdict JSON — not recalculated.",
        "Ledger rows are written by the shadow ledger append script after each sigma batch.",
        "No staking or betting decision is ever derived from ledger state.",
        "No lane can be promoted without explicit operator approval.",
    ],
    "lifecycle": {
        "stages": [
            "DESIGN (current) — lane defined, schema specified, no live rows",
            "SHADOW_CANDIDATE — live rows accumulating, no execution",
            "WATCHLIST — n gate passed, SR/Frame reviewed, watching for stability",
            "PAPER_EXECUTION — operator tracks as if executing, still no staking",
            "LIVE_DISCUSSION — sustained evidence, operator review for live activation",
            "LIVE_ACTIVATION — explicit operator approval, full audit trail required",
        ],
        "freeze_stages": ["FROZEN", "FROZEN_PENDING_REVIEW"],
        "current_stage_all_lanes": "DESIGN",
    },
    "append_script": {
        "name": "scripts/run_candidate_lane_shadow_append.py",
        "status": "NOT_YET_BUILT",
        "purpose": "Reads today's sigma results, evaluates each lane condition, appends qualifying rows to ledger CSVs.",
        "trigger": "After scripts/run_results_sigma.py completes",
        "next_mission": "candidate_lane_shadow_ledger_dry_run",
    },
    "storage": {
        "primary": "data/shadow_ledgers/ — CSV files, one per lane",
        "index": "data/shadow_ledgers/shadow_ledger_index.json — running stats per lane",
        "immutable_snapshots": "data/shadow_ledgers/snapshots/ — timestamped on each batch",
        "supabase_path": "FUTURE — table candidate_lane_shadow_rows if/when DB schema approved",
    },
    "hard_rules": [
        "NO staking or betting based on ledger state.",
        "NO router rule changes from ledger observations.",
        "NO model training based on ledger patterns.",
        "NO promotion without operator approval.",
        "NO auto-unfreeze of MARKET_DECEPTION_HIGH — operator-only.",
    ],
}


# ─────────────────────────────────────────────────────────────────────────────
# OUTPUT BUILDERS
# ─────────────────────────────────────────────────────────────────────────────

def build_json() -> dict:
    return {
        "design_version": 1,
        "created": RUN_TS,
        "status": "DESIGN_ONLY_NOT_YET_ACTIVE",
        "baseline_commits": {
            "candidate_lane_design": "3a007eb",
            "evidence_vault": "63f37e9",
            "router_baseline": "06ba74b",
        },
        "row_schema": ROW_SCHEMA,
        "running_stats_schema": RUNNING_STATS_SCHEMA,
        "lanes": LANES,
        "governance": GOVERNANCE,
    }


def status_icon(lane: dict) -> str:
    s = lane["status"]
    return {
        "SHADOW_CANDIDATE": "🔵",
        "WATCHLIST": "🟡",
        "SUPPRESS_CANDIDATE": "🔴",
        "FORENSICS_ONLY": "🔬",
    }.get(s, "⚪")


def build_markdown(data: dict) -> str:
    lines = [
        "# VÉLØ Candidate Lane Shadow Ledger Design V1",
        "",
        f"**Created:** {data['created']}",
        "**Status:** DESIGN ONLY — no live rows exist yet",
        "",
        "---",
        "",
        "## Purpose",
        "",
        "This document specifies the per-lane append ledger schema for all 6 VÉLØ candidate lanes.",
        "Each lane accumulates shadow evidence rows from closed race results.",
        "No staking. No routing changes. Evidence accumulation and operator visibility only.",
        "",
        "---",
        "",
        "## Lane Summary",
        "",
        "| # | Lane | Status | SR (baseline) | Frame | n | Priority |",
        "|---|---|---|---|---|---|---|",
    ]
    for lane in data["lanes"]:
        ev = lane["baseline_evidence"]
        sr_str = f"{ev.get('sr', 0)*100:.1f}%" if ev.get("sr") else "—"
        fr_str = f"{ev.get('frame', 0)*100:.1f}%" if ev.get("frame") else f"{ev.get('miss_count','?')} misses"
        n_str = str(ev.get("n", ev.get("miss_count", "?")))
        icon = status_icon(lane)
        lines.append(
            f"| {lane['priority']} | {icon} {lane['display_name']} | {lane['status']} | "
            f"{sr_str} | {fr_str} | {n_str} | {lane['priority']} |"
        )
    lines += [
        "",
        "---",
        "",
        "## Row Schema",
        "",
        "Every qualifying row appended to any lane ledger contains these fields:",
        "",
        "| Field | Type | Note |",
        "|---|---|---|",
    ]
    for f in data["row_schema"]["fields"]:
        lines.append(f"| `{f['name']}` | {f['type']} | {f['note']} |")
    lines += [
        "",
        f"**Primary key:** `{' + '.join(data['row_schema']['primary_key'])}`",
        f"**Append-only:** {data['row_schema']['append_only']}",
        f"**Dedup rule:** {data['row_schema']['dedup_rule']}",
        "",
        "---",
        "",
        "## Lane Specifications",
        "",
    ]

    for lane in data["lanes"]:
        icon = status_icon(lane)
        ev = lane["baseline_evidence"]
        lines += [
            f"### {icon} {lane['display_name']}",
            "",
            f"**Lane ID:** `{lane['lane_id']}`",
            f"**Status:** {lane['status']}",
            f"**Classification:** {lane['lane_classification']}",
            f"**Priority:** {lane['priority']}",
            "",
            f"**Condition:** `{lane['condition']}`",
            "",
            f"*{lane['description']}*",
            "",
        ]

        # Evidence
        if "sr" in ev:
            lines += [
                "**Baseline Evidence (49-day unified audit):**",
                "",
                f"| n | SR | Frame | Source |",
                f"|---|---|---|---|",
                f"| {ev['n']} | {ev['sr']*100:.1f}% | {ev.get('frame', 0)*100:.1f}% | {ev['source']} |",
                "",
            ]
            if ev.get("warning"):
                lines.append(f"> **Warning:** {ev['warning']}")
                lines.append("")
        else:
            lines += [
                "**Baseline Evidence:**",
                f"- Miss count: {ev.get('miss_count')} ({ev.get('pct_of_all_misses', 0)*100:.0f}% of all misses)",
                f"- SP zone: {ev.get('sp_zone')}",
                "",
            ]

        # Promotion or suppression gates
        if lane.get("promotion_gates"):
            pg = lane["promotion_gates"]
            lines += [
                "**Promotion Gates:**",
                "",
                f"| Gate | Requirement |",
                f"|---|---|",
                f"| Minimum n | {pg['minimum_n']} |",
                f"| SR floor | {pg.get('sr_floor', 0)*100:.0f}% |",
                f"| Frame floor | {pg.get('frame_floor', 0)*100:.0f}% |",
                f"| Multi-week required | {pg.get('multi_week_required', 'N/A')} |",
                f"| Human review required | {pg.get('human_review_required', True)} |",
                f"| Next stage | {pg['next_stage']} |",
                "",
                f"*{pg['notes']}*",
                "",
            ]
        elif lane.get("suppression_review_gates"):
            sg = lane["suppression_review_gates"]
            lines += [
                "**Suppression Review Gates:**",
                "",
                f"- Minimum n: {sg['minimum_n']}",
                f"- SR ceiling: {sg['sr_ceiling']*100:.0f}% (suppress if SR stays below this)",
                f"- Frame ceiling: {sg['frame_ceiling']*100:.0f}%",
                "",
                f"*{sg['notes']}*",
                "",
            ]

        # Freeze rules
        if lane.get("freeze_rules") and not lane["freeze_rules"].get("not_applicable"):
            fr = lane["freeze_rules"]
            lines += [
                "**Freeze Rules:**",
                "",
                f"- Auto-freeze: `{fr.get('auto_freeze_if', 'N/A')}`",
                f"- Review-freeze: `{fr.get('review_freeze_if', 'N/A')}`",
                f"- Unfreeze: {fr.get('unfreeze_condition', 'N/A')}",
                "",
            ]
            if fr.get("polarity_watch"):
                lines.append(f"> **Polarity Watch:** {fr['polarity_watch']}")
                lines.append("")

        # Research questions (forensics lane)
        if lane.get("research_questions"):
            lines += ["**Research Questions:**", ""]
            for q in lane["research_questions"]:
                lines.append(f"- {q}")
            lines += [
                "",
                f"**Goal:** {lane['forensics_goal']}",
                "",
            ]

        lines += [
            f"**Ledger file:** `{lane['ledger_file']}`",
            "",
            "---",
            "",
        ]

    lines += [
        "## Governance",
        "",
        "### Principles",
        "",
    ]
    for p in data["governance"]["principles"]:
        lines.append(f"- {p}")
    lines += [
        "",
        "### Lifecycle",
        "",
    ]
    for s in data["governance"]["lifecycle"]["stages"]:
        lines.append(f"- {s}")
    lines += [
        "",
        f"**Current stage (all lanes):** {data['governance']['lifecycle']['current_stage_all_lanes']}",
        "",
        "### Append Script",
        "",
        f"- **Script:** `{data['governance']['append_script']['name']}`",
        f"- **Status:** {data['governance']['append_script']['status']}",
        f"- **Purpose:** {data['governance']['append_script']['purpose']}",
        f"- **Next mission:** `{data['governance']['append_script']['next_mission']}`",
        "",
        "### Hard Rules",
        "",
    ]
    for r in data["governance"]["hard_rules"]:
        lines.append(f"- {r}")
    lines += [
        "",
        "---",
        f"*VÉLØ Candidate Lane Shadow Ledger Design V1 | {data['created']}*",
    ]
    return "\n".join(lines)


def build_protocol_doc(data: dict) -> str:
    lines = [
        "# VÉLØ Candidate Lane Shadow Ledger Protocol",
        "",
        f"**Version:** 1",
        f"**Created:** {data['created']}",
        "**Status:** DESIGN ONLY",
        "",
        "---",
        "",
        "## What This Protocol Governs",
        "",
        "The shadow ledger system tracks qualifying races against each candidate signal lane",
        "after race results close. It provides the evidence base for future promotion decisions.",
        "It does not change predictions, routing logic, staking, or any production system.",
        "",
        "---",
        "",
        "## When to Append",
        "",
        "After every sigma batch (`run_results_sigma.py`), run the append script:",
        "",
        "```bash",
        "source venv/bin/activate",
        "PYTHONPATH=. python scripts/run_candidate_lane_shadow_append.py --date YYYY-MM-DD",
        "```",
        "",
        "*(Script not yet built — next mission: candidate_lane_shadow_ledger_dry_run)*",
        "",
        "---",
        "",
        "## How Qualification Works",
        "",
        "For each sigma_audit row on the date:",
        "1. Load the verdict JSON for that race (VP, MDS, improve_score, place_prob, tier)",
        "2. Evaluate each lane condition",
        "3. If condition met: append one row to that lane's ledger CSV",
        "4. A race may qualify for multiple lanes simultaneously",
        "5. Dedup: skip if race_id already exists in that lane's ledger",
        "",
        "---",
        "",
        "## Highest Priority Lane",
        "",
        "> **MARKET_DECEPTION_HIGH** — SR=54.8%, Frame=96.8%, n=31",
        ">",
        "> This is the highest-lift signal in the system. The polarity flip (previously used as",
        "> a decoy blocker, now confirmed as a winner predictor) makes this the most important",
        "> signal to track. Every qualifying row added to this ledger is high-value evidence.",
        "",
        "---",
        "",
        "## Promotion Decision Process",
        "",
        "1. Running stats are computed after each batch",
        "2. When minimum_n is reached, SR and Frame are reviewed",
        "3. If SR >= floor AND Frame >= floor: generate promotion notice to operator",
        "4. Operator reviews lane evidence document before any promotion decision",
        "5. No promotion without explicit operator approval",
        "6. Promotion moves lane to next lifecycle stage — it does NOT activate live staking",
        "",
        "---",
        "",
        "## Storage Layout",
        "",
        "```",
        "data/shadow_ledgers/",
        "  vp30_tier_a_shadow_ledger.csv",
        "  market_deception_high_shadow_ledger.csv",
        "  improvement_score_high_shadow_ledger.csv",
        "  place_prob_high_shadow_ledger.csv",
        "  b_tier_low_vp_suppress_ledger.csv",
        "  mid_price_winner_forensics_ledger.csv",
        "  shadow_ledger_index.json           ← running stats per lane",
        "  snapshots/                          ← immutable timestamped snapshots",
        "```",
        "",
        "---",
        "",
        "## Hard Rules (Non-Negotiable)",
        "",
    ]
    for r in data["governance"]["hard_rules"]:
        lines.append(f"- {r}")
    lines += [
        "",
        "---",
        f"*VÉLØ Shadow Ledger Protocol V1 | {data['created']}*",
    ]
    return "\n".join(lines)


def main():
    print("VÉLØ Candidate Lane Shadow Ledger Design V1")
    print(f"Run: {RUN_TS}")
    print("=" * 60)

    data = build_json()

    # JSON
    json_path = ROOT / "data" / "candidate_lane_shadow_ledger_design_v1.json"
    with open(json_path, "w") as f:
        json.dump(data, f, indent=2, default=str)
    print(f"Written: {json_path}")

    # Markdown
    md_path = ROOT / "data" / "candidate_lane_shadow_ledger_design_v1.md"
    with open(md_path, "w") as f:
        f.write(build_markdown(data))
    print(f"Written: {md_path}")

    # Protocol doc
    proto_path = ROOT / "docs" / "evidence" / "VELO_CANDIDATE_LANE_SHADOW_LEDGER_PROTOCOL.md"
    proto_path.parent.mkdir(parents=True, exist_ok=True)
    with open(proto_path, "w") as f:
        f.write(build_protocol_doc(data))
    print(f"Written: {proto_path}")

    print()
    print("Design complete — no live ledger rows created.")
    print("No routing, model, or staking logic was changed.")
    print(f"\nHighest-priority lane: MARKET_DECEPTION_HIGH (SR=54.8%, n=31)")
    print(f"Next mission: candidate_lane_shadow_ledger_dry_run")


if __name__ == "__main__":
    main()
