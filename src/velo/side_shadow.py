"""Side shadows: research lanes that are recorded but fenced off from the main evidence line.

A side shadow may be scored and settled so its record accumulates honestly, but it never
authorises a stake, never appears as a main model on the dashboard, and is not part of the main
comparison. Promotion needs the lane's own forward evidence plus an operator decision.

One definition, imported by the scorecard builder and the dashboard metrics so they cannot drift.
"""
from __future__ import annotations

# Captain Velo: market-prior value picker (abstains unless the model beats the market by 1.20x
# and a 10% expected edge). Backtest "positive point estimate, not forward proven".
SIDE_SHADOW_MODELS = frozenset({"CAPTAIN_VELO_VALUE_V1"})


def is_side_shadow(model_name: object) -> bool:
    return str(model_name or "").strip().upper() in SIDE_SHADOW_MODELS
