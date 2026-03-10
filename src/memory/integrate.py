#!/usr/bin/env python3
"""
VÉLØ PRIME — Integration CLI
==============================
Command-line tool for the full race intelligence pipeline:
  parse_race_card  → stores race + runners in database
  log_prediction   → extracts Top Strike / Value / Danger and stores
  log_results      → stores results and triggers sigma evaluation
  full_cycle       → runs the complete pipeline
  pre_race_brief   → queries memory for all relevant historical context

Usage:
    python -m src.memory.integrate parse_race_card path/to/racecard.md
    python -m src.memory.integrate log_prediction path/to/analysis.md
    python -m src.memory.integrate log_results --race-id R001 --data path/to/results.json
    python -m src.memory.integrate full_cycle --card card.md --analysis analysis.md --results results.json
    python -m src.memory.integrate pre_race_brief --course Kempton --date 2026-02-16
    python -m src.memory.integrate stats
"""

import argparse
import json
import re
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Handle both direct execution and module execution
try:
    from .memory_engine import VeloMemoryEngine
    from .rpd_validator import RPDValidator
    from .github_sync import GitHubSync
except ImportError:
    from memory_engine import VeloMemoryEngine
    from rpd_validator import RPDValidator
    from github_sync import GitHubSync


DEFAULT_DB = "data/velo_memory.db"


def _uid() -> str:
    return uuid.uuid4().hex[:12]


# ─────────────────────────────────────────────
# PARSERS
# ─────────────────────────────────────────────

def parse_race_card_file(file_path: str) -> Tuple[dict, List[dict]]:
    """
    Parse a race card from Markdown or JSON file.
    Returns (race_data, runners_list).

    Supports:
      - JSON format (structured)
      - Markdown format (semi-structured, extracts what it can)
    """
    path = Path(file_path)
    content = path.read_text(encoding="utf-8")

    if path.suffix.lower() == ".json":
        return _parse_json_card(content)
    else:
        return _parse_md_card(content, path.stem)


def _parse_json_card(content: str) -> Tuple[dict, List[dict]]:
    """Parse a JSON-formatted race card."""
    data = json.loads(content)

    race_data = {
        "race_id": data.get("race_id", f"race_{_uid()}"),
        "date": data.get("date", data.get("off_time", "")[:10]),
        "course": data.get("course") or data.get("venue", ""),
        "time": data.get("time") or data.get("off_time", ""),
        "race_type": data.get("race_type"),
        "class": data.get("class") or data.get("class_"),
        "distance": data.get("distance"),
        "going": data.get("going"),
        "field_size": data.get("field_size") or len(data.get("runners", [])),
        "prize": data.get("prize"),
        "rail_position": data.get("rail_position"),
        "weather": data.get("weather"),
    }

    runners = []
    for r in data.get("runners", []):
        runners.append({
            "runner_id": r.get("runner_id") or r.get("id", f"{race_data['race_id']}_{_uid()}"),
            "horse_name": r.get("horse_name") or r.get("name", ""),
            "trainer": r.get("trainer"),
            "jockey": r.get("jockey"),
            "age": r.get("age"),
            "weight": r.get("weight"),
            "OR": r.get("OR") or r.get("or_rating"),
            "RPR": r.get("RPR") or r.get("rpr"),
            "TS": r.get("TS") or r.get("ts"),
            "form_figures": r.get("form_figures") or r.get("form"),
            "draw": r.get("draw"),
            "headgear": r.get("headgear"),
            "days_since_run": r.get("days_since_run"),
            "spotlight_notes": r.get("spotlight_notes"),
            "rpd_tag": r.get("rpd_tag"),
        })

    return race_data, runners


def _parse_md_card(content: str, filename: str) -> Tuple[dict, List[dict]]:
    """
    Parse a Markdown-formatted race card.
    Extracts structured data from semi-structured text.
    """
    race_id = f"race_{_uid()}"

    # Try to extract course from first heading or filename
    course_match = re.search(r"#\s*(.+?)(?:\s*[-–—]\s*|\n)", content)
    course = course_match.group(1).strip() if course_match else filename

    # Try to extract date
    date_match = re.search(r"(\d{4}-\d{2}-\d{2})", content)
    date_str = date_match.group(1) if date_match else datetime.utcnow().strftime("%Y-%m-%d")

    # Try to extract time
    time_match = re.search(r"(\d{1,2}[:.]\d{2})\s*(?:pm|am)?", content, re.IGNORECASE)
    time_str = time_match.group(1) if time_match else None

    # Try to extract going
    going_match = re.search(r"Going[:\s]+([^\n,]+)", content, re.IGNORECASE)
    going = going_match.group(1).strip() if going_match else None

    # Try to extract distance
    dist_match = re.search(r"Distance[:\s]+([^\n,]+)", content, re.IGNORECASE)
    if not dist_match:
        dist_match = re.search(r"(\d+[mf]\s*\d*[yf]?)", content)
    distance = dist_match.group(1).strip() if dist_match else None

    # Try to extract class
    class_match = re.search(r"Class\s*(\d+)", content, re.IGNORECASE)
    race_class = class_match.group(1) if class_match else None

    # Try to extract race type
    type_match = re.search(r"(Handicap|Novice|Maiden|Conditions|Stakes|Chase|Hurdle|Flat|Bumper)", content, re.IGNORECASE)
    race_type = type_match.group(1) if type_match else None

    race_data = {
        "race_id": race_id,
        "date": date_str,
        "course": course,
        "time": time_str,
        "race_type": race_type,
        "class": race_class,
        "distance": distance,
        "going": going,
        "field_size": None,  # Will be set after parsing runners
        "prize": None,
        "rail_position": None,
        "weather": None,
    }

    # Parse runners — look for numbered entries or horse name patterns
    runners = []
    # Pattern: number followed by horse name, possibly with trainer/jockey
    runner_pattern = re.compile(
        r"(?:^|\n)\s*(\d+)\.\s*\*?\*?([A-Z][A-Za-z\s\'\-]+?)(?:\*?\*?)?\s*(?:\(([^)]+)\))?"
    )
    for match in runner_pattern.finditer(content):
        draw = match.group(1)
        horse = match.group(2).strip()
        extra = match.group(3) or ""

        runners.append({
            "runner_id": f"{race_id}_{_uid()}",
            "horse_name": horse,
            "draw": int(draw) if draw.isdigit() else None,
            "trainer": None,
            "jockey": None,
        })

    race_data["field_size"] = len(runners) if runners else None
    return race_data, runners


def parse_analysis_file(file_path: str) -> dict:
    """
    Extract prediction data from an analysis Markdown file.
    Looks for Top Strike, Value Pick, Danger Horse patterns.

    Returns a prediction dict.
    """
    content = Path(file_path).read_text(encoding="utf-8")

    prediction: Dict[str, Any] = {
        "prediction_id": f"pred_{_uid()}",
        "date": datetime.utcnow().strftime("%Y-%m-%d"),
        "full_analysis_text": content,
    }

    # Extract Top Strike
    ts_match = re.search(
        r"(?:Top\s*Strike|PRIMARY\s*SELECTION|SELECTION)[:\s—–-]+\*?\*?([A-Z][A-Za-z\s\'\-]+?)(?:\*?\*?)?\s*(?:\n|$|—|-|\()",
        content, re.IGNORECASE
    )
    if ts_match:
        prediction["top_strike"] = ts_match.group(1).strip()

    # Extract Value Pick
    vp_match = re.search(
        r"(?:Value\s*Pick|VALUE\s*SELECTION|VALUE)[:\s—–-]+\*?\*?([A-Z][A-Za-z\s\'\-]+?)(?:\*?\*?)?\s*(?:\n|$|—|-|\()",
        content, re.IGNORECASE
    )
    if vp_match:
        prediction["value_pick"] = vp_match.group(1).strip()

    # Extract Danger Horse
    dh_match = re.search(
        r"(?:Danger\s*Horse|DANGER|THREAT)[:\s—–-]+\*?\*?([A-Z][A-Za-z\s\'\-]+?)(?:\*?\*?)?\s*(?:\n|$|—|-|\()",
        content, re.IGNORECASE
    )
    if dh_match:
        prediction["danger_horse"] = dh_match.group(1).strip()

    # Extract confidence band
    conf_match = re.search(
        r"(?:Confidence|CONFIDENCE)[:\s—–-]+\*?\*?([A-Za-z\s\d%]+?)(?:\*?\*?)?\s*(?:\n|$)",
        content, re.IGNORECASE
    )
    if conf_match:
        prediction["confidence_band"] = conf_match.group(1).strip()

    # Extract scenarios
    sc1_match = re.search(
        r"(?:Primary\s*Scenario|SCENARIO\s*1|Scenario\s*A)[:\s—–-]+(.+?)(?:\n|$)",
        content, re.IGNORECASE
    )
    if sc1_match:
        prediction["scenario_primary"] = sc1_match.group(1).strip()

    sc2_match = re.search(
        r"(?:Secondary\s*Scenario|SCENARIO\s*2|Scenario\s*B)[:\s—–-]+(.+?)(?:\n|$)",
        content, re.IGNORECASE
    )
    if sc2_match:
        prediction["scenario_secondary"] = sc2_match.group(1).strip()

    # Extract date from content if available
    date_match = re.search(r"(\d{4}-\d{2}-\d{2})", content)
    if date_match:
        prediction["date"] = date_match.group(1)

    return prediction


def parse_results_file(file_path: str) -> dict:
    """
    Parse results from a JSON file.
    Returns a results dict.
    """
    content = Path(file_path).read_text(encoding="utf-8")
    data = json.loads(content)

    results: Dict[str, Any] = {
        "result_id": data.get("result_id", f"res_{_uid()}"),
        "date": data.get("date", datetime.utcnow().strftime("%Y-%m-%d")),
        "winning_time": data.get("winning_time"),
        "non_runners": data.get("non_runners"),
    }

    # Handle different position formats
    if "positions" in data:
        results["positions"] = data["positions"]
    elif "placed" in data:
        # Convert simple format to structured
        positions = []
        sp_data = data.get("starting_prices", {})
        for i, runner_id in enumerate(data["placed"], 1):
            positions.append({
                "horse_name": runner_id,
                "position": i,
                "bsp": sp_data.get(runner_id),
                "isp": sp_data.get(runner_id),
            })
        results["positions"] = positions

    return results


# ─────────────────────────────────────────────
# CLI COMMANDS
# ─────────────────────────────────────────────

def cmd_parse_race_card(args):
    """Parse a race card and store in database."""
    mem = VeloMemoryEngine(args.db)
    race_data, runners = parse_race_card_file(args.file)

    race_id = mem.store_race(race_data)
    runner_ids = mem.store_runners(race_id, runners) if runners else []

    print(f"✓ Race stored: {race_id} ({race_data.get('course', 'unknown')})")
    print(f"  Runners: {len(runner_ids)}")
    for rid in runner_ids:
        print(f"    → {rid}")
    mem.close()


def cmd_log_prediction(args):
    """Extract prediction from analysis file and store."""
    mem = VeloMemoryEngine(args.db)
    prediction = parse_analysis_file(args.file)

    race_id = args.race_id
    if not race_id:
        # Try to find the most recent race
        races = mem.list_races(limit=1)
        if races:
            race_id = races[0]["race_id"]
        else:
            race_id = f"race_{_uid()}"
            print(f"  ⚠ No race found, created placeholder: {race_id}")

    pred_id = mem.store_prediction(race_id, prediction)
    print(f"✓ Prediction stored: {pred_id}")
    print(f"  Race: {race_id}")
    print(f"  Top Strike: {prediction.get('top_strike', 'N/A')}")
    print(f"  Value Pick: {prediction.get('value_pick', 'N/A')}")
    print(f"  Danger: {prediction.get('danger_horse', 'N/A')}")
    mem.close()


def cmd_log_results(args):
    """Store results and trigger sigma evaluation."""
    mem = VeloMemoryEngine(args.db)

    if args.data:
        results = parse_results_file(args.data)
    else:
        print("Error: --data is required for log_results")
        sys.exit(1)

    race_id = args.race_id
    if not race_id:
        races = mem.list_races(limit=1)
        if races:
            race_id = races[0]["race_id"]
        else:
            print("Error: --race-id required when no races in database")
            sys.exit(1)

    result_id = mem.store_results(race_id, results)
    print(f"✓ Results stored: {result_id}")

    # Auto-trigger sigma evaluation
    eval_id = mem.run_sigma_evaluation(race_id)
    if eval_id:
        sigma = mem.get_sigma(race_id)
        print(f"✓ Sigma evaluation: {eval_id}")
        print(f"  Top Strike: {sigma.get('top_strike_result', 'N/A')}")
        print(f"  Value: {sigma.get('value_result', 'N/A')}")
        print(f"  Danger: {sigma.get('danger_result', 'N/A')}")
        print(f"  Signal Quality: {sigma.get('signal_quality', 'N/A')}")
    else:
        print("  ⚠ No prediction found — sigma evaluation skipped")

    # Update patterns
    tp = mem.update_trainer_patterns(race_id)
    jp = mem.update_jockey_patterns(race_id)
    cb = mem.update_course_bias(race_id)
    print(f"  Patterns updated: {tp} trainer, {jp} jockey, {cb} course bias")

    # RPD validation
    rpd = RPDValidator(mem)
    validations = rpd.validate_batch(race_id)
    if validations:
        print(f"  RPD validated: {len(validations)} tags")
        for v in validations:
            status = "✓" if v["validated"] else "✗"
            print(f"    {status} {v['horse_name']} [{v['rpd_tag']}] → P{v['actual_position']}")

    mem.close()


def cmd_full_cycle(args):
    """Run the complete pipeline: card → prediction → results → sigma."""
    mem = VeloMemoryEngine(args.db)

    # Step 1: Parse race card
    print("═══ STEP 1: Parse Race Card ═══")
    race_data, runners = parse_race_card_file(args.card)
    race_id = mem.store_race(race_data)
    runner_ids = mem.store_runners(race_id, runners) if runners else []
    print(f"✓ Race: {race_id} — {len(runner_ids)} runners")

    # Step 2: Log prediction
    if args.analysis:
        print("\n═══ STEP 2: Log Prediction ═══")
        prediction = parse_analysis_file(args.analysis)
        pred_id = mem.store_prediction(race_id, prediction)
        print(f"✓ Prediction: {pred_id}")
        print(f"  Top Strike: {prediction.get('top_strike', 'N/A')}")

    # Step 3: Log results
    if args.results:
        print("\n═══ STEP 3: Log Results ═══")
        results = parse_results_file(args.results)
        result_id = mem.store_results(race_id, results)
        print(f"✓ Results: {result_id}")

        # Step 4: Sigma evaluation
        print("\n═══ STEP 4: Sigma Evaluation ═══")
        eval_id = mem.run_sigma_evaluation(race_id)
        if eval_id:
            sigma = mem.get_sigma(race_id)
            print(f"✓ Sigma: {eval_id}")
            print(f"  Top Strike: {sigma.get('top_strike_result')}")
            print(f"  Value: {sigma.get('value_result')}")
            print(f"  Danger: {sigma.get('danger_result')}")
            print(f"  Signal Quality: {sigma.get('signal_quality')}")

        # Step 5: Pattern updates
        print("\n═══ STEP 5: Pattern Updates ═══")
        tp = mem.update_trainer_patterns(race_id)
        jp = mem.update_jockey_patterns(race_id)
        cb = mem.update_course_bias(race_id)
        print(f"✓ Trainer patterns: {tp}")
        print(f"✓ Jockey patterns: {jp}")
        print(f"✓ Course bias: {cb}")

        # Step 6: RPD validation
        print("\n═══ STEP 6: RPD Validation ═══")
        rpd = RPDValidator(mem)
        validations = rpd.validate_batch(race_id)
        print(f"✓ Validated {len(validations)} RPD tags")

    print("\n═══ CYCLE COMPLETE ═══")
    stats = mem.get_system_stats()
    print(f"Database: {stats['total_races']} races, {stats['total_runners']} runners, "
          f"{stats['total_evaluations']} evaluations")
    mem.close()


def cmd_pre_race_brief(args):
    """Query memory for all relevant historical context."""
    mem = VeloMemoryEngine(args.db)

    trainers = [t.strip() for t in (args.trainers or "").split(",") if t.strip()]
    jockeys = [j.strip() for j in (args.jockeys or "").split(",") if j.strip()]

    context = mem.get_pre_race_context(args.course, trainers, jockeys)

    print(f"═══ VÉLØ PRE-RACE BRIEF: {args.course} ═══")
    print(f"Generated: {context['generated_at']}")

    if context["trainer_patterns"]:
        print(f"\n── Trainer Intelligence ({len(context['trainer_patterns'])} trainers) ──")
        for trainer, patterns in context["trainer_patterns"].items():
            for p in patterns:
                print(f"  {trainer} @ {p.get('course','all')}: "
                      f"{p.get('runs',0)} runs, {p.get('wins',0)} wins "
                      f"({p.get('strike_rate',0)*100:.1f}%)")

    if context["jockey_patterns"]:
        print(f"\n── Jockey Intelligence ({len(context['jockey_patterns'])} jockeys) ──")
        for jockey, patterns in context["jockey_patterns"].items():
            for p in patterns:
                print(f"  {jockey} @ {p.get('course','all')}: "
                      f"{p.get('runs',0)} runs, {p.get('wins',0)} wins "
                      f"({p.get('strike_rate',0)*100:.1f}%)")

    if context["course_bias"]:
        print(f"\n── Course Bias ({len(context['course_bias'])} records) ──")
        for b in context["course_bias"]:
            print(f"  {b.get('going','all')} / {b.get('distance','all')}: "
                  f"draw={b.get('draw_bias','?')} pace={b.get('pace_bias','?')} "
                  f"(n={b.get('sample_size',0)})")

    if context["recent_sigma_at_course"]:
        print(f"\n── Recent Sigma at {args.course} ({len(context['recent_sigma_at_course'])} evals) ──")
        for s in context["recent_sigma_at_course"][:5]:
            print(f"  {s.get('date','?')}: TS={s.get('top_strike_result','?')} "
                  f"V={s.get('value_result','?')} Q={s.get('signal_quality','?')}")

    mem.close()


def cmd_stats(args):
    """Display system statistics."""
    mem = VeloMemoryEngine(args.db)
    stats = mem.get_system_stats()

    print("═══ VÉLØ MEMORY SYSTEM STATS ═══")
    print(f"  Schema Version: {stats['schema_version']}")
    print(f"  Total Races: {stats['total_races']}")
    print(f"  Total Runners: {stats['total_runners']}")
    print(f"  Total Predictions: {stats['total_predictions']}")
    print(f"  Total Results: {stats['total_results']}")
    print(f"  Total Evaluations: {stats['total_evaluations']}")
    print(f"\n── Strike Rates ──")
    print(f"  Top Strike Win Rate: {stats['top_strike_hit_rate']*100:.1f}%")
    print(f"  Top Strike Place Rate: {stats['top_strike_place_rate']*100:.1f}%")
    print(f"  Value Win Rate: {stats['value_hit_rate']*100:.1f}%")
    print(f"  Value Place Rate: {stats['value_place_rate']*100:.1f}%")
    print(f"  Avg Signal Quality: {stats['avg_signal_quality']:.3f}")

    mem.close()


def cmd_sigma_report(args):
    """Export a sigma performance report."""
    mem = VeloMemoryEngine(args.db)
    report = mem.export_sigma_report(args.date_from, args.date_to)

    if args.output:
        Path(args.output).write_text(report, encoding="utf-8")
        print(f"✓ Report written to {args.output}")
    else:
        print(report)

    mem.close()


def cmd_rpd_report(args):
    """Generate RPD recalibration report."""
    mem = VeloMemoryEngine(args.db)
    rpd = RPDValidator(mem)
    report = rpd.recalibration_report()

    if args.output:
        Path(args.output).write_text(report, encoding="utf-8")
        print(f"✓ Report written to {args.output}")
    else:
        print(report)

    mem.close()


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        prog="velo-integrate",
        description="VÉLØ PRIME Integration CLI — Persistent Intelligence Pipeline",
    )
    parser.add_argument("--db", default=DEFAULT_DB, help="Path to velo_memory.db")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # parse_race_card
    p_card = subparsers.add_parser("parse_race_card", help="Parse and store a race card")
    p_card.add_argument("file", help="Path to race card file (MD or JSON)")

    # log_prediction
    p_pred = subparsers.add_parser("log_prediction", help="Extract and store prediction from analysis")
    p_pred.add_argument("file", help="Path to analysis markdown file")
    p_pred.add_argument("--race-id", dest="race_id", help="Race ID to associate with")

    # log_results
    p_res = subparsers.add_parser("log_results", help="Store results and trigger sigma")
    p_res.add_argument("--race-id", dest="race_id", help="Race ID")
    p_res.add_argument("--data", required=True, help="Path to results JSON file")

    # full_cycle
    p_full = subparsers.add_parser("full_cycle", help="Run complete pipeline")
    p_full.add_argument("--card", required=True, help="Race card file")
    p_full.add_argument("--analysis", help="Analysis markdown file")
    p_full.add_argument("--results", help="Results JSON file")

    # pre_race_brief
    p_brief = subparsers.add_parser("pre_race_brief", help="Query historical context")
    p_brief.add_argument("--course", required=True, help="Course name")
    p_brief.add_argument("--date", help="Race date")
    p_brief.add_argument("--trainers", help="Comma-separated trainer names")
    p_brief.add_argument("--jockeys", help="Comma-separated jockey names")

    # stats
    subparsers.add_parser("stats", help="Display system statistics")

    # sigma_report
    p_sigma = subparsers.add_parser("sigma_report", help="Export sigma performance report")
    p_sigma.add_argument("--date-from", dest="date_from", required=True)
    p_sigma.add_argument("--date-to", dest="date_to", required=True)
    p_sigma.add_argument("--output", help="Output file path")

    # rpd_report
    p_rpd = subparsers.add_parser("rpd_report", help="Generate RPD recalibration report")
    p_rpd.add_argument("--output", help="Output file path")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    commands = {
        "parse_race_card": cmd_parse_race_card,
        "log_prediction": cmd_log_prediction,
        "log_results": cmd_log_results,
        "full_cycle": cmd_full_cycle,
        "pre_race_brief": cmd_pre_race_brief,
        "stats": cmd_stats,
        "sigma_report": cmd_sigma_report,
        "rpd_report": cmd_rpd_report,
    }

    cmd_func = commands.get(args.command)
    if cmd_func:
        cmd_func(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
