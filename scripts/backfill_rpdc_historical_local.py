"""
backfill_rpdc_historical_local.py
-----------------------------------
Builds RPDC release candidate tags for all horses across all scored dates,
using ONLY local results files as the data source.

LOCAL ONLY — no Supabase reads or writes. Safe to run at any time.

Algorithm:
  1. Parse all local results files → build full horse career history
  2. For each scored date (verdict file exists):
     a. For each horse in that date's results:
        - Filter history to runs STRICTLY before that date
        - Compute RPDC tags using same logic as build_rpdc_daily.py
        - Compute trainer stats from local results window
  3. Write one JSONL row per horse per scored date

Outputs:
  data/rpdc_backfill/rpdc_tags_historical.jsonl     — primary artifact
  data/reports/rpdc_backfill_historical_latest.json — summary report
  data/reports/rpdc_backfill_historical_latest.md   — human-readable report

Usage:
  source venv/bin/activate
  PYTHONPATH=. python scripts/backfill_rpdc_historical_local.py
  PYTHONPATH=. python scripts/backfill_rpdc_historical_local.py --date 2026-05-07  # single date
  PYTHONPATH=. python scripts/backfill_rpdc_historical_local.py --dry-run          # no writes
"""
import argparse
import json
import logging
import re
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

log = logging.getLogger("velo.rpdc_backfill")
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

DATA_DIR = ROOT / "data"
BACKFILL_DIR = DATA_DIR / "rpdc_backfill"
REPORTS_DIR = DATA_DIR / "reports"

TAG_WEIGHTS = {
    "MARK_READY":             3.0,
    "BELOW_LAST_WIN_MARK":    2.0,
    "MARK_NEAR":              1.5,
    "CYCLE_RUN_1":            1.0,
    "CYCLE_RUN_2":            1.2,
    "CYCLE_RUN_3":            1.3,
    "FRESH_RETURN":           1.5,
    "LONG_ABSENCE":          -0.5,
    "STABLE_WARM":            1.0,
    "COURSE_RETURN":          1.2,
    "DISTANCE_RETURN":        1.0,
    "WIN_STREAK":             1.5,
    "PLACE_FORM":             0.8,
}
CASH_WINDOW_THRESHOLD = 3.0

_DATE_TAG_RE = re.compile(r"(\d{4})_(\d{2})_(\d{2})")


def _extract_date(filename: str) -> str | None:
    m = _DATE_TAG_RE.search(filename)
    return f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else None


def _to_int(v) -> int | None:
    try:
        return int(float(str(v).strip()))
    except (TypeError, ValueError):
        return None


def _to_float(v) -> float | None:
    try:
        f = float(str(v).replace("f", "").strip())
        return f if f > 0 else None
    except (TypeError, ValueError):
        return None


def _position_int(pos) -> int | None:
    try:
        return int(float(str(pos).split()[0]))
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Step 1 — load all local results into memory
# ---------------------------------------------------------------------------

def load_all_results() -> tuple[
    dict[str, list[dict]],   # horse_history[horse_id] = [run_dicts] sorted newest first
    dict[str, list[dict]],   # trainer_history[trainer_id] = [run_dicts]
    dict[str, list[dict]],   # results_by_date[date_str] = [race_dicts]
    list[str],               # source_files used
]:
    """
    Reads all results_YYYY_MM_DD.json files.
    Returns horse history, trainer history, and results indexed by date.
    Each run dict contains normalised fields compatible with compute_rpdc().
    """
    horse_history: dict[str, list[dict]] = defaultdict(list)
    trainer_history: dict[str, list[dict]] = defaultdict(list)
    results_by_date: dict[str, list[dict]] = {}
    source_files: list[str] = []

    results_paths = sorted(DATA_DIR.glob("results_*.json"))
    for path in results_paths:
        if "partial" in path.name:
            continue
        date_str = _extract_date(path.name)
        if not date_str:
            continue
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            log.warning("Failed to load %s: %s", path.name, e)
            continue

        races = raw.get("results", []) if isinstance(raw, dict) else raw
        if not isinstance(races, list):
            continue

        race_dicts: list[dict] = []
        for race in races:
            race_id = race.get("race_id", "")
            course_id = str(race.get("course_id", ""))
            course = race.get("course", "")
            dist_f = _to_float(race.get("dist_f"))
            race_class = _to_int(race.get("race_class") or race.get("class"))

            for runner in (race.get("runners") or []):
                horse_id = runner.get("horse_id", "")
                if not horse_id:
                    continue
                pos_raw = runner.get("position")
                pos_int = _position_int(pos_raw)
                is_win = pos_int == 1
                is_place = pos_int is not None and pos_int <= 3
                official_rating = _to_int(runner.get("or"))
                trainer_id = runner.get("trainer_id", "")
                jockey_id = runner.get("jockey_id", "")

                run = {
                    "run_date": date_str,
                    "race_id": race_id,
                    "course_id": course_id,
                    "course": course,
                    "distance_f": dist_f,
                    "race_class": race_class,
                    "position_int": pos_int,
                    "is_win": is_win,
                    "is_place": is_place,
                    "official_rating": official_rating,
                    "horse_id": horse_id,
                    "horse": runner.get("horse", ""),
                    "trainer_id": trainer_id,
                    "trainer": runner.get("trainer", ""),
                    "jockey_id": jockey_id,
                }
                horse_history[horse_id].append(run)
                if trainer_id:
                    trainer_history[trainer_id].append(run)

            race_dicts.append({
                "race_id": race_id,
                "course_id": course_id,
                "course": course,
                "dist_f": dist_f,
                "runners": [
                    {
                        "horse_id": r.get("horse_id", ""),
                        "horse": r.get("horse", ""),
                        "trainer_id": r.get("trainer_id", ""),
                        "trainer": r.get("trainer", ""),
                        "or": _to_int(r.get("or")),
                    }
                    for r in (race.get("runners") or [])
                    if r.get("horse_id")
                ],
            })

        results_by_date[date_str] = race_dicts
        source_files.append(path.name)

    # Sort each horse's history newest-first
    for hid in horse_history:
        horse_history[hid].sort(key=lambda r: r["run_date"], reverse=True)
    for tid in trainer_history:
        trainer_history[tid].sort(key=lambda r: r["run_date"], reverse=True)

    log.info(
        "Loaded %d result dates, %d unique horses, %d trainers",
        len(results_by_date), len(horse_history), len(trainer_history),
    )
    return dict(horse_history), dict(trainer_history), results_by_date, source_files


# ---------------------------------------------------------------------------
# Step 2 — per-date history slicing
# ---------------------------------------------------------------------------

def _horse_history_before(
    horse_id: str,
    all_history: dict[str, list[dict]],
    before_date: str,
    max_runs: int = 20,
) -> list[dict]:
    """Returns up to max_runs of horse's runs strictly before before_date, newest first."""
    return [
        r for r in all_history.get(horse_id, [])
        if r["run_date"] < before_date
    ][:max_runs]


def _trainer_stats_before(
    trainer_id: str,
    all_history: dict[str, list[dict]],
    before_date: str,
    window_days: int = 30,
) -> dict:
    """Trainer win rate in the window_days before before_date, from local results."""
    cutoff_date = (date.fromisoformat(before_date) - timedelta(days=window_days)).isoformat()
    runs = [
        r for r in all_history.get(trainer_id, [])
        if cutoff_date <= r["run_date"] < before_date
    ]
    if not runs:
        return {"runs": 0, "wins": 0, "places": 0, "win_rate": 0.0}
    wins = sum(1 for r in runs if r.get("is_win"))
    places = sum(1 for r in runs if r.get("is_place"))
    return {
        "runs": len(runs),
        "wins": wins,
        "places": places,
        "win_rate": round(wins / len(runs) * 100, 1),
    }


# ---------------------------------------------------------------------------
# Step 3 — compute RPDC (identical logic to build_rpdc_daily.compute_rpdc)
# ---------------------------------------------------------------------------

def compute_rpdc_local(
    horse_id: str,
    race_id: str,
    horse: str,
    trainer_id: str,
    current_or: int | None,
    today_course_id: str,
    today_dist_f: float | None,
    today_str: str,
    history: list[dict],
    trainer_stats: dict,
) -> dict:
    """
    Compute RPDC tags from local history (no Supabase).
    Mirrors build_rpdc_daily.compute_rpdc exactly.
    """
    tags: list[str] = []
    score = 0.0

    def add_tag(name: str) -> None:
        nonlocal score
        tags.append(name)
        score += TAG_WEIGHTS.get(name, 0.5)

    today = date.fromisoformat(today_str)
    current_year = today.year

    last_run_date = None
    days_since_run = None
    campaign_run_no = 0
    runs_since_win = 0
    runs_since_place = 0
    last_winning_or = None
    found_win = False
    found_place = False
    win_count_recent = 0
    last_course_id = None
    last_dist_f = None

    for i, run in enumerate(history):
        rd = run.get("run_date")
        if rd and last_run_date is None:
            last_run_date = rd
            try:
                days_since_run = (today - date.fromisoformat(rd)).days
            except ValueError:
                pass

        if rd:
            try:
                if date.fromisoformat(rd).year == current_year:
                    campaign_run_no += 1
            except ValueError:
                pass

        if not found_win:
            if run.get("is_win"):
                found_win = True
                last_winning_or = run.get("official_rating")
            else:
                runs_since_win += 1

        if not found_place:
            if run.get("is_place"):
                found_place = True
            else:
                runs_since_place += 1

        if last_course_id is None:
            last_course_id = run.get("course_id")
        if last_dist_f is None:
            last_dist_f = run.get("distance_f")

        if run.get("is_win") and i < 5:
            win_count_recent += 1

    or_delta_to_win = None
    if current_or is not None and last_winning_or is not None:
        try:
            or_delta_to_win = int(current_or) - int(last_winning_or)
        except (TypeError, ValueError):
            pass

    class_delta = None
    if history and current_or is not None and history[0].get("official_rating"):
        try:
            class_delta = int(current_or) - int(history[0]["official_rating"])
        except (TypeError, ValueError):
            pass

    course_return_flag = (
        today_course_id is not None
        and any(r.get("course_id") == today_course_id and r.get("is_win") for r in history)
    )

    distance_revert_flag = (
        today_dist_f is not None
        and last_dist_f is not None
        and abs(float(today_dist_f) - float(last_dist_f)) > 0.5
        and any(
            r.get("distance_f") is not None
            and abs(float(r["distance_f"]) - float(today_dist_f)) <= 0.5
            and r.get("is_win")
            for r in history
        )
    )

    stable_heat = trainer_stats.get("win_rate", 0.0)

    # Tags
    if or_delta_to_win is not None:
        if or_delta_to_win <= 0:
            add_tag("MARK_READY")
            if or_delta_to_win < 0:
                add_tag("BELOW_LAST_WIN_MARK")
        elif or_delta_to_win <= 3:
            add_tag("MARK_NEAR")

    if campaign_run_no == 1:
        add_tag("CYCLE_RUN_1")
    elif campaign_run_no == 2:
        add_tag("CYCLE_RUN_2")
    elif campaign_run_no == 3:
        add_tag("CYCLE_RUN_3")

    if days_since_run is not None:
        if 22 <= days_since_run <= 45:
            add_tag("FRESH_RETURN")
        elif days_since_run > 90:
            add_tag("LONG_ABSENCE")

    if stable_heat >= 15.0:
        add_tag("STABLE_WARM")

    if course_return_flag:
        add_tag("COURSE_RETURN")

    if distance_revert_flag:
        add_tag("DISTANCE_RETURN")

    if win_count_recent >= 2:
        add_tag("WIN_STREAK")

    if found_place and runs_since_place == 0 and not found_win:
        add_tag("PLACE_FORM")

    suppression_score = 0.0
    if or_delta_to_win is not None and or_delta_to_win > 10:
        suppression_score += 1.5
    if days_since_run is not None and days_since_run > 180:
        suppression_score += 1.0

    rpdc_cash_window_flag = score >= CASH_WINDOW_THRESHOLD
    primary_tag = tags[0] if tags else None

    prior_runs_count = len(history)
    provenance = "LOCAL_HISTORY_ONLY"
    if prior_runs_count == 0:
        provenance = "NO_PRIOR_HISTORY"

    return {
        "horse_id": horse_id,
        "horse": horse,
        "race_date": today_str,
        "race_id": race_id,
        "course_id": today_course_id,
        "current_or": current_or,
        "trainer_id": trainer_id,
        "prior_runs_count": prior_runs_count,
        "days_since_run": days_since_run,
        "campaign_run_no": campaign_run_no,
        "or_delta_to_win": or_delta_to_win,
        "class_delta": class_delta,
        "course_return_flag": course_return_flag,
        "distance_revert_flag": distance_revert_flag,
        "stable_heat": stable_heat,
        "rpdc_tags": tags,
        "rpdc_tag_count": len(tags),
        "rpdc_release_score": round(score, 2),
        "rpdc_primary_tag": primary_tag,
        "rpdc_cash_window_flag": rpdc_cash_window_flag,
        "rpdc_suppression_score": round(suppression_score, 2),
        "provenance_status": provenance,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Main backfill
# ---------------------------------------------------------------------------

def run_backfill(
    target_date: str | None = None,
    dry_run: bool = False,
) -> dict:
    print()
    print("=" * 60)
    print("RPDC LOCAL HISTORICAL BACKFILL")
    if dry_run:
        print("  DRY RUN — no files will be written")
    if target_date:
        print(f"  Target date: {target_date}")
    print("=" * 60)

    # Discover scored dates (verdict files)
    verdict_dates: list[str] = []
    for p in sorted(DATA_DIR.glob("velo_prime_verdicts_*.json")):
        d = _extract_date(p.name)
        if d and (target_date is None or d == target_date):
            verdict_dates.append(d)

    # For each scored date, we also need the race/runner data from results
    if not verdict_dates:
        print("  No verdict files found for the target date range.")
        return {}

    log.info("Scored dates to process: %d", len(verdict_dates))

    # Load ALL results into memory (needed for history)
    horse_all, trainer_all, results_by_date, source_files = load_all_results()

    BACKFILL_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    output_path = BACKFILL_DIR / "rpdc_tags_historical.jsonl"
    summary_json_path = REPORTS_DIR / "rpdc_backfill_historical_latest.json"
    summary_md_path = REPORTS_DIR / "rpdc_backfill_historical_latest.md"

    all_rows: list[dict] = []
    dates_processed: list[str] = []
    dates_skipped: list[str] = []
    tag_counter: dict[str, int] = {}
    cash_window_count = 0
    no_history_count = 0
    total_runner_count = 0
    unique_horses: set[str] = set()

    for scored_date in verdict_dates:
        if scored_date not in results_by_date:
            log.warning("No results file for scored date %s — skipping", scored_date)
            dates_skipped.append(scored_date)
            continue

        races = results_by_date[scored_date]
        date_rows: list[dict] = []

        for race in races:
            race_id = race.get("race_id", "")
            course_id = race.get("course_id", "")
            dist_f = race.get("dist_f")

            for runner in (race.get("runners") or []):
                horse_id = runner.get("horse_id", "")
                if not horse_id:
                    continue

                history = _horse_history_before(horse_id, horse_all, scored_date)
                trainer_stats = _trainer_stats_before(
                    runner.get("trainer_id", ""), trainer_all, scored_date
                )

                row = compute_rpdc_local(
                    horse_id=horse_id,
                    race_id=race_id,
                    horse=runner.get("horse", ""),
                    trainer_id=runner.get("trainer_id", ""),
                    current_or=runner.get("or"),
                    today_course_id=course_id,
                    today_dist_f=dist_f,
                    today_str=scored_date,
                    history=history,
                    trainer_stats=trainer_stats,
                )
                date_rows.append(row)
                unique_horses.add(horse_id)
                if not history:
                    no_history_count += 1
                if row["rpdc_cash_window_flag"]:
                    cash_window_count += 1
                for tag in row["rpdc_tags"]:
                    tag_counter[tag] = tag_counter.get(tag, 0) + 1

        all_rows.extend(date_rows)
        total_runner_count += len(date_rows)
        dates_processed.append(scored_date)
        log.info(
            "  %s — %d runners, %d tagged",
            scored_date,
            len(date_rows),
            sum(1 for r in date_rows if r["rpdc_tag_count"] > 0),
        )

    if not dry_run:
        # Write JSONL (append-safe: if target_date, append; otherwise full rewrite)
        if target_date and output_path.exists():
            existing = []
            with open(output_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        r = json.loads(line)
                        if r.get("race_date") != target_date:
                            existing.append(r)
                    except json.JSONDecodeError:
                        pass
            merged = existing + all_rows
            with open(output_path, "w", encoding="utf-8") as f:
                for row in merged:
                    f.write(json.dumps(row, default=str) + "\n")
            log.info("Updated JSONL (merged): %d total rows → %s", len(merged), output_path)
        else:
            with open(output_path, "w", encoding="utf-8") as f:
                for row in all_rows:
                    f.write(json.dumps(row, default=str) + "\n")
            log.info("Wrote JSONL: %d rows → %s", len(all_rows), output_path)

    # Build summary
    tag_sorted = sorted(tag_counter.items(), key=lambda x: -x[1])
    run_ts = datetime.now(timezone.utc).isoformat()

    summary = {
        "generated_at": run_ts,
        "dry_run": dry_run,
        "source_files_used": len(source_files),
        "dates_processed": len(dates_processed),
        "dates_skipped": len(dates_skipped),
        "dates_skipped_list": dates_skipped,
        "total_runner_rows": total_runner_count,
        "unique_horses": len(unique_horses),
        "runners_with_no_prior_history": no_history_count,
        "runners_with_cash_window": cash_window_count,
        "cash_window_pct": round(cash_window_count / total_runner_count * 100, 1) if total_runner_count else 0,
        "tag_distribution": dict(tag_sorted),
        "date_range": {
            "first": dates_processed[0] if dates_processed else None,
            "last": dates_processed[-1] if dates_processed else None,
        },
        "output_file": str(output_path) if not dry_run else None,
    }

    if not dry_run:
        summary_json_path.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
        _write_summary_md(summary_md_path, summary)

    _print_summary(summary)
    return summary


def _write_summary_md(path: Path, s: dict) -> None:
    lines = [
        "# RPDC Local Historical Backfill Report",
        "",
        f"**Generated:** {s['generated_at']}  ",
        f"**Dry run:** {s['dry_run']}  ",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Dates processed | {s['dates_processed']} |",
        f"| Dates skipped (no results) | {s['dates_skipped']} |",
        f"| Date range | {s['date_range']['first']} → {s['date_range']['last']} |",
        f"| Total runner rows | {s['total_runner_rows']:,} |",
        f"| Unique horses | {s['unique_horses']:,} |",
        f"| Runners with no prior history | {s['runners_with_no_prior_history']:,} |",
        f"| Runners with cash window | {s['runners_with_cash_window']:,} ({s['cash_window_pct']}%) |",
        f"| Source result files | {s['source_files_used']} |",
        "",
        "## Tag Distribution",
        "",
        "| Tag | Count |",
        "|---|---|",
    ]
    for tag, count in s["tag_distribution"].items():
        lines.append(f"| `{tag}` | {count} |")

    if s["dates_skipped_list"]:
        lines += [
            "",
            "## Skipped Dates (no results file)",
            "",
        ]
        for d in s["dates_skipped_list"]:
            lines.append(f"- {d}")

    lines += [
        "",
        "---",
        "",
        "```",
        f"BACKFILL_STATUS:        COMPLETE",
        f"DRY_RUN:                {s['dry_run']}",
        f"SUPABASE_WRITES:        NONE — local artifact only",
        f"ROWS_WRITTEN:           {s['total_runner_rows']:,}",
        f"CASH_WINDOW_PCT:        {s['cash_window_pct']}%",
        "```",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def _print_summary(s: dict) -> None:
    print()
    print("BACKFILL COMPLETE" if not s.get("dry_run") else "DRY RUN COMPLETE")
    print(f"  Dates processed:        {s['dates_processed']}")
    print(f"  Dates skipped:          {s['dates_skipped']}")
    print(f"  Date range:             {s['date_range']['first']} → {s['date_range']['last']}")
    print(f"  Total runner rows:      {s['total_runner_rows']:,}")
    print(f"  Unique horses:          {s['unique_horses']:,}")
    print(f"  No prior history:       {s['runners_with_no_prior_history']:,}")
    print(f"  Cash window (≥{CASH_WINDOW_THRESHOLD}):     {s['runners_with_cash_window']:,} ({s['cash_window_pct']}%)")
    print()
    print("Tag distribution (top 10):")
    for tag, count in list(s["tag_distribution"].items())[:10]:
        print(f"  {tag:<30} {count:>6}")
    if not s.get("dry_run") and s.get("output_file"):
        print()
        print(f"Output → {s['output_file']}")
        print(f"Report → data/reports/rpdc_backfill_historical_latest.json")
        print(f"Report → data/reports/rpdc_backfill_historical_latest.md")


def main() -> None:
    parser = argparse.ArgumentParser(description="Local RPDC historical backfill")
    parser.add_argument("--date", help="Process a single date only (YYYY-MM-DD)")
    parser.add_argument("--dry-run", action="store_true", help="Compute but do not write output")
    args = parser.parse_args()
    run_backfill(target_date=args.date, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
