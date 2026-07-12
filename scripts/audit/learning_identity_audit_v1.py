"""
LEARNING-LOOP-01A — Phase 1: read-only identity/truth audit.

Read-only. No writes to Supabase. No mutation of historical_feature_store,
Playbook G state, or any live scoring artefact.

Measures the real shape of the identity mismatch between prediction-side
tables (runner_prediction_snapshots, historical_feature_store) and
result-side tables (races, race_results, runner_results), so
LEARNING-LOOP-01A's canonical identity resolver (Phase 2) is built against
verified namespaces instead of assumptions.

Outputs:
  - data/reports/learning_identity_audit_v1.json
  - data/reports/learning_identity_audit_v1.md
  - data/reports/learning_identity_unresolved_v1.csv
"""

from __future__ import annotations

import csv
import glob
import json
import os
import re
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from dotenv import load_dotenv

from supabase import create_client

ROOT = Path(__file__).resolve().parent.parent.parent
REPORT_DIR = ROOT / "data" / "reports"
RESULTS_DIR = ROOT / "data" / "results"
OUT_JSON = REPORT_DIR / "learning_identity_audit_v1.json"
OUT_MD = REPORT_DIR / "learning_identity_audit_v1.md"
OUT_UNRESOLVED_CSV = REPORT_DIR / "learning_identity_unresolved_v1.csv"

RUN_TS = datetime.now(UTC).isoformat().replace("+00:00", "Z")

RACE_ID_PATTERNS = [
    ("rac_<digits>", re.compile(r"^rac_\d+$")),
    ("rp_<COURSE>_<YYYYMMDD>_<time>", re.compile(r"^rp_[A-Z0-9]+_\d{8}_\d{1,2}\.\d{2}$")),
    ("numeric", re.compile(r"^\d+$")),
]

HORSE_ID_PATTERNS = [
    ("hrs_rf_<hex>", re.compile(r"^hrs_rf_[0-9a-f]+$")),
    ("hrs_<digits>", re.compile(r"^hrs_\d+$")),
    ("rp_<COURSE>_<slug>", re.compile(r"^rp_[A-Z0-9]+_[a-z0-9_'()]+$")),
    ("numeric", re.compile(r"^\d+$")),
]


def classify(value: str, patterns: list[tuple[str, re.Pattern]]) -> str:
    if not value:
        return "empty"
    for label, pat in patterns:
        if pat.match(str(value)):
            return label
    return "other"


def fetch_all(sb, table: str, fields: str) -> list[dict]:
    rows: list[dict] = []
    offset = 0
    while True:
        batch = sb.table(table).select(fields).range(offset, offset + 999).execute().data
        if not batch:
            break
        rows.extend(batch)
        offset += 1000
        if len(batch) < 1000:
            break
    return rows


def norm_name(name: str) -> str:
    if not name:
        return ""
    name = re.sub(r"\s*\([A-Z]{2,4}\)\s*$", "", name.strip())
    return re.sub(r"[^a-z0-9]", "", name.lower())


def parse_time_to_minutes(value: str) -> int | None:
    if not value:
        return None
    value = str(value).strip()
    m = re.match(r"^(\d{1,2}):(\d{2}):(\d{2})$", value)  # 24h HH:MM:SS
    if m:
        return int(m.group(1)) * 60 + int(m.group(2))
    m = re.match(r"^(\d{1,2})\.(\d{2})$", value)  # racing dot-time, e.g. 1.42 (afternoon)
    if m:
        hh = int(m.group(1))
        if hh < 10:
            hh += 12
        return hh * 60 + int(m.group(2))
    m = re.match(r"^(\d{1,2}):(\d{2})$", value)
    if m:
        return int(m.group(1)) * 60 + int(m.group(2))
    return None


def main() -> None:
    load_dotenv(ROOT / ".env")
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")
    if not url or not key:
        raise SystemExit("SUPABASE_URL and a service key env var are required (read-only audit).")
    sb = create_client(url, key)

    print("Fetching runner_prediction_snapshots ...")
    rps = fetch_all(sb, "runner_prediction_snapshots", "race_id,horse_id,horse,race_date,course,off_time")
    print(f"  {len(rps)} rows")

    print("Fetching historical_feature_store ...")
    hfs = fetch_all(sb, "historical_feature_store", "race_id,horse_id,horse_name,race_date,course")
    print(f"  {len(hfs)} rows")

    print("Fetching races ...")
    races = fetch_all(sb, "races", "race_id,course,date,time")
    print(f"  {len(races)} rows")

    print("Fetching race_results ...")
    race_results = fetch_all(sb, "race_results", "race_id,non_runners,reconciled_at")
    print(f"  {len(race_results)} rows")

    print("Fetching runner_results ...")
    runner_results = fetch_all(sb, "runner_results", "race_id,horse_id,position,sp,sp_dec,is_winner")
    print(f"  {len(runner_results)} rows")

    print("Fetching runners ...")
    runners = fetch_all(sb, "runners", "race_id,horse_id,horse_name")
    print(f"  {len(runners)} rows")

    print("Fetching sigma_audits ...")
    sigma = fetch_all(sb, "sigma_audits", "race_id,date,track")
    print(f"  {len(sigma)} rows")

    print("Fetching velo_verdicts ...")
    verdicts = fetch_all(sb, "velo_verdicts", "race_id,generated_at")
    print(f"  {len(verdicts)} rows")

    # -- namespace classification -----------------------------------------
    def id_format_counts(rows, key, patterns):
        c = Counter(classify(r.get(key), patterns) for r in rows)
        return dict(c)

    namespace_report = {
        "runner_prediction_snapshots": {
            "rows": len(rps),
            "distinct_races": len({r["race_id"] for r in rps if r.get("race_id")}),
            "race_id_formats": id_format_counts(rps, "race_id", RACE_ID_PATTERNS),
            "horse_id_formats": id_format_counts(rps, "horse_id", HORSE_ID_PATTERNS),
        },
        "historical_feature_store": {
            "rows": len(hfs),
            "distinct_races": len({r["race_id"] for r in hfs if r.get("race_id")}),
            "race_id_formats": id_format_counts(hfs, "race_id", RACE_ID_PATTERNS),
            "horse_id_formats": id_format_counts(hfs, "horse_id", HORSE_ID_PATTERNS),
        },
        "races": {
            "rows": len(races),
            "distinct_races": len({r["race_id"] for r in races if r.get("race_id")}),
            "race_id_formats": id_format_counts(races, "race_id", RACE_ID_PATTERNS),
        },
        "race_results": {
            "rows": len(race_results),
            "distinct_races": len({r["race_id"] for r in race_results if r.get("race_id")}),
            "race_id_formats": id_format_counts(race_results, "race_id", RACE_ID_PATTERNS),
        },
        "runner_results": {
            "rows": len(runner_results),
            "distinct_races": len({r["race_id"] for r in runner_results if r.get("race_id")}),
            "race_id_formats": id_format_counts(runner_results, "race_id", RACE_ID_PATTERNS),
            "horse_id_formats": id_format_counts(runner_results, "horse_id", HORSE_ID_PATTERNS),
        },
        "runners": {
            "rows": len(runners),
            "distinct_races": len({r["race_id"] for r in runners if r.get("race_id")}),
            "horse_id_formats": id_format_counts(runners, "horse_id", HORSE_ID_PATTERNS),
        },
        "sigma_audits": {"rows": len(sigma), "distinct_races": len({r["race_id"] for r in sigma if r.get("race_id")})},
        "velo_verdicts": {
            "rows": len(verdicts),
            "distinct_races": len({r["race_id"] for r in verdicts if r.get("race_id")}),
        },
    }

    # -- CRITICAL: Supabase races/race_results/runner_results date coverage
    # stops at 2026-05-06 (Racing API decommission era), while
    # runner_prediction_snapshots only starts 2026-05-20. There is ZERO
    # date overlap between these Supabase tables for the current era --
    # so any race_id or course+date+time join against `races` will resolve
    # 0 rows regardless of ID-format alignment. This is a coverage gap,
    # not (only) a namespace-format gap.
    races_by_date = sorted({r.get("date") for r in races if r.get("date")})
    rps_by_date = sorted({r.get("race_date") for r in rps if r.get("race_date")})
    supabase_coverage_gap = {
        "races_table_max_date": races_by_date[-1] if races_by_date else None,
        "runner_prediction_snapshots_min_date": rps_by_date[0] if rps_by_date else None,
        "date_overlap_days": len(set(races_by_date) & set(rps_by_date)),
        "note": (
            "races/race_results/runner_results in Supabase are not populated for "
            "the era runner_prediction_snapshots covers. The real result-side "
            "source of truth for this era is the local data/results/rp_results_"
            "YYYY_MM_DD.json corpus, which uses the SAME rp_<COURSE>_<YYYYMMDD>_"
            "<time> race_id scheme as runner_prediction_snapshots."
        ),
    }

    # -- real join: runner_prediction_snapshots (Supabase) -> local rp_results_*.json --
    local_race_ids: set[str] = set()
    local_pairs: set[tuple[str, str]] = set()
    local_files = sorted(glob.glob(str(RESULTS_DIR / "rp_results_*.json")))
    for fp in local_files:
        try:
            d = json.loads(Path(fp).read_text(encoding="utf-8"))
        except Exception:
            continue
        results = d.get("results", []) if isinstance(d, dict) else d
        for race in results:
            rid = race.get("race_id")
            if rid:
                local_race_ids.add(rid)
            for runner in race.get("runners", []):
                hid = runner.get("horse_id")
                if rid and hid:
                    local_pairs.add((rid, hid))

    rps_races = {}
    for r in rps:
        rid = r.get("race_id")
        if rid not in rps_races:
            rps_races[rid] = r
    rps_race_ids = set(rps_races)
    rps_pairs = {(r.get("race_id"), r.get("horse_id")) for r in rps if r.get("race_id") and r.get("horse_id")}

    exact_race_join = rps_race_ids & local_race_ids
    exact_pair_join = rps_pairs & local_pairs
    unresolved_rows = []
    unmatched_by_date: Counter = Counter()
    for rid, r in rps_races.items():
        if rid not in local_race_ids:
            date = r.get("race_date")
            unmatched_by_date[date] += 1
            unresolved_rows.append(
                {
                    "race_id": rid,
                    "course": r.get("course"),
                    "date": date,
                    "off_time": r.get("off_time"),
                    "reason": "NO_LOCAL_RESULT_FILE_MATCH",
                    "candidates": 0,
                }
            )

    join_report = {
        "runner_prediction_snapshots_distinct_races": len(rps_races),
        "runner_prediction_snapshots_distinct_race_horse_pairs": len(rps_pairs),
        "local_result_files_scanned": len(local_files),
        "local_distinct_races": len(local_race_ids),
        "local_distinct_race_horse_pairs": len(local_pairs),
        "exact_race_id_join_to_local_results": len(exact_race_join),
        "exact_race_id_join_pct": round(100 * len(exact_race_join) / max(len(rps_races), 1), 1),
        "exact_race_horse_pair_join_to_local_results": len(exact_pair_join),
        "exact_race_horse_pair_join_pct": round(100 * len(exact_pair_join) / max(len(rps_pairs), 1), 1),
        "unresolved_races": len(unresolved_rows),
        "unresolved_by_date": dict(sorted(unmatched_by_date.items())),
        "supabase_races_table_coverage_gap": supabase_coverage_gap,
    }

    # -- feature non-null coverage on historical_feature_store --------------
    coverage_fields = [
        "sp_dec",
        "implied_prob",
        "log_sp",
        "sp_rank",
        "is_fav",
        "or_vs_field",
        "rpr_vs_field",
    ]
    hfs_full = fetch_all(
        sb,
        "historical_feature_store",
        "race_id,horse_id," + ",".join(coverage_fields),
    )
    coverage = {}
    n = len(hfs_full) or 1
    for f in coverage_fields:
        non_null = sum(1 for r in hfs_full if r.get(f) is not None)
        coverage[f] = {"non_null": non_null, "pct": round(100 * non_null / n, 2)}

    report = {
        "run_ts": RUN_TS,
        "mission": "LEARNING-LOOP-01A",
        "phase": 1,
        "read_only": True,
        "namespaces": namespace_report,
        "identity_join": join_report,
        "historical_feature_store_coverage": coverage,
        "classifications": [
            "LEARNING_IDENTITY_AUDITED",
            "NO_HFS_MUTATION",
            "NO_PLAYBOOK_G_MUTATION",
            "NO_LIVE_SCORING_CHANGE",
            "NO_MODEL_TRAINING",
            "NO_MODEL_PROMOTION",
            "NO_SUPABASE_WRITES",
            "NO_TELEGRAM_SEND",
        ],
    }

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

    with open(OUT_UNRESOLVED_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["race_id", "course", "date", "off_time", "reason", "candidates"])
        w.writeheader()
        for row in unresolved_rows:
            w.writerow(row)

    md_lines = [
        "# Learning Identity Audit V1 (LEARNING-LOOP-01A Phase 1)",
        "",
        f"Run: {RUN_TS}",
        "",
        "## Table row/race counts",
        "",
        "| table | rows | distinct races |",
        "|---|---|---|",
    ]
    for t, d in namespace_report.items():
        md_lines.append(f"| {t} | {d['rows']} | {d.get('distinct_races', '-')} |")
    md_lines += [
        "",
        "## Race-ID namespace formats",
        "",
    ]
    for t, d in namespace_report.items():
        if "race_id_formats" in d:
            md_lines.append(f"- **{t}**: {d['race_id_formats']}")
    md_lines += [
        "",
        "## Identity join (runner_prediction_snapshots -> results)",
        "",
    ]
    for k, v in join_report.items():
        md_lines.append(f"- {k}: {v}")
    md_lines += [
        "",
        "## historical_feature_store non-null coverage",
        "",
        "| field | non_null | pct |",
        "|---|---|---|",
    ]
    for f, d in coverage.items():
        md_lines.append(f"| {f} | {d['non_null']} | {d['pct']}% |")
    md_lines += ["", "## Classifications", ""]
    for c in report["classifications"]:
        md_lines.append(f"- {c}")

    OUT_MD.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    print()
    print("=== Identity join summary ===")
    for k, v in join_report.items():
        print(f"  {k}: {v}")
    print()
    print(f"Written: {OUT_JSON}")
    print(f"Written: {OUT_MD}")
    print(f"Written: {OUT_UNRESOLVED_CSV}")


if __name__ == "__main__":
    main()
