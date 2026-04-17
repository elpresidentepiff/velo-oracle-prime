"""
Integration smoke-test: VELO_PRIME_prob using available specialist models.
Uses a sample race from raceform_v17_features.parquet.
"""
import sys
from pathlib import Path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd
from src.intelligence.macro_regime.bha_macro_context import get_macro_context
from src.intelligence.specialist_models.loader import score_runners_batch
from src.intelligence.velo_prime_ensemble import VeloPrimeEnsemble

# Load raceform
df = pd.read_parquet(ROOT / "data" / "raceform_v17_features.parquet")
df["date_parsed"] = pd.to_datetime(df["date_parsed"], errors="coerce")

# Pick a 2024 race with 6+ runners that has a winner
test_races = df[df["date_parsed"] >= "2024-01-01"].copy()
race_counts = test_races.groupby("race_id")["target"].agg(["sum","count"])
good_races  = race_counts[(race_counts["sum"] == 1) & (race_counts["count"] >= 6)].index
race_id     = good_races[100]  # arbitrary 2024 race

race_df = test_races[test_races["race_id"] == race_id].copy()
print(f"\nRace: {race_id}")
print(f"Runners: {len(race_df)}  Date: {race_df['date_parsed'].iloc[0].date()}")
print(f"Course: {race_df['course'].iloc[0]}  Type: {race_df['type'].iloc[0]}")

# Score through specialist models
scored = score_runners_batch(race_df)
print(f"\nSpecialist scores available: {[c for c in scored.columns if c.endswith('_score') or c.endswith('_prob')]}")

# Build SQPE probabilities (use rpr_vs_field + implied_prob as proxy since no live model call)
# In production this would come from SQPEEngine.predict()
# For smoke test: normalise rpr_vs_field to probability
from scipy.special import softmax
sqpe_raw = scored["rpr_vs_field"].fillna(0).values
sqpe_probs = softmax(sqpe_raw * 5)  # scale before softmax

# Get macro context
year = race_df["date_parsed"].iloc[0].year
race_type = race_df["type"].iloc[0]
code = "aw" if scored["is_aw"].iloc[0] else ("jump" if "hurdle" in str(race_type).lower() or "chase" in str(race_type).lower() else "flat")
ctx = get_macro_context(year, code)

print(f"\nMacro context: year={year} code={code} regime={ctx.regime_label} fav_trap={ctx.favourite_trap_risk}")

# Build VeloPrime runners list
runners = []
for i, (_, row) in enumerate(scored.iterrows()):
    r = {
        "horse": row["horse"],
        "race_id": race_id,
        "sqpe_v17_prob": float(sqpe_probs[i]),
        "sp_dec": float(row["sp_dec"]) if pd.notna(row.get("sp_dec")) else None,
        "is_fav": bool(row.get("is_fav", 0)),
    }
    for col in scored.columns:
        if col.endswith("_score") or col.endswith("_prob"):
            if pd.notna(row[col]):
                r[col] = float(row[col])
    runners.append(r)

ensemble = VeloPrimeEnsemble()
preds = ensemble.predict_race(runners, macro_context=ctx)

print(f"\n{'Horse':<28} {'SQPE':>6} {'VELO_PRIME':>11} {'Conf':>8} {'Winner?':>8}")
print("-" * 68)
actual_winner = race_df[race_df["target"] == 1]["horse"].values
for p in preds:
    is_win = "*** WIN" if p.horse in actual_winner else ""
    print(f"{p.horse:<28} {p.sqpe_v17_prob:>6.3f} {p.velo_prime_prob:>11.4f} "
          f"{p.confidence_level:>8} {is_win}")

top_pick = preds[0].horse
print(f"\nTop pick: {top_pick}  Actual winner: {actual_winner[0] if len(actual_winner) else 'N/A'}")
print(f"Result: {'CORRECT' if top_pick in actual_winner else 'WRONG'}")
