#!/usr/bin/env python3
"""
JTC_D_TJ_DAILY_CONFIRMATION_WATCH_V1

Reads today's racecard and surfaces VÉLØ candidates with trainer_jockey_sr
at or above the 80th percentile threshold (D8+).

Governance:
  JTC_D_TJ_CONFIRMATION = CONFIRMED_QUALITY_FILTER
  USE = POST_SCORE_ONLY | NO_SCORING_CHANGE | NO_ROUTER_CHANGE | NO_STAKING_CHANGE

No Telegram. No scoring mutation. Local report only.

Usage:
  python scripts/jtc_d_tj_daily_confirmation_watch.py [--date YYYY-MM-DD]
  python scripts/jtc_d_tj_daily_confirmation_watch.py  # uses today's date
"""
import argparse
import json
import os
import re
import sys
from datetime import date as dt_date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

JTCD_DIR = ROOT / "data" / "features" / "jtc_d"
REPORTS_DIR = ROOT / "data" / "reports"
REPORTS_DIR.mkdir(exist_ok=True)

# 80th percentile threshold — from confirmation audit (D8 boundary)
# Computed dynamically from the TJ profile table
TJ_HIGH_PERCENTILE = 80


def _load_tj_lookup() -> tuple[dict, dict]:
    """Returns (tj_lookup, trainer_surname_map).
    trainer_surname_map: {SURNAME: [fullname, ...]} for fuzzy matching new racecard format.
    """
    path = JTCD_DIR / "trainer_jockey_profile.parquet"
    if not path.exists():
        return {}, {}
    df = pd.read_parquet(path)
    lookup = {
        (str(r["trainer"]).upper(), str(r["jockey"]).upper()): r["jtc_signal"]
        for _, r in df.iterrows() if r["trainer"] and r["jockey"]
    }
    # Build surname → [fullname] index for resolving initials format
    surname_map: dict[str, list] = {}
    for name in df["trainer"].dropna().unique():
        surname = str(name).split()[-1].upper()
        surname_map.setdefault(surname, [])
        if name not in surname_map[surname]:
            surname_map[surname].append(str(name))
    return lookup, surname_map


def _resolve_trainer(raw: object, surname_map: dict) -> str:
    """Extract trainer name from either string or new-format dict.
    New format: {'name': 'OWNER GROUP T Surname', 'id': ...}
    Tries last-word surname lookup against JTC-D trainer table.
    """
    if isinstance(raw, dict):
        combined = str(raw.get("name", ""))
    else:
        combined = str(raw or "")
    combined = combined.strip()
    if not combined:
        return ""
    # Check if combined is already a clean trainer name (no owner prefix)
    # Heuristic: if it contains comma or '&', it's likely owner+trainer concatenated
    if "," not in combined and "&" not in combined and "Syndicate" not in combined:
        return combined  # clean string format
    # Extract trainer: last 1-2 words (initials + surname)
    words = combined.split()
    # Try "INITIAL Surname" form: last 2 words
    if len(words) >= 2:
        candidate_2 = words[-2] + " " + words[-1]
        candidate_1 = words[-1]
        # Look up surname in map
        surname = words[-1].upper()
        matches = surname_map.get(surname, [])
        if len(matches) == 1:
            return matches[0]  # unique match — confident
        elif len(matches) > 1:
            # Try to narrow by initial
            initial = words[-2][0].upper() if len(words) >= 2 else ""
            narrow = [m for m in matches if m.split()[0][0].upper() == initial]
            if len(narrow) == 1:
                return narrow[0]
            if narrow:
                return narrow[0]  # best guess
        # Fallback: return last 2 words as-is
        return candidate_2
    return combined


def _load_tj_threshold() -> float:
    """Derive the 80th percentile threshold from the full TJ profile distribution."""
    path = JTCD_DIR / "trainer_jockey_profile.parquet"
    if not path.exists():
        return 0.18
    df = pd.read_parquet(path)
    return float(df["jtc_signal"].quantile(TJ_HIGH_PERCENTILE / 100))


def _load_racecard(date_str: str) -> list[dict]:
    """Load all runners from the daily racecard snapshot."""
    tag = date_str.replace("-", "_")
    candidates = [
        ROOT / "data" / f"racecards_{tag}_standard.json",
        ROOT / "data" / f"racecards_{tag}.json",
    ]
    for path in candidates:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            rcs = data.get("racecards", data) if isinstance(data, dict) else data
            if isinstance(rcs, list):
                return rcs
    return []


def _load_vp_scores(date_str: str) -> dict[str, float]:
    """Load VP scores for today's candidates from Supabase velo_verdicts.
    Returns {horse_id: velo_prime_prob}. Returns empty dict on failure."""
    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env")
        sb_url = os.getenv("SUPABASE_URL", "")
        sb_key = (os.getenv("SUPABASE_SERVICE_ROLE_KEY")
                  or os.getenv("SUPABASE_SERVICE_KEY")
                  or os.getenv("SUPABASE_KEY", ""))
        if not sb_url or not sb_key:
            return {}
        from supabase import create_client
        db = create_client(sb_url, sb_key)
        rows = (
            db.table("velo_verdicts")
            .select("horse_id, velo_prime_prob, decision_tier")
            .eq("race_date", date_str)
            .execute()
        ).data
        return {r["horse_id"]: r["velo_prime_prob"] for r in rows if r.get("horse_id")}
    except Exception:
        return {}


def _dist_cat(dist_text: str) -> str:
    t = str(dist_text or "").lower().replace(" ", "").replace("½", ".5").replace("¼", ".25")
    m = re.match(r"(?:(\d+)m)?(\d+(?:\.\d+)?f)?", t)
    if not m:
        return "unknown"
    miles = int(m.group(1) or 0)
    furlongs = float((m.group(2) or "0f").replace("f", "") or 0)
    total_f = miles * 8 + furlongs
    if total_f <= 7:
        return "sprint"
    elif total_f <= 10:
        return "mile"
    else:
        return "route"


def _sp_band(sp: float) -> str:
    if sp < 3.0:
        return "short(<3)"
    elif sp < 5.0:
        return "fav(3-5)"
    elif sp < 8.5:
        return "mid(5-8.5)"
    elif sp < 15.0:
        return "long(8.5-15)"
    else:
        return "outsider(15+)"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=str(dt_date.today()))
    args = parser.parse_args()
    date_str = args.date

    print("JTC-D TJ DAILY CONFIRMATION WATCH")
    print("=" * 60)
    print(f"Date: {date_str}")
    print(f"JTC_D_TJ_CONFIRMATION = CONFIRMED_QUALITY_FILTER | POST_SCORE_ONLY")

    # Load TJ lookup + threshold
    tj_lookup, trainer_surname_map = _load_tj_lookup()
    tj_threshold = _load_tj_threshold()
    print(f"TJ lookup: {len(tj_lookup):,} partnerships")
    print(f"TJ threshold (>=D8, 80th pct): {tj_threshold:.4f}")

    # Load racecard
    racecards = _load_racecard(date_str)
    if not racecards:
        print(f"No racecard found for {date_str}. Run run_prime_today.py first.")
        raise SystemExit(1)
    print(f"Racecard: {len(racecards)} races loaded")

    # Load VP scores from Supabase
    vp_scores = _load_vp_scores(date_str)
    print(f"VP scores from Supabase: {len(vp_scores)} candidates")

    # Build runner table
    rows = []
    for rc in racecards:
        race_id = rc.get("race_id", "")
        course = rc.get("course", "")
        off_time = rc.get("off_time", rc.get("off", ""))
        race_name = rc.get("race_name", "")
        dist = rc.get("distance", rc.get("distance_f", ""))
        race_type = rc.get("type", "")
        race_class = rc.get("race_class", "")
        is_handicap = "handicap" in race_name.lower() or "h'cap" in race_name.lower()
        dist_c = _dist_cat(str(dist))

        for runner in rc.get("runners", []):
            hid = runner.get("horse_id", "")
            raw_t = runner.get("trainer", "") or ""
            raw_j = runner.get("jockey", "") or ""
            # Resolve trainer: handles string and new dict {name, id} format
            trainer = _resolve_trainer(raw_t, trainer_surname_map)
            # Jockey: new format dict has clean 'name' field
            jockey = raw_j.get("name", "") if isinstance(raw_j, dict) else str(raw_j)
            odds = runner.get("odds", [])
            sp_est = None
            if odds:
                try:
                    sp_est = float(odds[0].get("decimal", 0))
                except Exception:
                    pass

            tj_key = (trainer.upper(), jockey.upper())
            tj_val = tj_lookup.get(tj_key)
            vp = vp_scores.get(hid, 0.0)
            is_tj_high = tj_val is not None and tj_val >= tj_threshold
            is_velo_candidate = vp > 0
            compound = vp >= 0.30 and is_tj_high

            rows.append({
                "race_id": race_id,
                "course": course,
                "off_time": off_time,
                "horse_id": hid,
                "horse": runner.get("horse", ""),
                "trainer": trainer,
                "jockey": jockey,
                "trainer_jockey_sr": round(tj_val, 5) if tj_val else None,
                "tj_high": is_tj_high,
                "velo_prime_prob": vp,
                "is_velo_candidate": is_velo_candidate,
                "compound": compound,
                "dist_cat": dist_c,
                "is_handicap": is_handicap,
                "race_type": race_type,
                "race_class": race_class,
                "sp_est": sp_est,
                "sp_band": _sp_band(sp_est) if sp_est else None,
            })

    df = pd.DataFrame(rows)
    if len(df) == 0:
        print("No runners found.")
        raise SystemExit(1)

    total_runners = len(df)
    tj_covered = df["trainer_jockey_sr"].notna().sum()
    tj_high = df[df["tj_high"] == True]
    compound_df = df[df["compound"] == True]

    print(f"\nRunners: {total_runners}  |  TJ covered: {tj_covered}  |  "
          f"TJ HIGH: {len(tj_high)}  |  Compound: {len(compound_df)}")

    # ── TJ High candidates ──────────────────────────────────────────────────
    print(f"\n── TJ HIGH (>=D8, trainer_jockey_sr >= {tj_threshold:.4f}) ─────────────────")
    if len(tj_high) == 0:
        print("  None today.")
    else:
        velo_cands = tj_high[tj_high["is_velo_candidate"] == True]
        shadow_watch = tj_high[tj_high["is_velo_candidate"] == False]

        if len(velo_cands) > 0:
            print(f"  VÉLØ CONFIRMED CANDIDATES ({len(velo_cands)} — VP>0 + TJ_HIGH):")
            for _, r in velo_cands.sort_values("velo_prime_prob", ascending=False).iterrows():
                is_compound = "★ COMPOUND" if r["velo_prime_prob"] >= 0.30 else ""
                hcap = "HCP" if r["is_handicap"] else "NH"
                sp_str = f"SP~{r['sp_est']:.1f}" if r["sp_est"] else "SP=?"
                sp_edge = "⚠ SP<3 (no TJ edge)" if r["sp_est"] and r["sp_est"] < 3.0 else ""
                print(f"    {r['off_time']:<6} {r['course']:<18} {r['horse']:<25} "
                      f"VP={r['velo_prime_prob']:.3f}  TJ={r['trainer_jockey_sr']:.4f}  "
                      f"{r['dist_cat']:<8} {hcap:<4} {sp_str:<10} {is_compound} {sp_edge}")
        else:
            print("  No VÉLØ candidates with TJ_HIGH today.")

        if len(shadow_watch) > 0:
            print(f"\n  SHADOW WATCH ({len(shadow_watch)} — TJ_HIGH but VP=0, not in VÉLØ selection):")
            for _, r in shadow_watch.sort_values("trainer_jockey_sr", ascending=False).head(10).iterrows():
                hcap = "HCP" if r["is_handicap"] else "NH"
                sp_str = f"SP~{r['sp_est']:.1f}" if r["sp_est"] else "SP=?"
                print(f"    {r['off_time']:<6} {r['course']:<18} {r['horse']:<25} "
                      f"TJ={r['trainer_jockey_sr']:.4f}  {r['dist_cat']:<8} {hcap} {sp_str}")

    # ── Summary ─────────────────────────────────────────────────────────────
    print(f"\n── Summary ─────────────────────────────────────────────────────")
    print(f"  TJ coverage today:        {tj_covered}/{total_runners} runners ({tj_covered/total_runners:.0%})")
    print(f"  TJ HIGH count:            {len(tj_high)}")
    print(f"  VÉLØ confirmed (TJ_HIGH): {len(tj_high[tj_high['is_velo_candidate']==True])}")
    print(f"  Compound (VP≥0.30+TJ):    {len(compound_df)}")
    print(f"\n  Governance: JTC_D_TJ_CONFIRMATION = CONFIRMED_QUALITY_FILTER")
    print(f"  Status: POST_SCORE_ONLY | NO_SCORING_CHANGE | NO_STAKING_CHANGE")

    # ── Write outputs ────────────────────────────────────────────────────────
    out_rows = tj_high.to_dict(orient="records")
    output = {
        "date": date_str,
        "version": "JTC_D_TJ_DAILY_CONFIRMATION_WATCH_V1",
        "tj_threshold": round(tj_threshold, 5),
        "tj_percentile": TJ_HIGH_PERCENTILE,
        "total_runners": total_runners,
        "tj_covered": int(tj_covered),
        "tj_high_count": len(tj_high),
        "velo_confirmed_count": int((tj_high["is_velo_candidate"] == True).sum()),
        "compound_count": len(compound_df),
        "tj_high_runners": out_rows,
        "governance": "JTC_D_TJ_CONFIRMATION=CONFIRMED_QUALITY_FILTER | POST_SCORE_ONLY | NO_SCORING_CHANGE",
    }

    json_path = REPORTS_DIR / "jtc_d_tj_daily_confirmation_latest.json"
    json_path.write_text(json.dumps(output, indent=2, default=str))
    print(f"\nWritten: {json_path}")

    md_lines = [
        f"# JTC-D TJ Daily Confirmation Watch — {date_str}",
        "",
        f"**TJ threshold (D8+, 80th pct):** {tj_threshold:.4f}",
        f"**TJ coverage:** {tj_covered}/{total_runners} runners",
        f"**TJ HIGH:** {len(tj_high)}  |  **VÉLØ confirmed:** {int((tj_high['is_velo_candidate']==True).sum())}  |  **Compound:** {len(compound_df)}",
        "",
        "---",
        "",
        "## TJ HIGH Candidates",
        "",
    ]
    if len(tj_high) == 0:
        md_lines.append("None today.")
    else:
        md_lines += [
            "| Time | Course | Horse | VP | TJ Signal | Dist | NH/HCP | SP est |",
            "|---|---|---|---|---|---|---|---|",
        ]
        for _, r in tj_high.sort_values(["is_velo_candidate", "velo_prime_prob"],
                                         ascending=[False, False]).iterrows():
            compound_flag = " ★" if r["compound"] else ""
            sp_warn = " ⚠" if r["sp_est"] and r["sp_est"] < 3.0 else ""
            md_lines.append(
                f"| {r['off_time']} | {r['course']} | **{r['horse']}**{compound_flag} | "
                f"{r['velo_prime_prob']:.3f} | {r['trainer_jockey_sr']:.4f} | "
                f"{r['dist_cat']} | {'HCP' if r['is_handicap'] else 'NH'} | "
                f"{r['sp_est'] if r['sp_est'] else '?'}{sp_warn} |"
            )
    md_lines += [
        "",
        "★ = Compound signal (VP≥0.30 + TJ_high)  ⚠ = SP<3.0, TJ edge absent",
        "",
        "---",
        "",
        "```",
        "JTC_D_TJ_CONFIRMATION = CONFIRMED_QUALITY_FILTER",
        "USE = POST_SCORE_ONLY | NO_SCORING_CHANGE | NO_ROUTER_CHANGE | NO_STAKING_CHANGE",
        "```",
    ]
    md_path = REPORTS_DIR / "jtc_d_tj_daily_confirmation_latest.md"
    md_path.write_text("\n".join(md_lines))
    print(f"Written: {md_path}")


if __name__ == "__main__":
    main()
