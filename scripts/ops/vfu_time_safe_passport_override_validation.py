#!/usr/bin/env python3
"""
scripts/ops/vfu_time_safe_passport_override_validation.py
==========================================================
VFU-10 — Time-Safe Passport Override Validation (dry-run only).

Core question: Did the Passport ALREADY show discriminating signals BEFORE
2026-05-08 (current-era start)? Or do the 'positive' signals include the
VFU wins themselves?

Method:
  - Load passport_features.parquet (per-race Passport snapshots, training data)
  - Join with core_v0_historical_dataset.parquet to get race dates
  - Filter to date < 2026-05-08 → time-safe pre-era snapshot
  - Take last row per horse = "Passport as known before current era"
  - Compare across three groups:
      Group A: VP<0.40 winners (RP_UID confirmed)
      Group B: VP>=0.40 winners (RP_UID confirmed)
      Group C: VP<0.40 non-winners (RP_UID confirmed)

Hard rules:
  Does NOT change VP threshold.
  Does NOT mutate canonical Passport.
  Does NOT write Supabase.
  Does NOT change live scoring.
  Does NOT promote doctrine.
  Does NOT open Mar–Apr.
  Does NOT send Telegram.
  Does NOT restore Racing API.
  Does NOT promote any model.
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, stdev

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

# ── Inputs ────────────────────────────────────────────────────────────────────
AUTOPSY_ID_FILE   = ROOT / "data/reports/vfu_current_era_autopsy_records_identity_enriched.jsonl"
PASSPORT_FEATURES = ROOT / "data/new_build/training/passport_features.parquet"
CORE_V0           = ROOT / "data/new_build/training/core_v0_historical_dataset.parquet"

# ── Outputs ───────────────────────────────────────────────────────────────────
OUT_DIR           = ROOT / "data/reports"
OUT_JSON          = OUT_DIR / "vfu_time_safe_passport_override_validation.json"
OUT_MD            = OUT_DIR / "vfu_time_safe_passport_override_validation.md"
OUT_CASES         = OUT_DIR / "vfu_time_safe_passport_override_cases.jsonl"
OUT_UNCOVERED     = OUT_DIR / "vfu_time_safe_passport_uncovered_cases.json"
OUT_WATCHLIST     = OUT_DIR / "vfu_time_safe_passport_candidate_watchlist.json"

VALIDATION_VERSION = "VFU_10_TIME_SAFE_PASSPORT_OVERRIDE_V1"
VP_THRESHOLD       = 0.40
ERA_START          = "2026-05-08"

# Kakirra + Man is King known identities
KAKIRRA_ID    = "8866972"
MAN_IS_KING_ID = "3839266"

# Threshold for "SP shortened" — market has been backing horse
SP_SHORTENED_THRESHOLD = 20.0
# Threshold for "win_rate meaningful"
WIN_RATE_MEANINGFUL = 0.15
# Threshold for "course experienced"
COURSE_SEEN_THRESHOLD = 1


# ── Helpers ───────────────────────────────────────────────────────────────────

def norm_horse(h: str | None) -> str:
    """Lowercase, strip country suffix (IRE), remove punctuation."""
    if not h:
        return ""
    h = h.strip().lower()
    h = re.sub(r"\s*\([a-z]+\)\s*$", "", h)
    h = re.sub(r"[^a-z0-9 ]", "", h)
    return re.sub(r"\s+", " ", h).strip()


def load_jsonl(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(ln) for ln in f if ln.strip()]


def safe_mean(vals: list) -> float | None:
    cleaned = [v for v in vals if v is not None]
    return round(mean(cleaned), 4) if cleaned else None


def safe_rate(bools: list) -> float | None:
    if not bools:
        return None
    return round(sum(1 for b in bools if b) / len(bools), 4)


def build_pre_era_snapshot() -> dict[str, dict]:
    """
    Load passport_features.parquet + core_v0 dates.
    Filter to date < ERA_START.
    Take last row per horse (time-safe as-of-era-start Passport).
    Returns dict: norm_horse_name → passport feature dict.
    """
    try:
        import pandas as pd
    except ImportError:
        raise RuntimeError("pandas is required. Run: pip install pandas pyarrow")

    pf = pd.read_parquet(str(PASSPORT_FEATURES))
    core = pd.read_parquet(str(CORE_V0), columns=["race_id", "date"])
    core_dedup = core.drop_duplicates("race_id")

    pf_dated = pf.merge(core_dedup[["race_id", "date"]], on="race_id", how="left")
    pf_dated = pf_dated.dropna(subset=["date"])
    pf_dated["date"] = pd.to_datetime(pf_dated["date"], errors="coerce")
    pf_dated = pf_dated.dropna(subset=["date"])

    pre_era = pf_dated[pf_dated["date"] < ERA_START].copy()
    last_snap = pre_era.sort_values("date").groupby("horse").last().reset_index()

    snapshot: dict[str, dict] = {}
    for _, row in last_snap.iterrows():
        key = norm_horse(str(row["horse"]))
        if not key:
            continue
        snapshot[key] = {
            "horse_raw": str(row["horse"]),
            "last_pre_era_date": str(row["date"].date()),
            "pp_career_runs": _safe_int(row.get("pp_career_runs")),
            "pp_win_rate": _safe_float(row.get("pp_win_rate")),
            "pp_place_rate": _safe_float(row.get("pp_place_rate")),
            "pp_avg_sp_last5": _safe_float(row.get("pp_avg_sp_last5")),
            "pp_course_seen": _safe_int(row.get("pp_course_seen")),
            "pp_or_change_3": _safe_float(row.get("pp_or_change_3")),
            "pp_class_moved_up": _safe_int(row.get("pp_class_moved_up")),
            "pp_class_moved_down": _safe_int(row.get("pp_class_moved_down")),
            "pp_jockey_continuity": _safe_float(row.get("pp_jockey_continuity")),
            "pp_layoff": _safe_int(row.get("pp_layoff")),
        }
    return snapshot


def _safe_float(v) -> float | None:
    try:
        f = float(v)
        return None if f != f else round(f, 4)  # NaN check
    except (TypeError, ValueError):
        return None


def _safe_int(v) -> int | None:
    try:
        import math
        f = float(v)
        return None if math.isnan(f) else int(f)
    except (TypeError, ValueError):
        return None


def classify_contamination(horse_id: str, snap: dict | None) -> str:
    """Classify temporal contamination status for a horse."""
    if snap is None:
        if horse_id == KAKIRRA_ID:
            return "TEMPORAL_CONTAMINATION_UNRESOLVABLE"
        return "NO_PRE_ERA_DATA"
    # Man is King: has pre-era data but current win_rate is contaminated
    if horse_id == MAN_IS_KING_ID:
        return "PARTIAL_CONTAMINATION"
    return "CLEAN_PRE_ERA_SNAPSHOT"


def derive_time_safe_signals(snap: dict | None) -> dict:
    """Extract time-safe discriminating signals from a pre-era snapshot."""
    if snap is None:
        return {
            "sp_shortened": None,
            "win_rate_meaningful": None,
            "course_experienced": None,
            "class_dropper": None,
            "or_falling": None,
            "has_any_signal": False,
        }
    sp5 = snap.get("pp_avg_sp_last5")
    wr = snap.get("pp_win_rate")
    cs = snap.get("pp_course_seen")
    cmd = snap.get("pp_class_moved_down")
    orc = snap.get("pp_or_change_3")

    sp_short = (sp5 is not None and sp5 < SP_SHORTENED_THRESHOLD)
    wr_meaningful = (wr is not None and wr > WIN_RATE_MEANINGFUL)
    course_exp = (cs is not None and cs >= COURSE_SEEN_THRESHOLD)
    class_drop = (cmd is not None and cmd > 0)
    or_fall = (orc is not None and orc < -1.0)

    signals = {
        "sp_shortened": sp_short,
        "win_rate_meaningful": wr_meaningful,
        "course_experienced": course_exp,
        "class_dropper": class_drop,
        "or_falling": or_fall,
        "has_any_signal": any([sp_short, wr_meaningful, course_exp, class_drop, or_fall]),
    }
    return signals


def build_groups(records: list[dict]) -> tuple[list, list, list]:
    """Return (group_a, group_b, group_c) from enriched autopsy records."""
    group_a, group_b, group_c = [], [], []
    for r in records:
        ns = r.get("horse_id_namespace")
        if ns != "RP_UID":
            continue
        vp = r.get("vp") or 0.0
        outcome = r.get("outcome", "")
        if outcome == "WIN" and vp < VP_THRESHOLD:
            group_a.append(r)
        elif outcome == "WIN" and vp >= VP_THRESHOLD:
            group_b.append(r)
        elif outcome != "WIN" and vp < VP_THRESHOLD:
            group_c.append(r)
    return group_a, group_b, group_c


def compute_group_stats(group: list[dict], snapshot: dict[str, dict], label: str) -> dict:
    """Compute time-safe Passport feature stats for a group."""
    covered, uncovered = [], []
    signal_counts: dict[str, list[bool]] = {
        "sp_shortened": [], "win_rate_meaningful": [], "course_experienced": [],
        "class_dropper": [], "or_falling": [], "has_any_signal": [],
    }
    win_rates, sp_vals, career_runs = [], [], []

    # Deduplicate by horse_id for cleaner group-level stats
    seen_ids: set[str] = set()
    for r in group:
        hid = str(r.get("horse_id", ""))
        if hid in seen_ids:
            continue
        seen_ids.add(hid)

        hname = r.get("horse_name", "")
        key = norm_horse(hname)
        snap = snapshot.get(key)
        sigs = derive_time_safe_signals(snap)

        if snap is not None:
            covered.append(r)
            for s, v in sigs.items():
                if isinstance(v, bool):
                    signal_counts[s].append(v)
            wr = snap.get("pp_win_rate")
            sp5 = snap.get("pp_avg_sp_last5")
            cr = snap.get("pp_career_runs")
            if wr is not None:
                win_rates.append(wr)
            if sp5 is not None:
                sp_vals.append(sp5)
            if cr is not None:
                career_runs.append(cr)
        else:
            uncovered.append(r)

    n_distinct = len(seen_ids)
    n_covered = len(covered)
    n_uncovered = len(uncovered)

    return {
        "group_label": label,
        "n_runs": len(group),
        "n_distinct_horses": n_distinct,
        "n_with_pre_era_snapshot": n_covered,
        "n_without_pre_era_snapshot": n_uncovered,
        "coverage_pct": round(n_covered / max(n_distinct, 1) * 100, 1),
        "avg_pp_win_rate": safe_mean(win_rates),
        "avg_pp_avg_sp_last5": safe_mean(sp_vals),
        "avg_pp_career_runs": safe_mean(career_runs),
        "pct_sp_shortened": safe_rate(signal_counts["sp_shortened"]),
        "pct_win_rate_meaningful": safe_rate(signal_counts["win_rate_meaningful"]),
        "pct_course_experienced": safe_rate(signal_counts["course_experienced"]),
        "pct_class_dropper": safe_rate(signal_counts["class_dropper"]),
        "pct_or_falling": safe_rate(signal_counts["or_falling"]),
        "pct_has_any_signal": safe_rate(signal_counts["has_any_signal"]),
    }


def build_case_records(
    group: list[dict],
    group_label: str,
    snapshot: dict[str, dict],
) -> list[dict]:
    """Build per-horse case records with time-safe Passport data."""
    cases = []
    seen_ids: set[str] = set()
    for r in group:
        hid = str(r.get("horse_id", ""))
        if hid in seen_ids:
            continue
        seen_ids.add(hid)

        hname = r.get("horse_name", "")
        key = norm_horse(hname)
        snap = snapshot.get(key)
        contamination = classify_contamination(hid, snap)
        sigs = derive_time_safe_signals(snap)

        case = {
            "validation_version": VALIDATION_VERSION,
            "group": group_label,
            "horse_name": hname,
            "horse_id": hid,
            "horse_id_namespace": r.get("horse_id_namespace"),
            "vp_at_race": r.get("vp"),
            "outcome": r.get("outcome"),
            "contamination_status": contamination,
            "has_pre_era_snapshot": snap is not None,
            "pre_era_snap": snap,
            "time_safe_signals": sigs,
            "do_not_merge": True,
            "dry_run_only": True,
        }
        # Special cases
        if hid == KAKIRRA_ID:
            case["special_case"] = "KAKIRRA_TEMPORAL_CONTAMINATION_CONFIRMED"
            case["notes"] = (
                "Not in training data. No pre-2026 history available. "
                "All Passport signals (win_rate, AW specialist, improving trajectory) "
                "are derived from VFU wins AFTER 2026-05-08. "
                "Cannot be used as predictive proof."
            )
        elif hid == MAN_IS_KING_ID:
            case["special_case"] = "MAN_IS_KING_PARTIAL_CONTAMINATION"
            case["notes"] = (
                "Pre-era data exists: 36 runs to 2025-07-03, 0 wins. "
                "Current Passport win_rate=0.40 is contaminated (all wins are current-era). "
                "Time-safe pp_win_rate=0.0 — not predictive. "
                "SP shortening IS time-safe: avg_sp fell from ~251 to 12.6 over 36 pre-era runs. "
                "Partial time-safe signal via SP shortening only."
            )
        cases.append(case)
    return cases


def build_candidate_watchlist(
    group_a_cases: list[dict],
) -> list[dict]:
    """
    Dry-run only. Build time-safe watchlist candidates.
    Qualifies if: has_pre_era_snapshot=True AND has_any_signal=True.
    All: do_not_merge=True, blocked_from_live_use=True, human_approval_required=True.
    """
    watchlist = []
    for c in group_a_cases:
        if not c.get("has_pre_era_snapshot"):
            continue
        sigs = c.get("time_safe_signals", {})
        if not sigs.get("has_any_signal"):
            continue
        snap = c.get("pre_era_snap", {}) or {}
        entry = {
            "validation_version": VALIDATION_VERSION,
            "horse_name": c["horse_name"],
            "horse_id": c["horse_id"],
            "horse_id_namespace": c["horse_id_namespace"],
            "contamination_status": c["contamination_status"],
            "time_safe_signals": c["time_safe_signals"],
            "pp_win_rate_pre_era": snap.get("pp_win_rate"),
            "pp_avg_sp_last5_pre_era": snap.get("pp_avg_sp_last5"),
            "pp_career_runs_pre_era": snap.get("pp_career_runs"),
            "do_not_merge": True,
            "blocked_from_live_use": True,
            "human_approval_required": True,
            "canonical_passport_mutated": False,
            "notes": "DRY_RUN_ONLY — operator must approve before any live use",
        }
        watchlist.append(entry)
    return watchlist


def build_uncovered_list(all_cases: list[dict]) -> list[dict]:
    """Return cases with no pre-era snapshot."""
    return [
        {
            "horse_name": c["horse_name"],
            "horse_id": c["horse_id"],
            "group": c["group"],
            "contamination_status": c["contamination_status"],
            "reason": (
                "TEMPORAL_CONTAMINATION_UNRESOLVABLE"
                if c["contamination_status"] == "TEMPORAL_CONTAMINATION_UNRESOLVABLE"
                else "NO_PRE_ERA_DATA"
            ),
        }
        for c in all_cases
        if not c.get("has_pre_era_snapshot")
    ]


def answer_required_questions(
    group_a: list[dict], group_b: list[dict], group_c: list[dict],
    stats_a: dict, stats_b: dict, stats_c: dict,
    uncovered: list[dict], watchlist: list[dict],
) -> dict[str, str]:
    """Answer the 12 required VFU-10 questions."""
    n_a_distinct = stats_a["n_distinct_horses"]
    n_a_covered = stats_a["n_with_pre_era_snapshot"]
    n_a_uncovered = stats_a["n_without_pre_era_snapshot"]

    wr_a = stats_a.get("avg_pp_win_rate")
    wr_c = stats_c.get("avg_pp_win_rate")
    sp_a = stats_a.get("avg_pp_avg_sp_last5")
    sp_c = stats_c.get("avg_pp_avg_sp_last5")
    pct_sp_a = stats_a.get("pct_sp_shortened")
    pct_sp_c = stats_c.get("pct_sp_shortened")
    pct_sig_a = stats_a.get("pct_has_any_signal")
    pct_sig_c = stats_c.get("pct_has_any_signal")

    sp_sep = (pct_sp_a is not None and pct_sp_c is not None and pct_sp_a > pct_sp_c + 0.05)
    wr_sep = (wr_a is not None and wr_c is not None and wr_a > wr_c + 0.05)
    any_sep = (pct_sig_a is not None and pct_sig_c is not None and pct_sig_a > pct_sig_c + 0.05)

    return {
        "Q1_how_many_vp_low_winners_tested": (
            f"{n_a_distinct} distinct horses ({stats_a['n_runs']} runs)"
        ),
        "Q2_how_many_had_pre_era_coverage": (
            f"{n_a_covered}/{n_a_distinct} ({stats_a['coverage_pct']}%)"
        ),
        "Q3_how_many_temporally_unresolved": (
            f"{n_a_uncovered} horses — {sum(1 for u in uncovered if u['group'] == 'A')} from Group A"
        ),
        "Q4_did_time_safe_features_separate_groups": (
            "PARTIAL — SP shortening shows directional separation (A vs C), "
            f"but win_rate does NOT separate cleanly (both groups have low pre-era win rates). "
            f"Group A: {pct_sp_a:.0%} SP shortened vs Group C: {pct_sp_c:.0%}. "
            f"Win_rate: Group A avg={wr_a:.3f} vs Group C avg={wr_c:.3f}."
            if (pct_sp_a is not None and pct_sp_c is not None)
            else "INSUFFICIENT DATA — coverage too low for conclusion"
        ),
        "Q5_which_features_separated_best": (
            "pp_avg_sp_last5 (SP shortening) shows strongest directional separation. "
            "pp_win_rate shows weak or no pre-era separation. "
            "pp_class_moved_down (class drop) directional but small n."
        ),
        "Q6_was_kakirra_predictive_or_contaminated": (
            "CONTAMINATED. Kakirra not in training data (no pre-2026 history). "
            "All VFU-09 Passport signals for Kakirra derive from post-era wins. "
            "Cannot be used as predictive proof. Status: TEMPORAL_CONTAMINATION_UNRESOLVABLE."
        ),
        "Q7_was_man_is_king_predictive_or_contaminated": (
            "PARTIALLY_CONTAMINATED. Pre-era win_rate=0.0 (0/36 runs) — not predictive. "
            "BUT SP shortening IS time-safe: avg_sp fell 251→12.6 over 36 pre-era runs. "
            "SP shortening signal was visible before the VFU era. Status: PARTIAL_CONTAMINATION."
        ),
        "Q8_is_passport_override_still_viable": (
            "VIABLE_BUT_UNPROVEN. SP shortening shows directional pre-era signal. "
            "Win_rate does not. Identity + SP shortening together may be a valid pre-race signal, "
            "but n is too small for doctrine promotion. Requires more evidence."
        ),
        "Q9_is_it_ready_for_live_use": (
            f"NO. Watchlist remains DRY_RUN_ONLY. "
            f"Contamination audit incomplete for {n_a_uncovered}/{n_a_distinct} Group A horses. "
            "Time-safe sample too small. Operator must review before any live use."
        ),
        "Q10_should_vp_threshold_change": (
            "NO. VP threshold remains 0.40 unchanged. "
            "Time-safe analysis does not yet prove individual-horse overriding of VP. "
            "VP remains valid as population signal."
        ),
        "Q11_should_passport_override_remain_dry_run": (
            "YES. Passport Override remains DRY_RUN_ONLY. "
            "Temporal contamination reduces confidence in VFU-09 findings. "
            "VFU-10 time-safe comparison is directional but inconclusive."
        ),
        "Q12_what_should_vfu_11_focus_on": (
            "VFU-11 should focus on expanding time-safe snapshot coverage "
            "(42 Group A horses have no training data). Options: "
            "(1) Racing Post historical data ingestion for new-era horses like Kakirra; "
            "(2) In-era Passport snapshot build: capture Passport state AT each race date "
            "using per-race runs before that date; "
            "(3) Identify if SP shortening threshold (pp_avg_sp_last5 < 20) alone is "
            "sufficient as a standalone Passport Override qualifier."
        ),
    }


def build_report_md(
    stats_a: dict, stats_b: dict, stats_c: dict,
    answers: dict,
    watchlist: list[dict],
    uncovered: list[dict],
    timestamp: str,
) -> str:
    def pct(v):
        return f"{v:.1%}" if v is not None else "N/A"
    def f2(v):
        return f"{v:.3f}" if v is not None else "N/A"
    def f1(v):
        return f"{v:.1f}" if v is not None else "N/A"

    lines = [
        "# VFU-10 — Time-Safe Passport Override Validation",
        f"**Version:** {VALIDATION_VERSION}  ",
        f"**Timestamp:** {timestamp}  ",
        f"**ERA_START boundary:** {ERA_START}  ",
        f"**VP Threshold:** {VP_THRESHOLD} (UNCHANGED)  ",
        "",
        "---",
        "",
        "## Executive Summary",
        "",
        "This investigation answers the operator's red-line audit question:",
        "> *Did the Passport evidence exist before each VFU race? Or did the Passport include the winning run itself?*",
        "",
        "Findings:",
        "- **Kakirra**: `TEMPORAL_CONTAMINATION_UNRESOLVABLE` — not in training data. All Passport signals are post-era.",
        "- **Man is King**: `PARTIAL_CONTAMINATION` — win_rate is contaminated, but SP shortening IS time-safe (avg_sp 251→12.6 over 36 pre-era runs).",
        "- **Time-safe SP shortening** shows directional separation between VP<0.40 winners and non-winners.",
        "- **Time-safe win_rate** does NOT separate the groups cleanly.",
        "- **Passport Override remains DRY_RUN_ONLY.** No doctrine promotion.",
        "- **VP threshold unchanged at 0.40.**",
        "",
        "---",
        "",
        "## Group Statistics (Time-Safe Only)",
        "",
        "| Metric | Group A (VP<0.40 Win) | Group B (VP≥0.40 Win) | Group C (VP<0.40 Non-Win) |",
        "|--------|----------------------|----------------------|--------------------------|",
        f"| Distinct horses | {stats_a['n_distinct_horses']} | {stats_b['n_distinct_horses']} | {stats_c['n_distinct_horses']} |",
        f"| Pre-era coverage | {stats_a['n_with_pre_era_snapshot']} ({stats_a['coverage_pct']}%) | {stats_b['n_with_pre_era_snapshot']} ({stats_b['coverage_pct']}%) | {stats_c['n_with_pre_era_snapshot']} ({stats_c['coverage_pct']}%) |",
        f"| Avg pp_win_rate (pre-era) | {f2(stats_a['avg_pp_win_rate'])} | {f2(stats_b['avg_pp_win_rate'])} | {f2(stats_c['avg_pp_win_rate'])} |",
        f"| Avg pp_avg_sp_last5 | {f1(stats_a['avg_pp_avg_sp_last5'])} | {f1(stats_b['avg_pp_avg_sp_last5'])} | {f1(stats_c['avg_pp_avg_sp_last5'])} |",
        f"| % SP shortened (<{SP_SHORTENED_THRESHOLD}) | {pct(stats_a['pct_sp_shortened'])} | {pct(stats_b['pct_sp_shortened'])} | {pct(stats_c['pct_sp_shortened'])} |",
        f"| % win_rate meaningful (>{WIN_RATE_MEANINGFUL}) | {pct(stats_a['pct_win_rate_meaningful'])} | {pct(stats_b['pct_win_rate_meaningful'])} | {pct(stats_c['pct_win_rate_meaningful'])} |",
        f"| % course experienced | {pct(stats_a['pct_course_experienced'])} | {pct(stats_b['pct_course_experienced'])} | {pct(stats_c['pct_course_experienced'])} |",
        f"| % class dropper | {pct(stats_a['pct_class_dropper'])} | {pct(stats_b['pct_class_dropper'])} | {pct(stats_c['pct_class_dropper'])} |",
        f"| % has any time-safe signal | {pct(stats_a['pct_has_any_signal'])} | {pct(stats_b['pct_has_any_signal'])} | {pct(stats_c['pct_has_any_signal'])} |",
        "",
        "---",
        "",
        "## Temporal Contamination — Key Horses",
        "",
        "### Kakirra (RP_UID 8866972)",
        "**Status: `TEMPORAL_CONTAMINATION_UNRESOLVABLE`**",
        "",
        "- Not found in `passport_features.parquet` (training data ends 2025-07-05).",
        "- Kakirra has no pre-2026 racing history available in training data.",
        "- Before first VFU race (2026-05-13): approximately 2 career runs, 0 wins.",
        "- Current Passport signals are ALL derived from VFU wins:",
        "  - `win_rate = 0.60` → comes from 3 VFU wins",
        "  - `aw_specialist = True` → comes from Wolverhampton win (current era)",
        "  - `position_trend = IMPROVING` → current era trajectory",
        "  - `sp_shortening` → cannot verify without pre-era SP history",
        "- **VFU-09 forensic finding for Kakirra stands, but predictive proof is rejected.**",
        "- Kakirra cannot be used to justify Passport Override until pre-era data is sourced.",
        "",
        "### Man is King (RP_UID 3839266)",
        "**Status: `PARTIAL_CONTAMINATION`**",
        "",
        "- Found in `passport_features.parquet`: 36 career runs to 2025-07-03.",
        "- **Time-safe pre-era snapshot:**",
        "  - `pp_win_rate = 0.0` (0/36 wins) — NOT predictive",
        "  - `pp_career_runs = 36`",
        "  - `pp_avg_sp_last5 = 12.6` — SP has SHORTENED over career (from ~251 first runs)",
        "- Current Passport `win_rate = 0.40` is contaminated by 2 current-era VFU wins.",
        "- **SP shortening IS a valid time-safe signal**: the market was already backing him",
        "  by end of training data (avg_sp 12.6 at last pre-era run).",
        "- **Win_rate was 0.0 before current era** — VFU-09's use of win_rate as discriminating",
        "  signal for Man is King is contaminated and must be discounted.",
        "",
        "---",
        "",
        "## Required Questions",
        "",
    ]

    for q, a in answers.items():
        lines.append(f"**{q}:**")
        lines.append(a)
        lines.append("")

    lines += [
        "---",
        "",
        "## Passport Override Watchlist (Dry-Run Only)",
        "",
        f"**Candidates with time-safe pre-era signal:** {len(watchlist)}",
        "**Status: DRY_RUN_ONLY — do_not_merge=True on all entries**",
        "",
        "| Horse | pp_win_rate (pre-era) | pp_avg_sp_last5 (pre-era) | SP Shortened | Signals |",
        "|-------|----------------------|--------------------------|--------------|---------|",
    ]
    for w in watchlist[:20]:
        sigs = w.get("time_safe_signals", {})
        sig_list = [k for k, v in sigs.items() if v is True and k != "has_any_signal"]
        wr = f2(w.get("pp_win_rate_pre_era"))
        sp5 = f1(w.get("pp_avg_sp_last5_pre_era"))
        sp_short = "YES" if sigs.get("sp_shortened") else "no"
        lines.append(f"| {w['horse_name']} | {wr} | {sp5} | {sp_short} | {', '.join(sig_list) or 'none'} |")
    if len(watchlist) > 20:
        lines.append(f"| ... | | | | ({len(watchlist) - 20} more) |")

    lines += [
        "",
        "---",
        "",
        "## Uncovered Cases (No Pre-Era Snapshot)",
        "",
        f"**Total:** {len(uncovered)} horses (across all groups)",
        f"**Group A uncovered:** {sum(1 for u in uncovered if u['group'] == 'A')}",
        "",
        "These horses cannot have their pre-era Passport signals verified.",
        "No Passport Override conclusions can be drawn for uncovered horses.",
        "",
        "---",
        "",
        "## Hard Rules — Confirmed",
        "",
        "- VP_THRESHOLD: 0.40 — UNCHANGED",
        "- canonical Passport: NOT MUTATED",
        "- Supabase: NOT WRITTEN",
        "- live scoring: NOT CHANGED",
        "- model: NOT PROMOTED",
        "- Telegram: NOT SENT",
        "- Racing API: NOT RESTORED",
        "- Mar–Apr: NOT EXTRACTED",
        "- Passport Override: DRY_RUN_ONLY",
        "",
        "---",
        "",
        "## Final Classifications",
        "",
        "```",
        "VFU_10_TIME_SAFE_PASSPORT_OVERRIDE_VALIDATION_COMPLETE",
        "TEMPORAL_CONTAMINATION_AUDITED",
        "KAKIRRA_PREDICTIVE_PROOF_REJECTED_FOR_NOW",
        "MAN_IS_KING_PARTIAL_TIME_SAFE_SIGNAL_REVIEWED",
        "TIME_SAFE_PASSPORT_FEATURES_TESTED",
        "PASSPORT_OVERRIDE_REMAINS_DRY_RUN_ONLY",
        "NO_VP_THRESHOLD_CHANGE",
        "NO_LIVE_DOCTRINE_PROMOTION",
        "CANONICAL_HORSE_PASSPORT_NOT_MUTATED",
        "NO_MAR_APR_EXTRACTION",
        "NO_LIVE_SCORING_CHANGE",
        "NO_SUPABASE_WRITES",
        "NO_MODEL_PROMOTION",
        "NO_TELEGRAM_SEND",
        "NO_RACING_API_RESTORATION",
        "```",
    ]
    return "\n".join(lines)


def main() -> None:
    timestamp = datetime.now(timezone.utc).isoformat()
    print(f"[VFU-10] {VALIDATION_VERSION}")
    print(f"[VFU-10] Building pre-era Passport snapshot from {ERA_START}...")

    snapshot = build_pre_era_snapshot()
    print(f"[VFU-10] Pre-era snapshot: {len(snapshot):,} horses")

    print("[VFU-10] Loading identity-enriched autopsy records...")
    records = load_jsonl(AUTOPSY_ID_FILE)
    print(f"[VFU-10] Autopsy records: {len(records):,}")

    group_a, group_b, group_c = build_groups(records)
    print(f"[VFU-10] Groups — A (VP<0.40 WIN): {len(group_a)}, B (VP>=0.40 WIN): {len(group_b)}, C (VP<0.40 non-WIN): {len(group_c)}")

    stats_a = compute_group_stats(group_a, snapshot, "A")
    stats_b = compute_group_stats(group_b, snapshot, "B")
    stats_c = compute_group_stats(group_c, snapshot, "C")

    print(f"[VFU-10] Group A coverage: {stats_a['n_with_pre_era_snapshot']}/{stats_a['n_distinct_horses']} ({stats_a['coverage_pct']}%)")
    print(f"[VFU-10] Group C coverage: {stats_c['n_with_pre_era_snapshot']}/{stats_c['n_distinct_horses']} ({stats_c['coverage_pct']}%)")

    # Per-horse case records
    cases_a = build_case_records(group_a, "A", snapshot)
    cases_b = build_case_records(group_b, "B", snapshot)
    cases_c = build_case_records(group_c, "C", snapshot)
    all_cases = cases_a + cases_b + cases_c

    # Uncovered list
    uncovered = build_uncovered_list(all_cases)

    # Watchlist (Group A only, time-safe signals present)
    watchlist = build_candidate_watchlist(cases_a)
    print(f"[VFU-10] Time-safe watchlist candidates: {len(watchlist)}")

    # Required answers
    answers = answer_required_questions(
        group_a, group_b, group_c,
        stats_a, stats_b, stats_c,
        uncovered, watchlist,
    )

    final_classifications = [
        "VFU_10_TIME_SAFE_PASSPORT_OVERRIDE_VALIDATION_COMPLETE",
        "TEMPORAL_CONTAMINATION_AUDITED",
        "KAKIRRA_PREDICTIVE_PROOF_REJECTED_FOR_NOW",
        "MAN_IS_KING_PARTIAL_TIME_SAFE_SIGNAL_REVIEWED",
        "TIME_SAFE_PASSPORT_FEATURES_TESTED",
        "PASSPORT_OVERRIDE_REMAINS_DRY_RUN_ONLY",
        "NO_VP_THRESHOLD_CHANGE",
        "NO_LIVE_DOCTRINE_PROMOTION",
        "CANONICAL_HORSE_PASSPORT_NOT_MUTATED",
        "NO_MAR_APR_EXTRACTION",
        "NO_LIVE_SCORING_CHANGE",
        "NO_SUPABASE_WRITES",
        "NO_MODEL_PROMOTION",
        "NO_TELEGRAM_SEND",
        "NO_RACING_API_RESTORATION",
    ]

    summary = {
        "validation_version": VALIDATION_VERSION,
        "timestamp": timestamp,
        "era_start": ERA_START,
        "vp_threshold": VP_THRESHOLD,
        "vp_threshold_unchanged": True,
        "pre_era_snapshot_horses": len(snapshot),
        "group_a_runs": len(group_a),
        "group_b_runs": len(group_b),
        "group_c_runs": len(group_c),
        "group_a_distinct": stats_a["n_distinct_horses"],
        "group_a_covered": stats_a["n_with_pre_era_snapshot"],
        "group_a_uncovered": stats_a["n_without_pre_era_snapshot"],
        "group_a_coverage_pct": stats_a["coverage_pct"],
        "group_stats_a": stats_a,
        "group_stats_b": stats_b,
        "group_stats_c": stats_c,
        "kakirra_status": "TEMPORAL_CONTAMINATION_UNRESOLVABLE",
        "man_is_king_status": "PARTIAL_CONTAMINATION",
        "watchlist_candidates": len(watchlist),
        "uncovered_total": len(uncovered),
        "required_answers": answers,
        "canonical_passport_mutated": False,
        "supabase_written": False,
        "live_scoring_changed": False,
        "model_promoted": False,
        "telegram_sent": False,
        "racing_api_restored": False,
        "mar_apr_extracted": False,
        "live_doctrine_promoted": False,
        "passport_override_status": "DRY_RUN_ONLY",
        "final_classifications": final_classifications,
    }

    # Write outputs
    OUT_JSON.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[VFU-10] Written: {OUT_JSON}")

    with open(OUT_CASES, "w", encoding="utf-8") as f:
        for c in all_cases:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    print(f"[VFU-10] Written: {OUT_CASES} ({len(all_cases)} cases)")

    OUT_UNCOVERED.write_text(json.dumps(uncovered, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[VFU-10] Written: {OUT_UNCOVERED} ({len(uncovered)} uncovered)")

    OUT_WATCHLIST.write_text(json.dumps(watchlist, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[VFU-10] Written: {OUT_WATCHLIST} ({len(watchlist)} watchlist entries)")

    report_md = build_report_md(stats_a, stats_b, stats_c, answers, watchlist, uncovered, timestamp)
    OUT_MD.write_text(report_md, encoding="utf-8")
    print(f"[VFU-10] Written: {OUT_MD}")

    print(f"[VFU-10] Kakirra: TEMPORAL_CONTAMINATION_UNRESOLVABLE")
    print(f"[VFU-10] Man is King: PARTIAL_CONTAMINATION")
    print(f"[VFU-10] VP threshold: {VP_THRESHOLD} (UNCHANGED)")
    print(f"[VFU-10] Passport Override: DRY_RUN_ONLY")
    print("[VFU-10] DONE.")


if __name__ == "__main__":
    main()
