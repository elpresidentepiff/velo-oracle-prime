"""
VELO v17 SQPE Predictions — full ranked card, all suggestions.

For each runner: fetches live form from Racing API, computes 37 v17 features,
scores with SQPE v17 model, ranks within race.

Usage:
    python scripts/v17_predict_today.py --date 2026-03-16
"""
import argparse
import logging
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

logging.basicConfig(level=logging.WARNING)
log = logging.getLogger("velo.v17")
log.setLevel(logging.INFO)

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = (
    os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    or os.getenv("SUPABASE_SERVICE_KEY")
    or os.getenv("SUPABASE_KEY", "")
)


def flag(prob: float, rank: int, field: int, odds: float) -> str:
    """Simple signal flag for display."""
    implied = 1.0 / odds if odds and odds > 1 else 0.5
    edge = prob - implied
    if rank == 1 and prob >= 0.28:
        return "*** STRONG"
    if edge >= 0.05 and odds and 3.0 <= odds <= 20.0:
        return "**  VALUE"
    if rank <= 3 and prob >= 0.15:
        return "*   WATCH"
    if rank > field - 2 and prob < 0.06:
        return "    LAY"
    return "    ---"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default="2026-03-16")
    args = parser.parse_args()

    if not SUPABASE_URL or not SUPABASE_KEY:
        print("ERROR: SUPABASE credentials missing"); sys.exit(1)

    sb = create_client(SUPABASE_URL, SUPABASE_KEY)

    # ── Load races ─────────────────────────────────────────────────────────
    races_resp = sb.table("races").select("*").eq("date", args.date).order("time").execute()
    races = races_resp.data or []
    if not races:
        print(f"No races for {args.date}"); sys.exit(0)
    print(f"VELO v17 PREDICTIONS — {args.date}  ({len(races)} races)")

    # ── Load model ─────────────────────────────────────────────────────────
    import importlib.util, types

    def _load_module(name, path):
        spec = importlib.util.spec_from_file_location(name, path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)
        return mod

    base = Path(__file__).parent.parent

    # Load without triggering app.services.__init__ (which needs pydantic_settings)
    mm_mod = _load_module("app.services.model_manager",
                          base / "app/services/model_manager.py")
    fe_mod = _load_module("app.services.feature_engineering",
                          base / "app/services/feature_engineering.py")
    v17_mod = _load_module("app.services.v17_feature_extractor",
                           base / "app/services/v17_feature_extractor.py")

    get_model_manager = mm_mod.get_model_manager
    V17FeatureExtractor = v17_mod.V17FeatureExtractor
    extract_features = fe_mod.extract_features

    mm = get_model_manager()
    extractor = V17FeatureExtractor()

    grand_selections = []   # all STRONG + VALUE across day

    for race in races:
        race_id = race["race_id"]
        course  = race.get("course", "")
        going   = race.get("going", "Good")
        dist_f  = race.get("distance_f", 16)
        off_time = str(race.get("time", ""))[:5]
        race_class = race.get("class", "")
        race_type = race.get("race_type", "")
        raw_race = race.get("raw") or {}

        # Build race dict for feature builder
        race_dict = {
            "course":      course,
            "going":       going,
            "dist":        raw_race.get("distance", f"{dist_f}f"),
            "distance_f":  dist_f,
            "class":       race_class,
            "ran":         race.get("runners_count", 10),
        }

        runners_resp = sb.table("runners").select("*").eq("race_id", race_id).execute()
        runners = runners_resp.data or []
        if not runners:
            continue

        field_size = len(runners)

        # ── Score each runner ───────────────────────────────────────────────
        scored = []
        for r in runners:
            raw_r = r.get("raw") or {}
            horse_id = r.get("horse_id", "")
            odds = raw_r.get("odds", 10.0) or 10.0
            sp_rank_val = raw_r.get("sp_rank", 5)
            is_fav = raw_r.get("is_fav", 0)

            runner_dict = {
                "horse_id":       horse_id,
                "horse":          r.get("horse_name", ""),
                "sp":             odds,
                "odds":           odds,
                "or":             r.get("or_rating") or 0,
                "official_rating": r.get("or_rating") or 0,
                "rpr":            r.get("rpr") or 0,
                "ts":             r.get("ts_rating") or 0,
                "wgt":            r.get("weight", ""),
                "draw":           r.get("draw") or 0,
                "age":            r.get("age") or 0,
                "jockey":         r.get("jockey", ""),
                "sp_rank":        sp_rank_val,
                "is_fav":         is_fav,
                "or_vs_field":    0.0,
                "rpr_vs_field":   0.0,
            }

            # v16 base features
            base_features = extract_features(runner_dict, race_dict, historical=None)

            # v17 doctrine features (live Racing API fetch)
            race_context = {
                "course":   course,
                "going":    going,
                "dist_f":   dist_f,
                "or_num":   r.get("or_rating"),
                "sp_dec":   odds,
                "jockey":   r.get("jockey", ""),
                "is_fav":   is_fav,
            }
            trainer_form = {}
            td14 = raw_r.get("trainer_14_days") or {}
            if td14:
                try:
                    trainer_form = {
                        "wins":   int(td14.get("wins", 0)),
                        "starts": int(td14.get("runs", 1)),
                    }
                except (TypeError, ValueError):
                    pass

            if horse_id:
                doctrine = extractor.extract(horse_id, race_context, trainer_form)
                base_features.update(doctrine)

            # Predict
            prob = mm.predict_sqpe(base_features, runner=runner_dict, race=race_dict)
            scored.append({
                "horse_id":   horse_id,
                "horse_name": r.get("horse_name", "Unknown"),
                "trainer":    r.get("trainer", ""),
                "jockey":     r.get("jockey", ""),
                "or_rating":  r.get("or_rating") or 0,
                "form":       r.get("form", ""),
                "odds":       odds,
                "prob":       prob,
            })

        # Rank by probability
        scored.sort(key=lambda x: x["prob"], reverse=True)
        total_prob = sum(s["prob"] for s in scored)

        # Print race header
        print(f"\n{'='*72}")
        print(f"  {course.upper()}  {off_time}  |  {race_type}  {race_class}  "
              f"|  {going}  |  {field_size} runners")
        print(f"  {race['race_name']}")
        print(f"{'='*72}")
        print(f"  {'#':<3} {'Horse':<28} {'Odds':>6} {'Prob':>6} {'OR':>4} {'Form':<10} Signal")
        print(f"  {'-'*67}")

        for rank, s in enumerate(scored, 1):
            sig = flag(s["prob"], rank, field_size, s["odds"])
            prob_pct = s["prob"] * 100
            print(
                f"  {rank:<3} {s['horse_name']:<28} "
                f"{s['odds']:>5.1f}x "
                f"{prob_pct:>5.1f}% "
                f"{s['or_rating']:>4} "
                f"{s['form']:<10} "
                f"{sig}"
            )
            if "STRONG" in sig or "VALUE" in sig:
                grand_selections.append({
                    "course": course,
                    "time": off_time,
                    "horse": s["horse_name"],
                    "odds": s["odds"],
                    "prob": s["prob"],
                    "signal": sig.strip(),
                    "or": s["or_rating"],
                })

        print(f"  Total prob mass: {total_prob*100:.1f}%  "
              f"(field-normal: {100/field_size:.1f}% each)")

    # ── Day summary ─────────────────────────────────────────────────────────
    print(f"\n{'='*72}")
    print(f"  VELO v17 DAY CARD — {args.date}")
    print(f"  {len(grand_selections)} actionable selections")
    print(f"{'='*72}")
    if grand_selections:
        for sel in grand_selections:
            implied = 1.0 / sel["odds"] if sel["odds"] > 1 else 0
            edge = sel["prob"] - implied
            print(
                f"  [{sel['signal']:<12}] {sel['course']} {sel['time']}  "
                f"{sel['horse']}  @ {sel['odds']:.1f}  "
                f"prob={sel['prob']*100:.1f}%  "
                f"edge={edge*100:+.1f}%"
            )
    else:
        print("  No STRONG or VALUE signals today across all 20 races.")
        print("  Top picks per race shown above — all ranked #1 horses are")
        print("  model's best choice within each field.")
    print(f"{'='*72}\n")


if __name__ == "__main__":
    main()
