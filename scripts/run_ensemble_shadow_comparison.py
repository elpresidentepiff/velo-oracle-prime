"""
run_ensemble_shadow_comparison.py

For each scoring day, scores with SQPE_IMPROVEMENT_MDS_V1 (live)
and LEGACY_FULL_ENSEMBLE (shadow) side by side.

Produces: data/ensemble_profile_comparison_YYYY_MM_DD.md

Run after run_prime_today.py closes:
  PYTHONPATH=. python scripts/run_ensemble_shadow_comparison.py --date YYYY-MM-DD

Mandatory for 30 live race days post Ensemble Surgery v1 (2026-05-08).
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path


def _score_with_profile(date_str: str, profile: str, out_path: Path) -> dict:
    """Run scoring dry-run for one profile and return parsed backup JSON."""
    env = os.environ.copy()
    env["VELO_ENSEMBLE_PROFILE"] = profile
    env["PYTHONPATH"] = "."

    result = subprocess.run(
        [sys.executable, "scripts/run_prime_today.py",
         "--date", date_str, "--dry-run", "--no-notify"],
        capture_output=True, text=True, env=env
    )
    if result.returncode != 0:
        raise RuntimeError(f"Scoring failed for {profile}:\n{result.stderr[-2000:]}")

    backup = Path(f"data/velo_prime_verdicts_{date_str.replace('-','_')}.json")
    if not backup.exists():
        raise FileNotFoundError(f"Backup not found: {backup}")
    with open(backup) as f:
        data = json.load(f)

    # Save a copy per profile so they don't overwrite each other
    out_path.write_text(json.dumps(data, indent=2))
    return data


def _analyze(data: list) -> dict:
    vps, tops, tiers, execs = [], [], [], []
    for race in data:
        top = race.get("top")
        if not top: continue
        vps.append(top.get("velo_prime_prob", 0))
        tops.append((top.get("horse") or "").strip())
        tiers.append(race.get("tier", "?"))
        execs.append(top.get("candidate_execution_allowed", False))
    return {
        "n": len(vps),
        "avg_vp": round(statistics.mean(vps), 4) if vps else 0,
        "median_vp": round(statistics.median(vps), 4) if vps else 0,
        "vp30": sum(1 for v in vps if v >= 0.30),
        "vp25": sum(1 for v in vps if v >= 0.25),
        "vp20": sum(1 for v in vps if v >= 0.20),
        "tier_a": tiers.count("A"),
        "tier_b": tiers.count("B"),
        "exec_allowed": sum(execs),
        "tops": tops,
    }


def _write_report(date_str: str, new: dict, leg: dict, new_data: list, leg_data: list, out: Path) -> None:
    top_changes = sum(
        1 for a, b in zip(new["tops"], leg["tops"]) if a != b
    )
    new_by_id = {r["race_id"]: r for r in new_data if r.get("race_id")}
    leg_by_id = {r["race_id"]: r for r in leg_data if r.get("race_id")}

    lines = [
        f"# Ensemble Profile Comparison — {date_str}",
        "",
        "| Metric | SQPE_IMPROVEMENT_MDS_V1 (live) | LEGACY_FULL_ENSEMBLE (shadow) |",
        "|---|---|---|",
        f"| Races | {new['n']} | {leg['n']} |",
        f"| Avg VP | {new['avg_vp']} | {leg['avg_vp']} |",
        f"| Median VP | {new['median_vp']} | {leg['median_vp']} |",
        f"| VP ≥ 0.30 | {new['vp30']} ({100*new['vp30']/new['n']:.1f}%) | {leg['vp30']} ({100*leg['vp30']/leg['n']:.1f}%) |",
        f"| VP ≥ 0.25 | {new['vp25']} ({100*new['vp25']/new['n']:.1f}%) | {leg['vp25']} ({100*leg['vp25']/leg['n']:.1f}%) |",
        f"| VP ≥ 0.20 | {new['vp20']} ({100*new['vp20']/new['n']:.1f}%) | {leg['vp20']} ({100*leg['vp20']/leg['n']:.1f}%) |",
        f"| Tier A | {new['tier_a']} | {leg['tier_a']} |",
        f"| Exec allowed | {new['exec_allowed']} | {leg['exec_allowed']} |",
        f"| Top selection changes | {top_changes} | — |",
        "",
        "## Top Selection Differences",
        "",
        "| Race | Live top | Shadow top | VP live | VP shadow | Δ VP |",
        "|---|---|---|---|---|---|",
    ]

    for rid in sorted(new_by_id.keys()):
        if rid not in leg_by_id: continue
        nt = new_by_id[rid].get("top") or {}
        lt = leg_by_id[rid].get("top") or {}
        nh = (nt.get("horse") or "").strip()
        lh = (lt.get("horse") or "").strip()
        nvp = nt.get("velo_prime_prob", 0)
        lvp = lt.get("velo_prime_prob", 0)
        delta = round(nvp - lvp, 4)
        if nh != lh:
            course = new_by_id[rid].get("course", rid)[:12]
            sign = "+" if delta >= 0 else ""
            lines.append(f"| {course} | **{nh}** | {lh} | {nvp:.4f} | {lvp:.4f} | {sign}{delta:.4f} |")

    if not any("|" in l and "**" in l for l in lines):
        lines.append("| — | No top-selection changes | — | — | — | — |")

    lines += [
        "",
        "## VP Distribution — New Profile",
        "",
        f"VP delta (new - legacy avg): {round(new['avg_vp'] - leg['avg_vp'], 4):+}",
        "",
        "| Band | Count | % |",
        "|---|---|---|",
    ]
    vps = [new_by_id[r]["top"]["velo_prime_prob"] for r in new_by_id if new_by_id[r].get("top")]
    n = len(vps) or 1
    for lo, hi in [(0, 0.20), (0.20, 0.25), (0.25, 0.30), (0.30, 0.40), (0.40, 1.01)]:
        cnt = sum(1 for v in vps if lo <= v < hi)
        band = f"{lo:.2f}–{hi:.2f}" if hi < 1.01 else f"≥ 0.40"
        lines.append(f"| {band} | {cnt} | {100*cnt/n:.1f}% |")

    lines += [
        "",
        "---",
        f"_Generated by scripts/run_ensemble_shadow_comparison.py — {date_str}_",
    ]

    out.write_text("\n".join(lines))
    print(f"Written: {out}")


def _append_monitor_csv(date_str: str, new: dict) -> None:
    csv_path = Path("data/ensemble_profile_monitor_latest.csv")
    import csv as _csv
    header = [
        "date","profile","races","sr_pct","frame_pct","roi",
        "vp30_n","vp25_n","vp20_n","mds_high_n","improve_high_n",
        "avg_sp","max_drawdown","top_change_vs_legacy","warnings"
    ]
    write_header = not csv_path.exists()
    with open(csv_path, "a", newline="") as f:
        w = _csv.DictWriter(f, fieldnames=header)
        if write_header: w.writeheader()
        w.writerow({
            "date": date_str,
            "profile": "SQPE_IMPROVEMENT_MDS_V1",
            "races": new["n"],
            "sr_pct": "",
            "frame_pct": "",
            "roi": "",
            "vp30_n": new["vp30"],
            "vp25_n": new["vp25"],
            "vp20_n": new["vp20"],
            "mds_high_n": "",
            "improve_high_n": "",
            "avg_sp": "",
            "max_drawdown": "",
            "top_change_vs_legacy": "",
            "warnings": "",
        })
    print(f"Appended: {csv_path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=str(date.today()), help="YYYY-MM-DD")
    args = parser.parse_args()
    date_str = args.date

    tmp = Path("data")
    new_path = tmp / f"_shadow_cmp_new_{date_str.replace('-','_')}.json"
    leg_path = tmp / f"_shadow_cmp_leg_{date_str.replace('-','_')}.json"

    print(f"=== Ensemble Shadow Comparison — {date_str} ===")
    print("Scoring with SQPE_IMPROVEMENT_MDS_V1...")
    new_data = _score_with_profile(date_str, "SQPE_IMPROVEMENT_MDS_V1", new_path)
    print("Scoring with LEGACY_FULL_ENSEMBLE...")
    leg_data = _score_with_profile(date_str, "LEGACY_FULL_ENSEMBLE", leg_path)

    new_stats = _analyze(new_data)
    leg_stats = _analyze(leg_data)

    out = Path(f"data/ensemble_profile_comparison_{date_str.replace('-','_')}.md")
    _write_report(date_str, new_stats, leg_stats, new_data, leg_data, out)
    _append_monitor_csv(date_str, new_stats)

    # Clean up temp copies
    new_path.unlink(missing_ok=True)
    leg_path.unlink(missing_ok=True)

    print(f"\nLive profile:   avg_vp={new_stats['avg_vp']}, vp30={new_stats['vp30']}, tier_a={new_stats['tier_a']}")
    print(f"Shadow legacy:  avg_vp={leg_stats['avg_vp']}, vp30={leg_stats['vp30']}, tier_a={leg_stats['tier_a']}")
    print(f"Top changes:    {sum(1 for a,b in zip(new_stats['tops'],leg_stats['tops']) if a!=b)}")


if __name__ == "__main__":
    main()
