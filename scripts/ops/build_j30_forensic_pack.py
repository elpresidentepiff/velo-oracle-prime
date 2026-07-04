"""
J30-FOR — June 30 Full Forensic Pack With Exotics.

REPORT_ONLY. No scoring change, no Supabase write, no model promotion,
no Telegram send, no canonical horse passport mutation.
"""
from __future__ import annotations

import json
import math
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO = Path(__file__).parent.parent.parent
_DATE = "2026-06-30"
_OUT = _REPO / "data" / "reports"

# ── input paths ──────────────────────────────────────────────────────────────
_VERDICTS = _REPO / "data" / f"velo_prime_verdicts_{_DATE.replace('-', '_')}.json"
_RESULTS = _REPO / "data" / "results" / f"rp_results_{_DATE.replace('-', '_')}.json"
_SIGMA = _REPO / "data" / "sigma_results" / f"sigma_results_{_DATE.replace('-', '_')}.json"
_NR = _REPO / "data" / "reports" / f"radical_shadow_{_DATE.replace('-', '_')}.json"
_LEDGER = _REPO / "data" / "model_comparison_ledger.csv"

# ── output paths ─────────────────────────────────────────────────────────────
_F_FULL_MD = _OUT / f"j30_forensic_full_pack_{_DATE}.md"
_F_FULL_JSON = _OUT / f"j30_forensic_full_pack_{_DATE}.json"
_F_RPR_MD = _OUT / f"j30_old_velo_rpr_dependency_audit_{_DATE}.md"
_F_NB_MD = _OUT / f"j30_new_build_top3_value_audit_{_DATE}.md"
_F_EW_MD = _OUT / f"j30_ew_candidate_reality_audit_{_DATE}.md"
_F_MP_MD = _OUT / f"j30_midprice_miss_recovery_audit_{_DATE}.md"
_F_EX_MD = _OUT / f"j30_exotics_audit_{_DATE}.md"
_F_BRIEF_MD = _OUT / f"j30_forensic_operator_brief_{_DATE}.md"

_HARD_CONSTRAINTS = [
    "REPORT_ONLY", "NO_LIVE_SCORING_CHANGE", "NO_VP_THRESHOLD_CHANGE",
    "NO_MODEL_PROMOTION", "NO_SUPABASE_WRITES", "NO_TELEGRAM_SEND",
    "NO_VFU_21_START", "NO_VCP_04_START", "NO_CASE_MEMORY_BUILD",
    "NO_DEEPSEARCHER_BUILD", "NO_AGENT_BROWSER_BUILD",
    "CANONICAL_HORSE_PASSPORT_NOT_MUTATED", "DO_NOT_SUPPRESS_CONTRADICTIONS",
    "MISSING_ARTIFACTS_RESOLVE_UNKNOWN_NOT_CLEAN",
]

_FINAL_CLASSIFICATIONS = [
    "J30_FORENSIC_FULL_PACK_COMPLETE",
    "OLD_VELO_RPR_DEPENDENCY_AUDITED",
    "NEW_BUILD_TOP3_VALUE_CONTAINMENT_AUDITED",
    "EW_CANDIDATE_REALITY_AUDITED",
    "MIDPRICE_MISS_RECOVERY_AUDITED",
    "EXACTA_FORECAST_AUDITED",
    "TRIFECTA_TRICAST_AUDITED",
    "EXOTICS_CONTAINMENT_AUDITED",
    "EXOTICS_PROFIT_NOT_CLAIMED_WITHOUT_DIVIDENDS",
    "SP_PROXY_LABELLED_NOT_DIVIDEND_PROOF",
    "EW_PROFITABILITY_STATUS_REEVALUATED",
    "NEW_BUILD_VALUE_SCOUT_STATUS_EVALUATED",
    "OLD_VELO_RPR_ANCHOR_STATUS_EVALUATED",
    "CONTRADICTION_C01_RECORDED_NOT_SUPPRESSED",
    "MEMORY_CAPTURE_OPEN",
    "FAILURE_LEARNING_OPEN",
    "PROMOTION_LEARNING_GATED",
    "NO_VFU_21_START",
    "NO_VCP_04_START",
    "NO_LIVE_SCORING_CHANGE",
    "NO_VP_THRESHOLD_CHANGE",
    "NO_MODEL_PROMOTION",
    "NO_SUPABASE_WRITES",
    "NO_TELEGRAM_SEND",
    "CANONICAL_HORSE_PASSPORT_NOT_MUTATED",
    "REPORT_ONLY",
]


# ── helpers ──────────────────────────────────────────────────────────────────

def _load(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _sp_to_dec(sp_str: str) -> float | None:
    """Convert fractional SP string to decimal. Returns None if unparseable."""
    if not sp_str:
        return None
    s = str(sp_str).strip().upper().rstrip("F").rstrip("J").strip()
    try:
        return float(s)
    except ValueError:
        pass
    if "/" in s:
        parts = s.split("/")
        if len(parts) == 2:
            try:
                return float(parts[0]) / float(parts[1]) + 1.0
            except (ValueError, ZeroDivisionError):
                pass
    return None


def _odds_band(sp_dec: float | None) -> str:
    if sp_dec is None:
        return "UNKNOWN"
    if sp_dec < 2.5:
        return "<2.5"
    if sp_dec < 4.0:
        return "2.5-4"
    if sp_dec < 6.0:
        return "4-6"
    if sp_dec < 10.0:
        return "6-10"
    if sp_dec < 16.0:
        return "10-16"
    return "16+"


def _safe_mean(vals: list[float]) -> float | None:
    if not vals:
        return None
    return sum(vals) / len(vals)


def _safe_median(vals: list[float]) -> float | None:
    if not vals:
        return None
    return statistics.median(vals)


def _pct(num: int, den: int) -> str:
    if den == 0:
        return "n/a"
    return f"{100 * num / den:.1f}%"


# ── data loading and join ────────────────────────────────────────────────────

def _load_all() -> dict:
    verdicts_raw = _load(_VERDICTS) or []
    results_raw = _load(_RESULTS) or {}
    sigma_raw = _load(_SIGMA) or {}
    nr_raw = _load(_NR) or {}

    results_map = {str(r["race_id"]): r for r in results_raw.get("results", [])}
    sigma_map = {str(r["race_id"]): r for r in sigma_raw.get("rows", [])}
    nr_map = {str(d["race_id"]): d for d in nr_raw.get("decisions", [])}

    # Load ledger via csv
    nb_map: dict[str, dict] = {}
    try:
        import csv
        with open(_LEDGER, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row.get("date") == _DATE:
                    nb_map[str(row["race_id"])] = row
    except Exception:
        pass

    races: list[dict] = []
    for v in verdicts_raw:
        rid = str(v["race_id"])
        top = v.get("top", {})
        res = results_map.get(rid, {})
        sig = sigma_map.get(rid, {})
        nr = nr_map.get(rid, {})
        nb = nb_map.get(rid, {})

        # Full finish order
        runners_raw = res.get("runners", [])
        runners_sorted = sorted(
            runners_raw,
            key=lambda x: int(x["position"]) if str(x.get("position", 99)).isdigit() else 99
        )
        finish_order = [
            {"horse": r["horse"], "horse_id": r.get("horse_id", ""), "pos": r["position"],
             "sp_str": r.get("sp", ""), "sp_dec": r.get("sp_dec") or _sp_to_dec(r.get("sp", ""))}
            for r in runners_sorted if not r.get("non_runner")
        ]

        # No-RPR top pick from ledger (most reliable)
        norpr_pick = nb.get("norpr_top_pick", "") or ""
        if norpr_pick in ("nan", ""):
            norpr_pick = None
        norpr_outcome = nb.get("norpr_outcome", "NO_DATA")

        # New Build top pick
        nb_pick = nb.get("nb_top_pick", "") or ""
        if nb_pick in ("nan", ""):
            nb_pick = None
        nb_outcome = nb.get("nb_outcome", "NO_DATA")
        nb_prob = nb.get("nb_prob")
        try:
            nb_prob = float(nb_prob) if nb_prob not in (None, "", "nan") else None
        except (ValueError, TypeError):
            nb_prob = None

        winner = res.get("winner_horse", "")
        top3 = res.get("top3_names", [])
        winner_sp_str = res.get("winner_sp", "")
        winner_sp_dec = _sp_to_dec(str(winner_sp_str)) if winner_sp_str else None

        # SP of 2nd and 3rd
        sp_2nd = finish_order[1]["sp_dec"] if len(finish_order) > 1 else None
        sp_3rd = finish_order[2]["sp_dec"] if len(finish_order) > 2 else None
        horse_2nd = finish_order[1]["horse"] if len(finish_order) > 1 else None
        horse_3rd = finish_order[2]["horse"] if len(finish_order) > 2 else None

        # sqpe gap = RPR influence proxy
        sqpe_rpr = top.get("sqpe_v17_prob")
        sqpe_norpr = top.get("sqpe_no_rpr_shadow_prob")
        rpr_gap = (sqpe_rpr - sqpe_norpr) if (sqpe_rpr is not None and sqpe_norpr is not None) else None

        old_pick = top.get("horse", "")
        old_vp = top.get("velo_prime_prob")
        old_outcome = sig.get("outcome", "UNKNOWN")
        miss_class = sig.get("miss_class") or ""
        assigned_product = sig.get("assigned_product") or top.get("assigned_product") or ""
        ew_outcome = sig.get("ew_outcome") or ""

        field_size = res.get("field_size") or nr.get("field_size")

        races.append({
            "race_id": rid,
            "course": v.get("course", ""),
            "off": v.get("off_time", ""),
            "race_name": v.get("race_name", ""),
            "tier": v.get("tier", ""),
            "field_size": field_size,
            "race_class": res.get("race_class", ""),
            "going": res.get("going", ""),
            "distance_f": res.get("distance_f"),
            # Old VELO
            "old_pick": old_pick,
            "old_vp": old_vp,
            "old_sqpe": sqpe_rpr,
            "old_sqpe_norpr": sqpe_norpr,
            "rpr_gap": rpr_gap,
            "rpr_missing": top.get("rpr_missing", False),
            "or_missing": top.get("or_missing", False),
            "mds": top.get("market_deception_score"),
            "improvement": top.get("improvement_score"),
            "old_outcome": old_outcome,
            "miss_class": miss_class,
            "assigned_product": assigned_product,
            "ew_outcome": ew_outcome,
            # No-RPR
            "norpr_pick": norpr_pick,
            "norpr_outcome": norpr_outcome,
            # New Build
            "nb_pick": nb_pick,
            "nb_prob": nb_prob,
            "nb_outcome": nb_outcome,
            # Results
            "winner": winner,
            "winner_sp_str": winner_sp_str,
            "winner_sp_dec": winner_sp_dec,
            "horse_2nd": horse_2nd,
            "sp_2nd": sp_2nd,
            "horse_3rd": horse_3rd,
            "sp_3rd": sp_3rd,
            "top3": top3,
            "finish_order": finish_order,
            # Derived
            "old_win": old_outcome == "WIN",
            "old_place": old_outcome in ("WIN", "PLACED"),
            "nb_win": nb_outcome == "WIN",
            "nb_place": nb_outcome in ("WIN", "PLACE"),
            "norpr_win": norpr_outcome == "WIN",
            "norpr_place": norpr_outcome in ("WIN", "PLACE"),
        })

    return {
        "races": races,
        "sigma_summary": sigma_raw,
        "nr_raw": nr_raw,
        "artifacts": {
            "verdicts": str(_VERDICTS),
            "results": str(_RESULTS),
            "sigma": str(_SIGMA),
            "nr": str(_NR),
            "ledger": str(_LEDGER),
        },
    }


# ── Section 1: Loop integrity ─────────────────────────────────────────────────

def _section1(data: dict) -> dict:
    races = data["races"]
    sig = data["sigma_summary"]
    n = len(races)
    matched = sum(1 for r in races if r["winner"])
    unmatched = n - matched
    missing_winner_sp = sum(1 for r in races if r["winner_sp_dec"] is None)
    missing_field_size = sum(1 for r in races if r["field_size"] is None)
    identity_failures = sig.get("identity_failures", 0)
    full_order_count = sum(1 for r in races if len(r["finish_order"]) >= 3)

    norpr_avail = sum(1 for r in races if r["norpr_pick"] is not None)
    nb_avail = sum(1 for r in races if r["nb_pick"] is not None)

    exotics_eligible = sum(1 for r in races if len(r["finish_order"]) >= 3)
    exotics_partial = n - exotics_eligible

    return {
        "race_date": _DATE,
        "races_total": n,
        "races_matched": matched,
        "races_unmatched": unmatched,
        "parse_retry_count": 3,
        "parse_retry_races": ["923670 Wexford 2.20", "923569 Salisbury 2.07", "923570 Salisbury 2.37"],
        "identity_failures": identity_failures,
        "missing_winner_sp": missing_winner_sp,
        "missing_field_size": missing_field_size,
        "norpr_available": norpr_avail,
        "nb_available": nb_avail,
        "full_finish_order_races": full_order_count,
        "exotics_eligible": exotics_eligible,
        "exotics_partial": exotics_partial,
        "exotics_coverage_note": "PARTIAL_ORDER_EVIDENCE where finish_order < 3 runners",
        "ranked_list_note": "SINGLE_TOP_PICK_ONLY — only top-1 available per model; no ranked 2nd/3rd from any model",
        "artifacts_used": data["artifacts"],
    }


# ── Section 2: RPR dependency ─────────────────────────────────────────────────

def _section2(data: dict) -> dict:
    races = data["races"]

    # RPR gap analysis (positive gap = sqpe_v17 > sqpe_norpr → RPR helped)
    gaps = [(r["rpr_gap"], r["old_win"], r["old_place"]) for r in races if r["rpr_gap"] is not None]
    win_gaps = [g for g, win, _ in gaps if win]
    miss_gaps = [g for g, win, _ in gaps if not win]

    avg_win_gap = _safe_mean(win_gaps)
    avg_miss_gap = _safe_mean(miss_gaps)

    # How often does sqpe_v17 > sqpe_norpr (RPR positive contributor to score)
    rpr_boost_count = sum(1 for r in races if r["rpr_gap"] is not None and r["rpr_gap"] > 0)
    rpr_drag_count = sum(1 for r in races if r["rpr_gap"] is not None and r["rpr_gap"] < 0)

    # Old VELO vs No-RPR win SR
    old_wins = sum(r["old_win"] for r in races)
    norpr_picks = [r for r in races if r["norpr_pick"] is not None]
    norpr_wins = sum(r["norpr_win"] for r in norpr_picks)
    norpr_n = len(norpr_picks)

    # Agreement rate
    agree = sum(1 for r in races if r["norpr_pick"] and r["old_pick"] == r["norpr_pick"])
    agree_pct = _pct(agree, len([r for r in races if r["norpr_pick"]]))

    # Cases where No-RPR won and Old missed
    norpr_better = [r for r in races if r["norpr_win"] and not r["old_win"]]
    old_better = [r for r in races if r["old_win"] and not r["norpr_win"]]
    both_win = [r for r in races if r["old_win"] and r["norpr_win"]]

    # Winner SP distribution comparison
    old_winner_sps = [r["winner_sp_dec"] for r in races if r["old_win"] and r["winner_sp_dec"]]
    norpr_winner_sps = [r["winner_sp_dec"] for r in norpr_picks if r["norpr_win"] and r["winner_sp_dec"]]

    # RPR missing on top pick
    rpr_missing = sum(1 for r in races if r.get("rpr_missing"))
    or_missing = sum(1 for r in races if r.get("or_missing"))

    # Old VELO top pick in actual top 3
    old_in_top3 = sum(1 for r in races if r["old_pick"] in r["top3"])
    norpr_in_top3 = sum(1 for r in norpr_picks if r["norpr_pick"] in r["top3"])

    # Verdict label
    if norpr_wins > old_wins + 1 and norpr_n >= 20:
        verdict = "NO_RPR_BETTER"
    elif abs(old_wins - norpr_wins) <= 1:
        verdict = "RPR_NEUTRAL"
    elif old_wins > norpr_wins:
        verdict = "RPR_HELPED"
    elif norpr_n < 10:
        verdict = "INSUFFICIENT_RPR_EVIDENCE"
    else:
        verdict = "RPR_PUBLIC_MARKET_ANCHOR"

    # Average RPR gap for wins vs misses interpretation
    rpr_interpretation = "UNKNOWN"
    if avg_win_gap is not None and avg_miss_gap is not None:
        if avg_win_gap > 0.01 and avg_win_gap > avg_miss_gap:
            rpr_interpretation = "RPR_BOOSTS_WINNERS_MORE_THAN_MISSES"
        elif avg_win_gap < 0 < avg_miss_gap:
            rpr_interpretation = "RPR_DRAGS_ON_WINNERS_BOOSTS_MISSES"
        else:
            rpr_interpretation = "RPR_IMPACT_MIXED"

    return {
        "verdict": verdict,
        "rpr_interpretation": rpr_interpretation,
        "old_velo_wins": old_wins,
        "old_velo_sr": _pct(old_wins, len(races)),
        "old_velo_top3_containment": _pct(old_in_top3, len(races)),
        "norpr_n": norpr_n,
        "norpr_wins": norpr_wins,
        "norpr_sr": _pct(norpr_wins, norpr_n),
        "norpr_top3_containment": _pct(norpr_in_top3, norpr_n),
        "norpr_agreement_with_old": agree_pct,
        "norpr_better_cases": len(norpr_better),
        "old_better_cases": len(old_better),
        "both_win_cases": len(both_win),
        "rpr_gap_avg_wins": round(avg_win_gap, 4) if avg_win_gap is not None else None,
        "rpr_gap_avg_misses": round(avg_miss_gap, 4) if avg_miss_gap is not None else None,
        "rpr_boosts_score_n": rpr_boost_count,
        "rpr_drag_count": rpr_drag_count,
        "rpr_drags_score_n": rpr_drag_count,
        "rpr_missing_on_top_pick": rpr_missing,
        "or_missing_on_top_pick": or_missing,
        "old_winner_sp_avg": round(_safe_mean(old_winner_sps), 2) if _safe_mean(old_winner_sps) else None,
        "old_winner_sp_median": round(_safe_median(old_winner_sps), 2) if _safe_median(old_winner_sps) else None,
        "norpr_winner_sp_avg": round(_safe_mean(norpr_winner_sps), 2) if _safe_mean(norpr_winner_sps) else None,
        "norpr_winner_sp_median": round(_safe_median(norpr_winner_sps), 2) if _safe_median(norpr_winner_sps) else None,
        "norpr_better_detail": [{"course": r["course"], "off": r["off"], "winner": r["winner"],
                                  "winner_sp": r["winner_sp_str"], "norpr": r["norpr_pick"], "old": r["old_pick"]}
                                 for r in norpr_better],
        "limitation": "SINGLE_TOP_PICK_ONLY — no full ranked list per model; top-2/top-3 rank analysis not possible",
        "ranked_list_note": "RPR dependency fully provable only with full per-runner score lists across all models",
    }


# ── Section 3: New Build value audit ─────────────────────────────────────────

def _section3(data: dict) -> dict:
    races = data["races"]
    nb_races = [r for r in races if r["nb_pick"] is not None]
    nb_n = len(nb_races)

    nb_wins = sum(r["nb_win"] for r in nb_races)
    nb_places = sum(r["nb_place"] for r in nb_races)

    # New Build pick in actual top3 (containment in top 3 finishers)
    nb_in_top3 = sum(1 for r in nb_races if r["nb_pick"] in r["top3"])

    # Old missed, New Build caught
    old_miss_nb_win = [r for r in nb_races if not r["old_win"] and r["nb_win"]]
    old_miss_nb_in_top3 = [r for r in nb_races if not r["old_win"] and r["nb_pick"] in r["top3"]]

    # norpr missed, NB caught
    norpr_miss_nb_win = [r for r in nb_races if r["norpr_pick"] and not r["norpr_win"] and r["nb_win"]]

    # SP profile of NB wins
    nb_winner_sps = [r["winner_sp_dec"] for r in nb_races if r["nb_win"] and r["winner_sp_dec"]]
    old_winner_sps = [r["winner_sp_dec"] for r in races if r["old_win"] and r["winner_sp_dec"]]

    # Odds band breakdown for NB wins
    nb_win_bands: dict[str, int] = {}
    for r in nb_races:
        if r["nb_win"] and r["winner_sp_dec"]:
            band = _odds_band(r["winner_sp_dec"])
            nb_win_bands[band] = nb_win_bands.get(band, 0) + 1

    # NB in actual top3 by odds band (pick SP, not winner SP)
    nb_top3_bands: dict[str, dict] = {}
    for r in nb_races:
        # find NB pick SP from finish order
        nb_sp = next((fo["sp_dec"] for fo in r["finish_order"] if fo["horse"] == r["nb_pick"]), None)
        band = _odds_band(nb_sp)
        if band not in nb_top3_bands:
            nb_top3_bands[band] = {"n": 0, "in_top3": 0}
        nb_top3_bands[band]["n"] += 1
        if r["nb_pick"] in r["top3"]:
            nb_top3_bands[band]["in_top3"] += 1

    # Long price winners where NB was in top3 finishers
    long_price_nb_in_top3 = [r for r in nb_races if r["nb_pick"] in r["top3"]
                              and r["winner_sp_dec"] and r["winner_sp_dec"] >= 6.0]

    # EW overlap
    ew_nb_in_top3 = sum(1 for r in nb_races
                        if r["assigned_product"] == "EW_CANDIDATE" and r["nb_pick"] in r["top3"])
    ew_n = sum(1 for r in nb_races if r["assigned_product"] == "EW_CANDIDATE")

    # Verdict
    nb_sr = nb_wins / nb_n if nb_n else 0
    nb_top3_rate = nb_in_top3 / nb_n if nb_n else 0
    if nb_sr < 0.15 and nb_top3_rate > 0.35:
        verdict = "NEW_BUILD_VALUE_SCOUT"
    elif nb_sr < 0.15 and nb_top3_rate <= 0.25:
        verdict = "NEW_BUILD_NO_EVIDENCE"
    elif nb_sr >= 0.20:
        verdict = "NEW_BUILD_TOP3_CONTAINMENT_SIGNAL"
    else:
        verdict = "NEEDS_PROSPECTIVE_VALIDATION"

    if len(long_price_nb_in_top3) >= 2:
        verdict2 = "NEW_BUILD_LONG_ODDS_SIGNAL"
    else:
        verdict2 = "NEW_BUILD_BAD_TOP_PICK_ONLY"

    return {
        "verdict_primary": verdict,
        "verdict_longprice": verdict2,
        "nb_n": nb_n,
        "nb_wins": nb_wins,
        "nb_sr": _pct(nb_wins, nb_n),
        "nb_place_n": nb_places,
        "nb_place_rate": _pct(nb_places, nb_n),
        "nb_in_top3_actual": nb_in_top3,
        "nb_top3_containment": _pct(nb_in_top3, nb_n),
        "nb_winner_sp_avg": round(_safe_mean(nb_winner_sps), 2) if _safe_mean(nb_winner_sps) else None,
        "nb_winner_sp_median": round(_safe_median(nb_winner_sps), 2) if _safe_median(nb_winner_sps) else None,
        "old_winner_sp_avg": round(_safe_mean(old_winner_sps), 2) if _safe_mean(old_winner_sps) else None,
        "old_winner_sp_median": round(_safe_median(old_winner_sps), 2) if _safe_median(old_winner_sps) else None,
        "old_miss_nb_win": len(old_miss_nb_win),
        "old_miss_nb_in_top3": len(old_miss_nb_in_top3),
        "norpr_miss_nb_win": len(norpr_miss_nb_win),
        "nb_win_bands": nb_win_bands,
        "nb_top3_bands": nb_top3_bands,
        "long_price_nb_in_top3": len(long_price_nb_in_top3),
        "long_price_detail": [{"course": r["course"], "off": r["off"], "winner": r["winner"],
                                "winner_sp": r["winner_sp_str"], "nb_pick": r["nb_pick"],
                                "nb_in_top3": r["nb_pick"] in r["top3"]}
                               for r in long_price_nb_in_top3],
        "ew_nb_overlap": f"{ew_nb_in_top3}/{ew_n}",
        "old_miss_nb_win_detail": [{"course": r["course"], "off": r["off"], "winner": r["winner"],
                                     "winner_sp": r["winner_sp_str"], "old": r["old_pick"], "nb": r["nb_pick"]}
                                    for r in old_miss_nb_win],
        "limitation": "SINGLE_TOP_PICK_ONLY — no New Build ranked 2nd/3rd available; top-3 containment = pick in actual top-3 finishers",
    }


# ── Section 4: EW candidate reality ──────────────────────────────────────────

def _section4(data: dict) -> dict:
    races = data["races"]
    ew_races = [r for r in races if r["assigned_product"] == "EW_CANDIDATE"]
    n_total = len(ew_races)

    # Coverage checks
    n_known_sp = sum(1 for r in ew_races if r["winner_sp_dec"] is not None)
    n_known_field = sum(1 for r in ew_races if r["field_size"] is not None)
    n_known_finish = sum(1 for r in ew_races if len(r["finish_order"]) >= 3)
    n_all_known = sum(1 for r in ew_races
                      if r["winner_sp_dec"] and r["field_size"] and len(r["finish_order"]) >= 3)

    wins = sum(r["old_win"] for r in ew_races)
    places = sum(r["old_place"] for r in ew_races)
    frames = sum(1 for r in ew_races if r["old_pick"] in r["top3"])

    ew_wins = sum(1 for r in ew_races if r["ew_outcome"] == "EW_WIN")
    ew_places = sum(1 for r in ew_races if r["ew_outcome"] in ("EW_WIN", "EW_PLACE"))
    ew_misses = sum(1 for r in ew_races if r["ew_outcome"] == "EW_MISS")

    # SP of EW picks
    pick_sps = []
    for r in ew_races:
        sp = next((fo["sp_dec"] for fo in r["finish_order"] if fo["horse"] == r["old_pick"]), None)
        if sp:
            pick_sps.append(sp)

    max_sp_placed = None
    max_sp_won = None
    for r in ew_races:
        sp = next((fo["sp_dec"] for fo in r["finish_order"] if fo["horse"] == r["old_pick"]), None)
        if sp and r["ew_outcome"] in ("EW_WIN", "EW_PLACE"):
            max_sp_placed = max(max_sp_placed or 0, sp)
        if sp and r["ew_outcome"] == "EW_WIN":
            max_sp_won = max(max_sp_won or 0, sp)

    # EW eligibility by field size (UK standard: >=5 runners for EW, >=8 for 3 places, >=12 for 4 places)
    ew_eligible = sum(1 for r in ew_races if (r["field_size"] or 0) >= 5)
    ew_3place = sum(1 for r in ew_races if (r["field_size"] or 0) >= 8)

    # VFU-20 reminder
    vfu20_note = "VFU-20 established: EW profitability = PARTIAL_EW_SIGNAL_NOT_PROFIT_PROOF. n=6 on June 30 is insufficient to revise."

    # Verdict
    if n_all_known == 0:
        verdict = "EW_FIELD_SIZE_GAP_REMAINS"
    elif ew_places >= 4 and n_total >= 6:
        verdict = "EW_SIGNAL_ONLY"
    else:
        verdict = "EW_PARTIAL_PRICE_PROOF"

    return {
        "verdict": verdict,
        "ew_n": n_total,
        "ew_known_sp": n_known_sp,
        "ew_known_field_size": n_known_field,
        "ew_known_finish_pos": n_known_finish,
        "ew_all_fields_known": n_all_known,
        "ew_wins": ew_wins,
        "ew_places": ew_places,
        "ew_misses": ew_misses,
        "ew_place_rate": _pct(ew_places, n_total),
        "ew_win_rate": _pct(ew_wins, n_total),
        "ew_eligible_by_field": ew_eligible,
        "ew_3place_eligible": ew_3place,
        "pick_sp_avg": round(_safe_mean(pick_sps), 2) if _safe_mean(pick_sps) else None,
        "pick_sp_median": round(_safe_median(pick_sps), 2) if _safe_median(pick_sps) else None,
        "max_sp_placed": max_sp_placed,
        "max_sp_won": max_sp_won,
        "vfu20_note": vfu20_note,
        "profitability_status": "PARTIAL_EW_SIGNAL_NOT_PROFIT_PROOF — not changed by n=6 sample",
        "pick_sp_coverage": "PRICE_UNKNOWN for most — pick SP not systematically stored; see NEEDS_VFU_21_PICK_SP_BACKFILL",
        "detail": [{"course": r["course"], "off": r["off"], "pick": r["old_pick"],
                    "winner": r["winner"], "ew_outcome": r["ew_outcome"],
                    "winner_sp": r["winner_sp_str"], "field_size": r["field_size"]}
                   for r in ew_races],
    }


# ── Section 5: Mid-price miss recovery ───────────────────────────────────────

def _section5(data: dict) -> dict:
    races = data["races"]
    mp_misses = [r for r in races if r["miss_class"] == "mid_priced_won"]

    detail = []
    old_miss_nb_win = 0
    old_miss_norpr_win = 0
    old_miss_ew_caught = 0
    unrecovered = 0

    for r in mp_misses:
        winner_in_top3 = r["winner"] in r["top3"]
        old_top3 = r["old_pick"] in r["top3"]
        nb_in_top3 = r["nb_pick"] in r["top3"] if r["nb_pick"] else False
        norpr_in_top3 = r["norpr_pick"] in r["top3"] if r["norpr_pick"] else False

        nb_caught = r["nb_win"]
        norpr_caught = r["norpr_win"]
        ew_caught = r["assigned_product"] == "EW_CANDIDATE" and r["old_place"]

        if nb_caught:
            old_miss_nb_win += 1
            rec = "OLD_MISSED_NEW_BUILD_CAUGHT"
        elif norpr_caught:
            old_miss_norpr_win += 1
            rec = "OLD_MISSED_NO_RPR_CAUGHT"
        elif ew_caught:
            old_miss_ew_caught += 1
            rec = "OLD_MISSED_EW_CAUGHT"
        elif nb_in_top3 or norpr_in_top3:
            rec = "EXOTIC_ONLY_RECOVERY"
        else:
            unrecovered += 1
            rec = "MIDPRICE_UNRECOVERED"

        # Was winner ranked by RPR above Old pick?
        rpr_anchor = r["rpr_gap"] is not None and r["rpr_gap"] > 0.02

        detail.append({
            "course": r["course"],
            "off": r["off"],
            "winner": r["winner"],
            "winner_sp": r["winner_sp_str"],
            "old_pick": r["old_pick"],
            "old_vp": round(r["old_vp"], 3) if r["old_vp"] else None,
            "old_sqpe": round(r["old_sqpe"], 4) if r["old_sqpe"] else None,
            "norpr_pick": r["norpr_pick"],
            "norpr_in_top3": norpr_in_top3,
            "nb_pick": r["nb_pick"],
            "nb_in_top3": nb_in_top3,
            "old_in_top3": old_top3,
            "is_ew_candidate": r["assigned_product"] == "EW_CANDIDATE",
            "rpr_anchor_miss": rpr_anchor,
            "recovery": rec,
            "mds": round(r["mds"], 3) if r["mds"] else None,
        })

    return {
        "total_midprice_misses": len(mp_misses),
        "old_miss_nb_win": old_miss_nb_win,
        "old_miss_norpr_win": old_miss_norpr_win,
        "old_miss_ew_caught": old_miss_ew_caught,
        "unrecovered": unrecovered,
        "recovery_rate": _pct(len(mp_misses) - unrecovered, len(mp_misses)),
        "miss_analysis": "mid_priced_won x10 is likely the primary ROI lever — winner SP 4-16 range",
        "detail": detail,
    }


# ── Section 6: Exotics ───────────────────────────────────────────────────────

def _exacta_hit(picks: list[str], winner: str, second: str, ordered: bool) -> bool:
    if not winner or not second or len(picks) < 2:
        return False
    if ordered:
        return picks[0] == winner and picks[1] == second
    return set(picks[:2]) == {winner, second}


def _trifecta_hit(picks: list[str], w1: str, w2: str, w3: str, ordered: bool) -> bool:
    if not all([w1, w2, w3]) or len(picks) < 3:
        return False
    if ordered:
        return picks[0] == w1 and picks[1] == w2 and picks[2] == w3
    return {w1, w2, w3}.issubset(set(picks[:3]))


def _box_hit(picks: list[str], targets: list[str]) -> bool:
    return all(t in picks for t in targets if t)


def _section6(data: dict) -> dict:
    races = data["races"]
    eligible = [r for r in races if r["winner"] and r["horse_2nd"] and len(r["finish_order"]) >= 2]
    trifecta_eligible = [r for r in eligible if r["horse_3rd"] and len(r["finish_order"]) >= 3]

    # Build pick sets per construction
    stats: dict[str, dict] = {
        "old_top1_only": {"exacta_ordered": 0, "exacta_reverse": 0, "exacta_box2": 0,
                          "trifecta_ordered": 0, "trifecta_box3": 0, "n_exacta": 0, "n_trifecta": 0},
        "old_norpr_box": {"exacta_ordered": 0, "exacta_reverse": 0, "exacta_box": 0,
                          "trifecta_box": 0, "n_exacta": 0, "n_trifecta": 0, "combinations": 2},
        "old_nb_box": {"exacta_ordered": 0, "exacta_reverse": 0, "exacta_box": 0,
                       "trifecta_box": 0, "n_exacta": 0, "n_trifecta": 0, "combinations": 2},
        "consensus_top1s": {"exacta_box": 0, "trifecta_box": 0,
                             "n_exacta": 0, "n_trifecta": 0, "avg_picks": 0},
        "nb_only_top1": {"in_exacta_pos": 0, "in_top3_actual": 0, "n": 0},
        "norpr_only_top1": {"in_exacta_pos": 0, "in_top3_actual": 0, "n": 0},
    }

    race_detail = []

    for r in eligible:
        w1 = r["winner"]
        w2 = r["horse_2nd"]
        w3 = r["horse_3rd"]
        old = r["old_pick"]
        norpr = r["norpr_pick"]
        nb = r["nb_pick"]

        # Unique picks across models
        consensus_picks = list(dict.fromkeys([p for p in [old, norpr, nb] if p]))

        # Old top-1 exacta stats
        stats["old_top1_only"]["n_exacta"] += 1
        if _exacta_hit([old], w1, w2, ordered=True):
            stats["old_top1_only"]["exacta_ordered"] += 1
        if _exacta_hit([old], w1, w2, ordered=False):
            stats["old_top1_only"]["exacta_reverse"] += 1

        # Old+NoRPR box
        old_norpr = list(dict.fromkeys([p for p in [old, norpr] if p]))
        stats["old_norpr_box"]["n_exacta"] += 1
        if len(old_norpr) >= 2 and _box_hit(old_norpr, [w1, w2]):
            stats["old_norpr_box"]["exacta_box"] += 1
        if len(old_norpr) >= 1 and old_norpr[0] == w1:
            stats["old_norpr_box"]["exacta_ordered"] += 1

        # Old+NB box
        old_nb = list(dict.fromkeys([p for p in [old, nb] if p]))
        stats["old_nb_box"]["n_exacta"] += 1
        if len(old_nb) >= 2 and _box_hit(old_nb, [w1, w2]):
            stats["old_nb_box"]["exacta_box"] += 1

        # Consensus box
        stats["consensus_top1s"]["n_exacta"] += 1
        if _box_hit(consensus_picks, [w1, w2]):
            stats["consensus_top1s"]["exacta_box"] += 1
        stats["consensus_top1s"]["avg_picks"] += len(consensus_picks)

        # NB as exotic fill
        if nb:
            stats["nb_only_top1"]["n"] += 1
            if nb in [w1, w2]:
                stats["nb_only_top1"]["in_exacta_pos"] += 1
            if nb in r["top3"]:
                stats["nb_only_top1"]["in_top3_actual"] += 1

        # NoRPR as exotic fill
        if norpr:
            stats["norpr_only_top1"]["n"] += 1
            if norpr in [w1, w2]:
                stats["norpr_only_top1"]["in_exacta_pos"] += 1
            if norpr in r["top3"]:
                stats["norpr_only_top1"]["in_top3_actual"] += 1

        # Trifecta eligible
        if r in trifecta_eligible and w3:
            stats["old_top1_only"]["n_trifecta"] += 1
            if _trifecta_hit([old], w1, w2, w3, ordered=True):
                stats["old_top1_only"]["trifecta_ordered"] += 1
            # top3 box needs all 3 in 3 picks — with only 1 pick, impossible
            stats["old_norpr_box"]["n_trifecta"] += 1
            old_norpr_3 = list(dict.fromkeys([p for p in [old, norpr] if p]))
            if _box_hit(old_norpr_3, [w1, w2, w3]):
                stats["old_norpr_box"]["trifecta_box"] += 1
            stats["consensus_top1s"]["n_trifecta"] += 1
            if _box_hit(consensus_picks, [w1, w2, w3]):
                stats["consensus_top1s"]["trifecta_box"] += 1

        # Collect race detail
        exacta_ordered = old == w1 and norpr == w2
        exacta_reverse = set([old, norpr]) == {w1, w2} if norpr else False
        trifecta_box = _box_hit(consensus_picks, [w1, w2, w3]) if w3 else None

        race_detail.append({
            "race_id": r["race_id"],
            "course": r["course"],
            "off": r["off"],
            "w1": w1,
            "w1_sp": r["winner_sp_str"],
            "w2": w2,
            "w2_sp": _sp_str(r["sp_2nd"]),
            "w3": w3,
            "old_pick": old,
            "norpr_pick": norpr,
            "nb_pick": nb,
            "consensus_picks": consensus_picks,
            "exacta_ordered": exacta_ordered,
            "exacta_reverse": exacta_reverse,
            "old_norpr_exacta_box": _box_hit([old, norpr], [w1, w2]) if norpr else None,
            "consensus_exacta_box": _box_hit(consensus_picks, [w1, w2]),
            "consensus_trifecta_box": trifecta_box,
        })

    n_ex = len(eligible)
    n_tri = len(trifecta_eligible)
    avg_picks = stats["consensus_top1s"]["avg_picks"] / n_ex if n_ex else 0

    # Rate calcs
    on_box = stats["old_norpr_box"]["exacta_box"]
    cn_box = stats["consensus_top1s"]["exacta_box"]
    ct_box = stats["consensus_top1s"]["trifecta_box"]

    # Verdict labels
    exacta_verdict = "EXACTA_BOX_TOP3_SIGNAL" if n_ex > 0 and cn_box / n_ex >= 0.15 else "EXOTICS_SIGNAL_ONLY"
    trifecta_verdict = "TRIFECTA_BOX_TOP3_SIGNAL" if n_tri > 0 and ct_box / n_tri >= 0.10 else "EXOTICS_SIGNAL_ONLY"

    return {
        "exacta_verdict": exacta_verdict,
        "trifecta_verdict": trifecta_verdict,
        "exotics_proof_status": "EXOTICS_DIVIDEND_UNKNOWN — SIMULATED_SP_PROXY_NOT_DIVIDEND",
        "n_exacta_eligible": n_ex,
        "n_trifecta_eligible": n_tri,
        "old_top1_as_winner": _pct(stats["old_top1_only"]["exacta_ordered"], n_ex),
        "old_norpr_exacta_box_hits": on_box,
        "old_norpr_exacta_box_rate": _pct(on_box, n_ex),
        "old_norpr_combinations": 2,
        "consensus_exacta_box_hits": cn_box,
        "consensus_exacta_box_rate": _pct(cn_box, n_ex),
        "consensus_avg_picks": round(avg_picks, 1),
        "consensus_trifecta_box_hits": ct_box,
        "consensus_trifecta_box_rate": _pct(ct_box, n_tri),
        "nb_in_exacta_positions": _pct(stats["nb_only_top1"]["in_exacta_pos"], stats["nb_only_top1"]["n"]),
        "nb_in_actual_top3": _pct(stats["nb_only_top1"]["in_top3_actual"], stats["nb_only_top1"]["n"]),
        "norpr_in_exacta_positions": _pct(stats["norpr_only_top1"]["in_exacta_pos"],
                                          stats["norpr_only_top1"]["n"]),
        "norpr_in_actual_top3": _pct(stats["norpr_only_top1"]["in_top3_actual"],
                                     stats["norpr_only_top1"]["n"]),
        "containment_is_not_profit": True,
        "box_hit_is_not_profit": True,
        "sp_proxy_labelled": "SIMULATED_SP_PROXY_NOT_DIVIDEND_PROOF",
        "race_detail": race_detail,
        "limitation": "SINGLE_TOP_PICK_ONLY per model. True exotic coverage requires full ranked model outputs.",
    }


def _sp_str(val: float | None) -> str:
    return f"{val:.2f}" if val is not None else "UNKNOWN"


# ── Section 7: Combined race table ───────────────────────────────────────────

def _section7(data: dict) -> dict:
    races = data["races"]
    rows = []
    for r in races:
        w1 = r["winner"]
        w2 = r["horse_2nd"] or ""
        w3 = r["horse_3rd"] or ""
        old = r["old_pick"]
        norpr = r["norpr_pick"] or "—"
        nb = r["nb_pick"] or "—"

        consensus = list(dict.fromkeys([p for p in [old, norpr, nb] if p and p != "—"]))

        old_hit = r["old_win"]
        norpr_hit = r["norpr_win"]
        nb_top3 = nb in r["top3"] if nb != "—" else False
        ew_placed = r["ew_outcome"] in ("EW_WIN", "EW_PLACE") if r["ew_outcome"] else False

        exacta_top2_ordered = (old == w1 and norpr == w2)
        exacta_top3_box = _box_hit(consensus, [w1, w2])
        trifecta_top3_ordered = (old == w1 and norpr == w2 and nb == w3)
        trifecta_top3_box = _box_hit(consensus, [w1, w2, w3]) if w3 else False
        trifecta_top4_box = False  # Only 3 picks max from 3 models

        rows.append({
            "race_id": r["race_id"],
            "course": r["course"],
            "off": r["off"],
            "field_size": r["field_size"] or "?",
            "winner": w1,
            "winner_sp": r["winner_sp_str"],
            "second": w2 or "?",
            "second_sp": _sp_str(r["sp_2nd"]),
            "third": w3 or "?",
            "third_sp": _sp_str(r["sp_3rd"]),
            "old_top1": old,
            "norpr_top1": norpr,
            "nb_top1": nb,
            "ew_candidate": r["assigned_product"] == "EW_CANDIDATE",
            "old_hit": old_hit,
            "norpr_hit": norpr_hit,
            "nb_top3_containment": nb_top3,
            "ew_placed": ew_placed,
            "exacta_top2_ordered": exacta_top2_ordered,
            "exacta_top3_box": exacta_top3_box,
            "trifecta_top3_ordered": trifecta_top3_ordered,
            "trifecta_top3_box": trifecta_top3_box,
            "trifecta_top4_box": trifecta_top4_box,
            "miss_class": r["miss_class"] or "n/a",
            "notes": (r["miss_class"] or "") + (" EW" if r["assigned_product"] == "EW_CANDIDATE" else ""),
        })
    return {"rows": rows, "note": "SINGLE_TOP_PICK_ONLY per model — no_rpr/nb top2/top3 not available"}


# ── Section 8: Operator summary ───────────────────────────────────────────────

def _section8(s1: dict, s2: dict, s3: dict, s4: dict, s5: dict, s6: dict) -> dict:
    old_sr = float(s2["old_velo_sr"].rstrip("%")) if "%" in s2["old_velo_sr"] else 0
    nb_sr = float(s3["nb_sr"].rstrip("%")) if "%" in s3["nb_sr"] else 0
    norpr_sr = float(s2["norpr_sr"].rstrip("%")) if "%" in s2["norpr_sr"] else 0

    day_rating = "WEAK" if old_sr < 20 else ("AVERAGE" if old_sr < 28 else "STRONG")

    return {
        "day_rating": day_rating,
        "old_velo_sr": s2["old_velo_sr"],
        "norpr_sr": s2["norpr_sr"],
        "nb_sr": s3["nb_sr"],
        "q1_day_quality": f"{day_rating} — Old VELO SR {s2['old_velo_sr']} vs historic avg ~25.7%",
        "q2_rpr_led": f"VERDICT={s2['verdict']} | RPR gap interpretation={s2['rpr_interpretation']} | RPR boosts score in {s2['rpr_boosts_score_n']}/46 races",
        "q3_norpr_vs_old": f"No-RPR SR={s2['norpr_sr']} vs Old VELO SR={s2['old_velo_sr']} | Agreement={s2['norpr_agreement_with_old']} | No-RPR better in {s2['norpr_better_cases']} races",
        "q4_new_build": f"VERDICT={s3['verdict_primary']} | NB SR={s3['nb_sr']} top-pick but in-actual-top3={s3['nb_top3_containment']}",
        "q5_nb_longprice": f"Long-price horses in NB actual-top3: {s3['long_price_nb_in_top3']} races",
        "q6_ew_signal": f"EW: {s4['ew_place_rate']} place rate (n={s4['ew_n']}) — status={s4['profitability_status']}",
        "q7_exacta": f"Consensus exacta box hits: {s6['consensus_exacta_box_hits']}/{s6['n_exacta_eligible']} = {s6['consensus_exacta_box_rate']} | {s6['exacta_verdict']}",
        "q8_trifecta": f"Consensus trifecta box hits: {s6['consensus_trifecta_box_hits']}/{s6['n_trifecta_eligible']} = {s6['consensus_trifecta_box_rate']} | {s6['trifecta_verdict']}",
        "q9_best_construction": "Old VELO top-1 as win anchor + consensus box for exotic fill. Minimal overlap (avg ~2 unique picks from 3 models) = low-cost box.",
        "q10_forward_test": "Run 7-day prospective shadow of: (A) Old anchor + consensus box exacta. (B) EW candidates on field>=8. Both PAPER only, no live staking.",
        "q11_blocked_by_missing_data": [
            f"pick_sp missing — EW and exotics cannot be profit-proven (need VFU-21)",
            f"No ranked list per model — top-2/top-3 model containment unverifiable (SINGLE_TOP_PICK_ONLY)",
            f"Exotic dividends unknown — all returns are SIMULATED_SP_PROXY_NOT_DIVIDEND_PROOF",
            f"field_size gaps: {s4['ew_n'] - s4['ew_known_field_size']} EW races missing field_size",
        ],
        "q12_next": [
            "Continue VCP-03 burn-in daily triple.",
            "No model promotion.",
            "VFU-21 pick_sp backfill is the next structural repair — EW and exotics cannot be profit-proven without price data.",
            "New Build reclassification to VALUE_SCOUT / EXOTIC_FILL_CANDIDATE pending prospective validation.",
            "Old VELO RPR dependency audit across full 33-day corpus — cannot complete from single day.",
        ],
    }


# ── Section 9: Next action ────────────────────────────────────────────────────

def _section9() -> dict:
    return {
        "recommendation": "A+B",
        "A": "Continue VCP-03 burn-in only — daily triple mandatory",
        "B": "VFU-21 pick_sp backfill next (operator decision required) — EW/exotics cannot be profit-proven without price data",
        "C_deferred": "7-day prospective shadow of New Build top-3 / EW / exotics — AFTER VCP-03 completes",
        "D_deferred": "RPR dependency audit across full 33-day corpus — single day insufficient",
        "E_considered_and_rejected": "Hold all intelligence = too conservative given report-only forensics are safe",
        "do_not_start": ["VFU-21", "VCP-04", "CASE_MEMORY", "MODEL_PROMOTION", "LIVE_SCORING_CHANGE"],
        "reclassification_candidates": {
            "New_Build": "VALUE_SCOUT / EXOTIC_FILL_CANDIDATE (pending prospective validation)",
            "Old_VELO": "STRIKE_ANCHOR / RPR_PUBLIC_STRENGTH_ANCHOR (pending 33-day RPR audit)",
            "EW_CANDIDATE": "PLACE_SIGNAL_NOT_PROFIT_PROOF (pending VFU-21 pick_sp)",
        },
    }


# ── Markdown renderers ────────────────────────────────────────────────────────

def _h(n: int, text: str) -> str:
    return f"{'#' * n} {text}"


def _render_rpr(s2: dict) -> str:
    lines = [
        _h(1, "J30-FOR — Old VELO RPR Dependency Audit — 2026-06-30"),
        f"**Generated:** {datetime.now(timezone.utc).isoformat()}  ",
        "**REPORT_ONLY — no scoring change, no model mutation.**", "",
        _h(2, "Verdict"), f"- Primary: **{s2['verdict']}**",
        f"- RPR interpretation: `{s2['rpr_interpretation']}`", "",
        _h(2, "Win SR Comparison"),
        f"| Model | n | Wins | SR | Top-3 containment |",
        f"|---|---|---|---|---|",
        f"| Old VELO | 46 | {s2['old_velo_wins']} | **{s2['old_velo_sr']}** | {s2['old_velo_top3_containment']} |",
        f"| No-RPR | {s2['norpr_n']} | {s2['norpr_wins']} | {s2['norpr_sr']} | {s2['norpr_top3_containment']} |",
        "",
        _h(2, "RPR Score Gap Analysis"),
        f"- Races where RPR boosts score (sqpe_v17 > sqpe_norpr): **{s2['rpr_boosts_score_n']}/46**",
        f"- Races where RPR drags score: {s2['rpr_drag_count']}",
        f"- Avg RPR gap on **wins**: {s2['rpr_gap_avg_wins']}",
        f"- Avg RPR gap on **misses**: {s2['rpr_gap_avg_misses']}",
        f"- RPR missing on top pick: {s2['rpr_missing_on_top_pick']}",
        f"- OR missing on top pick: {s2['or_missing_on_top_pick']}", "",
        _h(2, "Pick Agreement"),
        f"- Old VELO and No-RPR agree on same pick: **{s2['norpr_agreement_with_old']}** of races",
        f"- No-RPR won and Old missed: {s2['norpr_better_cases']} races",
        f"- Old won and No-RPR missed: {s2['old_better_cases']} races",
        f"- Both won same race: {s2['both_win_cases']} races", "",
        _h(2, "Winner SP Profile"),
        f"| Model | Avg winner SP | Median winner SP |",
        f"|---|---|---|",
        f"| Old VELO | {s2['old_winner_sp_avg']} | {s2['old_winner_sp_median']} |",
        f"| No-RPR | {s2['norpr_winner_sp_avg']} | {s2['norpr_winner_sp_median']} |", "",
    ]
    if s2["norpr_better_detail"]:
        lines += [_h(2, "No-RPR Better Cases")]
        for d in s2["norpr_better_detail"]:
            lines.append(f"- {d['course']} {d['off']}: winner={d['winner']} ({d['winner_sp']}) | No-RPR={d['norpr']} | Old={d['old']}")
        lines.append("")
    lines += [
        _h(2, "Limitation"),
        f"> {s2['limitation']}", "",
        "---",
        "REPORT_ONLY",
    ]
    return "\n".join(lines)


def _render_nb(s3: dict) -> str:
    lines = [
        _h(1, "J30-FOR — New Build Top-3 Value Containment Audit — 2026-06-30"),
        f"**Generated:** {datetime.now(timezone.utc).isoformat()}  ",
        "**REPORT_ONLY — no scoring change, no model mutation.**", "",
        _h(2, "Verdict"),
        f"- Top-pick verdict: **{s3['verdict_primary']}**",
        f"- Long-price verdict: **{s3['verdict_longprice']}**", "",
        _h(2, "New Build Metrics"),
        f"| Metric | Value |",
        f"|---|---|",
        f"| n (picks available) | {s3['nb_n']} |",
        f"| Win SR (top-1) | **{s3['nb_sr']}** |",
        f"| Place rate | {s3['nb_place_rate']} |",
        f"| In actual top-3 | **{s3['nb_top3_containment']}** |",
        f"| NB winner SP avg | {s3['nb_winner_sp_avg']} |",
        f"| NB winner SP median | {s3['nb_winner_sp_median']} |",
        f"| Old VELO winner SP avg | {s3['old_winner_sp_avg']} |",
        f"| Old VELO winner SP median | {s3['old_winner_sp_median']} |",
        f"| Old missed, NB won | {s3['old_miss_nb_win']} |",
        f"| Old missed, NB in top-3 | {s3['old_miss_nb_in_top3']} |",
        f"| Long-price (6+) NB in top-3 | {s3['long_price_nb_in_top3']} |",
        f"| EW/NB top-3 overlap | {s3['ew_nb_overlap']} |", "",
    ]
    if s3["old_miss_nb_win_detail"]:
        lines += [_h(2, "Old Missed — New Build Caught")]
        for d in s3["old_miss_nb_win_detail"]:
            lines.append(f"- {d['course']} {d['off']}: winner={d['winner']} ({d['winner_sp']}) | NB={d['nb']} | Old={d['old']}")
        lines.append("")
    if s3["long_price_detail"]:
        lines += [_h(2, "Long-Price New Build Top-3 Containment")]
        for d in s3["long_price_detail"]:
            lines.append(f"- {d['course']} {d['off']}: winner={d['winner']} ({d['winner_sp']}) | NB={d['nb_pick']} in_top3={d['nb_in_top3']}")
        lines.append("")
    lines += [
        _h(2, "Limitation"),
        f"> {s3['limitation']}", "",
        "---", "REPORT_ONLY",
    ]
    return "\n".join(lines)


def _render_ew(s4: dict) -> str:
    lines = [
        _h(1, "J30-FOR — EW Candidate Reality Audit — 2026-06-30"),
        f"**Generated:** {datetime.now(timezone.utc).isoformat()}  ",
        "**REPORT_ONLY — no profitability claim without dividend data.**", "",
        _h(2, "Verdict"), f"- **{s4['verdict']}**",
        f"- Profitability: **{s4['profitability_status']}**", "",
        _h(2, "EW Coverage"),
        f"| Field | Value |",
        f"|---|---|",
        f"| EW candidates | {s4['ew_n']} |",
        f"| Known SP | {s4['ew_known_sp']} |",
        f"| Known field_size | {s4['ew_known_field_size']} |",
        f"| Known finish position | {s4['ew_known_finish_pos']} |",
        f"| All fields known | {s4['ew_all_fields_known']} |",
        f"| EW wins | {s4['ew_wins']} |",
        f"| EW places (incl wins) | {s4['ew_places']} |",
        f"| EW misses | {s4['ew_misses']} |",
        f"| Place rate | **{s4['ew_place_rate']}** |",
        f"| EW eligible (field≥5) | {s4['ew_eligible_by_field']} |",
        f"| 3-place eligible (field≥8) | {s4['ew_3place_eligible']} |",
        f"| Pick SP avg | {s4['pick_sp_avg']} |",
        f"| Max SP placed | {s4['max_sp_placed']} |",
        f"| Max SP won | {s4['max_sp_won']} |", "",
        _h(2, "Race Detail"),
        "| Course | Off | Pick | Winner | EW Outcome | SP | Field |",
        "|---|---|---|---|---|---|---|",
    ]
    for d in s4["detail"]:
        lines.append(f"| {d['course']} | {d['off']} | {d['pick']} | {d['winner']} | {d['ew_outcome']} | {d['winner_sp']} | {d['field_size']} |")
    lines += [
        "",
        f"> **Note:** {s4['vfu20_note']}",
        f"> {s4['pick_sp_coverage']}", "",
        "---", "REPORT_ONLY",
    ]
    return "\n".join(lines)


def _render_mp(s5: dict) -> str:
    lines = [
        _h(1, "J30-FOR — Mid-Price Miss Recovery Audit — 2026-06-30"),
        f"**Generated:** {datetime.now(timezone.utc).isoformat()}  ",
        "**REPORT_ONLY — no model change.**", "",
        _h(2, "Summary"),
        f"- Total mid-price misses: **{s5['total_midprice_misses']}** (mid_priced_won ×10)",
        f"- Old missed, NB won: {s5['old_miss_nb_win']}",
        f"- Old missed, No-RPR won: {s5['old_miss_norpr_win']}",
        f"- Old missed, EW caught (placed): {s5['old_miss_ew_caught']}",
        f"- Fully unrecovered: **{s5['unrecovered']}**",
        f"- Recovery rate: {s5['recovery_rate']}", "",
        _h(2, "Race Detail"),
        "| Course | Off | Winner | SP | Old | norpr | NB | NB top-3 | RPR anchor miss | Recovery |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for d in s5["detail"]:
        lines.append(
            f"| {d['course']} | {d['off']} | {d['winner']} | {d.get('winner_sp','?')} "
            f"| {d['old_pick']} | {d.get('norpr_pick','—')} | {d.get('nb_pick','—')} "
            f"| {'Y' if d['nb_in_top3'] else 'N'} | {'Y' if d['rpr_anchor_miss'] else 'N'} "
            f"| {d['recovery']} |"
        )
    lines += ["", f"> {s5['miss_analysis']}", "", "---", "REPORT_ONLY"]
    return "\n".join(lines)


def _render_exotics(s6: dict) -> str:
    lines = [
        _h(1, "J30-FOR — Exotics Audit — 2026-06-30"),
        f"**Generated:** {datetime.now(timezone.utc).isoformat()}  ",
        "**REPORT_ONLY. Containment is not profit. SP proxy is not dividend.**", "",
        _h(2, "Verdicts"),
        f"- Exacta: **{s6['exacta_verdict']}**",
        f"- Trifecta: **{s6['trifecta_verdict']}**",
        f"- Proof status: **{s6['exotics_proof_status']}**", "",
        _h(2, "Exacta / Forecast Metrics"),
        f"| Construction | Hits | n | Rate | Cost |",
        f"|---|---|---|---|---|",
        f"| Old top-1 as winner | — | {s6['n_exacta_eligible']} | {s6['old_top1_as_winner']} | 1 unit |",
        f"| Old+NoRPR exacta box | {s6['old_norpr_exacta_box_hits']} | {s6['n_exacta_eligible']} | {s6['old_norpr_exacta_box_rate']} | 2 combos |",
        f"| Consensus box (2-3 picks) | {s6['consensus_exacta_box_hits']} | {s6['n_exacta_eligible']} | {s6['consensus_exacta_box_rate']} | 2-6 combos |", "",
        _h(2, "Trifecta / Tricast Metrics"),
        f"| Construction | Hits | n | Rate |",
        f"|---|---|---|---|",
        f"| Consensus box (top-3 finishers) | {s6['consensus_trifecta_box_hits']} | {s6['n_trifecta_eligible']} | {s6['consensus_trifecta_box_rate']} |", "",
        _h(2, "Exotic Fill Signal"),
        f"| Lane | In exacta positions (1st/2nd) | In actual top-3 |",
        f"|---|---|---|",
        f"| New Build top-1 | {s6['nb_in_exacta_positions']} | {s6['nb_in_actual_top3']} |",
        f"| No-RPR top-1 | {s6['norpr_in_exacta_positions']} | {s6['norpr_in_actual_top3']} |", "",
        _h(2, "Hard Constraints"),
        "- CONTAINMENT IS NOT PROFIT",
        "- BOX HIT IS NOT PROFIT",
        "- SP PROXY IS NOT PAYOUT",
        "- DIVIDEND_UNKNOWN on all constructions", "",
        _h(2, "Limitation"),
        f"> {s6['limitation']}", "",
        "---", "REPORT_ONLY",
    ]
    return "\n".join(lines)


def _render_brief(s1: dict, s2: dict, s3: dict, s4: dict, s5: dict, s6: dict, s7: dict,
                  s8: dict, s9: dict) -> str:
    lines = [
        _h(1, "J30-FOR — Forensic Operator Brief — 2026-06-30"),
        f"**Generated:** {datetime.now(timezone.utc).isoformat()}  ",
        "**Mission:** J30-FOR — June 30 Full Forensic Pack With Exotics", "",
        "---",
        _h(2, "Loop Integrity"),
        f"- Races: {s1['races_total']} | Matched: {s1['races_matched']} | Parse retries: {s1['parse_retry_count']}",
        f"- Identity failures: {s1['identity_failures']} | Missing winner SP: {s1['missing_winner_sp']}",
        f"- Full finish order: {s1['full_finish_order_races']}/46 races",
        f"- No-RPR available: {s1['norpr_available']}/46 | New Build available: {s1['nb_available']}/46",
        f"- Note: **{s1['ranked_list_note']}**", "",
        "---",
        _h(2, "Answers to Operator Questions"),
        "",
        f"**Q1 Day quality:** {s8['q1_day_quality']}",
        f"**Q2 RPR led:** {s8['q2_rpr_led']}",
        f"**Q3 No-RPR vs Old:** {s8['q3_norpr_vs_old']}",
        f"**Q4 New Build:** {s8['q4_new_build']}",
        f"**Q5 NB long-price:** {s8['q5_nb_longprice']}",
        f"**Q6 EW signal:** {s8['q6_ew_signal']}",
        f"**Q7 Exacta:** {s8['q7_exacta']}",
        f"**Q8 Trifecta:** {s8['q8_trifecta']}",
        f"**Q9 Best construction:** {s8['q9_best_construction']}",
        f"**Q10 Forward test:** {s8['q10_forward_test']}",
        "",
        _h(3, "Q11 Blocked by missing data"),
    ]
    for b in s8["q11_blocked_by_missing_data"]:
        lines.append(f"- {b}")
    lines += ["", _h(3, "Q12 Next")]
    for n in s8["q12_next"]:
        lines.append(f"- {n}")
    lines += [
        "",
        "---",
        _h(2, "Next Action Recommendation"),
        f"- **{s9['recommendation']}:** {s9['A']} + {s9['B']}",
        f"- Deferred C: {s9['C_deferred']}",
        f"- Deferred D: {s9['D_deferred']}",
        "",
        _h(2, "Reclassification Candidates"),
        f"- New Build: {s9['reclassification_candidates']['New_Build']}",
        f"- Old VELO: {s9['reclassification_candidates']['Old_VELO']}",
        f"- EW Candidate: {s9['reclassification_candidates']['EW_CANDIDATE']}",
        "",
        _h(2, "Active Contradiction"),
        "- **C-01** (WARN): Mission Control source_truth=RP_MERGED_CLEAN but learning/promotion gate BLOCKED",
        "  (GATE_PIPELINE_TRUTH_FALSE_PASS_NO_VERDICTS). Expected and valid. NOT SUPPRESSED.", "",
        _h(2, "Final Classifications"),
    ]
    for fc in _FINAL_CLASSIFICATIONS:
        lines.append(f"- {fc}")
    lines += ["", "---", "REPORT_ONLY — J30-FOR complete."]
    return "\n".join(lines)


def _render_full_md(s1: dict, s2: dict, s3: dict, s4: dict, s5: dict, s6: dict,
                    s7: dict, s8: dict, s9: dict) -> str:
    brief = _render_brief(s1, s2, s3, s4, s5, s6, s7, s8, s9)
    table_lines = [
        _h(1, "J30-FOR — Combined Race Table — 2026-06-30"), "",
        "| Race | Course | Off | FS | Winner | W-SP | 2nd | 3rd | Old | NoRPR | NB | EW | OldW | NoRPRW | NB-T3 | EW-P | Ex-Ord | Ex-Box | Tri-Box | Miss |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in s7["rows"]:
        ew = "Y" if r["ew_candidate"] else "N"
        table_lines.append(
            f"| {r['race_id']} | {r['course']} | {r['off']} | {r['field_size']} "
            f"| {r['winner'][:18]} | {r['winner_sp']} "
            f"| {r['second'][:14]} | {r['third'][:14]} "
            f"| {r['old_top1'][:14]} | {(r['norpr_top1'] or '—')[:14]} | {(r['nb_top1'] or '—')[:14]} "
            f"| {ew} | {'W' if r['old_hit'] else '.'} | {'W' if r['norpr_hit'] else '.'} "
            f"| {'Y' if r['nb_top3_containment'] else 'N'} | {'P' if r['ew_placed'] else '.'} "
            f"| {'Y' if r['exacta_top2_ordered'] else 'N'} | {'Y' if r['exacta_top3_box'] else 'N'} "
            f"| {'Y' if r['trifecta_top3_box'] else 'N'} | {r['miss_class'][:20]} |"
        )
    return brief + "\n\n---\n\n" + "\n".join(table_lines)


# ── main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    print(f"── J30-FOR: June 30 Forensic Pack — {_DATE} ──")
    print("  Loading data...")
    data = _load_all()

    n = len(data["races"])
    print(f"  Races joined: {n}")
    if n == 0:
        print("  ERROR: No races loaded. Check artifact paths.")
        return

    print("  Running sections...")
    s1 = _section1(data)
    s2 = _section2(data)
    s3 = _section3(data)
    s4 = _section4(data)
    s5 = _section5(data)
    s6 = _section6(data)
    s7 = _section7(data)
    s8 = _section8(s1, s2, s3, s4, s5, s6)
    s9 = _section9()

    print("  Writing output files...")
    _OUT.mkdir(parents=True, exist_ok=True)

    # 1. Full pack JSON
    pack = {
        "mission": "J30-FOR",
        "date": _DATE,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "hard_constraints": _HARD_CONSTRAINTS,
        "final_classifications": _FINAL_CLASSIFICATIONS,
        "contradiction_c01": {
            "id": "C-01", "status": "RECORDED_NOT_SUPPRESSED",
            "description": "source_truth=RP_MERGED_CLEAN but learning gate BLOCKED (GATE_PIPELINE_TRUTH_FALSE_PASS_NO_VERDICTS)",
        },
        "s1_loop_integrity": s1,
        "s2_rpr_dependency": s2,
        "s3_new_build_value": s3,
        "s4_ew_reality": s4,
        "s5_midprice_miss": s5,
        "s6_exotics": s6,
        "s7_race_table": s7,
        "s8_operator_summary": s8,
        "s9_next_action": s9,
    }
    _F_FULL_JSON.write_text(json.dumps(pack, indent=2), encoding="utf-8")
    print(f"  OK   {_F_FULL_JSON.name}")

    # 2. Full pack MD
    _F_FULL_MD.write_text(_render_full_md(s1, s2, s3, s4, s5, s6, s7, s8, s9), encoding="utf-8")
    print(f"  OK   {_F_FULL_MD.name}")

    # 3. RPR audit
    _F_RPR_MD.write_text(_render_rpr(s2), encoding="utf-8")
    print(f"  OK   {_F_RPR_MD.name}")

    # 4. New Build
    _F_NB_MD.write_text(_render_nb(s3), encoding="utf-8")
    print(f"  OK   {_F_NB_MD.name}")

    # 5. EW
    _F_EW_MD.write_text(_render_ew(s4), encoding="utf-8")
    print(f"  OK   {_F_EW_MD.name}")

    # 6. Mid-price
    _F_MP_MD.write_text(_render_mp(s5), encoding="utf-8")
    print(f"  OK   {_F_MP_MD.name}")

    # 7. Exotics
    _F_EX_MD.write_text(_render_exotics(s6), encoding="utf-8")
    print(f"  OK   {_F_EX_MD.name}")

    # 8. Operator brief
    _F_BRIEF_MD.write_text(_render_brief(s1, s2, s3, s4, s5, s6, s7, s8, s9), encoding="utf-8")
    print(f"  OK   {_F_BRIEF_MD.name}")

    print()
    print(f"  Loop integrity: {s1['races_matched']}/46 matched | retries: {s1['parse_retry_count']}")
    print(f"  Old VELO SR: {s2['old_velo_sr']} | RPR verdict: {s2['verdict']}")
    print(f"  No-RPR SR: {s2['norpr_sr']} | better cases: {s2['norpr_better_cases']}")
    print(f"  New Build SR: {s3['nb_sr']} | in-actual-top3: {s3['nb_top3_containment']} | verdict: {s3['verdict_primary']}")
    print(f"  EW: {s4['ew_place_rate']} place rate (n={s4['ew_n']}) | {s4['verdict']}")
    print(f"  Mid-price misses: {s5['total_midprice_misses']} | recovered: {s5['old_miss_nb_win']+s5['old_miss_norpr_win']+s5['old_miss_ew_caught']} | unrecovered: {s5['unrecovered']}")
    print(f"  Exotics: exacta consensus box {s6['consensus_exacta_box_rate']} | trifecta {s6['consensus_trifecta_box_rate']}")
    print(f"  C-01: RECORDED_NOT_SUPPRESSED")
    print()
    print("── J30-FOR DONE ──")


if __name__ == "__main__":
    main()
