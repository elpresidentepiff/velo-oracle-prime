"""
build_sidecar_training_dataset.py

Builds the VÉLØ sidecar training dataset from Supabase.
Joins velo_verdicts (expanded full_analysis) with runner_results, runners,
races, sigma_audits, and Racing API analysis tables.

Output: data/sidecar_training_dataset_v1.csv
        data/sidecar_training_dataset_v1.md  (coverage report)

Usage:
    PYTHONPATH=. python scripts/build_sidecar_training_dataset.py
    PYTHONPATH=. python scripts/build_sidecar_training_dataset.py --out data/sidecar_v2.csv
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import urllib.request
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from src.velo.distance_normalizer import float_to_dist_key

load_dotenv(dotenv_path=".env")

_URL = os.getenv("SUPABASE_URL", "")
_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
_HEADERS = {"apikey": _KEY, "Authorization": f"Bearer {_KEY}"}

OUTPUT_FIELDS = [
    "race_id","horse_id","horse_name","date","course","course_id","dist_f",
    "race_class","field_size","going","trainer_id","jockey_id",
    "or_rating","rpr","ts_rating",
    # VÉLØ ensemble scores
    "velo_prime_prob","sqpe_v17_prob","improvement_score","market_deception_score",
    "place_prob","longshot_score","comment_intel_score","release_day_prob",
    # context
    "verdict_tier","confidence_level","verdict_flags_str",
    # RPDC
    "rpdc_score","rpdc_tags_str",
    # Racing API — trainer stats (from full_analysis)
    "trainer_course_win_pct","trainer_course_ae","trainer_course_runs",
    "trainer_dist_win_pct","trainer_dist_ae","trainer_dist_runs",
    # Racing API — jockey stats (from Supabase tables)
    "jockey_course_win_pct","jockey_course_pnl","jockey_course_ae","jockey_course_runs",
    "jockey_dist_win_pct","jockey_dist_pnl",
    "trainer_jockey_win_pct","trainer_jockey_pnl",
    "jockey_trainer_win_pct","jockey_trainer_pnl",
    # outcomes
    "is_winner","placed","sp_dec","position","flat_profit_loss",
    # sigma
    "sigma_outcome","sigma_verdict_score",
    # split
    "split",
]


def _fetch_all(table: str, select: str = "*", filters: str = "", verbose: bool = True) -> list:
    rows, offset = [], 0
    if verbose:
        print(f"  Fetching {table}...", end="", flush=True)
    while True:
        req = urllib.request.Request(
            f"{_URL}/rest/v1/{table}?select={select}{filters}&offset={offset}&limit=1000",
            headers={**_HEADERS, "Range": f"{offset}-{offset+999}"},
        )
        with urllib.request.urlopen(req) as r:
            batch = json.loads(r.read())
        rows.extend(batch)
        if len(batch) < 1000:
            break
        offset += 1000
    if verbose:
        print(f" {len(rows)}")
    return rows


def _build_lookup(rows: list, *key_fields) -> dict:
    """Build dict keyed by tuple of key_fields, keeping highest runners_or_rides row."""
    d: dict = {}
    for r in rows:
        k = tuple(r.get(f) for f in key_fields)
        if None in k:
            continue
        existing = d.get(k)
        cur_runs = r.get("runners_or_rides") or 0
        if existing is None or cur_runs > (existing.get("runners_or_rides") or 0):
            d[k] = r
    return d


def _norm_dist(dist_f_raw) -> str | None:
    """Normalize distance to Racing API 'Xf' string key.

    racing_horse_runs.distance_f is already a float (e.g. 6.5);
    float_to_dist_key converts to "6.5f" matching analysis table format.
    """
    return float_to_dist_key(dist_f_raw)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="data/sidecar_training_dataset_v1.csv")
    args = parser.parse_args()

    print("=== VÉLØ Sidecar Training Dataset Builder ===")
    print("Step 1: Loading reference tables...")

    # --- Load all reference tables into memory ---
    races_rows = _fetch_all("races", select="race_id,course,date,distance_f,going,class,runners_count")
    runners_rows = _fetch_all("runners", select="race_id,horse_id,trainer_id,jockey_id,or_rating,rpr,ts_rating")
    rr_rows = _fetch_all("runner_results", select="race_id,horse_id,is_winner,sp_dec,position,position_text")
    sigma_rows = _fetch_all("sigma_audits", select="race_id,horse_id,outcome,verdict_score")
    rpdc_rows = _fetch_all("runner_release_candidates",
                           select="race_id,horse_id,rpdc_release_score,rpdc_tags,rpdc_cash_window_flag")
    # racing_horse_runs: authoritative source for course_id and distance_f (float furlongs)
    rhr_rows = _fetch_all("racing_horse_runs",
                          select="race_id,horse_id,course_id,distance_f", verbose=True)

    print("Step 2: Loading Racing API jockey stats...")
    jc_rows = _fetch_all("racing_api_jockey_analysis_courses",
                          select="entity_id,course_id,win_pct,pnl,ae_ratio,runners_or_rides")
    jd_rows = _fetch_all("racing_api_jockey_analysis_distances",
                          select="entity_id,dist_f,win_pct,pnl,runners_or_rides")
    jt_rows = _fetch_all("racing_api_jockey_analysis_trainers",
                          select="entity_id,trainer_id,win_pct,pnl,runners_or_rides")
    tj_rows = _fetch_all("racing_api_trainer_analysis_jockeys",
                          select="entity_id,jockey_id,win_pct,pnl,runners_or_rides")

    print("Step 3: Building lookup indices...")
    races_by_id: dict = {r["race_id"]: r for r in races_rows if r.get("race_id")}
    runners_by_key: dict = {(r["race_id"], r["horse_id"]): r for r in runners_rows
                            if r.get("race_id") and r.get("horse_id")}
    rr_by_key: dict = {(r["race_id"], r["horse_id"]): r for r in rr_rows
                       if r.get("race_id") and r.get("horse_id")}
    sigma_by_key: dict = {(r["race_id"], r["horse_id"]): r for r in sigma_rows
                          if r.get("race_id") and r.get("horse_id")}
    rpdc_by_key: dict = {(r["race_id"], r["horse_id"]): r for r in rpdc_rows
                         if r.get("race_id") and r.get("horse_id")}
    # racing_horse_runs keyed by (race_id, horse_id) for course_id + distance_f lookup
    rhr_by_key: dict = {(r["race_id"], r["horse_id"]): r for r in rhr_rows
                        if r.get("race_id") and r.get("horse_id")}

    jc_lkp = _build_lookup(jc_rows, "entity_id", "course_id")
    jd_lkp = _build_lookup(jd_rows, "entity_id", "dist_f")
    jt_lkp = _build_lookup(jt_rows, "entity_id", "trainer_id")
    tj_lkp = _build_lookup(tj_rows, "entity_id", "jockey_id")

    print("Step 4: Fetching velo_verdicts and expanding full_analysis...")
    vv_rows = _fetch_all("velo_verdicts",
                          select="race_id,full_analysis,confidence_level",
                          verbose=True)

    print("Step 5: Building training rows...")
    training_rows: list[dict] = []
    skipped_no_outcome = 0
    skipped_no_fa = 0

    for vv in vv_rows:
        race_id = vv.get("race_id")
        fa = vv.get("full_analysis")
        if not fa:
            skipped_no_fa += 1
            continue
        if isinstance(fa, str):
            try:
                fa = json.loads(fa)
            except Exception:
                skipped_no_fa += 1
                continue
        if not isinstance(fa, list):
            skipped_no_fa += 1
            continue

        race = races_by_id.get(race_id, {})
        course = race.get("course")
        field_size = race.get("runners_count")
        # course_id and distance_f resolved from racing_horse_runs (authoritative)
        # These are set per-horse below using rhr_by_key

        for horse in fa:
            horse_id = horse.get("horse_id")
            if not horse_id:
                continue

            key = (race_id, horse_id)
            rr = rr_by_key.get(key, {})
            is_winner = rr.get("is_winner")

            # Skip unresolved races
            if is_winner is None:
                skipped_no_outcome += 1
                continue

            sp_dec = rr.get("sp_dec")
            position = rr.get("position")
            place_threshold = 4 if (field_size or 0) > 12 else 3
            placed = 1 if (position is not None and position <= place_threshold) else 0
            flat_pnl = ((sp_dec - 1) if is_winner else -1.0) if sp_dec else None

            runner = runners_by_key.get(key, {})
            trainer_id = runner.get("trainer_id")
            jockey_id = runner.get("jockey_id")

            sigma = sigma_by_key.get(key, {})
            rpdc = rpdc_by_key.get(key, {})
            rpdc_tags = rpdc.get("rpdc_tags") or []
            if isinstance(rpdc_tags, str):
                try:
                    rpdc_tags = json.loads(rpdc_tags)
                except Exception:
                    rpdc_tags = [rpdc_tags]

            # Resolve course_id and dist_f from racing_horse_runs (authoritative join)
            rhr = rhr_by_key.get(key, {})
            course_id = rhr.get("course_id")
            dist_f_float = rhr.get("distance_f")
            dist_f_str = _norm_dist(dist_f_float) if dist_f_float is not None else None

            # Jockey Racing API lookups
            jc = jc_lkp.get((jockey_id, course_id), {}) if jockey_id and course_id else {}
            jd = jd_lkp.get((jockey_id, dist_f_str), {}) if jockey_id and dist_f_str else {}
            jt = jt_lkp.get((jockey_id, trainer_id), {}) if jockey_id and trainer_id else {}
            tj = tj_lkp.get((trainer_id, jockey_id), {}) if trainer_id and jockey_id else {}

            # Verdict flags
            vf = horse.get("verdict_flags") or []
            tier = next((f.split(":")[1] for f in vf if f.startswith("tier:")), None)
            if not tier:
                tier = vv.get("confidence_level") or horse.get("confidence_level")

            row = {
                "race_id": race_id,
                "horse_id": horse_id,
                "horse_name": horse.get("horse", ""),
                "date": race.get("date", ""),
                "course": course or "",
                "course_id": course_id or "",
                "dist_f": dist_f_str or "",
                "race_class": race.get("class", ""),
                "field_size": field_size,
                "going": race.get("going", ""),
                "trainer_id": trainer_id or "",
                "jockey_id": jockey_id or "",
                "or_rating": runner.get("or_rating"),
                "rpr": runner.get("rpr"),
                "ts_rating": runner.get("ts_rating"),
                # ensemble scores from full_analysis
                "velo_prime_prob": horse.get("velo_prime_prob"),
                "sqpe_v17_prob": horse.get("sqpe_v17_prob"),
                "improvement_score": horse.get("improvement_score"),
                "market_deception_score": horse.get("market_deception_score"),
                "place_prob": horse.get("place_prob"),
                "longshot_score": horse.get("longshot_prob"),
                "comment_intel_score": horse.get("comment_intel_score"),
                "release_day_prob": horse.get("release_day_prob"),
                # context
                "verdict_tier": tier or "",
                "confidence_level": horse.get("confidence_level", ""),
                "verdict_flags_str": "|".join(vf) if isinstance(vf, list) else str(vf),
                # RPDC
                "rpdc_score": rpdc.get("rpdc_release_score"),
                "rpdc_tags_str": "|".join(rpdc_tags) if isinstance(rpdc_tags, list) else "",
                # trainer stats — already embedded in full_analysis
                "trainer_course_win_pct": horse.get("trainer_course_win_pct"),
                "trainer_course_ae": horse.get("trainer_course_ae"),
                "trainer_course_runs": horse.get("trainer_course_runners"),
                "trainer_dist_win_pct": horse.get("hdta_win_pct"),
                "trainer_dist_ae": horse.get("hdta_ae"),
                "trainer_dist_runs": horse.get("trainer_dist_runners"),
                # jockey stats — from Racing API tables
                "jockey_course_win_pct": jc.get("win_pct"),
                "jockey_course_pnl": jc.get("pnl"),
                "jockey_course_ae": jc.get("ae_ratio"),
                "jockey_course_runs": jc.get("runners_or_rides"),
                "jockey_dist_win_pct": jd.get("win_pct"),
                "jockey_dist_pnl": jd.get("pnl"),
                "trainer_jockey_win_pct": tj.get("win_pct"),
                "trainer_jockey_pnl": tj.get("pnl"),
                "jockey_trainer_win_pct": jt.get("win_pct"),
                "jockey_trainer_pnl": jt.get("pnl"),
                # outcomes
                "is_winner": 1 if is_winner else 0,
                "placed": placed,
                "sp_dec": sp_dec,
                "position": position,
                "flat_profit_loss": flat_pnl,
                # sigma
                "sigma_outcome": sigma.get("outcome", ""),
                "sigma_verdict_score": sigma.get("verdict_score"),
                # split filled below
                "split": "",
            }
            training_rows.append(row)

    print(f"  Raw rows built: {len(training_rows)}")
    print(f"  Skipped (no outcome): {skipped_no_outcome}")
    print(f"  Skipped (no full_analysis): {skipped_no_fa}")

    if not training_rows:
        print("ERROR: No training rows built — check velo_verdicts data.")
        return

    # --- Time-aware split ---
    print("Step 6: Time-aware split...")
    training_rows.sort(key=lambda r: r.get("date") or "")
    dates = sorted(set(r["date"] for r in training_rows if r["date"]))
    if dates:
        n = len(dates)
        train_cut = dates[int(n * 0.60)]
        val_cut = dates[int(n * 0.80)]
        for r in training_rows:
            d = r.get("date", "")
            if d <= train_cut:
                r["split"] = "train"
            elif d <= val_cut:
                r["split"] = "validation"
            else:
                r["split"] = "test"
        train_n = sum(1 for r in training_rows if r["split"] == "train")
        val_n = sum(1 for r in training_rows if r["split"] == "validation")
        test_n = sum(1 for r in training_rows if r["split"] == "test")
        print(f"  Train: {train_n} (up to {train_cut})")
        print(f"  Validation: {val_n} (up to {val_cut})")
        print(f"  Test: {test_n} ({val_cut} →)")
    else:
        for r in training_rows:
            r["split"] = "train"

    # --- Write CSV ---
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(training_rows)

    print(f"\nWritten: {out_path}  ({len(training_rows)} rows)")

    # --- Coverage report ---
    n = len(training_rows)
    winners = sum(1 for r in training_rows if r["is_winner"])

    def cov(field: str) -> str:
        has = sum(1 for r in training_rows if r.get(field) is not None and r[field] != "")
        return f"{has}/{n} ({100*has/n:.1f}%)"

    report_lines = [
        "# VÉLØ Sidecar Training Dataset v1",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        f"## Summary",
        f"Total rows: {n}",
        f"Winners: {winners} ({100*winners/n:.1f}%)",
        f"Win baseline: {100*winners/n:.2f}%",
        "",
        "## Time-Aware Split",
        f"| Split | Rows | % |",
        f"|---|---|---|",
    ]
    for sp in ["train","validation","test"]:
        cnt = sum(1 for r in training_rows if r["split"] == sp)
        report_lines.append(f"| {sp} | {cnt} | {100*cnt/n:.1f}% |")

    report_lines += [
        "",
        "## Racing API Coverage",
        f"| Field | Coverage |",
        f"|---|---|",
        f"| trainer_course_win_pct (from full_analysis) | {cov('trainer_course_win_pct')} |",
        f"| trainer_dist_win_pct (from full_analysis) | {cov('trainer_dist_win_pct')} |",
        f"| jockey_course_win_pct (from Supabase) | {cov('jockey_course_win_pct')} |",
        f"| jockey_dist_win_pct (from Supabase) | {cov('jockey_dist_win_pct')} |",
        f"| trainer_jockey_win_pct | {cov('trainer_jockey_win_pct')} |",
        f"| jockey_trainer_win_pct | {cov('jockey_trainer_win_pct')} |",
        f"| rpdc_score | {cov('rpdc_score')} |",
        f"| sigma_outcome | {cov('sigma_outcome')} |",
        "",
        "## Ensemble Score Coverage",
        f"| Field | Coverage |",
        f"|---|---|",
        f"| velo_prime_prob | {cov('velo_prime_prob')} |",
        f"| sqpe_v17_prob | {cov('sqpe_v17_prob')} |",
        f"| improvement_score | {cov('improvement_score')} |",
        f"| market_deception_score | {cov('market_deception_score')} |",
        f"| place_prob | {cov('place_prob')} |",
        "",
        "## Notes",
        "- Jockey course lookups require course_id — races table stores course name only.",
        "  Run `scripts/refresh_racing_api_stat_cache.py --full-refresh` to build local SQLite",
        "  cache for faster lookups once course_id mapping is established.",
        "- Trainer stats extracted directly from velo_verdicts.full_analysis (already embedded).",
        "- Jockey stats fetched from Supabase Racing API tables (jockey_id × dist_f match).",
        "- dist_f matching uses 'Xf' string format — verify against Racing API table values.",
        "- DO NOT use this dataset for live VP weight changes without evidence gate passage.",
        "- TIER: DATA_AVAILABLE → CALIBRATION_TEST only. No live scoring effect.",
    ]

    md_path = Path(args.out.replace(".csv", ".md"))
    md_path.write_text("\n".join(report_lines))
    print(f"Written: {md_path}")

    # Print summary
    print("\n=== Coverage Summary ===")
    for field in ["trainer_course_win_pct","trainer_dist_win_pct",
                  "jockey_course_win_pct","jockey_dist_win_pct",
                  "trainer_jockey_win_pct","jockey_trainer_win_pct",
                  "rpdc_score","improvement_score","velo_prime_prob"]:
        print(f"  {field}: {cov(field)}")

    sr = 100 * winners / n
    print(f"\n=== Baseline (all rows) ===")
    print(f"  Win rate: {sr:.1f}%")
    placed_n = sum(1 for r in training_rows if r["placed"])
    print(f"  Place rate: {100*placed_n/n:.1f}%")


if __name__ == "__main__":
    main()
