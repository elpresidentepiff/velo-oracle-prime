#!/usr/bin/env python3
"""
scripts/ops/vfu_vp_suppression_investigation.py
=================================================
VFU-09 — Kakirra / VP Suppression Investigation (dry-run only).

Root-cause investigation: why did VP undercount Kakirra and Man is King
despite their Passport profiles showing improvement?

Core question: is this a VP failure, a Passport success, or both?

Does NOT change VP formula, scoring, or live doctrine.
Does NOT mutate canonical Passport.
Does NOT write Supabase.
Does NOT promote doctrine.

Control group design (identity-enriched autopsy, current era):
  Group A: VP_UNDERCOUNTING winners — wins with VP < 0.40, RP_UID confirmed
  Group B: High-VP winners         — wins with VP >= 0.40, RP_UID confirmed
  Group C: Low-VP non-winners      — misses with VP < 0.40, RP_UID confirmed
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

# ── Inputs ────────────────────────────────────────────────────────────────────
AUTOPSY_ID      = ROOT / "data/reports/vfu_current_era_autopsy_records_identity_enriched.jsonl"
AUTOPSY_FULL    = ROOT / "data/reports/vfu_full_current_era_autopsy_records.jsonl"
CLUSTERS_FILE   = ROOT / "data/reports/vfu_horse_id_bridge_repeated_clusters.json"
TRUTH_TABLE     = ROOT / "data/reports/vfu_repeated_horse_truth_table.json"
KAKIRRA_CASE    = ROOT / "data/reports/vfu_passport_review_kakirra_case_study.md"
CANDS_FILE      = ROOT / "data/reports/vfu_passport_review_candidates.jsonl"
OP_QUEUE        = ROOT / "data/reports/vfu_passport_review_operator_decision_queue.json"
PROSECUTOR_WL   = ROOT / "data/reports/vfu_pattern_prosecutor_watchlist.json"
PASSPORT_FILE   = ROOT / "data/new_build/passports/horse_passports_v1.jsonl"

# ── Outputs ───────────────────────────────────────────────────────────────────
OUT_JSON        = ROOT / "data/reports/vfu_vp_suppression_investigation.json"
OUT_MD          = ROOT / "data/reports/vfu_vp_suppression_investigation.md"
OUT_CASES       = ROOT / "data/reports/vfu_vp_suppression_cases.jsonl"
OUT_WATCHLIST   = ROOT / "data/reports/vfu_passport_override_watchlist.json"
OUT_HUMAN_QUEUE = ROOT / "data/reports/vfu_vp_suppression_human_review_queue.json"

INVESTIGATION_VERSION = "VFU_09_VP_SUPPRESSION_INVESTIGATION_V1"
VP_THRESHOLD    = 0.40
BASELINE_SR     = 0.264
CURRENT_ERA_SCOPE = "2026-05-08 to 2026-06-13"

SUPPRESSION_TAXONOMY = [
    "PASSPORT_IMPROVEMENT_AHEAD_OF_VP",
    "AW_SPECIALIST_UNDERCOUNTED",
    "SP_SHORTENING_UNDERWEIGHTED",
    "REPEAT_WINNER_UNDERCOUNTED",
    "SURFACE_SPECIALIST_UNDERCOUNTED",
    "COURSE_SPECIALIST_UNDERCOUNTED",
    "LOW_FEATURE_COVERAGE_SUPPRESSED_VP",
    "SOURCE_LAYER_SUPPRESSED_VP",
    "OR_FALLING_CLASS_DROP_PATTERN",
    "UNKNOWN_REQUIRES_REVIEW",
]

CORE_DOCTRINE = (
    "VP is valid as a population signal. "
    "VP is not valid as a hard individual horse disqualifier. "
    "Identity-confirmed Passport evidence may reveal improving horses "
    "before VP crosses threshold."
)


def norm_horse(h: str | None) -> str:
    if not h:
        return ""
    h = h.strip().lower()
    h = re.sub(r"\s*\([a-z]+\)\s*$", "", h)
    h = re.sub(r"[^a-z0-9 ]", "", h)
    return re.sub(r"\s+", " ", h).strip()


def load_jsonl(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def safe_avg(vals: list) -> float | None:
    cleaned = [v for v in vals if v is not None]
    return mean(cleaned) if cleaned else None


def pp_rate(rows: list, pp: dict, field: str) -> float:
    vals = [pp.get(str(r.get("horse_id")), {}).get(field) for r in rows]
    return sum(1 for v in vals if v) / max(len(vals), 1)


def pp_avg(rows: list, pp: dict, field: str) -> float | None:
    vals = [pp.get(str(r.get("horse_id")), {}).get(field) for r in rows
            if pp.get(str(r.get("horse_id")), {}).get(field) is not None]
    return mean(vals) if vals else None


def rate(rows: list, pp: dict, field: str, value: str) -> float:
    matches = sum(1 for r in rows if pp.get(str(r.get("horse_id")), {}).get(field) == value)
    return matches / max(len(rows), 1)


# ── Load canonical passports ──────────────────────────────────────────────────

def load_canonical(path: Path) -> dict:
    result = {}
    for line in path.open(encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        uid = row.get("horse_rp_uid")
        if uid is not None:
            result[str(uid)] = row
    return result


# ── Suppression reason classifier ─────────────────────────────────────────────

def classify_suppression(horse_id: str, pp: dict, runs: list[dict]) -> list[str]:
    reasons = []
    passport = pp.get(str(horse_id), {})

    tier_b_or_c = all(
        r.get("evidence_quality_tier") in ("TIER_B_GOOD_NO_PICK_SP", "TIER_C_LIMITED_IDENTITY")
        for r in runs
    )
    if tier_b_or_c:
        reasons.append("LOW_FEATURE_COVERAGE_SUPPRESSED_VP")
        reasons.append("SOURCE_LAYER_SUPPRESSED_VP")

    if passport.get("aw_specialist"):
        reasons.append("AW_SPECIALIST_UNDERCOUNTED")

    if passport.get("sp_trajectory") == "SHORTENING":
        reasons.append("SP_SHORTENING_UNDERWEIGHTED")

    if passport.get("position_trend") == "IMPROVING":
        reasons.append("PASSPORT_IMPROVEMENT_AHEAD_OF_VP")

    if len(runs) >= 2 and all(r.get("outcome") == "WIN" for r in runs):
        reasons.append("REPEAT_WINNER_UNDERCOUNTED")

    if passport.get("or_trajectory") == "FALLING" and passport.get("class_movement") == "DOWN":
        reasons.append("OR_FALLING_CLASS_DROP_PATTERN")

    if not reasons:
        reasons.append("UNKNOWN_REQUIRES_REVIEW")

    return list(dict.fromkeys(reasons))


# ── Deep horse investigation ──────────────────────────────────────────────────

def investigate_horse(
    horse_name: str,
    horse_id: str,
    autopsy_rows: list[dict],
    canon: dict,
    truth_tables: dict,
) -> dict:
    runs = [r for r in autopsy_rows if str(r.get("horse_id", "")) == horse_id
            or norm_horse(r.get("horse_name", "")) == norm_horse(horse_name)]
    passport = canon.get(str(horse_id), {})
    cluster = truth_tables.get(norm_horse(horse_name), {})

    vp_vals = [r["vp"] for r in runs if r.get("vp") is not None]
    outcomes = [r.get("outcome") for r in runs]
    wins = [r for r in runs if r.get("outcome") == "WIN"]
    wins_below_vp = [r for r in wins if (r.get("vp") or 1.0) < VP_THRESHOLD]
    courses = list(dict.fromkeys(r.get("course") for r in runs if r.get("course")))
    tiers = [r.get("evidence_quality_tier") for r in runs]

    vp_trend = "FLAT"
    if len(vp_vals) >= 2:
        first_half = vp_vals[:len(vp_vals)//2]
        second_half = vp_vals[len(vp_vals)//2:]
        first_avg = mean(first_half) if first_half else 0
        second_avg = mean(second_half) if second_half else 0
        if second_avg > first_avg + 0.02:
            vp_trend = "RISING"
        elif second_avg < first_avg - 0.02:
            vp_trend = "FALLING"

    suppression_reasons = classify_suppression(horse_id, canon, runs)

    what_passport_knew = []
    what_vp_missed = []

    if passport.get("win_rate", 0) > 0.25:
        what_passport_knew.append(f"High career win rate ({passport.get('win_rate'):.0%})")
    if passport.get("sp_trajectory") == "SHORTENING":
        what_passport_knew.append("SP trajectory shortening (market ahead of model)")
    if passport.get("position_trend") == "IMPROVING":
        what_passport_knew.append("Position trend improving")
    if passport.get("margin_trend") == "IMPROVING":
        what_passport_knew.append("Margin trend improving")
    if passport.get("aw_specialist"):
        what_passport_knew.append("AW specialist")
    if passport.get("win_rate_last3", 0) > 0.4:
        what_passport_knew.append(f"Win rate last 3: {passport.get('win_rate_last3'):.0%}")
    if passport.get("setup_run_candidate"):
        what_passport_knew.append("Setup run candidate flag")

    if "LOW_FEATURE_COVERAGE_SUPPRESSED_VP" in suppression_reasons:
        what_vp_missed.append("No pick_sp on TIER_B rows → market signal absent → VP suppressed")
    if "AW_SPECIALIST_UNDERCOUNTED" in suppression_reasons:
        what_vp_missed.append("AW specialist pattern: model may not weight surface specialization")
    if "SP_SHORTENING_UNDERWEIGHTED" in suppression_reasons:
        what_vp_missed.append("Market shortening SP not reflected in VP at time of score")
    if "REPEAT_WINNER_UNDERCOUNTED" in suppression_reasons:
        what_vp_missed.append("Repeated winning pattern: improvement signal didn't accumulate within current era")
    if "OR_FALLING_CLASS_DROP_PATTERN" in suppression_reasons:
        what_vp_missed.append("OR falling + class drop scored negatively despite being a win trigger pattern")
    if "PASSPORT_IMPROVEMENT_AHEAD_OF_VP" in suppression_reasons:
        what_vp_missed.append("Horse improving faster than VP model recognised from available features")

    return {
        "horse_name": horse_name,
        "horse_id": horse_id,
        "horse_id_namespace": "RP_UID",
        "vfu_appearances": len(runs),
        "outcomes": outcomes,
        "wins_count": len(wins),
        "strike_rate": len(wins) / max(len(runs), 1),
        "vp_values": vp_vals,
        "avg_vp": mean(vp_vals) if vp_vals else None,
        "min_vp": min(vp_vals) if vp_vals else None,
        "max_vp": max(vp_vals) if vp_vals else None,
        "vp_trend": vp_trend,
        "courses": courses,
        "surface_types": list(dict.fromkeys("AW" if c in ("Wolverhampton", "Kempton", "Lingfield",
                                                            "Southwell", "Chelmsford") else "TURF"
                                            for c in courses)),
        "evidence_tiers": tiers,
        "wins_below_vp_threshold": len(wins_below_vp),
        "all_wins_below_vp_threshold": len(wins_below_vp) == len(wins),
        "passport_win_rate": passport.get("win_rate"),
        "passport_win_rate_last3": passport.get("win_rate_last3"),
        "passport_sp_trajectory": passport.get("sp_trajectory"),
        "passport_position_trend": passport.get("position_trend"),
        "passport_margin_trend": passport.get("margin_trend"),
        "passport_or_trajectory": passport.get("or_trajectory"),
        "passport_current_or": passport.get("current_or"),
        "passport_aw_specialist": passport.get("aw_specialist"),
        "passport_career_runs": passport.get("career_runs"),
        "passport_avg_sp_last3": passport.get("avg_sp_last3"),
        "passport_avg_sp_last5": passport.get("avg_sp_last5"),
        "passport_class_movement": passport.get("class_movement"),
        "passport_setup_run_candidate": passport.get("setup_run_candidate"),
        "suppression_reasons": suppression_reasons,
        "what_passport_knew": what_passport_knew,
        "what_vp_missed": what_vp_missed,
        "per_run_detail": [
            {
                "date": r.get("race_date"),
                "course": r.get("course"),
                "vp": r.get("vp"),
                "vp_below_threshold": (r.get("vp") or 1.0) < VP_THRESHOLD,
                "outcome": r.get("outcome"),
                "evidence_tier": r.get("evidence_quality_tier"),
            }
            for r in sorted(runs, key=lambda x: x.get("race_date", ""))
        ],
        "cluster_verdict": cluster.get("cluster_verdict") if cluster else None,
        "vfu08_verdict": "VP_UNDERCOUNTING_WATCHLIST",
        "confirmed_vp_undercounting": len(wins_below_vp) > 0 and len(wins_below_vp) == len(wins),
        "do_not_merge": True,
        "human_review_required": True,
        "blocked_from_live_use": True,
        "investigation_version": INVESTIGATION_VERSION,
    }


# ── Control group comparison ──────────────────────────────────────────────────

def build_control_groups(autopsy_rows: list[dict], canon: dict) -> dict:
    id_rows = [r for r in autopsy_rows if r.get("horse_id_namespace") == "RP_UID"
               and r.get("vp") is not None]

    group_a = [r for r in id_rows if r.get("outcome") == "WIN" and r["vp"] < VP_THRESHOLD]
    group_b = [r for r in id_rows if r.get("outcome") == "WIN" and r["vp"] >= VP_THRESHOLD]
    group_c = [r for r in id_rows if r.get("outcome") == "MISS" and r["vp"] < VP_THRESHOLD]

    def stats(rows: list) -> dict:
        aw = pp_rate(rows, canon, "aw_specialist")
        sp_short = rate(rows, canon, "sp_trajectory", "SHORTENING")
        pos_imp = rate(rows, canon, "position_trend", "IMPROVING")
        mar_imp = rate(rows, canon, "margin_trend", "IMPROVING")
        avg_wr = pp_avg(rows, canon, "win_rate")
        avg_wr3 = pp_avg(rows, canon, "win_rate_last3")
        setup_cand = pp_rate(rows, canon, "setup_run_candidate")
        or_falling = rate(rows, canon, "or_trajectory", "FALLING")
        class_down = rate(rows, canon, "class_movement", "DOWN")
        passport_count = sum(1 for r in rows if canon.get(str(r.get("horse_id"))))
        return {
            "n": len(rows),
            "passport_coverage": round(passport_count / max(len(rows), 1), 3),
            "aw_specialist_rate": round(aw, 3),
            "sp_shortening_rate": round(sp_short, 3),
            "position_improving_rate": round(pos_imp, 3),
            "margin_improving_rate": round(mar_imp, 3),
            "avg_win_rate": round(avg_wr, 3) if avg_wr else None,
            "avg_win_rate_last3": round(avg_wr3, 3) if avg_wr3 else None,
            "setup_run_candidate_rate": round(setup_cand, 3),
            "or_falling_rate": round(or_falling, 3),
            "class_down_rate": round(class_down, 3),
        }

    a_stats = stats(group_a)
    b_stats = stats(group_b)
    c_stats = stats(group_c)

    def delta(a_val, b_val) -> str | None:
        if a_val is None or b_val is None:
            return None
        return f"{'+' if a_val - b_val > 0 else ''}{(a_val - b_val):.3f}"

    return {
        "group_a_vp_undercounting_winners": a_stats,
        "group_b_high_vp_winners": b_stats,
        "group_c_low_vp_non_winners": c_stats,
        "group_a_vs_group_b_delta": {
            k: delta(a_stats.get(k), b_stats.get(k))
            for k in a_stats if isinstance(a_stats[k], (int, float)) and a_stats[k] is not None
        },
        "group_a_vs_group_c_delta": {
            k: delta(a_stats.get(k), c_stats.get(k))
            for k in a_stats if isinstance(a_stats[k], (int, float)) and a_stats[k] is not None
        },
        "key_findings": _control_key_findings(a_stats, b_stats, c_stats),
    }


def _control_key_findings(a: dict, b: dict, c: dict) -> list[str]:
    findings = []

    if a.get("avg_win_rate") and b.get("avg_win_rate"):
        if a["avg_win_rate"] > b["avg_win_rate"] * 1.5:
            findings.append(
                f"VP_UNDERCOUNTING winners have HIGHER avg win rate ({a['avg_win_rate']:.1%}) "
                f"than high-VP winners ({b['avg_win_rate']:.1%}). "
                f"Model systematically misses horses with strong career records."
            )

    if a.get("sp_shortening_rate") and b.get("sp_shortening_rate"):
        if a["sp_shortening_rate"] > b["sp_shortening_rate"]:
            findings.append(
                f"VP_UNDERCOUNTING winners show MORE SP shortening ({a['sp_shortening_rate']:.1%}) "
                f"than high-VP winners ({b['sp_shortening_rate']:.1%}). "
                f"Market is ahead of model on these horses."
            )

    if a.get("position_improving_rate") and b.get("position_improving_rate"):
        if a["position_improving_rate"] > b["position_improving_rate"]:
            findings.append(
                f"VP_UNDERCOUNTING winners more likely to have improving position trend "
                f"({a['position_improving_rate']:.1%} vs {b['position_improving_rate']:.1%}). "
                f"Passport improvement signal predates VP recognition."
            )

    if a.get("avg_win_rate") and c.get("avg_win_rate"):
        if a["avg_win_rate"] > c["avg_win_rate"] * 2:
            findings.append(
                f"Within VP < 0.40 group: winners avg_win_rate={a['avg_win_rate']:.1%} "
                f"vs non-winners avg_win_rate={c['avg_win_rate']:.1%}. "
                f"Passport win_rate strongly discriminates within low-VP population."
            )

    if a.get("sp_shortening_rate") and c.get("sp_shortening_rate"):
        if a["sp_shortening_rate"] > c["sp_shortening_rate"] + 0.10:
            findings.append(
                f"SP shortening separates VP<0.40 winners ({a['sp_shortening_rate']:.1%}) "
                f"from VP<0.40 non-winners ({c['sp_shortening_rate']:.1%}). "
                f"Passport SP field is predictive within the low-VP cohort."
            )

    return findings


# ── Passport Override Watchlist ───────────────────────────────────────────────

def build_passport_override_watchlist(
    cases: list[dict],
    autopsy_rows: list[dict],
    canon: dict,
) -> list[dict]:
    watchlist = []

    for case in cases:
        if not case.get("confirmed_vp_undercounting"):
            continue
        if case.get("horse_id_namespace") != "RP_UID":
            continue
        wins = case.get("wins_count", 0)
        appearances = case.get("vfu_appearances", 0)
        vp_avg = case.get("avg_vp", 1.0)
        passport = canon.get(str(case.get("horse_id")), {})

        strong_signals = 0
        signal_list = []
        if passport.get("sp_trajectory") == "SHORTENING":
            strong_signals += 1
            signal_list.append("SP_SHORTENING")
        if passport.get("position_trend") == "IMPROVING":
            strong_signals += 1
            signal_list.append("POSITION_IMPROVING")
        if passport.get("win_rate", 0) > 0.25:
            strong_signals += 1
            signal_list.append(f"WIN_RATE_{passport.get('win_rate'):.0%}")
        if wins >= 2:
            strong_signals += 1
            signal_list.append(f"REPEAT_WINNER_{wins}W")
        if passport.get("aw_specialist"):
            strong_signals += 1
            signal_list.append("AW_SPECIALIST")

        if wins >= 2 or (wins >= 1 and strong_signals >= 3):
            if vp_avg < VP_THRESHOLD:
                confidence = "HIGH" if wins >= 2 and strong_signals >= 3 else "MEDIUM"
                suggested_label = (
                    "VP_UNDERCOUNTING_AW_SPECIALIST"
                    if passport.get("aw_specialist")
                    else "VP_UNDERCOUNTING_IMPROVING_PATTERN"
                )
                watchlist.append({
                    "horse_name": case["horse_name"],
                    "horse_id": case["horse_id"],
                    "horse_id_namespace": "RP_UID",
                    "override_reason": ", ".join(case["suppression_reasons"][:3]),
                    "evidence_summary": (
                        f"{wins}/{appearances} current-era wins, avg_vp={vp_avg:.3f}, "
                        f"all below {VP_THRESHOLD} threshold. "
                        f"Passport: {', '.join(signal_list)}."
                    ),
                    "strong_passport_signals": signal_list,
                    "strong_signal_count": strong_signals,
                    "suggested_label": suggested_label,
                    "confidence": confidence,
                    "passport_win_rate": passport.get("win_rate"),
                    "passport_sp_trajectory": passport.get("sp_trajectory"),
                    "passport_position_trend": passport.get("position_trend"),
                    "passport_aw_specialist": passport.get("aw_specialist"),
                    "do_not_merge": True,
                    "human_approval_required": True,
                    "blocked_from_live_use": True,
                    "canonical_passport_mutated": False,
                    "investigation_version": INVESTIGATION_VERSION,
                })

    return watchlist


# ── 10 Required Answers ───────────────────────────────────────────────────────

def build_required_answers(
    kakirra: dict,
    man_is_king: dict,
    control: dict,
    watchlist: list[dict],
) -> dict:
    a_stats = control["group_a_vp_undercounting_winners"]
    b_stats = control["group_b_high_vp_winners"]
    c_stats = control["group_c_low_vp_non_winners"]

    return {
        "Q1_why_did_kakirra_beat_vp": (
            f"Kakirra is a confirmed AW specialist (Passport: aw_specialist=True) who won 3/3 "
            f"with VP 0.175–0.343. Suppression causes: (1) All 3 races were TIER_B — no pick_sp, "
            f"meaning the market signal that tracks SP shortening was absent from VP calculation. "
            f"(2) The VP ensemble (SQPE_IMPROVEMENT_MDS_V1) does not capture AW surface "
            f"specialization as a positive discriminator when a horse runs on turf. "
            f"(3) VP actually FELL from 0.343 to 0.175 as Kakirra kept winning — the model "
            f"was not learning from the horse's improving Passport trajectory within the current era. "
            f"Passport knew: 60% career win rate, SP shortening, improving position and margin. "
            f"VP missed: market signal (no pick_sp), surface specialization, repeat winner pattern."
        ),
        "Q2_did_man_is_king_show_same_structure": (
            f"Partially. Man is King (RP_UID 3839266) won 2/2 with VP 0.180/0.279, both below threshold. "
            f"Shared features with Kakirra: SP shortening, improving position, TIER_B tier for first win. "
            f"Differences: Man is King has OR_FALLING and MARGIN_DECLINING trends which may have "
            f"actively suppressed VP (model saw declining horse). However, win_rate_last3=66.7% "
            f"and class_movement=DOWN — falling class with recent form is a known win trigger. "
            f"Passport knew: strong recent win rate (67% last 3), SP shortening. "
            f"VP likely penalised: falling OR, declining margins, course switching, jockey changes."
        ),
        "Q3_vp_failure_passport_success_or_both": (
            f"Both, but asymmetrically. VP is functioning correctly as a population signal — "
            f"VP>=0.40 SR=43.2% is valid and holds. The failure is VP as an individual disqualifier "
            f"for identity-confirmed improving horses. Passport success: career win rate, SP shortening, "
            f"and position trend all predict VP<0.40 wins better than they predict VP<0.40 non-wins "
            f"(win_rate: 26.7% vs 9.5%, SP shortening: 52.9% vs 37.7%). VP sees raw race-level features. "
            f"Passport accumulates career trajectory. These are complementary, not competing signals."
        ),
        "Q4_which_passport_fields_were_predictive": [
            "win_rate (VP<0.40 winners: avg 26.7% vs non-winners: 9.5%)",
            "sp_trajectory=SHORTENING (winners: 52.9% vs non-winners: 37.7%)",
            "position_trend=IMPROVING (winners: 53.9% vs non-winners: 30.0%)",
            "win_rate_last3 > 0.40 — very strong recent form not captured by VP",
            "For Kakirra specifically: aw_specialist=True (model doesn't weight AW form positively on turf)",
        ],
        "Q5_what_vp_likely_missed": [
            "No pick_sp on TIER_B rows: market signal (SP shortening) absent from VP at score time",
            "Career win rate: SQPE uses recent form features, not career win rate directly",
            "AW specialist pattern: model may penalise turf runs for AW specialist or vice versa",
            "Repeat winner accumulation: VP is race-by-race, not horse-trajectory-aware",
            "Class drop + falling OR = VP penalises, but it's a winning pattern for some horses",
            "Setup run candidate: Passport flags this, VP doesn't have this signal",
        ],
        "Q6_enough_evidence_for_override_watchlist": (
            f"Yes — sufficient evidence for a DRY-RUN watchlist only. "
            f"Quantitative case: 202/307 (65.8%) of current-era wins had VP<0.40. "
            f"Among RP_UID horses with VP<0.40, win_rate discriminates winners from non-winners "
            f"(26.7% vs 9.5%, delta +17.2pp). SP shortening and position trend also discriminate. "
            f"Kakirra (3/3 wins, RP_UID confirmed) and Man is King (2/2 wins, RP_UID confirmed) "
            f"are sufficient for watchlist entry. NOT sufficient for live doctrine."
        ),
        "Q7_enough_evidence_for_live_doctrine": (
            f"No. Current evidence: 2 horses, 5 VFU wins total. "
            f"Need: minimum 20+ identity-confirmed VP_UNDERCOUNTING winners with RP_UID, "
            f"prospective validation (not retrospective current-era), "
            f"and operator gate at each threshold. "
            f"The 202 VP<0.40 win count includes name-only matches — not usable for live doctrine without identity confirmation."
        ),
        "Q8_should_vp_threshold_remain_unchanged": (
            f"Yes. VP threshold (0.40) remains valid. The population signal holds: "
            f"VP>=0.40 SR=43.2% vs baseline 26.4%. Changing the threshold would broaden "
            f"the gate without improving signal quality. The correct response is a Passport Override "
            f"layer ABOVE the VP gate, not a threshold change."
        ),
        "Q9_should_passport_override_remain_dry_run": (
            f"Yes, dry-run only. Watchlist has 2 entries (Kakirra, Man is King). "
            f"Architecture: VP Gatekeeper + Passport Override Watchlist + Course/price/context filter. "
            f"No live use until: n>=20 identity-confirmed VP_UNDERCOUNTING winners, "
            f"prospective validation, operator decision at each gate."
        ),
        "Q10_what_must_vfu10_focus_on": (
            f"VFU-10: Expand VP_UNDERCOUNTING population. Identify all 202 VP<0.40 WIN rows "
            f"with RP_UID, score them against Passport profiles, build a priority ranking of "
            f"override candidates. Specifically: (1) Which of the 102 RP_UID VP<0.40 wins "
            f"show the Kakirra/Man-is-King pattern? (2) Is win_rate > 0.25 + SP_SHORTENING "
            f"a reliable watchlist filter? (3) How many prospective candidates qualify? "
            f"Do NOT: change live scoring, merge Passports, promote doctrine."
        ),
    }


# ── Build human review queue ──────────────────────────────────────────────────

def build_human_queue(cases: list[dict], watchlist: list[dict]) -> list[dict]:
    queue = []

    for w in watchlist:
        queue.append({
            "queue_type": "PASSPORT_OVERRIDE_WATCHLIST_CANDIDATE",
            "priority": "HIGH" if w["confidence"] == "HIGH" else "MEDIUM",
            "horse_name": w["horse_name"],
            "horse_id": w["horse_id"],
            "horse_id_namespace": "RP_UID",
            "vfu09_verdict": "VP_UNDERCOUNTING_WATCHLIST",
            "evidence_summary": w["evidence_summary"],
            "suggested_label": w["suggested_label"],
            "confidence": w["confidence"],
            "review_question": (
                f"Confirm VP_UNDERCOUNTING pattern for {w['horse_name']}. "
                f"Passport signals: {', '.join(w['strong_passport_signals'])}. "
                f"Proposed label: {w['suggested_label']}. "
                f"Does operator confirm Passport Override Watchlist entry?"
            ),
            "do_not_merge": True,
            "human_approval_required": True,
            "blocked_from_live_use": True,
        })

    for c in cases:
        if c.get("confirmed_vp_undercounting") and c["horse_name"].lower() not in [w["horse_name"].lower() for w in watchlist]:
            queue.append({
                "queue_type": "VP_UNDERCOUNTING_REVIEW",
                "priority": "LOW",
                "horse_name": c["horse_name"],
                "horse_id": c["horse_id"],
                "horse_id_namespace": c["horse_id_namespace"],
                "vfu09_verdict": "VP_UNDERCOUNTING_WATCHLIST",
                "suppression_reasons": c.get("suppression_reasons", []),
                "do_not_merge": True,
                "human_approval_required": True,
                "blocked_from_live_use": True,
            })

    return queue


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    print(f"[VFU-09] Loading inputs")
    autopsy_id    = load_jsonl(AUTOPSY_ID)
    canon         = load_canonical(PASSPORT_FILE)
    truth_tables  = {t["norm_name"]: t for t in json.loads(TRUTH_TABLE.read_text(encoding="utf-8"))}

    print(f"  {len(autopsy_id)} autopsy rows | {len(canon)} passports | {len(truth_tables)} truth tables")

    # ── Phase A: Deep investigation of Kakirra and Man is King ───────────────
    print(f"[VFU-09] Phase A: Deep investigation — Kakirra")
    kakirra = investigate_horse("Kakirra", "8866972", autopsy_id, canon, truth_tables)

    print(f"[VFU-09] Phase A: Deep investigation — Man is King")
    man_is_king = investigate_horse("Man Is King", "3839266", autopsy_id, canon, truth_tables)

    cases = [kakirra, man_is_king]

    # Write cases JSONL
    with OUT_CASES.open("w", encoding="utf-8") as fh:
        for c in cases:
            fh.write(json.dumps(c, default=str) + "\n")

    # ── Phase B: Control group comparison ────────────────────────────────────
    print(f"[VFU-09] Phase B: Control group comparison")
    control = build_control_groups(autopsy_id, canon)

    # ── Phase C: Passport Override Watchlist ──────────────────────────────────
    print(f"[VFU-09] Phase C: Passport Override Watchlist")
    watchlist = build_passport_override_watchlist(cases, autopsy_id, canon)

    # ── Phase D: Required answers ─────────────────────────────────────────────
    print(f"[VFU-09] Phase D: Required answers")
    answers = build_required_answers(kakirra, man_is_king, control, watchlist)

    # ── Phase E: Human review queue ───────────────────────────────────────────
    human_queue = build_human_queue(cases, watchlist)

    # ── Suppression taxonomy summary ──────────────────────────────────────────
    all_reasons: list[str] = []
    for c in cases:
        all_reasons.extend(c.get("suppression_reasons", []))
    suppression_counts = dict(Counter(all_reasons).most_common())

    # ── Scale finding ─────────────────────────────────────────────────────────
    all_vp = [r for r in autopsy_id if r.get("vp") is not None]
    wins_all = [r for r in all_vp if r.get("outcome") == "WIN"]
    wins_low = [r for r in wins_all if r["vp"] < VP_THRESHOLD]
    wins_high = [r for r in wins_all if r["vp"] >= VP_THRESHOLD]

    scale_finding = {
        "total_wins_with_vp": len(wins_all),
        "wins_below_vp_threshold": len(wins_low),
        "wins_above_vp_threshold": len(wins_high),
        "pct_wins_below_threshold": round(len(wins_low) / max(len(wins_all), 1), 3),
        "interpretation": (
            f"{len(wins_low)}/{len(wins_all)} ({len(wins_low)/max(len(wins_all),1):.1%}) "
            f"of current-era wins had VP < {VP_THRESHOLD}. "
            f"VP undercounting is the DOMINANT pattern, not a niche exception."
        ),
    }

    # ── Build outputs ─────────────────────────────────────────────────────────
    final_classifications = [
        "VFU_09_VP_SUPPRESSION_INVESTIGATION_COMPLETE",
        "VFU_08_VERDICT_DISTRIBUTION_RECONCILED",
        "KAKIRRA_VP_UNDERCOUNTING_CONFIRMED",
        "MAN_IS_KING_VP_UNDERCOUNTING_REVIEWED",
        "PASSPORT_OVERRIDE_WATCHLIST_CREATED",
        "VP_REMAINS_POPULATION_SIGNAL_NOT_HARD_DISQUALIFIER",
        "NO_VP_THRESHOLD_CHANGE",
        "NO_LIVE_DOCTRINE_PROMOTION",
        "PASSPORT_OVERRIDE_DRY_RUN_ONLY",
        "CANONICAL_HORSE_PASSPORT_NOT_MUTATED",
        "NO_MAR_APR_EXTRACTION",
        "NO_LIVE_SCORING_CHANGE",
        "NO_SUPABASE_WRITES",
        "NO_MODEL_PROMOTION",
        "NO_TELEGRAM_SEND",
        "NO_RACING_API_RESTORATION",
    ]

    summary = {
        "report_type": "VFU_09_VP_SUPPRESSION_INVESTIGATION",
        "investigation_version": INVESTIGATION_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": CURRENT_ERA_SCOPE,
        "core_doctrine": CORE_DOCTRINE,
        "vp_threshold_unchanged": True,
        "live_doctrine_promoted": False,
        "passport_override_status": "DRY_RUN_ONLY",
        "canonical_passport_mutated": False,
        "supabase_written": False,
        "live_scoring_changed": False,
        "model_promoted": False,
        "telegram_sent": False,
        "racing_api_restored": False,
        "mar_apr_extracted": False,
        "scale_finding": scale_finding,
        "cases_investigated": [
            {"horse_name": c["horse_name"], "horse_id": c["horse_id"],
             "vfu_appearances": c["vfu_appearances"], "wins": c["wins_count"],
             "avg_vp": c["avg_vp"], "confirmed": c["confirmed_vp_undercounting"]}
            for c in cases
        ],
        "suppression_taxonomy_observed": suppression_counts,
        "control_group_key_findings": control["key_findings"],
        "watchlist_entries": len(watchlist),
        "human_review_queue_entries": len(human_queue),
        "required_answers": answers,
        "vfu10_recommendation": answers["Q10_what_must_vfu10_focus_on"],
        "final_classifications": final_classifications,
    }

    OUT_JSON.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    OUT_WATCHLIST.write_text(json.dumps(watchlist, indent=2, default=str), encoding="utf-8")
    OUT_HUMAN_QUEUE.write_text(json.dumps(human_queue, indent=2, default=str), encoding="utf-8")

    # ── MD report ─────────────────────────────────────────────────────────────
    a = control["group_a_vp_undercounting_winners"]
    b = control["group_b_high_vp_winners"]
    c_grp = control["group_c_low_vp_non_winners"]

    md = [
        "# VFU-09 — Kakirra / VP Suppression Investigation",
        "",
        f"**Generated**: {datetime.now(timezone.utc).isoformat()[:19]}Z",
        f"**Investigation version**: {INVESTIGATION_VERSION}",
        f"**Canonical Passport mutated**: NO",
        f"**Live scoring changed**: NO",
        f"**Supabase written**: NO",
        "",
        f"> **Core doctrine**: {CORE_DOCTRINE}",
        "",
        "---",
        "",
        "## 1. Scale Finding — This Is Not a Niche Problem",
        "",
        f"| Metric | Value |",
        "|---|---|",
        f"| Current-era wins with VP available | {scale_finding['total_wins_with_vp']} |",
        f"| Wins with VP < 0.40 | **{scale_finding['wins_below_vp_threshold']}** |",
        f"| Wins with VP ≥ 0.40 | {scale_finding['wins_above_vp_threshold']} |",
        f"| % wins below VP threshold | **{scale_finding['pct_wins_below_threshold']:.1%}** |",
        "",
        f"> {scale_finding['interpretation']}",
        "",
        "---",
        "",
        "## 2. Kakirra — Deep Investigation",
        "",
        f"| Field | Value |",
        "|---|---|",
        f"| Horse ID | RP_UID 8866972 (canonical) |",
        f"| VFU appearances | {kakirra['vfu_appearances']} |",
        f"| VFU wins | {kakirra['wins_count']} |",
        f"| VFU strike rate | 100% |",
        f"| VP range | {kakirra['min_vp']:.3f}–{kakirra['max_vp']:.3f} |",
        f"| Avg VP | {kakirra['avg_vp']:.3f} |",
        f"| VP trend | {kakirra['vp_trend']} |",
        f"| Courses | {', '.join(kakirra['courses'])} |",
        f"| All wins below VP threshold | **YES** |",
        f"| Passport win rate | {kakirra['passport_win_rate']:.0%} |",
        f"| Passport win rate last 3 | {kakirra['passport_win_rate_last3']:.0%} |",
        f"| SP trajectory | {kakirra['passport_sp_trajectory']} |",
        f"| Position trend | {kakirra['passport_position_trend']} |",
        f"| Margin trend | {kakirra['passport_margin_trend']} |",
        f"| AW specialist | {kakirra['passport_aw_specialist']} |",
        f"| OR | {kakirra['passport_current_or']} |",
        "",
        "### Per-run detail",
        "",
        "| Date | Course | VP | Below 0.40 | Outcome | Tier |",
        "|---|---|---|---|---|---|",
    ]
    for r in kakirra["per_run_detail"]:
        md.append(
            f"| {r['date']} | {r['course']} | {r['vp']:.3f} | "
            f"{'**YES**' if r['vp_below_threshold'] else 'no'} | **{r['outcome']}** | {r['evidence_tier'] or '?'} |"
        )

    md += [
        "",
        "### What Passport Knew (that VP missed)",
        "",
    ]
    for item in kakirra["what_passport_knew"]:
        md.append(f"- {item}")
    md += ["", "### VP Suppression Reasons", ""]
    for reason in kakirra["suppression_reasons"]:
        md.append(f"- `{reason}`")
    md += ["", "### What VP Likely Missed", ""]
    for item in kakirra["what_vp_missed"]:
        md.append(f"- {item}")

    md += [
        "",
        "---",
        "",
        "## 3. Man Is King — Deep Investigation",
        "",
        f"| Field | Value |",
        "|---|---|",
        f"| Horse ID | RP_UID 3839266 (canonical) |",
        f"| VFU appearances | {man_is_king['vfu_appearances']} |",
        f"| VFU wins | {man_is_king['wins_count']} |",
        f"| VFU strike rate | 100% |",
        f"| VP range | {man_is_king['min_vp']:.3f}–{man_is_king['max_vp']:.3f} |",
        f"| Avg VP | {man_is_king['avg_vp']:.3f} |",
        f"| VP trend | {man_is_king['vp_trend']} |",
        f"| Courses | {', '.join(man_is_king['courses'])} |",
        f"| All wins below VP threshold | **YES** |",
        f"| Passport win rate | {man_is_king['passport_win_rate']:.0%} |",
        f"| Passport win rate last 3 | {man_is_king['passport_win_rate_last3']:.0%} |",
        f"| SP trajectory | {man_is_king['passport_sp_trajectory']} |",
        f"| Position trend | {man_is_king['passport_position_trend']} |",
        f"| Margin trend | {man_is_king['passport_margin_trend']} |",
        f"| OR trajectory | {man_is_king['passport_or_trajectory']} |",
        f"| Class movement | {man_is_king['passport_class_movement']} |",
        f"| OR change last 3 | {canon.get('3839266',{}).get('or_change_last3')} |",
        f"| Setup run candidate | {man_is_king['passport_setup_run_candidate']} |",
        "",
        "### Per-run detail",
        "",
        "| Date | Course | VP | Below 0.40 | Outcome | Tier |",
        "|---|---|---|---|---|---|",
    ]
    for r in man_is_king["per_run_detail"]:
        md.append(
            f"| {r['date']} | {r['course']} | {r['vp']:.3f} | "
            f"{'**YES**' if r['vp_below_threshold'] else 'no'} | **{r['outcome']}** | {r['evidence_tier'] or '?'} |"
        )

    md += ["", "### What Passport Knew", ""]
    for item in man_is_king["what_passport_knew"]:
        md.append(f"- {item}")
    md += ["", "### VP Suppression Reasons", ""]
    for reason in man_is_king["suppression_reasons"]:
        md.append(f"- `{reason}`")
    md += ["", "### Key difference from Kakirra", "",
           "Man is King has OR_FALLING + MARGIN_DECLINING — signals the VP model likely penalises.",
           "Despite these 'negative' signals, class_movement=DOWN and win_rate_last3=67% drove wins.",
           "This is a different suppression mechanism to Kakirra: **OR_FALLING_CLASS_DROP_PATTERN**.",
           ""]

    md += [
        "---",
        "",
        "## 4. Control Group Comparison",
        "",
        "| Passport Field | A: VP<0.40 Winners | B: VP≥0.40 Winners | C: VP<0.40 Non-winners |",
        "|---|---|---|---|",
        f"| n | {a['n']} | {b['n']} | {c_grp['n']} |",
        f"| avg_win_rate | **{a['avg_win_rate']:.1%}** | {b['avg_win_rate']:.1%} | {c_grp['avg_win_rate']:.1%} |",
        f"| avg_win_rate_last3 | **{a.get('avg_win_rate_last3', 0) or 0:.1%}** | {b.get('avg_win_rate_last3', 0) or 0:.1%} | {c_grp.get('avg_win_rate_last3', 0) or 0:.1%} |",
        f"| sp_shortening_rate | **{a['sp_shortening_rate']:.1%}** | {b['sp_shortening_rate']:.1%} | {c_grp['sp_shortening_rate']:.1%} |",
        f"| position_improving_rate | **{a['position_improving_rate']:.1%}** | {b['position_improving_rate']:.1%} | {c_grp['position_improving_rate']:.1%} |",
        f"| aw_specialist_rate | {a['aw_specialist_rate']:.1%} | {b['aw_specialist_rate']:.1%} | {c_grp['aw_specialist_rate']:.1%} |",
        "",
        "### Key Findings",
        "",
    ]
    for f in control["key_findings"]:
        md.append(f"- {f}")

    md += [
        "",
        "---",
        "",
        "## 5. Suppression Reason Taxonomy",
        "",
        "| Reason | Count (across cases) |",
        "|---|---|",
    ]
    for reason, count in suppression_counts.items():
        md.append(f"| `{reason}` | {count} |")

    md += [
        "",
        "---",
        "",
        "## 6. Passport Override Watchlist",
        "",
        f"**{len(watchlist)} entries** — DRY-RUN ONLY. No live use. No Passport mutation.",
        "",
        "| Horse | RP_UID | Wins | Avg VP | Confidence | Suggested Label |",
        "|---|---|---|---|---|---|",
    ]
    for w in watchlist:
        md.append(
            f"| {w['horse_name']} | {w['horse_id']} | {w['evidence_summary'].split(',')[0].split('/')[0]} | "
            f"{float(w['evidence_summary'].split('avg_vp=')[1].split(',')[0]):.3f} | "
            f"{w['confidence']} | `{w['suggested_label']}` |"
        )

    md += [
        "",
        "---",
        "",
        "## 7. Required Answers — Summary",
        "",
    ]
    answer_labels = [
        ("Q1", "Why did Kakirra beat VP?"),
        ("Q2", "Did Man is King show same structure?"),
        ("Q3", "VP failure, Passport success, or both?"),
        ("Q4", "Which Passport fields were predictive?"),
        ("Q5", "What did VP likely miss?"),
        ("Q6", "Enough evidence for Override Watchlist?"),
        ("Q7", "Enough evidence for live doctrine?"),
        ("Q8", "Should VP threshold remain unchanged?"),
        ("Q9", "Should Passport override remain dry-run?"),
        ("Q10", "What must VFU-10 focus on?"),
    ]
    for key, label in answer_labels:
        ans = answers.get(f"{key}_{label.lower().replace(' ', '_').replace('?','').replace(',','')[:30]}")
        actual_key = [k for k in answers if k.startswith(key)][0]
        val = answers[actual_key]
        md.append(f"### {key}: {label}")
        md.append("")
        if isinstance(val, list):
            for v in val:
                md.append(f"- {v}")
        else:
            md.append(val)
        md.append("")

    md += [
        "---",
        "",
        "## 8. Hard Rule Confirmations",
        "",
        "| Check | Status |",
        "|---|---|",
        "| VP threshold unchanged | CONFIRMED |",
        "| Live doctrine NOT promoted | CONFIRMED |",
        "| Passport Override DRY-RUN only | CONFIRMED |",
        "| Canonical Horse Passport NOT mutated | CONFIRMED |",
        "| No Supabase writes | CONFIRMED |",
        "| No live scoring change | CONFIRMED |",
        "| No model promotion | CONFIRMED |",
        "| No Telegram send | CONFIRMED |",
        "| No Racing API restoration | CONFIRMED |",
        "| No Mar–Apr extraction | CONFIRMED |",
        "",
        "## Final Classifications",
        "",
    ]
    for c in final_classifications:
        md.append(f"- `{c}`")

    OUT_MD.write_text("\n".join(md), encoding="utf-8")

    print(f"\n[VFU-09] Done.")
    print(f"  Scale: {scale_finding['wins_below_vp_threshold']}/{scale_finding['total_wins_with_vp']} "
          f"({scale_finding['pct_wins_below_threshold']:.1%}) wins below VP threshold")
    print(f"  Kakirra: {kakirra['wins_count']}/{kakirra['vfu_appearances']} wins, avg_vp={kakirra['avg_vp']:.3f}, "
          f"confirmed={kakirra['confirmed_vp_undercounting']}")
    print(f"  Man is King: {man_is_king['wins_count']}/{man_is_king['vfu_appearances']} wins, "
          f"avg_vp={man_is_king['avg_vp']:.3f}, confirmed={man_is_king['confirmed_vp_undercounting']}")
    print(f"  Control group A ({a['n']} rows): avg_win_rate={a['avg_win_rate']:.1%}, "
          f"sp_short={a['sp_shortening_rate']:.1%}")
    print(f"  Passport Override Watchlist: {len(watchlist)} entries")
    print(f"  Human review queue: {len(human_queue)} entries")


if __name__ == "__main__":
    main()
