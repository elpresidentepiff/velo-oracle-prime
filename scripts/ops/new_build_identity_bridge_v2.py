#!/usr/bin/env python3
"""
new_build_identity_bridge_v2.py
Link RP horse_rp_uid ↔ raceform horse name strings ↔ Racing API result files.
Shadow only.
"""
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import pandas as pd

RACE_SHAPE_DIR = ROOT / "data" / "race_shape"
RESULTS_DIR = ROOT / "data"
BRIDGE_DIR = ROOT / "data" / "new_build" / "bridges"
RPT_DIR = ROOT / "data" / "new_build" / "reports"
BRIDGE_DIR.mkdir(parents=True, exist_ok=True)
RPT_DIR.mkdir(parents=True, exist_ok=True)

TRUST_POLICY = "ARCHIVE_CONTEXT_ONLY_NOT_SCORING"
VELO_SCORING_ALLOWED = False


def _norm(name: str) -> str:
    """Normalize horse name: lowercase, strip country codes, strip punctuation, collapse spaces."""
    if not name:
        return ""
    n = name.lower()
    # strip country codes like (IRE), (FR), (USA), (GB), (GER) etc.
    n = re.sub(r"\s*\([a-z]{2,4}\)\s*$", "", n)
    n = re.sub(r"[^a-z0-9 ]", "", n)
    n = re.sub(r"\s+", " ", n).strip()
    return n


def _ratio(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def load_form_history_horses() -> dict:
    """Return {rp_uid: {horse_name, runs}} from form history JSONs."""
    horses = {}
    for f in sorted(RACE_SHAPE_DIR.glob("form_history_2026-*.json")):
        if "latest" in f.name:
            continue
        data = json.loads(f.read_text())
        for run in data.get("runs", []):
            uid = run.get("horse_rp_uid")
            if uid and uid not in horses:
                horses[uid] = {
                    "horse_name": run["horse_name"],
                    "horse_name_norm": _norm(run["horse_name"]),
                    "horse_rp_uid": uid,
                    "runs_in_form_history": 0,
                }
            if uid:
                horses[uid]["runs_in_form_history"] = horses[uid].get("runs_in_form_history", 0) + 1
    return horses


def load_raceform_names() -> dict:
    """Return {norm_name: [original_names]} from raceform_clean.parquet."""
    print("  Loading raceform_clean horse names ...")
    df = pd.read_parquet(ROOT / "data" / "raceform_clean.parquet", columns=["horse", "trainer", "date"])
    name_map: dict[str, dict] = {}
    for _, row in df.drop_duplicates("horse").iterrows():
        norm = _norm(str(row["horse"]))
        name_map[norm] = {
            "raceform_horse_name": row["horse"],
            "trainer": row.get("trainer", ""),
        }
    print(f"  {len(name_map):,} unique horse names in raceform")
    return name_map


def load_results_horses() -> dict:
    """Return {norm_name: original_name} from results JSON files."""
    names = {}
    for f in RESULTS_DIR.glob("results_*.json"):
        try:
            data = json.loads(f.read_text())
            for race in data.get("results", []):
                for runner in race.get("runners", []):
                    name = runner.get("horse", "")
                    if name:
                        names[_norm(name)] = name
        except Exception:
            continue
    return names


def run():
    print("Loading form history horses ...")
    fh_horses = load_form_history_horses()
    print(f"  {len(fh_horses)} horses with RP uids")

    raceform_names = load_raceform_names()
    results_names = load_results_horses()
    print(f"  {len(results_names):,} unique horse names in results JSONs")

    records = []
    status_counts = defaultdict(int)

    for uid, info in fh_horses.items():
        norm = info["horse_name_norm"]
        horse_name = info["horse_name"]

        rec = {
            "horse_name_normalized": norm,
            "horse_rp_uid": uid,
            "horse_rp_name": horse_name,
            "raceform_horse_name": None,
            "results_horse_name": None,
            "match_method": None,
            "confidence": None,
            "status": None,
            "runs_in_form_history": info["runs_in_form_history"],
            "runs_in_raceform": None,
            "trust_policy": TRUST_POLICY,
            "velo_scoring_allowed": VELO_SCORING_ALLOWED,
        }

        # 1. Exact match in raceform
        if norm in raceform_names:
            rec["raceform_horse_name"] = raceform_names[norm]["raceform_horse_name"]
            rec["match_method"] = "EXACT_NAME"
            rec["confidence"] = "HIGH"
            rec["status"] = "CONFIRMED"
            # Count runs
            status_counts["CONFIRMED"] += 1
        else:
            # 2. Exact match in results JSONs
            if norm in results_names:
                rec["results_horse_name"] = results_names[norm]
                # Then try to find in raceform via results name
                rn = _norm(results_names[norm])
                if rn in raceform_names:
                    rec["raceform_horse_name"] = raceform_names[rn]["raceform_horse_name"]
                    rec["match_method"] = "RESULTS_TO_RACEFORM"
                    rec["confidence"] = "HIGH"
                    rec["status"] = "CONFIRMED"
                    status_counts["CONFIRMED"] += 1
                else:
                    rec["match_method"] = "RESULTS_ONLY"
                    rec["confidence"] = "MEDIUM"
                    rec["status"] = "NAME_ONLY"
                    status_counts["NAME_ONLY"] += 1
            else:
                # 3. Fuzzy match
                best_ratio = 0.0
                best_match = None
                best_match2 = None
                # Check raceform names
                for rn, rdata in raceform_names.items():
                    r = _ratio(norm, rn)
                    if r > best_ratio:
                        best_match2 = best_match
                        best_ratio = r
                        best_match = (rn, rdata["raceform_horse_name"])

                if best_ratio >= 0.92 and best_match:
                    # Check there's no ambiguous second candidate
                    if best_match2 and _ratio(norm, best_match2[0]) >= 0.87:
                        rec["match_method"] = "FUZZY_AMBIGUOUS"
                        rec["confidence"] = "LOW"
                        rec["status"] = "AMBIGUOUS"
                        status_counts["AMBIGUOUS"] += 1
                    else:
                        rec["raceform_horse_name"] = best_match[1]
                        rec["match_method"] = f"FUZZY_{best_ratio:.2f}"
                        rec["confidence"] = "MEDIUM"
                        rec["status"] = "FUZZY"
                        status_counts["FUZZY"] += 1
                elif best_ratio >= 0.85:
                    rec["match_method"] = f"FUZZY_AMBIGUOUS_{best_ratio:.2f}"
                    rec["confidence"] = "LOW"
                    rec["status"] = "AMBIGUOUS"
                    status_counts["AMBIGUOUS"] += 1
                else:
                    rec["match_method"] = "NO_MATCH"
                    rec["confidence"] = "NONE"
                    rec["status"] = "NO_MATCH"
                    status_counts["NO_MATCH"] += 1

        records.append(rec)

    # Write JSONL
    out_path = BRIDGE_DIR / "identity_bridge_v2.jsonl"
    with out_path.open("w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")

    confirmed = [r for r in records if r["status"] == "CONFIRMED"]
    print(f"\nIdentity Bridge V2:")
    for status, count in sorted(status_counts.items()):
        print(f"  {status:<15} {count}")
    print(f"  TOTAL: {len(records)}")
    print(f"  (V1 had 9 confirmed links)")

    # MD report
    lines = [
        "# Identity Bridge V2",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Summary",
        f"| Status | Count |",
        f"|---|---|",
    ]
    for status, count in sorted(status_counts.items()):
        lines.append(f"| {status} | {count} |")
    lines += [
        f"| **TOTAL** | **{len(records)}** |",
        "",
        f"V1 baseline: 9 confirmed links",
        f"V2 upgrade: **{status_counts['CONFIRMED']} confirmed** (+{status_counts['CONFIRMED'] - 9} new links)",
        "",
        "## AMBIGUOUS — needs human review",
        "| Horse | RP UID | Form History Runs |",
        "|---|---|---|",
    ]
    for r in records:
        if r["status"] == "AMBIGUOUS":
            lines.append(f"| {r['horse_rp_name']} | {r['horse_rp_uid']} | {r['runs_in_form_history']} |")

    (RPT_DIR / "identity_bridge_v2_latest.md").write_text("\n".join(lines))

    report_json = {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "trust_policy": TRUST_POLICY,
        "velo_scoring_allowed": VELO_SCORING_ALLOWED,
        "total": len(records),
        "v1_confirmed_baseline": 9,
        "status_counts": dict(status_counts),
        "v2_upgrade": status_counts["CONFIRMED"] - 9,
    }
    (RPT_DIR / "identity_bridge_v2_latest.json").write_text(json.dumps(report_json, indent=2))
    print("  Reports written.")


if __name__ == "__main__":
    run()
