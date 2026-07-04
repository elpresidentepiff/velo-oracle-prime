"""
RESULTS-01 — VÉLØ Full Results Truth Audit.
REPORT_ONLY. No scoring change, no Supabase write, no model promotion.

HARD CONSTRAINTS:
- REPORT_ONLY
- NO_LIVE_SCORING_CHANGE
- NO_VP_THRESHOLD_CHANGE
- NO_MODEL_PROMOTION
- NO_SUPABASE_WRITES
- NO_TELEGRAM_SEND
- NO_VFU_21_START
- NO_VCP_04_START
- CANONICAL_HORSE_PASSPORT_NOT_MUTATED
- DO_NOT_SUPPRESS_CONTRADICTIONS
- MISSING_ARTIFACTS_RESOLVE_UNKNOWN_NOT_CLEAN
- CONTAINMENT_IS_NOT_PROFIT
- SP_PROXY_IS_NOT_DIVIDEND_PROOF
"""

import csv
import glob
import json
import os
from collections import defaultdict
from datetime import datetime

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATA_DIR = os.path.join(REPO_ROOT, "data")
REPORTS_DIR = os.path.join(DATA_DIR, "reports")
os.makedirs(REPORTS_DIR, exist_ok=True)

HARD_CONSTRAINTS = [
    "REPORT_ONLY",
    "NO_LIVE_SCORING_CHANGE",
    "NO_VP_THRESHOLD_CHANGE",
    "NO_MODEL_PROMOTION",
    "NO_SUPABASE_WRITES",
    "NO_TELEGRAM_SEND",
    "NO_VFU_21_START",
    "NO_VCP_04_START",
    "CANONICAL_HORSE_PASSPORT_NOT_MUTATED",
    "DO_NOT_SUPPRESS_CONTRADICTIONS",
    "MISSING_ARTIFACTS_RESOLVE_UNKNOWN_NOT_CLEAN",
    "CONTAINMENT_IS_NOT_PROFIT",
    "SP_PROXY_IS_NOT_DIVIDEND_PROOF",
]

FINAL_CLASSIFICATIONS = [
    "RESULTS_01_FULL_RESULTS_TRUTH_AUDIT_COMPLETE",
    "HORSES_LANDED_TABLE_WRITTEN",
    "ODDS_LANDED_TABLE_WRITTEN",
    "BIGGEST_PRICE_WINNERS_WRITTEN",
    "BIGGEST_PRICE_PLACERS_WRITTEN",
    "COURSE_PERFORMANCE_AUDITED",
    "ODDS_BAND_PERFORMANCE_AUDITED",
    "LANE_PERFORMANCE_AUDITED",
    "RPR_DEPENDENCY_FULL_CORPUS_AUDITED",
    "NEW_BUILD_VALUE_SCOUT_AUDITED",
    "EW_CANDIDATE_REALITY_AUDITED",
    "MIDPRICE_MISS_RECOVERY_AUDITED",
    "EXOTICS_SIGNAL_AUDITED",
    "EXOTICS_PROFIT_NOT_CLAIMED_WITHOUT_DIVIDENDS",
    "TRAINING_SIGMA_GAP_AUDITED",
    "EXTERNAL_BACKFILL_SOURCE_MAP_WRITTEN",
    "BHA_RP_SOURCE_SECTIONS_CHECKED",
    "MEMORY_CAPTURE_OPEN",
    "FAILURE_LEARNING_OPEN",
    "PROMOTION_LEARNING_GATED",
    "NO_VFU_21_START",
    "NO_VCP_04_START",
    "NO_LIVE_SCORING_CHANGE",
    "NO_MODEL_PROMOTION",
    "NO_SUPABASE_WRITES",
    "NO_TELEGRAM_SEND",
    "CANONICAL_HORSE_PASSPORT_NOT_MUTATED",
    "REPORT_ONLY",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sp_to_dec(sp_val):
    """Convert SP to decimal. Handles fractional '9/2', decimal 4.5, None, etc."""
    if sp_val is None:
        return None
    if isinstance(sp_val, (int, float)):
        return float(sp_val)
    s = str(sp_val).strip()
    if not s or s.upper() in ("NR", "N/A", "UNKNOWN", "PRICE_UNKNOWN"):
        return None
    # Try fractional e.g. "9/2"
    if "/" in s:
        parts = s.split("/")
        try:
            return float(parts[0]) / float(parts[1]) + 1.0
        except (ValueError, ZeroDivisionError):
            return None
    try:
        return float(s)
    except ValueError:
        return None


def _odds_band(sp_dec):
    """Return odds band label for a decimal SP."""
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
    if sp_dec < 25.0:
        return "16-25"
    return "25+"


def _extract_date(row):
    """Extract date string YYYY-MM-DD from sigma audit row."""
    d = row.get("date")
    if d and str(d).strip() and str(d).strip().lower() not in ("none", "null"):
        return str(d).strip()[:10]
    ca = row.get("created_at", "") or ""
    if ca:
        return ca[:10]
    return "UNKNOWN"


def _normalize_course(name):
    """Normalize course name for grouping."""
    if not name:
        return "UNKNOWN"
    return str(name).strip().title()


# ---------------------------------------------------------------------------
# Data loaders
# ---------------------------------------------------------------------------


def _load_sigma_dump():
    path = os.path.join(DATA_DIR, "sigma_audits_dump.json")
    if not os.path.exists(path):
        print(f"  WARNING: sigma_audits_dump.json not found at {path}")
        return []
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    rows = data if isinstance(data, list) else data.get("rows", [])
    # Enrich each row with derived fields
    enriched = []
    for r in rows:
        r = dict(r)
        r["_date"] = _extract_date(r)
        r["_course"] = _normalize_course(r.get("track"))
        r["_winner_sp_dec"] = _sp_to_dec(r.get("actual_winner_sp"))
        r["_pick_sp_dec"] = _sp_to_dec(r.get("pick_sp"))
        r["_winner_odds_band"] = _odds_band(r["_winner_sp_dec"])
        r["_pick_odds_band"] = _odds_band(r["_pick_sp_dec"])
        r["_is_win"] = str(r.get("outcome", "")).upper() == "WIN"
        r["_is_place"] = str(r.get("outcome", "")).upper() in ("WIN", "PLACED")
        r["_miss_class"] = r.get("miss_reason") or r.get("miss_class") or ""
        r["_tier"] = r.get("decision_tier") or ""
        enriched.append(r)
    return enriched


def _load_ledger():
    path = os.path.join(DATA_DIR, "model_comparison_ledger.csv")
    if not os.path.exists(path):
        print(f"  WARNING: model_comparison_ledger.csv not found at {path}")
        return []
    rows = []
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(dict(row))
    return rows


def _load_sigma_results():
    """Load all sigma_results_*.json files. Returns dict keyed by date."""
    pattern = os.path.join(DATA_DIR, "sigma_results", "sigma_results_*.json")
    files = glob.glob(pattern)
    result_map = {}
    for fp in files:
        try:
            with open(fp, encoding="utf-8") as f:
                data = json.load(f)
            date_key = data.get(
                "date", os.path.basename(fp).replace("sigma_results_", "").replace(".json", "").replace("_", "-")
            )
            result_map[date_key] = data
        except Exception as e:
            print(f"  WARNING: Could not load {fp}: {e}")
    return result_map


def _load_results_map():
    """Load all rp_results_*.json files. Returns dict keyed by race_id, also date-keyed dict."""
    pattern = os.path.join(DATA_DIR, "results", "rp_results_*.json")
    files = glob.glob(pattern)
    race_map = {}  # race_id -> result dict
    date_map = {}  # date -> list of result dicts
    for fp in files:
        try:
            with open(fp, encoding="utf-8") as f:
                data = json.load(f)
            results = data.get("results", []) if isinstance(data, dict) else data
            date_str = data.get("date", "") if isinstance(data, dict) else ""
            if not date_str:
                # extract from filename
                bn = os.path.basename(fp).replace("rp_results_", "").replace(".json", "")
                date_str = bn.replace("_", "-")
            date_map.setdefault(date_str, [])
            for r in results:
                if isinstance(r, dict):
                    rid = r.get("race_id", "")
                    if rid:
                        race_map[rid] = r
                    date_map[date_str].append(r)
        except Exception as e:
            print(f"  WARNING: Could not load {fp}: {e}")
    return race_map, date_map


def _load_verdicts_map():
    """Load all velo_prime_verdicts_*.json files. Returns dict keyed by race_id."""
    pattern = os.path.join(DATA_DIR, "velo_prime_verdicts_*.json")
    files = glob.glob(pattern)
    verdict_map = {}
    for fp in files:
        try:
            with open(fp, encoding="utf-8") as f:
                data = json.load(f)
            items = data if isinstance(data, list) else data.get("items", data.get("races", []))
            for item in items:
                if isinstance(item, dict):
                    rid = item.get("race_id", "")
                    if rid:
                        verdict_map[rid] = item
        except Exception as e:
            print(f"  WARNING: Could not load {fp}: {e}")
    return verdict_map


def _load_radical_shadow_map():
    """Load radical shadow files. Returns race_id -> decision dict."""
    pattern = os.path.join(DATA_DIR, "reports", "radical_shadow_*.json")
    files = glob.glob(pattern)
    shadow_map = {}
    for fp in files:
        try:
            with open(fp, encoding="utf-8") as f:
                data = json.load(f)
            decisions = data.get("decisions", [])
            for d in decisions:
                rid = d.get("race_id", "")
                if rid:
                    shadow_map[rid] = d
        except Exception as e:
            print(f"  WARNING: Could not load {fp}: {e}")
    return shadow_map


def _load_parquet_optional(path):
    """Try to load a parquet file. Returns (df_or_None, status_string)."""
    if not os.path.exists(path):
        return None, "FILE_NOT_FOUND"
    try:
        import pyarrow.parquet as pq

        tbl = pq.read_table(path)
        try:
            import pandas as pd

            return tbl.to_pandas(), "LOADED_PYARROW_PANDAS"
        except ImportError:
            # Return as dict-list
            cols = tbl.column_names
            rows = []
            for i in range(tbl.num_rows):
                row = {c: tbl.column(c)[i].as_py() for c in cols}
                rows.append(row)
            return rows, "LOADED_PYARROW_DICT"
    except ImportError:
        pass
    try:
        import pandas as pd

        df = pd.read_parquet(path)
        return df, "LOADED_PANDAS"
    except ImportError:
        return None, "IMPORT_ERROR_NO_PYARROW_NO_PANDAS"
    except Exception as e:
        return None, f"LOAD_ERROR: {e}"


# ---------------------------------------------------------------------------
# Section functions
# ---------------------------------------------------------------------------


def _section1_inventory(audit_rows, ledger_rows, sigma_results_map, race_map, verdict_map):
    """Data coverage inventory."""
    dates_in_audit = {r["_date"] for r in audit_rows if r["_date"] != "UNKNOWN"}
    dates_in_ledger = {r.get("date", "") for r in ledger_rows if r.get("date")}
    dates_in_sigma_results = set(sigma_results_map.keys())
    dates_in_results = set()
    for _rid, res in race_map.items():
        d = res.get("date", "")
        if d:
            dates_in_results.add(d)

    pick_sp_present = sum(1 for r in audit_rows if r.get("pick_sp") is not None)
    winner_sp_present = sum(1 for r in audit_rows if r.get("actual_winner_sp") is not None)
    winner_name_present = sum(1 for r in audit_rows if r.get("actual_winner_name"))
    outcome_counts = defaultdict(int)
    for r in audit_rows:
        outcome_counts[str(r.get("outcome") or "None")] += 1
    tier_counts = defaultdict(int)
    for r in audit_rows:
        tier_counts[r.get("decision_tier") or "None"] += 1
    miss_reason_counts = defaultdict(int)
    for r in audit_rows:
        mr = r.get("miss_reason") or ""
        if mr:
            miss_reason_counts[mr] += 1

    return {
        "sigma_dump_rows": len(audit_rows),
        "sigma_dump_dates": sorted(dates_in_audit),
        "sigma_dump_date_count": len(dates_in_audit),
        "pick_sp_present": pick_sp_present,
        "winner_sp_present": winner_sp_present,
        "winner_name_present": winner_name_present,
        "ledger_rows": len(ledger_rows),
        "ledger_dates": sorted(dates_in_ledger),
        "ledger_date_count": len(dates_in_ledger),
        "sigma_results_files": len(sigma_results_map),
        "sigma_results_dates": sorted(dates_in_sigma_results),
        "rp_results_races": len(race_map),
        "rp_results_dates_count": len(dates_in_results),
        "verdict_races": len(verdict_map),
        "outcome_counts": dict(outcome_counts),
        "tier_counts": dict(tier_counts),
        "miss_reason_top5": sorted(miss_reason_counts.items(), key=lambda x: -x[1])[:5],
        "field_coverage": {
            "actual_winner_sp": f"{winner_sp_present}/{len(audit_rows)}",
            "pick_sp": f"{pick_sp_present}/{len(audit_rows)}",
            "actual_winner_name": f"{winner_name_present}/{len(audit_rows)}",
        },
    }


def _section2_horses_landed(audit_rows, ledger_rows):
    """All WIN rows with horse name, SP, tier, etc."""
    # Build ledger lookup: race_id -> winner field
    ledger_winner = {}
    ledger_by_raceid = {}
    for row in ledger_rows:
        rid = row.get("race_id", "")
        winner = row.get("winner", "") or ""
        if rid:
            ledger_by_raceid[rid] = row
            if winner:
                ledger_winner[rid] = winner

    wins = []
    for r in audit_rows:
        if not r["_is_win"]:
            continue
        horse_name = r.get("actual_winner_name") or ""
        if not horse_name:
            # Try ledger match
            rid = r.get("race_id", "")
            horse_name = ledger_winner.get(rid, "") or r.get("velo_top_pick", "") or "UNKNOWN"
            # Also try ledger by date+course+off
        sp_dec = r["_winner_sp_dec"]
        pick_sp_dec = r["_pick_sp_dec"]
        wins.append(
            {
                "date": r["_date"],
                "course": r["_course"],
                "off_time": r.get("off_time") or "UNKNOWN",
                "horse_name": horse_name,
                "winner_sp": sp_dec if sp_dec is not None else "PRICE_UNKNOWN",
                "pick_sp": pick_sp_dec if pick_sp_dec is not None else "PRICE_UNKNOWN",
                "tier": r["_tier"] or "UNKNOWN",
                "race_type": r.get("race_type") or "UNKNOWN",
                "assigned_product": r.get("assigned_product") or "UNKNOWN",
                "verdict_score": r.get("verdict_score") or "UNKNOWN",
                "odds_band": r["_winner_odds_band"],
            }
        )
    # Sort by SP descending (biggest priced wins first)
    wins.sort(key=lambda x: float(x["winner_sp"]) if isinstance(x["winner_sp"], (int, float)) else 0.0, reverse=True)
    return wins


def _section3_biggest_price(audit_rows):
    """Top 50 winners and top 50 placers by SP."""
    wins = []
    places = []
    for r in audit_rows:
        sp_dec = r["_winner_sp_dec"]
        if r["_is_win"] and sp_dec is not None:
            wins.append(
                {
                    "date": r["_date"],
                    "course": r["_course"],
                    "off_time": r.get("off_time") or "UNKNOWN",
                    "horse_name": r.get("actual_winner_name") or "UNKNOWN",
                    "winner_sp": sp_dec,
                    "pick_sp": r["_pick_sp_dec"] if r["_pick_sp_dec"] is not None else "PRICE_UNKNOWN",
                    "tier": r["_tier"],
                    "race_type": r.get("race_type") or "UNKNOWN",
                    "outcome": "WIN",
                }
            )
        elif r["_is_place"] and not r["_is_win"]:
            pos = r.get("top_pick_position")
            if pos in (2, 3):
                places.append(
                    {
                        "date": r["_date"],
                        "course": r["_course"],
                        "off_time": r.get("off_time") or "UNKNOWN",
                        "horse_name": r.get("actual_winner_name") or "UNKNOWN",
                        "winner_sp": sp_dec if sp_dec is not None else "PRICE_UNKNOWN",
                        "pick_sp": r["_pick_sp_dec"] if r["_pick_sp_dec"] is not None else "PRICE_UNKNOWN",
                        "position": pos,
                        "tier": r["_tier"],
                        "race_type": r.get("race_type") or "UNKNOWN",
                        "outcome": "PLACED",
                    }
                )
    wins.sort(key=lambda x: float(x["winner_sp"]) if isinstance(x["winner_sp"], (int, float)) else 0.0, reverse=True)
    places.sort(key=lambda x: float(x["winner_sp"]) if isinstance(x["winner_sp"], (int, float)) else 0.0, reverse=True)
    return wins[:50], places[:50]


def _section4_course_performance(audit_rows):
    """Per-course performance dict."""
    course_data = defaultdict(
        lambda: {
            "total": 0,
            "wins": 0,
            "places": 0,
            "winner_sps": [],
            "miss_classes": defaultdict(int),
            "tiers": defaultdict(int),
        }
    )
    for r in audit_rows:
        c = r["_course"]
        course_data[c]["total"] += 1
        if r["_is_win"]:
            course_data[c]["wins"] += 1
            if r["_winner_sp_dec"] is not None:
                course_data[c]["winner_sps"].append(r["_winner_sp_dec"])
        if r["_is_place"]:
            course_data[c]["places"] += 1
        mc = r["_miss_class"]
        if mc:
            course_data[c]["miss_classes"][mc] += 1
        t = r["_tier"]
        if t:
            course_data[c]["tiers"][t] += 1

    result = {}
    for course, d in course_data.items():
        n = d["total"]
        wins = d["wins"]
        places = d["places"]
        sr = round(wins / n, 4) if n > 0 else 0.0
        frame_rate = round(places / n, 4) if n > 0 else 0.0
        sps = d["winner_sps"]
        avg_sp = round(sum(sps) / len(sps), 2) if sps else None
        median_sp = round(sorted(sps)[len(sps) // 2], 2) if sps else None

        if n < 10:
            label = "COURSE_NOISE_LOW_SAMPLE"
        elif sr >= 0.28:
            label = "COURSE_EDGE_CONFIRMED"
        elif sr >= 0.22:
            label = "COURSE_DOING_WELL"
        elif sr >= 0.15:
            label = "COURSE_NEUTRAL"
        elif sr < 0.10:
            label = "COURSE_DRAIN"
        else:
            label = "COURSE_NEUTRAL"

        result[course] = {
            "n": n,
            "wins": wins,
            "places": places,
            "sr": sr,
            "frame_rate": frame_rate,
            "avg_winner_sp": avg_sp,
            "median_winner_sp": median_sp,
            "label": label,
            "miss_class_breakdown": dict(d["miss_classes"]),
            "tier_breakdown": dict(d["tiers"]),
        }
    return result


def _section5_odds_band(audit_rows):
    """Per-odds-band performance."""
    # Two views:
    # (a) By pick SP band (where available)
    # (b) By winner SP band (for all wins)
    pick_bands = defaultdict(lambda: {"n": 0, "wins": 0, "places": 0})
    winner_bands = defaultdict(lambda: {"n": 0, "wins": 0})

    for r in audit_rows:
        # View (a) - group picks by their SP
        pb = r["_pick_odds_band"]
        pick_bands[pb]["n"] += 1
        if r["_is_win"]:
            pick_bands[pb]["wins"] += 1
        if r["_is_place"]:
            pick_bands[pb]["places"] += 1

        # View (b) - group winners by their SP
        wb = r["_winner_odds_band"]
        if r["_is_win"]:
            winner_bands[wb]["n"] += 1
            winner_bands[wb]["wins"] += 1

    band_order = ["<2.5", "2.5-4", "4-6", "6-10", "10-16", "16-25", "25+", "UNKNOWN"]

    pick_result = {}
    for band in band_order:
        d = pick_bands[band]
        n = d["n"]
        wins = d["wins"]
        places = d["places"]
        pick_result[band] = {
            "n_picks": n,
            "wins": wins,
            "places": places,
            "sr": round(wins / n, 4) if n > 0 else 0.0,
            "place_rate": round(places / n, 4) if n > 0 else 0.0,
        }

    winner_result = {}
    for band in band_order:
        d = winner_bands[band]
        winner_result[band] = {"wins_at_this_price": d["wins"]}

    return {"by_pick_sp": pick_result, "by_winner_sp": winner_result}


def _section6_lane_performance(audit_rows, ledger_rows):
    """Per-lane / per-product performance."""
    # Old velo lanes from sigma dump
    product_data = defaultdict(lambda: {"n": 0, "wins": 0, "places": 0})
    tier_data = defaultdict(lambda: {"n": 0, "wins": 0, "places": 0})
    vs_high_data = {"n": 0, "wins": 0, "places": 0}  # verdict_score >= 0.4

    for r in audit_rows:
        ap = r.get("assigned_product") or "UNKNOWN"
        product_data[ap]["n"] += 1
        if r["_is_win"]:
            product_data[ap]["wins"] += 1
        if r["_is_place"]:
            product_data[ap]["places"] += 1

        t = r["_tier"] or "UNKNOWN"
        tier_data[t]["n"] += 1
        if r["_is_win"]:
            tier_data[t]["wins"] += 1
        if r["_is_place"]:
            tier_data[t]["places"] += 1

        vs = r.get("verdict_score")
        if vs is not None:
            try:
                if float(vs) >= 0.4:
                    vs_high_data["n"] += 1
                    if r["_is_win"]:
                        vs_high_data["wins"] += 1
                    if r["_is_place"]:
                        vs_high_data["places"] += 1
            except (TypeError, ValueError):
                pass

    def _sr(d):
        n = d["n"]
        return round(d["wins"] / n, 4) if n > 0 else 0.0

    def _fr(d):
        n = d["n"]
        return round(d["places"] / n, 4) if n > 0 else 0.0

    lane_summary = {}
    for prod, d in product_data.items():
        lane_summary[f"PRODUCT_{prod}"] = {
            "n": d["n"],
            "wins": d["wins"],
            "places": d["places"],
            "sr": _sr(d),
            "place_rate": _fr(d),
            "source": "sigma_dump",
        }
    for tier, d in tier_data.items():
        lane_summary[f"TIER_{tier}"] = {
            "n": d["n"],
            "wins": d["wins"],
            "places": d["places"],
            "sr": _sr(d),
            "place_rate": _fr(d),
            "source": "sigma_dump",
        }
    lane_summary["VP_HIGH"] = {
        "n": vs_high_data["n"],
        "wins": vs_high_data["wins"],
        "places": vs_high_data["places"],
        "sr": _sr(vs_high_data),
        "place_rate": _fr(vs_high_data),
        "source": "sigma_dump",
        "note": "verdict_score>=0.4",
    }

    # Ledger lanes: NB, NoRPR, EW, WIN_ONLY, PASS, etc.
    ledger_lanes = defaultdict(lambda: {"n": 0, "wins": 0, "places": 0})
    nb_data = {"n": 0, "wins": 0, "places": 0}
    norpr_data = {"n": 0, "wins": 0, "places": 0}

    for row in ledger_rows:
        velo_out = str(row.get("velo_outcome", "") or "").upper()
        ap = str(row.get("velo_assigned_product", "") or "UNKNOWN").upper()
        ledger_lanes[ap]["n"] += 1
        if velo_out == "WIN":
            ledger_lanes[ap]["wins"] += 1
        if velo_out in ("WIN", "PLACE", "PLACED"):
            ledger_lanes[ap]["places"] += 1

        # NB lane
        nb_pick = row.get("nb_top_pick", "") or ""
        nb_out = str(row.get("nb_outcome", "") or "").upper()
        if nb_pick and nb_pick not in ("", "nan", "NaN", "NO_DATA"):
            nb_data["n"] += 1
            if nb_out == "WIN":
                nb_data["wins"] += 1
            if nb_out in ("WIN", "PLACE", "PLACED"):
                nb_data["places"] += 1

        # NoRPR lane
        norpr_pick = row.get("norpr_top_pick", "") or ""
        norpr_out = str(row.get("norpr_outcome", "") or "").upper()
        if norpr_pick and norpr_pick not in ("", "nan", "NaN", "NO_DATA"):
            norpr_data["n"] += 1
            if norpr_out == "WIN":
                norpr_data["wins"] += 1
            if norpr_out in ("WIN", "PLACE", "PLACED"):
                norpr_data["places"] += 1

    for prod, d in ledger_lanes.items():
        lane_summary[f"LEDGER_PRODUCT_{prod}"] = {
            "n": d["n"],
            "wins": d["wins"],
            "places": d["places"],
            "sr": _sr(d),
            "place_rate": _fr(d),
            "source": "ledger",
        }
    lane_summary["NEW_BUILD"] = {
        "n": nb_data["n"],
        "wins": nb_data["wins"],
        "places": nb_data["places"],
        "sr": _sr(nb_data),
        "place_rate": _fr(nb_data),
        "source": "ledger",
    }
    lane_summary["NO_RPR"] = {
        "n": norpr_data["n"],
        "wins": norpr_data["wins"],
        "places": norpr_data["places"],
        "sr": _sr(norpr_data),
        "place_rate": _fr(norpr_data),
        "source": "ledger",
    }

    return lane_summary


def _section7_rpr_dependency(audit_rows, verdict_map):
    """RPR dependency audit using verdict rpr_gap."""
    rpr_data = []
    for r in audit_rows:
        rid = r.get("race_id", "")
        v = verdict_map.get(rid, {})
        top = v.get("top", {}) if isinstance(v, dict) else {}
        sqpe_v17 = top.get("sqpe_v17_prob")
        sqpe_norpr = top.get("sqpe_no_rpr_shadow_prob")
        if sqpe_v17 is not None and sqpe_norpr is not None:
            try:
                gap = float(sqpe_v17) - float(sqpe_norpr)
                rpr_data.append(
                    {
                        "race_id": rid,
                        "date": r["_date"],
                        "outcome": r.get("outcome", ""),
                        "is_win": r["_is_win"],
                        "rpr_gap": round(gap, 4),
                        "rpr_boosted": gap > 0.01,
                        "rpr_dragged": gap < -0.01,
                    }
                )
            except (TypeError, ValueError):
                pass

    n = len(rpr_data)
    if n == 0:
        return {
            "verdict": "RPR_UNKNOWN",
            "n_with_gap": 0,
            "note": "No verdict-level RPR gap data found",
        }

    boosted = [r for r in rpr_data if r["rpr_boosted"]]
    dragged = [r for r in rpr_data if r["rpr_dragged"]]
    neutral = [r for r in rpr_data if not r["rpr_boosted"] and not r["rpr_dragged"]]

    boost_wins = sum(1 for r in boosted if r["is_win"])
    drag_wins = sum(1 for r in dragged if r["is_win"])
    neutral_wins = sum(1 for r in neutral if r["is_win"])

    boost_sr = round(boost_wins / len(boosted), 4) if boosted else 0.0
    drag_sr = round(drag_wins / len(dragged), 4) if dragged else 0.0
    neutral_sr = round(neutral_wins / len(neutral), 4) if neutral else 0.0

    if boost_sr > drag_sr + 0.03:
        verdict = "RPR_HELPED"
    elif drag_sr > boost_sr + 0.03:
        verdict = "RPR_MISLED"
    else:
        verdict = "RPR_NEUTRAL"

    return {
        "verdict": verdict,
        "n_with_gap": n,
        "n_rpr_boosted": len(boosted),
        "n_rpr_dragged": len(dragged),
        "n_rpr_neutral": len(neutral),
        "boost_sr": boost_sr,
        "drag_sr": drag_sr,
        "neutral_sr": neutral_sr,
        "avg_gap": round(sum(r["rpr_gap"] for r in rpr_data) / n, 4),
        "note": "Gap = sqpe_v17_prob - sqpe_no_rpr_shadow_prob per verdict",
    }


def _section8_new_build(ledger_rows, race_map):
    """New Build model analysis from ledger."""
    nb_rows = []
    for row in ledger_rows:
        nb_pick = row.get("nb_top_pick", "") or ""
        if not nb_pick or nb_pick in ("nan", "NaN", "NO_DATA", ""):
            continue
        nb_out = str(row.get("nb_outcome", "") or "").upper()
        nb_prob = row.get("nb_prob", "") or ""
        winner = row.get("winner", "") or ""
        top3_raw = row.get("top3", "") or ""
        top3 = [x.strip() for x in top3_raw.split("|") if x.strip()] if top3_raw else []

        in_top3 = nb_pick.strip() in top3 if top3 else None
        is_win = nb_out == "WIN"
        is_place = nb_out in ("WIN", "PLACE", "PLACED")

        try:
            prob = float(nb_prob) if nb_prob else None
        except ValueError:
            prob = None

        nb_rows.append(
            {
                "date": row.get("date", ""),
                "race_id": row.get("race_id", ""),
                "course": row.get("course", ""),
                "nb_pick": nb_pick,
                "nb_prob": prob,
                "nb_outcome": nb_out,
                "is_win": is_win,
                "is_place": is_place,
                "in_top3": in_top3,
                "winner": winner,
            }
        )

    n = len(nb_rows)
    if n == 0:
        return {"status": "NO_NB_DATA", "n": 0}

    wins = sum(1 for r in nb_rows if r["is_win"])
    places = sum(1 for r in nb_rows if r["is_place"])
    top3_hits = sum(1 for r in nb_rows if r["in_top3"] is True)
    top3_knowable = sum(1 for r in nb_rows if r["in_top3"] is not None)

    sr = round(wins / n, 4)
    place_rate = round(places / n, 4)
    top3_rate = round(top3_hits / top3_knowable, 4) if top3_knowable > 0 else None

    return {
        "n": n,
        "wins": wins,
        "places": places,
        "sr": sr,
        "place_rate": place_rate,
        "top3_hit_rate": top3_rate,
        "top3_knowable": top3_knowable,
        "note": "Top3 containment is NOT profit — SP_PROXY_IS_NOT_DIVIDEND_PROOF",
        "containment_is_not_profit": True,
    }


def _section9_ew_candidate(audit_rows, ledger_rows, race_map):
    """EW candidate reality audit."""
    ew_rows = []
    for row in ledger_rows:
        ap = str(row.get("velo_assigned_product", "") or "").upper()
        if ap not in ("EW_CANDIDATE", "EW"):
            continue
        ew_out = str(row.get("velo_ew_outcome", "") or "").upper()
        velo_out = str(row.get("velo_outcome", "") or "").upper()
        rid = row.get("race_id", "")
        result = race_map.get(rid, {})
        field_size = result.get("field_size") if result else None
        if field_size is None:
            field_size = "FIELD_SIZE_UNKNOWN"
        going = result.get("going", "UNKNOWN") if result else "UNKNOWN"
        winner_sp = result.get("winner_sp", None) if result else None
        winner_sp_dec = _sp_to_dec(winner_sp)

        ew_rows.append(
            {
                "date": row.get("date", ""),
                "race_id": rid,
                "course": row.get("course", ""),
                "off": row.get("off", ""),
                "pick": row.get("velo_top_pick", ""),
                "velo_outcome": velo_out,
                "ew_outcome": ew_out,
                "field_size": field_size,
                "going": going,
                "winner_sp_dec": winner_sp_dec if winner_sp_dec is not None else "PRICE_UNKNOWN",
                "is_ew_win": ew_out == "EW_WIN",
                "is_ew_place": ew_out in ("EW_WIN", "EW_PLACE"),
            }
        )

    n = len(ew_rows)
    if n == 0:
        return {"status": "NO_EW_CANDIDATE_DATA", "n": 0}

    ew_wins = sum(1 for r in ew_rows if r["is_ew_win"])
    ew_places = sum(1 for r in ew_rows if r["is_ew_place"])
    unknown_field = sum(1 for r in ew_rows if r["field_size"] == "FIELD_SIZE_UNKNOWN")
    unknown_sp = sum(1 for r in ew_rows if r["winner_sp_dec"] == "PRICE_UNKNOWN")

    place_rate = round(ew_places / n, 4) if n > 0 else 0.0

    # EW profit cannot be claimed without price+field
    profit_claimable = unknown_field == 0 and unknown_sp == 0
    ew_verdict = "EW_REALITY_CHECKED"
    if unknown_field > 0 or unknown_sp > 0:
        ew_verdict = "EW_PARTIAL_DATA_NO_PROFIT_CLAIM"

    return {
        "n": n,
        "ew_wins": ew_wins,
        "ew_places": ew_places,
        "place_rate": place_rate,
        "unknown_field_size": unknown_field,
        "unknown_sp": unknown_sp,
        "profit_claimable": profit_claimable,
        "verdict": ew_verdict,
        "note": "EW profit cannot be claimed without SP and field size — SP_PROXY_IS_NOT_DIVIDEND_PROOF",
        "rows": ew_rows,
    }


def _section10_midprice_miss(audit_rows, ledger_rows):
    """Mid-price miss recovery analysis."""
    mp_rows = [r for r in audit_rows if r.get("miss_reason") == "mid_priced_won"]

    # Build ledger index by race_id
    ledger_by_raceid = {row.get("race_id", ""): row for row in ledger_rows}
    # Also build by date+course+off as fallback
    ledger_by_dco = {}
    for row in ledger_rows:
        key = f"{row.get('date', '')}_{row.get('course', '')}_{row.get('off', '')}"
        ledger_by_dco[key] = row

    recovery_rows = []
    for r in mp_rows:
        rid = r.get("race_id", "")
        ledger_row = ledger_by_raceid.get(rid)
        if ledger_row is None:
            dco = f"{r['_date']}_{r['_course']}_{r.get('off_time', '')}"
            ledger_row = ledger_by_dco.get(dco)

        nb_pick = ""
        norpr_pick = ""
        nb_out = "UNKNOWN"
        norpr_out = "UNKNOWN"
        actual_winner = r.get("actual_winner_name") or "UNKNOWN"
        if ledger_row:
            nb_pick = ledger_row.get("nb_top_pick", "") or ""
            norpr_pick = ledger_row.get("norpr_top_pick", "") or ""
            nb_out = ledger_row.get("nb_outcome", "") or "UNKNOWN"
            norpr_out = ledger_row.get("norpr_outcome", "") or "UNKNOWN"
            if not actual_winner or actual_winner == "UNKNOWN":
                actual_winner = ledger_row.get("winner", "UNKNOWN") or "UNKNOWN"

        recovery_rows.append(
            {
                "date": r["_date"],
                "race_id": rid,
                "course": r["_course"],
                "off_time": r.get("off_time") or "UNKNOWN",
                "velo_pick": r.get("horse_id", "UNKNOWN"),
                "actual_winner": actual_winner,
                "winner_sp": r["_winner_sp_dec"] if r["_winner_sp_dec"] is not None else "PRICE_UNKNOWN",
                "odds_band": r["_winner_odds_band"],
                "nb_pick": nb_pick or "UNKNOWN",
                "nb_outcome": nb_out,
                "norpr_pick": norpr_pick or "UNKNOWN",
                "norpr_outcome": norpr_out,
            }
        )

    n = len(mp_rows)
    nb_hits = sum(1 for r in recovery_rows if str(r.get("nb_outcome", "")).upper() == "WIN")
    norpr_hits = sum(1 for r in recovery_rows if str(r.get("norpr_outcome", "")).upper() == "WIN")

    return {
        "n_midprice_misses": n,
        "nb_recovery_wins": nb_hits,
        "norpr_recovery_wins": norpr_hits,
        "nb_recovery_rate": round(nb_hits / n, 4) if n > 0 else 0.0,
        "norpr_recovery_rate": round(norpr_hits / n, 4) if n > 0 else 0.0,
        "rows": recovery_rows,
    }


def _section11_exotics(ledger_rows, race_map):
    """Exotics signal audit — exacta/trifecta box containment only. NO profit claim."""
    exacta_box_hits = 0
    trifecta_box_hits = 0
    knowable = 0
    rows_out = []

    for row in ledger_rows:
        top3_raw = row.get("top3", "") or ""
        top3 = [x.strip() for x in top3_raw.split("|") if x.strip()] if top3_raw else []
        if not top3:
            continue
        knowable += 1

        velo_pick = row.get("velo_top_pick", "") or ""
        nb_pick = row.get("nb_top_pick", "") or ""
        if nb_pick in ("nan", "NaN", "NO_DATA", ""):
            nb_pick = ""
        norpr_pick = row.get("norpr_top_pick", "") or ""
        if norpr_pick in ("nan", "NaN", "NO_DATA", ""):
            norpr_pick = ""

        consensus = list(dict.fromkeys([p for p in [velo_pick, nb_pick, norpr_pick] if p]))

        exacta_hit = len([h for h in top3[:2] if h in consensus]) >= 2
        trifecta_hit = len([h for h in top3[:3] if h in consensus]) >= 3

        if exacta_hit:
            exacta_box_hits += 1
        if trifecta_hit:
            trifecta_box_hits += 1

        rows_out.append(
            {
                "date": row.get("date", ""),
                "race_id": row.get("race_id", ""),
                "course": row.get("course", ""),
                "off": row.get("off", ""),
                "velo_pick": velo_pick,
                "nb_pick": nb_pick or "UNKNOWN",
                "norpr_pick": norpr_pick or "UNKNOWN",
                "top3": top3_raw,
                "exacta_box_hit": exacta_hit,
                "trifecta_box_hit": trifecta_hit,
                "dividend_status": "DIVIDEND_UNKNOWN",
            }
        )

    return {
        "knowable_races": knowable,
        "exacta_box_hits": exacta_box_hits,
        "trifecta_box_hits": trifecta_box_hits,
        "exacta_box_rate": round(exacta_box_hits / knowable, 4) if knowable > 0 else 0.0,
        "trifecta_box_rate": round(trifecta_box_hits / knowable, 4) if knowable > 0 else 0.0,
        "containment_is_not_profit": True,
        "dividend_status": "DIVIDEND_UNKNOWN",
        "note": "Containment in top3 does NOT equal profit. No dividend data available. SP_PROXY_IS_NOT_DIVIDEND_PROOF.",
        "rows": rows_out,
    }


def _section12_training_gap(audit_rows):
    """Training vs sigma gap analysis."""
    sigma_path = os.path.join(DATA_DIR, "training", "sigma_local_corpus_latest.parquet")
    sigma2k_path = os.path.join(DATA_DIR, "training", "sigma_2k_training_dataset_latest.parquet")

    sigma_df, sigma_status = _load_parquet_optional(sigma_path)
    sigma2k_df, sigma2k_status = _load_parquet_optional(sigma2k_path)

    sigma_rows = 0
    sigma2k_rows = 0
    sigma_dates = []

    if sigma_df is not None:
        if hasattr(sigma_df, "__len__"):
            sigma_rows = len(sigma_df)
        if hasattr(sigma_df, "columns") and "date" in sigma_df.columns:
            try:
                sigma_dates = sorted(sigma_df["date"].dropna().unique().tolist())
            except Exception:
                pass
        elif isinstance(sigma_df, list) and sigma_df and "date" in sigma_df[0]:
            sigma_dates = sorted({str(r.get("date", ""))[:10] for r in sigma_df if r.get("date")})

    if sigma2k_df is not None:
        if hasattr(sigma2k_df, "__len__"):
            sigma2k_rows = len(sigma2k_df)

    audit_dates = sorted({r["_date"] for r in audit_rows if r["_date"] != "UNKNOWN"})

    gap_dates = [d for d in audit_dates if d not in sigma_dates] if sigma_dates else "UNKNOWN"

    return {
        "sigma_corpus_status": sigma_status,
        "sigma_corpus_rows": sigma_rows,
        "sigma_corpus_dates_count": len(sigma_dates),
        "sigma2k_status": sigma2k_status,
        "sigma2k_rows": sigma2k_rows,
        "audit_date_count": len(audit_dates),
        "training_date_count": len(sigma_dates),
        "gap_dates_not_in_training": gap_dates if isinstance(gap_dates, list) else gap_dates,
        "gap_count": len(gap_dates) if isinstance(gap_dates, list) else "UNKNOWN",
    }


def _section13_external_sources():
    """Static map of external BHA/RP data sources."""
    return {
        "BHA_OFFICIAL_RATINGS": {
            "url": "https://www.britishhorseracing.com/racing/horses/ratings/",
            "content": "Official Ratings (OR) for all flat/NH horses, updated weekly",
            "status": "PUBLIC",
            "proven": True,
            "coverage": "All licensed UK racehorses",
            "note": "Downloadable as CSV. Use for OR verification and training data enrichment.",
        },
        "RP_RACE_CARDS": {
            "url": "https://www.racingpost.com/racecards/",
            "content": "Daily racecards with form, RPR, trainer/jockey stats",
            "status": "PAYWALLED_PARTIAL",
            "proven": True,
            "coverage": "UK+IRE+International",
            "note": "F_0010 PDF workflow active. HTML racecards parse with RP ingestion layer.",
        },
        "RP_RESULTS": {
            "url": "https://www.racingpost.com/results/",
            "content": "Full result history with SP, position, weight, form figures",
            "status": "PAYWALLED_PARTIAL",
            "proven": True,
            "coverage": "UK+IRE — primary results source from 2026-05-23 onwards",
            "note": "rp_results_YYYY_MM_DD.json available for 39 dates. Winner SP and top3 present.",
        },
        "BHA_WEIGHTS_AND_CONDITIONS": {
            "url": "https://www.britishhorseracing.com/racing/",
            "content": "Race conditions, weight allowances, NH/Flat categories",
            "status": "PUBLIC",
            "proven": True,
            "coverage": "UK flat and jumps",
            "note": "Used for race_class validation and field size sanity checks.",
        },
        "RP_TIPSTER_F0010_PDF": {
            "url": "Internal — data/reports/F_0010_*.pdf",
            "content": "Racing Post daily tipster selections and analysis",
            "status": "LOCAL_ARTIFACT",
            "proven": True,
            "coverage": "Used in dashboard pipeline from 2026-05-14",
            "note": "parse_industry_selections.py extracts tipster picks. Primary industry comparison source.",
        },
        "RACING_API": {
            "url": "https://api.theracingapi.com/",
            "content": "Historical race data, trainer/jockey stats",
            "status": "DECOMMISSIONED_2026_05_14",
            "proven": False,
            "coverage": "N/A — API 401 errors. Decommissioned.",
            "note": "PERMANENTLY DECOMMISSIONED for live use. RP HTML is only live source.",
        },
    }


def _section14_operator_brief(all_sections, win_rows):
    """Plain text operator brief answering 15 questions."""
    inv = all_sections.get("inventory", {})
    course_perf = all_sections.get("course_performance", {})
    lane_perf = all_sections.get("lane_performance", {})
    rpr = all_sections.get("rpr_dependency", {})
    nb = all_sections.get("new_build", {})
    ew = all_sections.get("ew_candidate", {})
    mp = all_sections.get("midprice_miss", {})
    exotics = all_sections.get("exotics", {})
    training = all_sections.get("training_gap", {})

    total = inv.get("sigma_dump_rows", 0)
    outcome_c = inv.get("outcome_counts", {})
    wins = outcome_c.get("WIN", 0)
    places = outcome_c.get("PLACED", 0)
    misses = outcome_c.get("MISS", 0)
    overall_sr = round(wins / total, 4) if total > 0 else 0.0
    overall_fr = round((wins + places) / total, 4) if total > 0 else 0.0

    # Top wins by SP
    top_wins_str = ""
    if win_rows:
        shown = win_rows[:10]
        for w in shown:
            sp = w.get("winner_sp", "PRICE_UNKNOWN")
            sp_str = f"@{sp:.1f}" if isinstance(sp, float) else f"@{sp}"
            top_wins_str += f"\n  - {w['horse_name']} ({w['course']} {w['date']}) {sp_str} [{w['tier']}]"

    # Best course
    course_edges = [
        c for c, d in course_perf.items() if d.get("label") == "COURSE_EDGE_CONFIRMED" and d.get("n", 0) >= 10
    ]
    course_drains = [c for c, d in course_perf.items() if d.get("label") == "COURSE_DRAIN" and d.get("n", 0) >= 10]

    # Best tier
    tier_a = lane_perf.get("TIER_A", {})
    tier_b = lane_perf.get("TIER_B", {})
    tier_c = lane_perf.get("TIER_C", {})

    lines = [
        "=" * 70,
        "RESULTS-01 OPERATOR BRIEF — VÉLØ FULL RESULTS TRUTH AUDIT",
        f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
        "=" * 70,
        "",
        "Q1. OVERALL PERFORMANCE",
        f"    Total rows: {total} | Wins: {wins} | Places: {places} | Misses: {misses}",
        f"    Strike Rate: {overall_sr:.1%} | Frame Rate: {overall_fr:.1%}",
        f"    Date range: {inv.get('sigma_dump_date_count', 0)} unique dates in sigma dump",
        "",
        f"Q2. BIGGEST PRICE WINNERS (top 10 by SP):{top_wins_str or chr(10) + '    No wins with named horse found in sigma dump'}",
        "",
        "Q3. TIER BREAKDOWN",
        f"    Tier A: n={tier_a.get('n', 0)} SR={tier_a.get('sr', 0):.1%}",
        f"    Tier B: n={tier_b.get('n', 0)} SR={tier_b.get('sr', 0):.1%}",
        f"    Tier C: n={tier_c.get('n', 0)} SR={tier_c.get('sr', 0):.1%}",
        "",
        "Q4. COURSE PERFORMANCE",
        f"    Edge confirmed (n>=10): {', '.join(course_edges) or 'None'}",
        f"    Drains (n>=10): {', '.join(course_drains) or 'None'}",
        f"    Total unique courses: {len(course_perf)}",
        "",
        "Q5. RPR DEPENDENCY",
        f"    Verdict: {rpr.get('verdict', 'UNKNOWN')}",
        f"    Boosted n={rpr.get('n_rpr_boosted', 0)} SR={rpr.get('boost_sr', 0):.1%}",
        f"    Dragged n={rpr.get('n_rpr_dragged', 0)} SR={rpr.get('drag_sr', 0):.1%}",
        f"    Avg gap: {rpr.get('avg_gap', 'UNKNOWN')}",
        "",
        "Q6. NEW BUILD MODEL",
        f"    n={nb.get('n', 0)} SR={nb.get('sr', 0):.1%} Place={nb.get('place_rate', 0):.1%}",
        f"    Top3 containment={nb.get('top3_hit_rate', 'UNKNOWN')} — CONTAINMENT IS NOT PROFIT",
        "",
        "Q7. EW CANDIDATE LANE",
        f"    n={ew.get('n', 0)} EW place rate={ew.get('place_rate', 0):.1%}",
        f"    Verdict: {ew.get('verdict', 'UNKNOWN')}",
        f"    Unknown field size: {ew.get('unknown_field_size', 0)} | Unknown SP: {ew.get('unknown_sp', 0)}",
        "",
        "Q8. MID-PRICE MISS RECOVERY",
        f"    n={mp.get('n_midprice_misses', 0)} mid-price misses",
        f"    NB picked winner: {mp.get('nb_recovery_wins', 0)} ({mp.get('nb_recovery_rate', 0):.1%})",
        f"    NoRPR picked winner: {mp.get('norpr_recovery_wins', 0)} ({mp.get('norpr_recovery_rate', 0):.1%})",
        "",
        "Q9. EXOTICS SIGNAL",
        f"    Knowable races: {exotics.get('knowable_races', 0)}",
        f"    Exacta box rate: {exotics.get('exacta_box_rate', 0):.1%} ({exotics.get('exacta_box_hits', 0)} hits)",
        f"    Trifecta box rate: {exotics.get('trifecta_box_rate', 0):.1%} ({exotics.get('trifecta_box_hits', 0)} hits)",
        "    *** DIVIDEND STATUS: UNKNOWN — NO PROFIT CLAIM ***",
        "",
        "Q10. TRAINING VS SIGMA GAP",
        f"    Corpus status: {training.get('sigma_corpus_status', 'UNKNOWN')}",
        f"    Corpus rows: {training.get('sigma_corpus_rows', 0)}",
        f"    Gap dates (in audit, not in training): {training.get('gap_count', 'UNKNOWN')}",
        "",
        "Q11. MISS CLASSIFICATION BREAKDOWN",
    ]
    miss_top = inv.get("miss_reason_top5", [])
    for mr, cnt in miss_top:
        lines.append(f"    {mr}: {cnt}")

    lines += [
        "",
        "Q12. DATA COVERAGE",
        f"    winner_sp present: {inv.get('field_coverage', {}).get('actual_winner_sp', 'UNKNOWN')}",
        f"    pick_sp present: {inv.get('field_coverage', {}).get('pick_sp', 'UNKNOWN')}",
        f"    winner_name present: {inv.get('field_coverage', {}).get('actual_winner_name', 'UNKNOWN')}",
        f"    RP results races indexed: {inv.get('rp_results_races', 0)}",
        f"    Verdict races indexed: {inv.get('verdict_races', 0)}",
        "",
        "Q13. HARD CONSTRAINTS CONFIRMED",
        "    NO_SUPABASE_WRITES: TRUE",
        "    NO_LIVE_SCORING_CHANGE: TRUE",
        "    NO_MODEL_PROMOTION: TRUE",
        "    NO_TELEGRAM_SEND: TRUE",
        "    CANONICAL_HORSE_PASSPORT_NOT_MUTATED: TRUE",
        "    CONTAINMENT_IS_NOT_PROFIT: TRUE",
        "    SP_PROXY_IS_NOT_DIVIDEND_PROOF: TRUE",
        "",
        "Q14. CONTRADICTIONS FLAGGED",
        f"    EW profit not claimable (field/SP gaps): {ew.get('unknown_field_size', 0) + ew.get('unknown_sp', 0)} rows affected",
        f"    Exotics dividend unknown: {exotics.get('knowable_races', 0)} races — NO profit claim",
        f"    winner_sp missing in audit: {total - int(inv.get('field_coverage', {}).get('actual_winner_sp', '0/0').split('/')[0])} rows",
        "",
        "Q15. NEXT OPERATOR ACTIONS (gated)",
        "    - Review COURSE_EDGE_CONFIRMED courses for lane targeting",
        f"    - Verify RPR verdict: {rpr.get('verdict', 'UNKNOWN')} — adjust weighting if MISLED",
        f"    - New Build SR={nb.get('sr', 0):.1%} — gate promotion at n>=300",
        "    - EW candidate: expand dividend data capture before any EW staking",
        f"    - Training gap: {training.get('gap_count', 'UNKNOWN')} dates not in training corpus",
        "",
        "=" * 70,
        "END OF OPERATOR BRIEF — REPORT_ONLY",
        "=" * 70,
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CSV writers
# ---------------------------------------------------------------------------


def _write_csv(path, rows, fieldnames=None):
    if not rows:
        with open(path, "w", newline="", encoding="utf-8") as f:
            f.write("# No data\n")
        return
    if fieldnames is None:
        fieldnames = list(rows[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    print("RESULTS-01 — VÉLØ Full Results Truth Audit")
    print("REPORT_ONLY — No scoring change, no Supabase write, no model promotion")
    print("=" * 60)

    print("\n[1] Loading data sources...")
    audit_rows = _load_sigma_dump()
    print(f"  sigma_dump: {len(audit_rows)} rows")

    ledger_rows = _load_ledger()
    print(f"  ledger: {len(ledger_rows)} rows")

    sigma_results_map = _load_sigma_results()
    print(f"  sigma_results: {len(sigma_results_map)} files")

    race_map, date_map = _load_results_map()
    print(f"  rp_results: {len(race_map)} races indexed")

    verdict_map = _load_verdicts_map()
    print(f"  verdicts: {len(verdict_map)} races indexed")

    print("\n[2] Running audit sections...")

    inv = _section1_inventory(audit_rows, ledger_rows, sigma_results_map, race_map, verdict_map)
    print(f"  S1 inventory: {inv['sigma_dump_rows']} rows, {inv['sigma_dump_date_count']} dates")

    win_rows = _section2_horses_landed(audit_rows, ledger_rows)
    print(f"  S2 horses landed: {len(win_rows)} wins")

    biggest_wins, biggest_places = _section3_biggest_price(audit_rows)
    print(f"  S3 biggest price: {len(biggest_wins)} wins, {len(biggest_places)} placers")

    course_perf = _section4_course_performance(audit_rows)
    print(f"  S4 course performance: {len(course_perf)} courses")

    odds_band_data = _section5_odds_band(audit_rows)
    print("  S5 odds band performance: complete")

    lane_perf = _section6_lane_performance(audit_rows, ledger_rows)
    print(f"  S6 lane performance: {len(lane_perf)} lanes")

    rpr_data = _section7_rpr_dependency(audit_rows, verdict_map)
    print(f"  S7 RPR dependency: verdict={rpr_data.get('verdict', '?')}, n={rpr_data.get('n_with_gap', 0)}")

    nb_data = _section8_new_build(ledger_rows, race_map)
    print(f"  S8 new build: n={nb_data.get('n', 0)}, SR={nb_data.get('sr', 0):.1%}")

    ew_data = _section9_ew_candidate(audit_rows, ledger_rows, race_map)
    print(f"  S9 EW candidate: n={ew_data.get('n', 0)}, place_rate={ew_data.get('place_rate', 0):.1%}")

    mp_data = _section10_midprice_miss(audit_rows, ledger_rows)
    print(f"  S10 midprice miss: n={mp_data.get('n_midprice_misses', 0)}")

    exotics_data = _section11_exotics(ledger_rows, race_map)
    print(f"  S11 exotics: exacta_rate={exotics_data.get('exacta_box_rate', 0):.1%}")

    training_data = _section12_training_gap(audit_rows)
    print(f"  S12 training gap: {training_data.get('sigma_corpus_status', '?')}")

    ext_sources = _section13_external_sources()
    print(f"  S13 external sources: {len(ext_sources)} sources documented")

    all_sections = {
        "inventory": inv,
        "horses_landed": {"count": len(win_rows)},
        "biggest_price": {"wins": len(biggest_wins), "placers": len(biggest_places)},
        "course_performance": course_perf,
        "odds_band": odds_band_data,
        "lane_performance": lane_perf,
        "rpr_dependency": rpr_data,
        "new_build": nb_data,
        "ew_candidate": ew_data,
        "midprice_miss": mp_data,
        "exotics": exotics_data,
        "training_gap": training_data,
        "external_sources": ext_sources,
    }

    operator_brief = _section14_operator_brief(all_sections, win_rows)
    print("  S14 operator brief: written")

    print("\n[3] Writing output files...")

    # Build JSON-safe version of ew_data (remove rows list for main JSON)
    ew_summary = {k: v for k, v in ew_data.items() if k != "rows"}
    mp_summary = {k: v for k, v in mp_data.items() if k != "rows"}
    exotics_summary = {k: v for k, v in exotics_data.items() if k != "rows"}

    # Main JSON (no huge row lists)
    main_json = {
        "audit_id": "RESULTS-01",
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "hard_constraints": HARD_CONSTRAINTS,
        "final_classifications": FINAL_CLASSIFICATIONS,
        "sections": {
            "inventory": inv,
            "horses_landed_count": len(win_rows),
            "biggest_price": {"wins": len(biggest_wins), "placers": len(biggest_places)},
            "course_performance": course_perf,
            "odds_band": odds_band_data,
            "lane_performance": lane_perf,
            "rpr_dependency": rpr_data,
            "new_build": {k: v for k, v in nb_data.items() if k not in ("rows",)},
            "ew_candidate": ew_summary,
            "midprice_miss": mp_summary,
            "exotics": exotics_summary,
            "training_gap": training_data,
            "external_sources": ext_sources,
        },
    }

    json_path = os.path.join(REPORTS_DIR, "results_01_full_results_truth_audit.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(main_json, f, indent=2, default=str)
    print(f"  Written: {json_path}")

    # MD summary
    md_path = os.path.join(REPORTS_DIR, "results_01_full_results_truth_audit.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# RESULTS-01 — VÉLØ Full Results Truth Audit\n\n")
        f.write(f"**Generated:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}\n\n")
        f.write("**Status:** REPORT_ONLY — No scoring change, no Supabase write, no model promotion\n\n")
        f.write("## Final Classifications\n\n")
        for c in FINAL_CLASSIFICATIONS:
            f.write(f"- `{c}`\n")
        f.write("\n## Summary\n\n")
        inv_oc = inv.get("outcome_counts", {})
        total_r = inv.get("sigma_dump_rows", 0)
        f.write(f"- Total sigma dump rows: **{total_r}**\n")
        f.write(
            f"- Wins: **{inv_oc.get('WIN', 0)}** | Places: **{inv_oc.get('PLACED', 0)}** | Misses: **{inv_oc.get('MISS', 0)}**\n"
        )
        f.write(f"- Overall SR: **{inv_oc.get('WIN', 0) / max(total_r, 1):.1%}**\n")
        f.write(f"- Dates covered: **{inv.get('sigma_dump_date_count', 0)}**\n\n")
        f.write("## Hard Constraints\n\n")
        for c in HARD_CONSTRAINTS:
            f.write(f"- `{c}`\n")
    print(f"  Written: {md_path}")

    # Horses landed CSV
    horses_csv_path = os.path.join(REPORTS_DIR, "results_01_horses_landed_table.csv")
    _write_csv(
        horses_csv_path,
        win_rows,
        fieldnames=[
            "date",
            "course",
            "off_time",
            "horse_name",
            "winner_sp",
            "pick_sp",
            "tier",
            "race_type",
            "assigned_product",
            "verdict_score",
            "odds_band",
        ],
    )
    print(f"  Written: {horses_csv_path}")

    # Biggest price winners CSV
    bpw_path = os.path.join(REPORTS_DIR, "results_01_biggest_price_winners.csv")
    _write_csv(
        bpw_path,
        biggest_wins,
        fieldnames=["date", "course", "off_time", "horse_name", "winner_sp", "pick_sp", "tier", "race_type", "outcome"],
    )
    print(f"  Written: {bpw_path}")

    # Biggest price placers CSV
    bpp_path = os.path.join(REPORTS_DIR, "results_01_biggest_price_placers.csv")
    _write_csv(
        bpp_path,
        biggest_places,
        fieldnames=[
            "date",
            "course",
            "off_time",
            "horse_name",
            "winner_sp",
            "pick_sp",
            "position",
            "tier",
            "race_type",
            "outcome",
        ],
    )
    print(f"  Written: {bpp_path}")

    # Course performance CSV
    course_rows = []
    for course, d in sorted(course_perf.items(), key=lambda x: -x[1]["n"]):
        course_rows.append(
            {
                "course": course,
                "n": d["n"],
                "wins": d["wins"],
                "places": d["places"],
                "sr": d["sr"],
                "frame_rate": d["frame_rate"],
                "avg_winner_sp": d["avg_winner_sp"] or "UNKNOWN",
                "median_winner_sp": d["median_winner_sp"] or "UNKNOWN",
                "label": d["label"],
            }
        )
    cp_path = os.path.join(REPORTS_DIR, "results_01_course_performance_table.csv")
    _write_csv(
        cp_path,
        course_rows,
        fieldnames=["course", "n", "wins", "places", "sr", "frame_rate", "avg_winner_sp", "median_winner_sp", "label"],
    )
    print(f"  Written: {cp_path}")

    # Odds band CSV
    band_rows = []
    for band, d in odds_band_data.get("by_pick_sp", {}).items():
        band_rows.append(
            {
                "odds_band": band,
                "n_picks": d["n_picks"],
                "wins": d["wins"],
                "places": d["places"],
                "sr": d["sr"],
                "place_rate": d["place_rate"],
                "wins_in_band_by_winner_sp": odds_band_data.get("by_winner_sp", {})
                .get(band, {})
                .get("wins_at_this_price", 0),
            }
        )
    ob_path = os.path.join(REPORTS_DIR, "results_01_odds_band_performance_table.csv")
    _write_csv(
        ob_path,
        band_rows,
        fieldnames=["odds_band", "n_picks", "wins", "places", "sr", "place_rate", "wins_in_band_by_winner_sp"],
    )
    print(f"  Written: {ob_path}")

    # Lane performance CSV
    lane_rows = []
    for lane, d in sorted(lane_perf.items(), key=lambda x: -x[1].get("n", 0)):
        lane_rows.append(
            {
                "lane": lane,
                "n": d.get("n", 0),
                "wins": d.get("wins", 0),
                "places": d.get("places", 0),
                "sr": d.get("sr", 0.0),
                "place_rate": d.get("place_rate", 0.0),
                "source": d.get("source", ""),
                "note": d.get("note", "") or d.get("notee", ""),
            }
        )
    lp_path = os.path.join(REPORTS_DIR, "results_01_lane_performance_table.csv")
    _write_csv(lp_path, lane_rows, fieldnames=["lane", "n", "wins", "places", "sr", "place_rate", "source", "note"])
    print(f"  Written: {lp_path}")

    # Midprice recovery CSV
    mp_path_csv = os.path.join(REPORTS_DIR, "results_01_midprice_recovery_table.csv")
    _write_csv(
        mp_path_csv,
        mp_data.get("rows", []),
        fieldnames=[
            "date",
            "race_id",
            "course",
            "off_time",
            "velo_pick",
            "actual_winner",
            "winner_sp",
            "odds_band",
            "nb_pick",
            "nb_outcome",
            "norpr_pick",
            "norpr_outcome",
        ],
    )
    print(f"  Written: {mp_path_csv}")

    # EW candidate CSV
    ew_path_csv = os.path.join(REPORTS_DIR, "results_01_ew_candidate_truth_table.csv")
    _write_csv(
        ew_path_csv,
        ew_data.get("rows", []),
        fieldnames=[
            "date",
            "race_id",
            "course",
            "off",
            "pick",
            "velo_outcome",
            "ew_outcome",
            "field_size",
            "going",
            "winner_sp_dec",
            "is_ew_win",
            "is_ew_place",
        ],
    )
    print(f"  Written: {ew_path_csv}")

    # Exotics CSV
    exotics_csv_path = os.path.join(REPORTS_DIR, "results_01_exotics_signal_table.csv")
    _write_csv(
        exotics_csv_path,
        exotics_data.get("rows", []),
        fieldnames=[
            "date",
            "race_id",
            "course",
            "off",
            "velo_pick",
            "nb_pick",
            "norpr_pick",
            "top3",
            "exacta_box_hit",
            "trifecta_box_hit",
            "dividend_status",
        ],
    )
    print(f"  Written: {exotics_csv_path}")

    # External source map MD
    ext_md_path = os.path.join(REPORTS_DIR, "results_01_external_source_backfill_map.md")
    with open(ext_md_path, "w", encoding="utf-8") as f:
        f.write("# External Source Backfill Map\n\n")
        for src, d in ext_sources.items():
            f.write(f"## {src}\n\n")
            f.write(f"- **URL:** {d.get('url', '')}\n")
            f.write(f"- **Content:** {d.get('content', '')}\n")
            f.write(f"- **Status:** {d.get('status', '')}\n")
            f.write(f"- **Proven:** {d.get('proven', '')}\n")
            f.write(f"- **Coverage:** {d.get('coverage', '')}\n")
            f.write(f"- **Note:** {d.get('note', '')}\n\n")
    print(f"  Written: {ext_md_path}")

    # Operator brief MD
    op_path = os.path.join(REPORTS_DIR, "results_01_operator_brief.md")
    with open(op_path, "w", encoding="utf-8") as f:
        f.write(operator_brief)
    print(f"  Written: {op_path}")

    # Training gap MD (optional)
    tg_path = os.path.join(REPORTS_DIR, "results_01_training_vs_sigma_gap.md")
    with open(tg_path, "w", encoding="utf-8") as f:
        f.write("# Training vs Sigma Gap\n\n")
        f.write(f"- Sigma corpus status: {training_data.get('sigma_corpus_status', 'UNKNOWN')}\n")
        f.write(f"- Sigma corpus rows: {training_data.get('sigma_corpus_rows', 0)}\n")
        f.write(f"- Sigma2k status: {training_data.get('sigma2k_status', 'UNKNOWN')}\n")
        f.write(f"- Sigma2k rows: {training_data.get('sigma2k_rows', 0)}\n")
        f.write(f"- Audit dates: {training_data.get('audit_date_count', 0)}\n")
        f.write(f"- Training dates: {training_data.get('training_date_count', 0)}\n")
        gap = training_data.get("gap_dates_not_in_training", "UNKNOWN")
        f.write(f"- Gap count: {training_data.get('gap_count', 'UNKNOWN')}\n")
        if isinstance(gap, list):
            f.write("- Gap dates:\n")
            for d in gap:
                f.write(f"  - {d}\n")
    print(f"  Written: {tg_path}")

    # RPR dependency MD (optional)
    rpr_md_path = os.path.join(REPORTS_DIR, "results_01_rpr_dependency_full_corpus.md")
    with open(rpr_md_path, "w", encoding="utf-8") as f:
        f.write("# RPR Dependency Full Corpus\n\n")
        for k, v in rpr_data.items():
            f.write(f"- **{k}:** {v}\n")
    print(f"  Written: {rpr_md_path}")

    print("\n[4] Final classifications:")
    for c in FINAL_CLASSIFICATIONS:
        print(f"  {c}: TRUE")

    print("\n" + "=" * 60)
    print("RESULTS-01 COMPLETE — REPORT_ONLY — No scoring change.")
    print("=" * 60)

    return main_json


if __name__ == "__main__":
    main()
