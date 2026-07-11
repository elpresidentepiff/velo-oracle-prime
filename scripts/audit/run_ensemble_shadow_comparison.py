"""
run_ensemble_shadow_comparison.py

For each scoring day, scores with SQPE_IMPROVEMENT_MDS_V1 (live)
and LEGACY_FULL_ENSEMBLE (shadow) side by side.

Produces: data/ensemble_profile_comparison_YYYY_MM_DD.md

Run after run_prime_today.py closes:
  PYTHONPATH=. python scripts/audit/run_ensemble_shadow_comparison.py --date YYYY-MM-DD

Mandatory for 30 live race days post Ensemble Surgery v1 (2026-05-08).

ENSEMBLE-TRUTH-01 (2026-07-11): this comparison previously joined the two
profiles' top-selection lists positionally (zip(new["tops"], leg["tops"])).
A missing race, a reordered race, or a race present in one profile's output
but not the other's would silently produce a believable but wrong agreement
count -- the two lists would still be the same length and just line up
against the wrong races. All comparison is now done by an explicit race_id
join (join_by_race_id), which hard-fails rather than silently degrading
when the two profiles' race universes don't match exactly, when either
profile is missing a top selection for a scored race, or when duplicate
race_ids exist in either profile's output. The monitor ledger is also
idempotent per (date, live_profile, shadow_profile) now -- rerunning a date
replaces its row rather than appending a duplicate.
"""

from __future__ import annotations

import argparse
import csv as _csv
import json
import os
import statistics
import subprocess
import sys
from datetime import date
from pathlib import Path

LIVE_PROFILE = "SQPE_IMPROVEMENT_MDS_V1"
SHADOW_PROFILE = "LEGACY_FULL_ENSEMBLE"


class EnsembleComparisonError(RuntimeError):
    """A hard-fail condition in the ensemble shadow comparison.

    Raised instead of silently degrading: race universe mismatch, duplicate
    race_ids, a missing top selection for a scored race, or a frozen
    profile output being mutated by the other profile's run.
    """


def _score_with_profile(date_str: str, profile: str, out_path: Path) -> dict:
    """Run scoring dry-run for one profile and return parsed backup JSON."""
    env = os.environ.copy()
    env["VELO_ENSEMBLE_PROFILE"] = profile
    env["PYTHONPATH"] = "."

    result = subprocess.run(
        [
            sys.executable,
            "scripts/ops/run_prime_today.py",
            "--date",
            date_str,
            "--dry-run",
            "--no-notify",
        ],
        capture_output=True,
        text=True,
        env=env,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Scoring failed for {profile}:\n{result.stderr[-2000:]}")

    backup = Path(f"data/velo_prime_verdicts_{date_str.replace('-', '_')}.json")
    if not backup.exists():
        raise FileNotFoundError(f"Backup not found: {backup}")
    with open(backup) as f:
        data = json.load(f)

    # Save a copy per profile so they don't overwrite each other, and so a
    # regression can prove one profile's saved copy is never mutated by the
    # other's subsequent scoring run (see _assert_untouched below).
    out_path.write_text(json.dumps(data, indent=2))
    return data


def _sha256_of_file(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def _assert_untouched(path: Path, expected_sha256: str, label: str) -> None:
    if not path.exists():
        raise EnsembleComparisonError(f"FROZEN_OUTPUT_MISSING: {label} ({path})")
    actual = _sha256_of_file(path)
    if actual != expected_sha256:
        raise EnsembleComparisonError(
            f"FROZEN_OUTPUT_MUTATED: {label} ({path}) sha256 changed from {expected_sha256[:12]}... to {actual[:12]}..."
        )


def to_race_map(data: list) -> dict[str, dict]:
    """Build race_id -> race dict. Hard-fails on duplicate race_ids."""
    m: dict[str, dict] = {}
    duplicates: list[str] = []
    for race in data:
        rid = race.get("race_id")
        if not rid:
            continue
        if rid in m:
            duplicates.append(rid)
        m[rid] = race
    if duplicates:
        raise EnsembleComparisonError(f"DUPLICATE_RACE_IDS: {sorted(set(duplicates))}")
    return m


def join_by_race_id(new_data: list, leg_data: list) -> dict:
    """Join two profile outputs by race_id.

    Hard-fails (EnsembleComparisonError) if the two race universes differ,
    if either profile's output contains duplicate race_ids, or if either
    profile has no top selection for a race both profiles scored.
    """
    new_map = to_race_map(new_data)
    leg_map = to_race_map(leg_data)

    new_ids = set(new_map)
    leg_ids = set(leg_map)
    live_only = sorted(new_ids - leg_ids)
    legacy_only = sorted(leg_ids - new_ids)

    if live_only or legacy_only:
        raise EnsembleComparisonError(f"RACE_UNIVERSE_MISMATCH: live_only={live_only} legacy_only={legacy_only}")

    shared = sorted(new_ids & leg_ids)
    missing_top: list[str] = []
    for rid in shared:
        if not new_map[rid].get("top"):
            missing_top.append(f"live:{rid}")
        if not leg_map[rid].get("top"):
            missing_top.append(f"legacy:{rid}")
    if missing_top:
        raise EnsembleComparisonError(f"MISSING_TOP_SELECTION: {missing_top}")

    return {
        "new_map": new_map,
        "leg_map": leg_map,
        "shared": shared,
        "live_only": live_only,
        "legacy_only": legacy_only,
        "live_count": len(new_ids),
        "legacy_count": len(leg_ids),
        "shared_count": len(shared),
    }


def _norm_horse(value) -> str:
    return (value or "").strip().lower()


def compute_race_diffs(join: dict) -> list[dict]:
    """Per-race comparison rows for every shared race, ID-joined (never
    positional). Includes agreement flag, tier/exec migration, and VP delta."""
    new_map, leg_map = join["new_map"], join["leg_map"]
    rows = []
    for rid in join["shared"]:
        n_race, l_race = new_map[rid], leg_map[rid]
        n_top, l_top = n_race["top"], l_race["top"]
        n_horse, l_horse = (n_top.get("horse") or "").strip(), (l_top.get("horse") or "").strip()
        n_vp = float(n_top.get("velo_prime_prob") or 0)
        l_vp = float(l_top.get("velo_prime_prob") or 0)
        n_tier, l_tier = n_race.get("tier", "?"), l_race.get("tier", "?")
        n_exec = bool(n_top.get("candidate_execution_allowed", False))
        l_exec = bool(l_top.get("candidate_execution_allowed", False))
        rows.append(
            {
                "race_id": rid,
                "course": n_race.get("course", rid),
                "off_time": n_race.get("off_time", ""),
                "agree": _norm_horse(n_horse) == _norm_horse(l_horse),
                "live_horse": n_horse,
                "legacy_horse": l_horse,
                "live_vp": round(n_vp, 4),
                "legacy_vp": round(l_vp, 4),
                "vp_delta": round(n_vp - l_vp, 4),
                "live_tier": n_tier,
                "legacy_tier": l_tier,
                "tier_migrated": n_tier != l_tier,
                "live_exec": n_exec,
                "legacy_exec": l_exec,
                "exec_migrated": n_exec != l_exec,
            }
        )
    return rows


def summarize_diffs(diff_rows: list[dict]) -> dict:
    n = len(diff_rows)
    agree_n = sum(1 for r in diff_rows if r["agree"])
    abs_deltas = [abs(r["vp_delta"]) for r in diff_rows]
    tier_matrix: dict[str, int] = {}
    exec_matrix: dict[str, int] = {}
    for r in diff_rows:
        tkey = f"{r['live_tier']}->{r['legacy_tier']}"
        tier_matrix[tkey] = tier_matrix.get(tkey, 0) + 1
        ekey = f"{r['live_exec']}->{r['legacy_exec']}"
        exec_matrix[ekey] = exec_matrix.get(ekey, 0) + 1
    return {
        "n": n,
        "agreement_count": agree_n,
        "agreement_rate": round(agree_n / n, 4) if n else 0.0,
        "disagreement_count": n - agree_n,
        "tier_migration_matrix": tier_matrix,
        "execution_migration_matrix": exec_matrix,
        "max_abs_vp_delta": round(max(abs_deltas), 4) if abs_deltas else 0.0,
        "mean_abs_vp_delta": round(statistics.mean(abs_deltas), 4) if abs_deltas else 0.0,
        "median_abs_vp_delta": round(statistics.median(abs_deltas), 4) if abs_deltas else 0.0,
    }


def _analyze(data: list) -> dict:
    vps, tiers, execs = [], [], []
    for race in data:
        top = race.get("top")
        if not top:
            continue
        vps.append(top.get("velo_prime_prob", 0))
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
    }


def _write_report(
    date_str: str,
    new: dict,
    leg: dict,
    join: dict,
    diff_rows: list[dict],
    diff_summary: dict,
    out: Path,
) -> None:
    lines = [
        f"# Ensemble Profile Comparison — {date_str}",
        "",
        f"- Live race count: {join['live_count']}",
        f"- Legacy race count: {join['legacy_count']}",
        f"- Shared race count: {join['shared_count']}",
        f"- Live-only race IDs: {join['live_only'] or '(none)'}",
        f"- Legacy-only race IDs: {join['legacy_only'] or '(none)'}",
        "",
        "| Metric | SQPE_IMPROVEMENT_MDS_V1 (live) | LEGACY_FULL_ENSEMBLE (shadow) |",
        "|---|---|---|",
        f"| Races | {new['n']} | {leg['n']} |",
        f"| Avg VP | {new['avg_vp']} | {leg['avg_vp']} |",
        f"| Median VP | {new['median_vp']} | {leg['median_vp']} |",
        f"| VP ≥ 0.30 | {new['vp30']} ({100 * new['vp30'] / new['n']:.1f}%) | {leg['vp30']} ({100 * leg['vp30'] / leg['n']:.1f}%) |",
        f"| VP ≥ 0.25 | {new['vp25']} ({100 * new['vp25'] / new['n']:.1f}%) | {leg['vp25']} ({100 * leg['vp25'] / leg['n']:.1f}%) |",
        f"| VP ≥ 0.20 | {new['vp20']} ({100 * new['vp20'] / new['n']:.1f}%) | {leg['vp20']} ({100 * leg['vp20'] / leg['n']:.1f}%) |",
        f"| Tier A | {new['tier_a']} | {leg['tier_a']} |",
        f"| Exec allowed | {new['exec_allowed']} | {leg['exec_allowed']} |",
        f"| Top-pick agreement (race_id join) | {diff_summary['agreement_count']}/{diff_summary['n']} ({100 * diff_summary['agreement_rate']:.1f}%) | — |",
        f"| Max abs VP delta | {diff_summary['max_abs_vp_delta']} | — |",
        f"| Mean / median abs VP delta | {diff_summary['mean_abs_vp_delta']} / {diff_summary['median_abs_vp_delta']} | — |",
        "",
        "## Tier Migration Matrix (live -> legacy)",
        "",
        "| Migration | Count |",
        "|---|---:|",
    ]
    for k, v in sorted(diff_summary["tier_migration_matrix"].items()):
        lines.append(f"| {k} | {v} |")

    lines += [
        "",
        "## Execution-Allowed Migration Matrix (live -> legacy)",
        "",
        "| Migration | Count |",
        "|---|---:|",
    ]
    for k, v in sorted(diff_summary["execution_migration_matrix"].items()):
        lines.append(f"| {k} | {v} |")

    lines += [
        "",
        "## Top Selection Differences (race_id-joined, never positional)",
        "",
        "| Race | Course | Off Time | Live top | Shadow top | VP live | VP shadow | Δ VP |",
        "|---|---|---|---|---|---|---|---|",
    ]
    disagreements = [r for r in diff_rows if not r["agree"]]
    for r in disagreements:
        sign = "+" if r["vp_delta"] >= 0 else ""
        lines.append(
            f"| {r['race_id']} | {r['course']} | {r['off_time']} | **{r['live_horse']}** | "
            f"{r['legacy_horse']} | {r['live_vp']:.4f} | {r['legacy_vp']:.4f} | {sign}{r['vp_delta']:.4f} |"
        )
    if not disagreements:
        lines.append("| — | No top-selection changes | — | — | — | — | — | — |")

    lines += [
        "",
        "## VP Distribution — New Profile",
        "",
        f"VP delta (new - legacy avg): {round(new['avg_vp'] - leg['avg_vp'], 4):+}",
        "",
        "| Band | Count | % |",
        "|---|---|---|",
    ]
    vps = [r["live_vp"] for r in diff_rows]
    n_vp = len(vps) or 1
    for lo, hi in [(0, 0.20), (0.20, 0.25), (0.25, 0.30), (0.30, 0.40), (0.40, 1.01)]:
        cnt = sum(1 for v in vps if lo <= v < hi)
        band = f"{lo:.2f}–{hi:.2f}" if hi < 1.01 else "≥ 0.40"
        lines.append(f"| {band} | {cnt} | {100 * cnt / n_vp:.1f}% |")

    lines += [
        "",
        "---",
        f"_Generated by scripts/audit/run_ensemble_shadow_comparison.py — {date_str}_",
    ]

    out.write_text("\n".join(lines))
    print(f"Written: {out}")


_MONITOR_HEADER = [
    "date",
    "live_profile",
    "shadow_profile",
    "races",
    "sr_pct",
    "frame_pct",
    "roi",
    "vp30_n",
    "vp25_n",
    "vp20_n",
    "mds_high_n",
    "improve_high_n",
    "avg_sp",
    "max_drawdown",
    "agreement_count",
    "agreement_rate",
    "disagreement_count",
    "warnings",
]


def _read_monitor_rows(csv_path: Path) -> list[dict]:
    if not csv_path.exists():
        return []
    with open(csv_path, newline="") as f:
        return list(_csv.DictReader(f))


def upsert_monitor_row(csv_path: Path, row: dict) -> None:
    """Idempotent per (date, live_profile, shadow_profile): replaces the
    existing row for that key instead of appending a duplicate."""
    key = (row["date"], row["live_profile"], row["shadow_profile"])
    rows = _read_monitor_rows(csv_path)
    replaced = False
    for i, existing in enumerate(rows):
        if (existing.get("date"), existing.get("live_profile"), existing.get("shadow_profile")) == key:
            rows[i] = row
            replaced = True
            break
    if not replaced:
        rows.append(row)

    with open(csv_path, "w", newline="") as f:
        w = _csv.DictWriter(f, fieldnames=_MONITOR_HEADER)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in _MONITOR_HEADER})
    print(f"Upserted (idempotent): {csv_path}")


def run_comparison(date_str: str, tmp_dir: Path = Path("data")) -> dict:
    """Score both profiles, join by race_id, hard-fail on any correctness
    violation, and return the full comparison payload. Separated from
    main() so it's directly testable without argv/stdout side effects."""
    new_path = tmp_dir / f"_shadow_cmp_new_{date_str.replace('-', '_')}.json"
    leg_path = tmp_dir / f"_shadow_cmp_leg_{date_str.replace('-', '_')}.json"

    print("Scoring with", LIVE_PROFILE, "...")
    new_data = _score_with_profile(date_str, LIVE_PROFILE, new_path)
    new_sha = _sha256_of_file(new_path)

    print("Scoring with", SHADOW_PROFILE, "...")
    leg_data = _score_with_profile(date_str, SHADOW_PROFILE, leg_path)

    # Prove the legacy scoring run did not mutate the live profile's frozen
    # output file (both are written from the same shared backup path
    # sequentially, so this is the concrete check for that).
    _assert_untouched(new_path, new_sha, label=LIVE_PROFILE)

    join = join_by_race_id(new_data, leg_data)
    new_stats = _analyze(new_data)
    leg_stats = _analyze(leg_data)
    diff_rows = compute_race_diffs(join)
    diff_summary = summarize_diffs(diff_rows)

    new_path.unlink(missing_ok=True)
    leg_path.unlink(missing_ok=True)

    return {
        "date": date_str,
        "new_stats": new_stats,
        "leg_stats": leg_stats,
        "join": join,
        "diff_rows": diff_rows,
        "diff_summary": diff_summary,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=str(date.today()), help="YYYY-MM-DD")
    args = parser.parse_args()
    date_str = args.date

    print(f"=== Ensemble Shadow Comparison — {date_str} ===")
    result = run_comparison(date_str)

    out = Path(f"data/ensemble_profile_comparison_{date_str.replace('-', '_')}.md")
    _write_report(
        date_str,
        result["new_stats"],
        result["leg_stats"],
        result["join"],
        result["diff_rows"],
        result["diff_summary"],
        out,
    )

    upsert_monitor_row(
        Path("data/ensemble_profile_monitor_latest.csv"),
        {
            "date": date_str,
            "live_profile": LIVE_PROFILE,
            "shadow_profile": SHADOW_PROFILE,
            "races": result["new_stats"]["n"],
            "sr_pct": "",
            "frame_pct": "",
            "roi": "",
            "vp30_n": result["new_stats"]["vp30"],
            "vp25_n": result["new_stats"]["vp25"],
            "vp20_n": result["new_stats"]["vp20"],
            "mds_high_n": "",
            "improve_high_n": "",
            "avg_sp": "",
            "max_drawdown": "",
            "agreement_count": result["diff_summary"]["agreement_count"],
            "agreement_rate": result["diff_summary"]["agreement_rate"],
            "disagreement_count": result["diff_summary"]["disagreement_count"],
            "warnings": "sr_frame_roi_not_yet_joined_to_results",
        },
    )

    ns, ls, ds = result["new_stats"], result["leg_stats"], result["diff_summary"]
    print(f"\nLive profile:   avg_vp={ns['avg_vp']}, vp30={ns['vp30']}, tier_a={ns['tier_a']}")
    print(f"Shadow legacy:  avg_vp={ls['avg_vp']}, vp30={ls['vp30']}, tier_a={ls['tier_a']}")
    print(f"Top agreement:  {ds['agreement_count']}/{ds['n']} ({100 * ds['agreement_rate']:.1f}%)")
    print(f"Disagreements:  {ds['disagreement_count']}")


if __name__ == "__main__":
    main()
