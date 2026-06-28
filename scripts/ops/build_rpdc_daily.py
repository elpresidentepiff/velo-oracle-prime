"""
build_rpdc_daily.py
--------------------
Computes RPDC release candidate tags for each horse in today's racecards
and writes to runner_release_candidates.

Run BEFORE run_prime_today.py so RPDC data is available at scoring time.
Depends on racing_horse_runs being current (run ingest_results_to_horse_runs.py
the night before to keep it up to date).

Usage:
  source venv/bin/activate
  PYTHONPATH=. python scripts/build_rpdc_daily.py --date YYYY-MM-DD
"""
import argparse
import json
import logging
import os
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(ROOT / ".env")

log = logging.getLogger("velo.build_rpdc_daily")
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")

SB_URL = os.getenv("SUPABASE_URL", "")
SB_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY", "")
SB_HEADERS = {
    "apikey": SB_KEY,
    "Authorization": f"Bearer {SB_KEY}",
    "Content-Type": "application/json",
    "Accept": "application/json",
}

# Tag weights (match the live RPDC scoring)
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

CASH_WINDOW_THRESHOLD = 3.0   # release_score >= this → cash_window=True


def _to_float(v) -> float | None:
    try:
        f = float(str(v).replace("f", "").strip())
        return f if f > 0 else None
    except (TypeError, ValueError):
        return None


def _to_int(v) -> int | None:
    try:
        return int(float(str(v).strip()))
    except (TypeError, ValueError):
        return None


def _resolve_injection_path(date_str: str, injection_path: str | Path | None = None) -> Path | None:
    """Resolve exactly one injection source for the RPDC build."""
    if injection_path:
        path = Path(injection_path)
        if not path.is_absolute():
            path = ROOT / path
        return path.resolve()

    candidates = list(
        (ROOT / "data" / "racing_post_account_parsed").glob(
            f"*{date_str}*/racecard_injection.json"
        )
    )
    if not candidates:
        return None
    # File recency is authoritative. Lexicographic path order is unsafe on Windows.
    return max(candidates, key=lambda path: (path.stat().st_mtime_ns, path.parent.name))


def _load_injection_runners(injection_path: Path) -> tuple[list[dict], set[str]]:
    """Load active runners and their race identities from an RP injection."""
    injection = json.loads(injection_path.read_text(encoding="utf-8"))
    runners: list[dict] = []
    race_ids: set[str] = set()
    for race in injection.get("races") or []:
        race_id = str(race.get("race_id") or "").strip()
        if not race_id:
            continue
        race_ids.add(race_id)
        course_id = str(race.get("course_id") or "")
        dist_f = _to_float(race.get("distance_furlongs"))
        for runner in race.get("runners") or []:
            if runner.get("non_runner"):
                continue
            horse_id = str(runner.get("horse_id") or "").strip()
            if not horse_id:
                continue
            runners.append({
                "horse_id": horse_id,
                "horse": runner.get("horse", ""),
                "race_id": race_id,
                "trainer_id": str(runner.get("trainer_id") or ""),
                "trainer": runner.get("trainer", ""),
                "current_or": _to_int(runner.get("official_rating")),
                "course_id": course_id,
                "dist_f": dist_f,
            })
    return runners, race_ids


def _sb_get(path: str) -> list[dict]:
    if not SB_URL or not SB_KEY:
        return []
    url = f"{SB_URL}/rest/v1{path}"
    req = urllib.request.Request(url, headers=SB_HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        log.warning("sb_get failed for %s: %s", path, e)
        return []


def _sb_upsert(path: str, rows: list[dict], conflict: str) -> int:
    if not rows or not SB_URL or not SB_KEY:
        return 0
    url = f"{SB_URL}/rest/v1{path}?on_conflict={conflict}"
    body = json.dumps(rows).encode()
    headers = {**SB_HEADERS, "Prefer": "resolution=merge-duplicates,return=minimal"}
    req = urllib.request.Request(url, data=body, headers=headers)
    try:
        urllib.request.urlopen(req, timeout=30)
        return len(rows)
    except urllib.error.HTTPError as e:
        err_body = e.read().decode(errors="replace")[:500]
        log.warning("sb_upsert failed (%d rows): HTTP %s — %s", len(rows), e.code, err_body)
        return 0
    except Exception as e:
        log.warning("sb_upsert failed (%d rows): %s", len(rows), e)
        return 0


def _sb_delete(path: str) -> bool:
    if not SB_URL or not SB_KEY:
        return False
    url = f"{SB_URL}/rest/v1{path}"
    headers = {**SB_HEADERS, "Prefer": "return=minimal"}
    req = urllib.request.Request(url, headers=headers, method="DELETE")
    try:
        urllib.request.urlopen(req, timeout=30)
        return True
    except Exception as exc:
        log.error("sb_delete failed for %s: %s", path, exc)
        return False


def _fetch_horse_history(horse_id: str, horse_name: str = "") -> list[dict]:
    """Fetch last 20 runs for a horse, ordered newest first.

    racing_horse_runs uses a name-based horse_id format (rp_{COURSE}_{name})
    while racecard injection uses numeric IDs — so we fall back to horse-name
    lookup when the ID query returns nothing.
    """
    _fields = (
        "run_date,official_rating,race_class,course,course_id"
        ",distance_f,position_int,is_win,is_place,headgear,jockey_id,trainer_id"
    )
    rows = _sb_get(
        f"/racing_horse_runs?horse_id=eq.{horse_id}"
        f"&order=run_date.desc&limit=20&select={_fields}"
    )
    if not rows and horse_name:
        # Horse_id format mismatch — fall back to name match (URL-encode the name)
        encoded_name = urllib.parse.quote(horse_name, safe="")
        rows = _sb_get(
            f"/racing_horse_runs?horse=ilike.{encoded_name}"
            f"&order=run_date.desc&limit=20&select={_fields}"
        )
    return rows


def _trainer_stats(trainer_id: str, today_str: str, trainer_name: str = "") -> dict:
    """Compute trainer win/place rate over last 30 days from racing_horse_runs.

    racing_horse_runs.trainer_id is empty for RP-sourced rows; falls back to
    trainer name lookup when the ID query returns nothing.
    """
    cutoff = (date.fromisoformat(today_str) - timedelta(days=30)).isoformat()
    rows = _sb_get(
        f"/racing_horse_runs?trainer_id=eq.{trainer_id}"
        f"&run_date=gte.{cutoff}"
        f"&select=is_win,is_place"
    )
    if not rows and trainer_name:
        encoded = urllib.parse.quote(trainer_name, safe="")
        rows = _sb_get(
            f"/racing_horse_runs?trainer=ilike.{encoded}"
            f"&run_date=gte.{cutoff}"
            f"&select=is_win,is_place"
        )
    if not rows:
        return {"runs": 0, "wins": 0, "places": 0, "win_rate": 0.0}
    wins = sum(1 for r in rows if r.get("is_win"))
    places = sum(1 for r in rows if r.get("is_place"))
    return {
        "runs": len(rows),
        "wins": wins,
        "places": places,
        "win_rate": round(wins / len(rows) * 100, 1) if rows else 0.0,
    }


def compute_rpdc(
    horse_id: str,
    race_id: str,
    horse: str,
    trainer_id: str,
    trainer: str,
    current_or: int | None,
    today_course_id: str,
    today_dist_f: float | None,
    today_str: str,
    history: list[dict],
    trainer_stats: dict,
) -> dict:
    """
    Compute RPDC release candidate fields for one runner.
    Returns a dict ready for runner_release_candidates upsert.
    """
    tags: list[str] = []
    score = 0.0

    def add_tag(name: str):
        nonlocal score
        tags.append(name)
        score += TAG_WEIGHTS.get(name, 0.5)

    today = date.fromisoformat(today_str)

    # ── Run history derived values ────────────────────────────────────────────
    last_run_date = None
    days_since_run = None
    campaign_run_no = 0       # runs in current year
    runs_since_win = 0
    runs_since_place = 0
    last_winning_or = None
    last_course_id = None
    last_dist_f = None
    found_win = False
    found_place = False

    current_year = today.year
    win_count_recent = 0

    for i, run in enumerate(history):
        rd = run.get("run_date")
        if rd and last_run_date is None:
            last_run_date = rd
            try:
                delta = (today - date.fromisoformat(rd)).days
                days_since_run = delta
            except ValueError:
                pass

        if rd:
            try:
                if date.fromisoformat(rd).year == current_year:
                    campaign_run_no += 1
            except ValueError:
                pass

        pos = run.get("position_int")
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

    # ── OR delta ─────────────────────────────────────────────────────────────
    or_delta_to_win = None
    if current_or is not None and last_winning_or is not None:
        try:
            or_delta_to_win = int(current_or) - int(last_winning_or)
        except (TypeError, ValueError):
            pass

    # ── Class delta ───────────────────────────────────────────────────────────
    class_delta = None
    if history and current_or is not None and history[0].get("official_rating"):
        try:
            class_delta = int(current_or) - int(history[0]["official_rating"])
        except (TypeError, ValueError):
            pass

    # ── Flags ─────────────────────────────────────────────────────────────────
    # course_id is empty in RP-sourced racing_horse_runs rows — fall back to
    # course name match (today_course_id often IS the short course name from injection)
    def _course_match(run: dict) -> bool:
        if today_course_id and run.get("course_id") == today_course_id:
            return True
        if today_course_id and run.get("course", "").lower() == today_course_id.lower():
            return True
        return False

    course_return_flag = bool(
        today_course_id
        and any(_course_match(r) and r.get("is_win") for r in history)
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

    jockey_upgrade_flag = False  # requires booking data, not available here

    stable_heat = trainer_stats.get("win_rate", 0.0)

    # ── Tag computation ───────────────────────────────────────────────────────
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

    if runs_since_place is not None and runs_since_place == 0 and not found_win:
        add_tag("PLACE_FORM")

    # ── Suppression score ─────────────────────────────────────────────────────
    suppression_score = 0.0
    if or_delta_to_win is not None and or_delta_to_win > 10:
        suppression_score += 1.5
    if days_since_run is not None and days_since_run > 180:
        suppression_score += 1.0

    rpdc_trap_flag = suppression_score >= 2.0
    rpdc_cash_window_flag = score >= CASH_WINDOW_THRESHOLD

    return {
        "run_date": today_str,
        "race_id": race_id,
        "horse_id": horse_id,
        "horse": horse,
        "trainer_id": trainer_id,
        "trainer": trainer,
        "current_or": current_or,
        "or_delta_to_win": or_delta_to_win,
        "runs_since_win": runs_since_win,
        "runs_since_place": runs_since_place,
        "campaign_run_no": campaign_run_no,
        "days_since_run": days_since_run,
        "class_delta": class_delta,
        "distance_revert_flag": distance_revert_flag,
        "course_return_flag": course_return_flag,
        "jockey_upgrade_flag": jockey_upgrade_flag,
        "stable_heat": stable_heat,
        "market_position": None,
        "rpdc_tag_count": len(tags),
        "rpdc_release_score": round(score, 2),
        "rpdc_suppression_score": round(suppression_score, 2),
        "rpdc_cash_window_flag": rpdc_cash_window_flag,
        "rpdc_trap_flag": rpdc_trap_flag,
        "rpdc_tags": tags,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def build_rpdc_for_date(date_str: str, injection_path: str | Path | None = None) -> bool:
    print(f"\nBUILD RPDC DAILY — {date_str}")
    print("=" * 60)

    # ── Gate 5: RPDC_COVERAGE_WARN ────────────────────────────────────────────
    _latest_rrc = _sb_get(
        "/runner_release_candidates?order=run_date.desc&limit=1&select=run_date"
    )
    if _latest_rrc:
        _latest_rrc_date = _latest_rrc[0].get("run_date", "")
        try:
            _staleness = (date.fromisoformat(date_str) - date.fromisoformat(_latest_rrc_date)).days
        except (ValueError, TypeError):
            _staleness = None
        if _staleness is not None and _staleness > 1:
            print(
                f"\n⚠ RPDC_COVERAGE_WARN\n"
                f"  runner_release_candidates last updated: {_latest_rrc_date} ({_staleness} days stale)\n"
                f"  RPDC context will be absent from scoring if chain not repaired.\n"
                f"  Repair: ingest_results_to_horse_runs.py --date "
                f"{(date.fromisoformat(date_str) - timedelta(days=1)).isoformat()}"
            )
            log.warning(
                "RPDC_COVERAGE_WARN: runner_release_candidates is %d days stale (last: %s)",
                _staleness, _latest_rrc_date,
            )
    else:
        print(
            "\n⚠ RPDC_COVERAGE_WARN\n"
            "  runner_release_candidates has NO rows. RPDC has never been built.\n"
            "  Run the full ingest + build chain before scoring."
        )
        log.warning("RPDC_COVERAGE_WARN: runner_release_candidates is empty")

    # Load today's racecards — source priority:
    #   1. results_YYYY_MM_DD.json          — post-race, has positions and SPs (most complete)
    #   2. racecard_injection.json          — pre-scoring RP source (Step 8.5: run BEFORE scoring)
    #                                         Has real RP horse_ids and trainer_ids from the HTML parse.
    #   3. runner_snapshots_YYYY_MM_DD.jsonl — post-scoring fallback (real IDs since loader fix)
    #   4. None found → error
    import glob as _glob
    date_tag = date_str.replace("-", "_")
    results_path = ROOT / "data" / f"results_{date_tag}.json"

    runners_to_score: list[dict] = []
    expected_race_ids: set[str] = set()
    selected_injection = _resolve_injection_path(date_str, injection_path)

    if injection_path:
        if not selected_injection or not selected_injection.exists():
            log.error("RPDC explicit injection does not exist: %s", selected_injection)
            return False
        log.info("Loading runners from explicit injection JSON: %s", selected_injection)
        try:
            runners_to_score, expected_race_ids = _load_injection_runners(selected_injection)
        except Exception as exc:
            log.error("Failed to load explicit injection JSON %s: %s", selected_injection, exc)
            return False
        log.info(
            "Loaded %d runners across %d races from explicit injection JSON",
            len(runners_to_score),
            len(expected_race_ids),
        )
    elif results_path.exists():
        with open(results_path) as f:
            data = json.load(f)
        races_list = data if isinstance(data, list) else (data.get("results") or [])
        for race in races_list:
            race_id = str(race.get("race_id", ""))
            if race_id:
                expected_race_ids.add(race_id)
            for runner in race.get("runners") or []:
                if runner.get("horse_id"):
                    runners_to_score.append({
                        "horse_id": str(runner["horse_id"]),
                        "horse": runner.get("horse", ""),
                        "race_id": race_id,
                        "trainer_id": str(runner.get("trainer_id") or ""),
                        "trainer": runner.get("trainer", ""),
                        "current_or": _to_int(runner.get("or")),
                        "course_id": str(race.get("course_id", "")),
                        "dist_f": _to_float(race.get("dist_f")),
                    })
        log.info("Loaded %d runners from results file", len(runners_to_score))
    else:
        # No results file — try injection JSON (primary pre-scoring RP source)
        # Glob for any capture label containing the date: live-full-racepages-YYYY-MM-DD*
        if selected_injection:
            log.info("Loading runners from injection JSON (RP source): %s", selected_injection.parent.name)
            try:
                runners_to_score, expected_race_ids = _load_injection_runners(selected_injection)
                log.info(
                    "Loaded %d runners across %d races from injection JSON",
                    len(runners_to_score),
                    len(expected_race_ids),
                )
            except Exception as _e:
                log.warning("Failed to load injection JSON %s: %s", selected_injection, _e)

        if not runners_to_score:
            # Injection not available or failed — try runner_snapshots (post-scoring fallback)
            _snap_files = sorted(
                _glob.glob(str(ROOT / "data" / f"runner_snapshots_{date_tag}_*.jsonl"))
            )
            if _snap_files:
                _snap_path = _snap_files[-1]
                log.info("Loading runners from runner_snapshots (fallback): %s", Path(_snap_path).name)
                _seen_runners: dict[str, dict] = {}
                with open(_snap_path) as _f:
                    for _line in _f:
                        _line = _line.strip()
                        if not _line:
                            continue
                        try:
                            _r = json.loads(_line)
                            _hid = _r.get("horse_id")
                            _rid = _r.get("race_id")
                            if _hid and _rid:
                                _key = f"{_hid}:{_rid}"
                                if _key not in _seen_runners:
                                    _seen_runners[_key] = {
                                        "horse_id": str(_hid),
                                        "horse": _r.get("horse", ""),
                                        "race_id": str(_rid),
                                        "trainer_id": str(_r.get("trainer_id") or ""),
                                        "trainer": _r.get("trainer") or "",
                                        "current_or": None,
                                        "course_id": "",
                                        "dist_f": None,
                                    }
                        except (json.JSONDecodeError, KeyError):
                            continue
                runners_to_score = list(_seen_runners.values())
                log.info("Loaded %d runners from runner_snapshots", len(runners_to_score))

        if not runners_to_score:
            print(
                f"\n⚠ RPDC_SOURCE_UNAVAILABLE — {date_str}\n"
                f"  No source found for runners. Checked (in order):\n"
                f"    data/results_{date_tag}.json\n"
                f"    data/racing_post_account_parsed/*{date_str}*/racecard_injection.json\n"
                f"    data/runner_snapshots_{date_tag}_*.jsonl\n"
                f"  Run Step 4 (parse HTML) to create the injection JSON, then re-run RPDC."
            )
            log.error("RPDC_SOURCE_UNAVAILABLE: no source for runners on %s", date_str)
            return False

    if not runners_to_score:
        print("  No runners to score.")
        return False

    # Deduplicate by horse_id (keep last — same horse may run multiple times today)
    seen_horses: dict[str, dict] = {}
    for r in runners_to_score:
        seen_horses[f"{r['horse_id']}:{r['race_id']}"] = r

    runners_unique = list(seen_horses.values())
    print(f"  Runners to score: {len(runners_unique)}")

    # Pre-fetch trainer stats (batch by unique trainer_id; keyed by name for fallback)
    trainer_ids = list({r["trainer_id"] for r in runners_unique if r.get("trainer_id")})
    log.info("Pre-fetching stats for %d trainers", len(trainer_ids))
    # Build trainer_id → trainer_name map for name fallback
    _tid_to_name: dict[str, str] = {}
    for r in runners_unique:
        tid = r.get("trainer_id", "")
        if tid and tid not in _tid_to_name:
            _tid_to_name[tid] = r.get("trainer", "")
    trainer_cache: dict[str, dict] = {}
    for tid in trainer_ids:
        trainer_cache[tid] = _trainer_stats(tid, date_str, _tid_to_name.get(tid, ""))

    # Score each runner
    candidates = []
    ok = 0
    fail = 0
    for runner in runners_unique:
        hid = runner["horse_id"]
        try:
            history = _fetch_horse_history(hid, runner.get("horse", ""))
            t_stats = trainer_cache.get(runner.get("trainer_id", ""), {"win_rate": 0.0})
            row = compute_rpdc(
                horse_id=hid,
                race_id=runner["race_id"],
                horse=runner["horse"],
                trainer_id=runner.get("trainer_id", ""),
                trainer=runner.get("trainer", ""),
                current_or=runner.get("current_or"),
                today_course_id=runner.get("course_id", ""),
                today_dist_f=runner.get("dist_f"),
                today_str=date_str,
                history=history,
                trainer_stats=t_stats,
            )
            candidates.append(row)
            ok += 1
        except Exception as e:
            log.warning("RPDC failed for %s: %s", hid, e)
            fail += 1

    print(f"  Scored: {ok} OK / {fail} FAIL")

    # Replace the day. Keeping stale rows from an earlier capture corrupts
    # coverage checks and can attach context to runners no longer on the card.
    if not _sb_delete(f"/runner_release_candidates?run_date=eq.{date_str}"):
        log.error("RPDC_REPLACE_FAILED: could not clear existing rows for %s", date_str)
        return False

    written = 0
    for i in range(0, len(candidates), 100):
        batch = candidates[i:i + 100]
        n = _sb_upsert("/runner_release_candidates", batch, "run_date,race_id,horse_id")
        written += n

    print(f"  runner_release_candidates: {written} rows written")
    if written != len(candidates):
        log.error(
            "RPDC_WRITE_INCOMPLETE: wrote %d/%d candidates; downstream scoring blocked",
            written,
            len(candidates),
        )
        return False

    persisted = _sb_get(
        f"/runner_release_candidates?run_date=eq.{date_str}&select=race_id&limit=2000"
    )
    persisted_race_ids = {str(row.get("race_id") or "") for row in persisted}
    missing_race_ids = expected_race_ids - persisted_race_ids
    if expected_race_ids and missing_race_ids:
        log.error(
            "RPDC_IDENTITY_MISMATCH: persisted coverage %d/%d races; missing=%s",
            len(expected_race_ids) - len(missing_race_ids),
            len(expected_race_ids),
            sorted(missing_race_ids),
        )
        return False

    # Summary of tags fired
    all_tags: list[str] = []
    for c in candidates:
        all_tags.extend(c.get("rpdc_tags") or [])
    from collections import Counter
    counts = Counter(all_tags)
    print("\n  Tag frequencies:")
    for tag, n in counts.most_common(10):
        print(f"    {tag}: {n}")

    cash_window = sum(1 for c in candidates if c.get("rpdc_cash_window_flag"))
    trap_flag = sum(1 for c in candidates if c.get("rpdc_trap_flag"))
    print(f"\n  Cash window (score>={CASH_WINDOW_THRESHOLD}): {cash_window}")
    print(f"  Trap flagged: {trap_flag}")
    print(f"\nRPDC DAILY COMPLETE — {date_str}")
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=None, help="YYYY-MM-DD")
    parser.add_argument(
        "--injection-path",
        default=None,
        help="Exact racecard_injection.json selected by the One Truth pipeline.",
    )
    args = parser.parse_args()
    date_str = args.date or TODAY
    if not build_rpdc_for_date(date_str, injection_path=args.injection_path):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
