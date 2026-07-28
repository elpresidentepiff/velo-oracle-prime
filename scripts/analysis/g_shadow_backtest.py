#!/usr/bin/env python3
"""
G Shadow Multiplier Backtest — Fix 5 (analysis only, no writes)

For each date with both verdict + sigma files, extracts the g_shadow_multiplier
for each top-pick horse and buckets by outcome (WIN/LOSS). Reports whether G
amplifies winners or losers — determines safety of flipping VELO_G_SHADOW_MODE=live.
"""
from __future__ import annotations
import json
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parents[2]
VERDICT_DIR = ROOT / "data"
SIGMA_DIR = ROOT / "data" / "sigma_results"


def load_json(p: Path) -> dict | list | None:
    try:
        return json.loads(p.read_text())
    except Exception as e:
        print(f"  [WARN] Cannot read {p}: {e}")
        return None


def bucket(mult: float) -> str:
    if mult < 0.80:
        return "A_STRONG_DAMPEN (<0.80)"
    if mult < 0.95:
        return "B_MILD_DAMPEN (0.80-0.95)"
    if mult < 1.05:
        return "C_NEUTRAL (0.95-1.05)"
    if mult < 1.20:
        return "D_MILD_AMPLIFY (1.05-1.20)"
    return "E_STRONG_AMPLIFY (>1.20)"


def main():
    sigma_files = sorted(SIGMA_DIR.glob("sigma_results_*.json"))
    dates = [f.stem.replace("sigma_results_", "") for f in sigma_files]

    bucket_stats: dict[str, dict] = defaultdict(lambda: {"wins": 0, "total": 0, "vp_sum": 0.0, "adj_vp_sum": 0.0})
    races_analysed = 0
    races_no_mult = 0

    for date_tag in dates:
        verdict_path = VERDICT_DIR / f"velo_prime_verdicts_{date_tag}.json"
        sigma_path = SIGMA_DIR / f"sigma_results_{date_tag}.json"
        if not verdict_path.exists():
            continue

        verdicts = load_json(verdict_path)
        sigma = load_json(sigma_path)
        if not verdicts or not sigma:
            continue

        # Build sigma lookup: race_id → outcome (WIN / MISS / PLACED)
        sigma_map: dict[str, str] = {}
        for row in sigma.get("rows", []):
            race_id = str(row.get("race_id", ""))
            outcome = row.get("outcome", "")
            if race_id and outcome in ("WIN", "MISS", "PLACED"):
                sigma_map[race_id] = outcome

        # Process each race verdict — handles two schemas:
        # Schema A (pre-July 27): flat list of runner-level dicts with full_analysis.predictions
        # Schema B (July 27+): list of race-level dicts with race["top"]["g_shadow_multiplier"]
        for race in verdicts:
            race_id = str(race.get("race_id", ""))
            if race_id not in sigma_map:
                continue

            outcome = sigma_map[race_id]
            is_win = (outcome == "WIN")

            mult = None
            vp = 0.0

            top_obj = race.get("top")  # Schema B
            if top_obj and isinstance(top_obj, dict):
                mult = top_obj.get("g_shadow_multiplier")
                vp = float(top_obj.get("velo_prime_prob") or 0)
            else:
                # Schema A: top_rank_horse_id + full_analysis.predictions
                top_horse_id = str(race.get("top_rank_horse_id") or "")
                vp = float(race.get("velo_prime_prob") or 0)
                predictions = (race.get("full_analysis") or {}).get("predictions") or []
                for pred in predictions:
                    if str(pred.get("horse_id") or "") == top_horse_id:
                        mult = pred.get("g_shadow_multiplier")
                        break

            if mult is None:
                races_no_mult += 1
                continue

            mult = float(mult)
            b = bucket(mult)
            bucket_stats[b]["wins"] += int(is_win)
            bucket_stats[b]["total"] += 1
            bucket_stats[b]["vp_sum"] += vp
            bucket_stats[b]["adj_vp_sum"] += vp * mult
            races_analysed += 1

    print(f"\n{'='*72}")
    print(f"G SHADOW MULTIPLIER BACKTEST — {races_analysed} races analysed, {races_no_mult} skipped (no multiplier)")
    print(f"{'='*72}")
    print(f"\n{'Bucket':<32} {'N':>5} {'Wins':>5} {'WinRate':>8} {'AvgVP':>7} {'AvgAdjVP':>9}")
    print(f"{'-'*72}")

    total_wins = total_races = 0
    for b in sorted(bucket_stats.keys()):
        s = bucket_stats[b]
        n = s["total"]
        wins = s["wins"]
        wr = wins / n if n else 0
        avg_vp = s["vp_sum"] / n if n else 0
        avg_adj_vp = s["adj_vp_sum"] / n if n else 0
        print(f"{b:<32} {n:>5} {wins:>5} {wr:>8.1%} {avg_vp:>7.3f} {avg_adj_vp:>9.3f}")
        total_wins += wins
        total_races += n

    overall_wr = total_wins / total_races if total_races else 0
    print(f"{'-'*72}")
    print(f"{'OVERALL':<32} {total_races:>5} {total_wins:>5} {overall_wr:>8.1%}")

    print(f"\nVERDICT GUIDE:")
    print(f"  If STRONG_DAMPEN (<0.80) win rate > overall → G hurts winners → DO NOT flip live")
    print(f"  If STRONG_AMPLIFY (>1.20) win rate > overall → G helps winners → safer to flip live")
    print(f"  If STRONG_AMPLIFY win rate < overall → G amplifies losers → DO NOT flip live")

    # Directional verdict
    dampen_stats = bucket_stats.get("A_STRONG_DAMPEN (<0.80)", {})
    amplify_stats = bucket_stats.get("E_STRONG_AMPLIFY (>1.20)", {})
    d_wr = dampen_stats.get("wins", 0) / dampen_stats.get("total", 1)
    a_wr = amplify_stats.get("wins", 0) / amplify_stats.get("total", 1)

    print(f"\nDIRECTIONAL VERDICT:")
    if amplify_stats.get("total", 0) < 10:
        print(f"  INSUFFICIENT DATA: only {amplify_stats.get('total', 0)} amplify races")
    elif a_wr > overall_wr * 1.05:
        delta = (a_wr - overall_wr) * 100
        print(f"  G AMPLIFIES WINNERS: amplify win rate {a_wr:.1%} > overall {overall_wr:.1%} (+{delta:.1f}pp)")
        print(f"  TENTATIVE: flipping VELO_G_SHADOW_MODE=live may lift win rate")
    elif a_wr < overall_wr * 0.95:
        delta = (overall_wr - a_wr) * 100
        print(f"  G AMPLIFIES LOSERS: amplify win rate {a_wr:.1%} < overall {overall_wr:.1%} (-{delta:.1f}pp)")
        print(f"  WARNING: do NOT flip VELO_G_SHADOW_MODE=live — G would hurt VP accuracy")
    else:
        print(f"  NEUTRAL: no clear directional signal (amplify={a_wr:.1%}, overall={overall_wr:.1%})")
        print(f"  Recommend more data before flipping live")

    if dampen_stats.get("total", 0) >= 10:
        if d_wr > overall_wr * 1.05:
            print(f"  WARNING: G dampens winners (dampen win rate {d_wr:.1%} > overall {overall_wr:.1%})")
        else:
            print(f"  OK: G dampened horses win rate {d_wr:.1%} (expected <= {overall_wr:.1%})")


if __name__ == "__main__":
    main()
