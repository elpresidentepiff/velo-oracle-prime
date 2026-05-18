#!/usr/bin/env python3
"""
BUILD_RP_RUNNER_PROFILE_V1

Builds rp_runner_profile_latest.parquet from Racing Post PDF files (1-5 only).
File 6 (F_0010 selections) is quarantined — never touches scoring.

Pipeline:
  1. Find all RP PDFs for the target date in data/incoming_pdfs/
  2. Quarantine F_0010_XX (File 6) → data/audit/rp_competitor_selections_latest.json
  3. Parse F_0012_XX (colour card backbone) → horse identity, OR/TS/RPR, form, jockey
  4. Enrich with horse_id/trainer_id/jockey_id from Racing API racecard snapshots
  5. Join JTC-D lookup tables (trainer/jockey course+dist profiles with shrinkage)
  6. Output data/features/rp_runner_profile_latest.parquet + .json

Governance:
  POST_SCORE_ONLY | NO_SCORING_MUTATION | NO_MODEL_USE for File 6
  Advisory only — does not alter scoring pipeline

Usage:
  python scripts/build_rp_runner_profile.py [--date YYYY-MM-DD] [--dry-run]
"""
import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from workers.colour_card_parser import parse_colour_card_pdf
from workers.ingestion_spine.racingpost_pdf.normalize import normalize_horse_name

INCOMING = ROOT / "data" / "incoming_pdfs"
RACECARDS_DIR = ROOT / "data"
JTCD_DIR = ROOT / "data" / "features" / "jtc_d"
FEATURES_DIR = ROOT / "data" / "features"
AUDIT_DIR = ROOT / "data" / "audit"
FEATURES_DIR.mkdir(exist_ok=True)
AUDIT_DIR.mkdir(exist_ok=True)

VENUE_MAP = {
    "ASC": "Ascot", "AYR": "Ayr", "BAT": "Bath", "BEV": "Beverley",
    "CAT": "Catterick", "CHL": "Cheltenham", "CHP": "Chepstow",
    "CHS": "Chester", "COR": "Cork", "CUR": "Curragh", "DON": "Doncaster",
    "DUN": "Dundalk", "EPS": "Epsom", "FAI": "Fairyhouse", "FAK": "Fakenham",
    "FON": "Fontwell", "GOO": "Goodwood", "GOW": "Gowran Park",
    "HAM": "Hamilton", "HAY": "Haydock", "HER": "Hereford", "HEX": "Hexham",
    "KEL": "Kelso", "KEM": "Kempton", "KLB": "Kilbeggan", "KLN": "Killarney",
    "LEI": "Leicester", "LEO": "Leopardstown", "LIM": "Limerick",
    "LIN": "Lingfield", "LUD": "Ludlow", "MUS": "Musselburgh",
    "NAA": "Naas", "NAB": "Newton Abbot", "NAV": "Navan", "NBY": "Newbury",
    "NCS": "Newcastle", "NMK": "Newmarket", "NOT": "Nottingham",
    "PER": "Perth", "PON": "Pontefract", "PUN": "Punchestown",
    "RED": "Redcar", "SAL": "Salisbury", "SAN": "Sandown", "SLI": "Sligo",
    "STH": "Southwell", "TAU": "Taunton", "WAR": "Warwick",
    "WDR": "Windsor", "WIN": "Windsor", "WOL": "Wolverhampton",
    "YAR": "Yarmouth", "YOR": "York", "CHE": "Chelmsford",
    "CHF": "Chelmsford", "Ffo": "Ffos Las", "FFO": "Ffos Las",
    "FFF": "Ffos Las", "EXE": "Exeter", "PLU": "Plumpton",
    "UTT": "Uttoxeter", "STR": "Stratford", "BAN": "Bangor-On-Dee",
    "MKT": "Market Rasen", "HUN": "Huntingdon", "WOR": "Worcester",
    "BRI": "Brighton", "CHT": "Chepstow",
}


def _find_pdfs(date_str: str) -> dict[str, list[Path]]:
    """Find all RP PDFs for a date, grouped by file type code."""
    date_tag = date_str.replace("-", "")
    groups: dict[str, list[Path]] = {}

    search_roots = [INCOMING / date_str, INCOMING]
    for root in search_roots:
        if not root.exists():
            continue
        for pdf in sorted(root.glob(f"*_{date_tag}_*.pdf")):
            stem = pdf.stem.upper()
            for code in ["F_0010", "F_0012", "F_0015_OR", "F_0011", "F_0016", "F_0032_TS", "F_0015_PM"]:
                if f"_{code}_" in stem or stem.endswith(f"_{code}"):
                    groups.setdefault(code, []).append(pdf)
                    break

    return groups


def _venue_from_pdf(pdf: Path) -> str:
    code = pdf.stem.split("_")[0]
    return VENUE_MAP.get(code, VENUE_MAP.get(code.upper(), code))


def _date_from_pdf(pdf: Path) -> str:
    parts = pdf.stem.split("_")
    raw = parts[1] if len(parts) > 1 else ""
    return f"{raw[:4]}-{raw[4:6]}-{raw[6:]}" if len(raw) == 8 else ""


def _quarantine_selections(pdfs: list[Path], date_str: str) -> dict:
    """Parse F_0010 files and write to audit dir."""
    if not pdfs:
        return {"quarantined": 0}

    try:
        from scripts.parse_industry_selections import parse_selection_box_pdf  # type: ignore
    except ImportError:
        try:
            sys.path.insert(0, str(ROOT / "scripts"))
            from parse_industry_selections import parse_selection_box_pdf  # type: ignore
        except ImportError:
            return {"quarantined": len(pdfs), "error": "parse_industry_selections not importable"}

    all_venues = []
    for pdf in pdfs:
        try:
            course, d, col_xs, picks = parse_selection_box_pdf(str(pdf))
            race_times = sorted(col_xs.keys()) if col_xs else []
            all_venues.append({
                "course": course,
                "race_times": race_times,
                "tipster_count": len(picks),
                "tipsters": picks,
                "classification": "POST_SCORE_ONLY|NO_SCORING_USE|NO_MODEL_USE|NO_ROUTER_USE|NO_STAKING_USE",
            })
        except Exception as e:
            all_venues.append({"file": str(pdf), "error": str(e)})

    output = {
        "date": date_str,
        "classification": "POST_SCORE_ONLY|NO_SCORING_USE|NO_MODEL_USE|NO_ROUTER_USE|NO_STAKING_USE",
        "governance": "File 6 quarantine — competitor selections must not influence VELO scoring",
        "venues": all_venues,
    }
    out_path = AUDIT_DIR / "rp_competitor_selections_latest.json"
    out_path.write_text(json.dumps(output, indent=2))
    return {"quarantined": len(pdfs), "output": str(out_path)}


def _build_racecard_bridge(date_str: str) -> dict[str, dict]:
    """
    Build normalized_horse_name → {horse_id, trainer_id, trainer, jockey_id, jockey, ...}
    from Racing API racecard snapshot JSONs.
    """
    date_tag = date_str.replace("-", "_")
    candidates = [
        RACECARDS_DIR / f"racecards_{date_tag}_standard.json",
        RACECARDS_DIR / f"racecards_{date_tag}.json",
    ]

    bridge: dict[str, dict] = {}
    for cand in candidates:
        if not cand.exists():
            continue
        try:
            data = json.loads(cand.read_text(encoding="utf-8"))
            racecards = data.get("racecards", data) if isinstance(data, dict) else data
            if not isinstance(racecards, list):
                continue
            for rc in racecards:
                for runner in rc.get("runners", []):
                    horse = runner.get("horse") or ""
                    key = normalize_horse_name(horse)
                    if not key:
                        continue
                    bridge[key] = {
                        "horse_id": runner.get("horse_id"),
                        "trainer": runner.get("trainer"),
                        "trainer_id": runner.get("trainer_id"),
                        "jockey": runner.get("jockey"),
                        "jockey_id": runner.get("jockey_id"),
                        "trainer_rtf": runner.get("trainer_rtf"),
                        "ofr_api": runner.get("ofr"),
                        "rpr_api": runner.get("rpr"),
                        "ts_api": runner.get("ts"),
                        "form_api": runner.get("form"),
                        "comment_api": runner.get("comment"),
                        "spotlight_api": runner.get("spotlight"),
                        "race_id_api": rc.get("race_id"),
                    }
        except Exception:
            continue
        break

    return bridge


def _load_jtcd_profiles() -> dict[str, pd.DataFrame | None]:
    profiles = {}
    for name in ["trainer_course", "trainer_dist", "jockey_course",
                 "jockey_dist", "trainer_jockey"]:
        path = JTCD_DIR / f"{name}_profile.parquet"
        profiles[name] = pd.read_parquet(path) if path.exists() else None
    return profiles


def _lookup_jtcd(profiles: dict, trainer: str, jockey: str,
                  course: str, dist_band: str) -> dict:
    out: dict = {}

    def _get(df: pd.DataFrame | None, key_cols: list, key_vals: list) -> float | None:
        if df is None or not all(key_vals):
            return None
        mask = pd.Series([True] * len(df))
        for col, val in zip(key_cols, key_vals):
            if col not in df.columns:
                return None
            mask = mask & (df[col].str.upper() == str(val).upper())
        rows = df[mask]
        return round(float(rows.iloc[0]["jtc_signal"]), 4) if len(rows) > 0 else None

    out["trainer_course_sr"] = _get(profiles["trainer_course"], ["trainer", "course"], [trainer, course])
    out["trainer_dist_sr"] = _get(profiles["trainer_dist"], ["trainer", "dist_band"], [trainer, dist_band])
    out["jockey_course_sr"] = _get(profiles["jockey_course"], ["jockey", "course"], [jockey, course])
    out["jockey_dist_sr"] = _get(profiles["jockey_dist"], ["jockey", "dist_band"], [jockey, dist_band])
    out["trainer_jockey_sr"] = _get(profiles["trainer_jockey"], ["trainer", "jockey"], [trainer, jockey])
    return out


def _dist_band_from_text(dist_text: str) -> str:
    """Convert distance text (e.g. '6f', '1m2f') to canonical band."""
    import re
    dist_text = (dist_text or "").lower().strip()
    m = re.match(r"(?:(\d+)m\s*)?(?:(\d+(?:[½⅝¾¼])?)\s*f)?", dist_text)
    if not m:
        return "unknown"
    miles = int(m.group(1)) if m.group(1) else 0
    furlongs_raw = str(m.group(2) or "0").replace("½", ".5").replace("⅝", ".625").replace("¾", ".75").replace("¼", ".25")
    try:
        furlongs_total = miles * 8 + float(furlongs_raw)
    except ValueError:
        return "unknown"
    bins = [(5.5, "5f"), (6.5, "6f"), (7.5, "7f"), (8.5, "8f"),
            (10.5, "9-10f"), (12.5, "11-12f"), (14.5, "13-14f"), (17.5, "15-17f")]
    for ceiling, label in bins:
        if furlongs_total < ceiling:
            return label
    return "18f+"


def _extract_dist_from_race_info(race_info: str) -> str:
    """Extract distance text from race info string."""
    m = re.search(r"\b(\d+(?:m\s*)?\d*f)\b", race_info, re.IGNORECASE)
    return m.group(1) if m else ""


def _extract_class_from_race_info(race_info: str) -> str:
    m = re.search(r"Class\s+(\d+)", race_info, re.IGNORECASE)
    return f"Class {m.group(1)}" if m else ""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    date = args.date

    print(f"RP RUNNER PROFILE BUILD V1 — {date}")
    print("=" * 60)

    # ── Step 1: Find PDFs ────────────────────────────────────────
    pdf_groups = _find_pdfs(date)
    total_pdfs = sum(len(v) for v in pdf_groups.values())
    print(f"Found {total_pdfs} PDFs for {date}:")
    for code, pdfs in sorted(pdf_groups.items()):
        print(f"  {code}: {len(pdfs)} files")

    if not pdf_groups.get("F_0012"):
        print(f"\nNo F_0012_XX backbone files found for {date}. Cannot build profile.")
        sys.exit(1)

    # ── Step 2: Quarantine File 6 ────────────────────────────────
    sel_pdfs = pdf_groups.pop("F_0010", [])
    q = _quarantine_selections(sel_pdfs, date)
    print(f"\nFile 6 quarantine: {q.get('quarantined',0)} files → "
          f"{q.get('output','(not written)')}")

    # ── Step 3: Identity bridge ──────────────────────────────────
    bridge = _build_racecard_bridge(date)
    print(f"Identity bridge: {len(bridge)} horses from Racing API snapshot")

    # ── Step 4: JTC-D profiles ───────────────────────────────────
    jtcd = _load_jtcd_profiles()
    jtcd_available = sum(1 for v in jtcd.values() if v is not None)
    print(f"JTC-D profiles: {jtcd_available}/5 tables loaded")

    # ── Step 5: Parse colour cards ───────────────────────────────
    all_rows: list[dict] = []
    venues_processed = 0
    venues_failed = []

    for pdf in pdf_groups.get("F_0012", []):
        venue = _venue_from_pdf(pdf)
        try:
            races = parse_colour_card_pdf(pdf)
        except Exception as e:
            venues_failed.append(f"{venue}: {e}")
            continue

        if not races:
            venues_failed.append(f"{venue}: 0 races parsed")
            continue

        venues_processed += 1

        for race_time, race_data in races.items():
            race_info = race_data.get("race_info", "")
            dist_text = _extract_dist_from_race_info(race_info)
            dist_band = _dist_band_from_text(dist_text)
            class_band = _extract_class_from_race_info(race_info)
            spotlight_verdict = race_data.get("spotlight_verdict", "")
            betting_forecast = race_data.get("betting_forecast", "")

            # Build race_id consistent with API format
            race_id = f"{date}_{venue}_{race_time.replace('.', '')}"

            for horse_data in race_data.get("horses", []):
                horse_name = horse_data.get("horse_name", "")
                norm_name = normalize_horse_name(horse_name)
                id_data = bridge.get(norm_name, {})

                # Jockey from colour card (more reliable per-race than API for same day)
                jockey_cc = horse_data.get("jockey", "")
                jockey = jockey_cc or id_data.get("jockey", "")
                jockey_id = id_data.get("jockey_id")

                trainer = id_data.get("trainer", "")
                trainer_id = id_data.get("trainer_id")
                horse_id = id_data.get("horse_id")

                jtcd_data = _lookup_jtcd(jtcd, trainer, jockey, venue, dist_band)

                # OR/TS/RPR: colour card is authoritative (from RP PDF, not API)
                cc_or = horse_data.get("cc_or")
                cc_ts = horse_data.get("cc_ts")
                cc_rpr = horse_data.get("cc_rpr")
                # API values as fallback for zero/missing
                or_rating = cc_or or id_data.get("ofr_api")
                ts_rating = cc_ts or id_data.get("ts_api")
                rpr_rating = cc_rpr or id_data.get("rpr_api")

                # Spotlight comment from API (per-horse) or race verdict (from CC)
                horse_comment = id_data.get("spotlight_api") or id_data.get("comment_api") or ""

                # Missing field audit
                missing = []
                if not horse_id: missing.append("horse_id")
                if not trainer: missing.append("trainer")
                if not or_rating: missing.append("or_rating")
                if not ts_rating: missing.append("ts_rating")
                if not horse_comment: missing.append("comment")
                quality_score = round(1.0 - len(missing) / 8.0, 2)

                row = {
                    # Race identity
                    "race_date": date,
                    "course": venue,
                    "race_id": race_id,
                    "off_time": race_time,
                    "race_info": race_info[:120],
                    "dist_text": dist_text,
                    "dist_band": dist_band,
                    "class_band": class_band,
                    "spotlight_verdict": spotlight_verdict[:300] if spotlight_verdict else "",
                    "betting_forecast": betting_forecast[:200] if betting_forecast else "",
                    # Runner identity
                    "horse": horse_name,
                    "horse_norm": norm_name,
                    "horse_id": horse_id,
                    "stall": horse_data.get("stall"),
                    "age": horse_data.get("age"),
                    "weight": horse_data.get("weight", ""),
                    "headgear": horse_data.get("headgear_cc", ""),
                    "form_figures": horse_data.get("form_string", ""),
                    "days_since_run": horse_data.get("days_since_last_run"),
                    "breeding": horse_data.get("breeding", ""),
                    # Ratings from RP colour card
                    "current_or": or_rating,
                    "current_ts": ts_rating,
                    "current_rpr": rpr_rating,
                    # Course/dist specialist flags
                    "course_winner": horse_data.get("course_winner_cc", False),
                    "dist_winner": horse_data.get("dist_winner_cc", False),
                    "cd_winner": horse_data.get("cd_winner_cc", False),
                    "bf_flag": horse_data.get("bf_flag", False),
                    # People — identity bridge (trainer) + CC (jockey) merged
                    "trainer": trainer,
                    "trainer_id": trainer_id,
                    "jockey": jockey,
                    "jockey_id": jockey_id,
                    "trainer_rtf": id_data.get("trainer_rtf"),
                    # JTC-D signals (shrinkage-adjusted from raceform_v17, 10yr history)
                    "trainer_course_sr": jtcd_data.get("trainer_course_sr"),
                    "trainer_dist_sr": jtcd_data.get("trainer_dist_sr"),
                    "jockey_course_sr": jtcd_data.get("jockey_course_sr"),
                    "jockey_dist_sr": jtcd_data.get("jockey_dist_sr"),
                    "trainer_jockey_sr": jtcd_data.get("trainer_jockey_sr"),
                    # Spotlight narrative (from Racing API snapshot)
                    "horse_comment": horse_comment,
                    # Quality
                    "rp_data_quality_score": quality_score,
                    "rp_missing_fields": ",".join(missing),
                }
                all_rows.append(row)

    print(f"\nProcessed {venues_processed} venues, {len(all_rows)} runner rows")
    if venues_failed:
        print(f"Failed venues ({len(venues_failed)}): {venues_failed}")

    if not all_rows:
        print("No runner rows produced — check PDF parse errors above")
        sys.exit(1)

    df = pd.DataFrame(all_rows)

    # Quality report
    id_cov = df["horse_id"].notna().mean()
    or_cov = df["current_or"].notna().mean()
    ts_cov = df["current_ts"].notna().mean()
    trainer_cov = (df["trainer"] != "").mean()
    jtcd_cov = df["trainer_course_sr"].notna().mean()
    avg_q = df["rp_data_quality_score"].mean()

    print(f"\nQuality:")
    print(f"  horse_id coverage:    {id_cov:.1%}")
    print(f"  trainer coverage:     {trainer_cov:.1%}")
    print(f"  OR coverage:          {or_cov:.1%}")
    print(f"  TS coverage:          {ts_cov:.1%}")
    print(f"  JTC-D coverage:       {jtcd_cov:.1%}")
    print(f"  Avg quality score:    {avg_q:.2f}")

    if args.dry_run:
        print("\nDRY RUN — no files written")
        print(df[["horse", "course", "off_time", "current_or", "jockey",
                   "horse_id", "trainer_course_sr"]].head(10).to_string())
        return

    # ── Coerce numeric columns ───────────────────────────────────
    def _to_int(col: pd.Series) -> pd.Series:
        return pd.to_numeric(col, errors="coerce").astype("Int64")

    for c in ["current_or", "current_ts", "current_rpr", "stall", "age", "days_since_run"]:
        if c in df.columns:
            df[c] = _to_int(df[c])

    for c in ["trainer_course_sr", "trainer_dist_sr", "jockey_course_sr",
              "jockey_dist_sr", "trainer_jockey_sr", "rp_data_quality_score", "trainer_rtf"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    # ── Write outputs ────────────────────────────────────────────
    parquet_path = FEATURES_DIR / "rp_runner_profile_latest.parquet"
    json_path = FEATURES_DIR / "rp_runner_profile_latest.json"

    df.to_parquet(parquet_path, index=False)
    print(f"\nWritten: {parquet_path}  ({len(df)} rows)")

    json_out: dict = {"date": date, "runner_count": len(df), "races": {}}
    for race_id, group in df.groupby("race_id"):
        json_out["races"][str(race_id)] = group.to_dict(orient="records")
    json_path.write_text(json.dumps(json_out, indent=2, default=str))
    print(f"Written: {json_path}")

    print(f"\nGovernance: NO_SCORING_CHANGE | NO_MODEL_CHANGE | RP_RUNNER_PROFILE_V1")
    return df


if __name__ == "__main__":
    main()
