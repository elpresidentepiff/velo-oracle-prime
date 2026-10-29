"""Pure helpers for the world-day / VELO-vs-FormFav dashboard endpoints.

Kept free of FastAPI and I/O so they are unit-testable. Everything here is a
read-only presentation of shadow data: FormFav never feeds Prime scoring.
"""

from __future__ import annotations

import re
from typing import Any

SHADOW_BOUNDARY = {
    "shadow_only": True,
    "production_influence": False,
    "stake_authorised": False,
    "promotion_eligible": False,
}

_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


def valid_date(value: str | None) -> bool:
    """Dates go into a PostgREST query string, so accept only YYYY-MM-DD."""
    return bool(value and _DATE.fullmatch(value))


def summarise_velo_vs_formfav(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Head-to-head totals. Winners are counted only where a winner is known."""
    n = len(rows)
    agree = sum(1 for r in rows if r.get("agree_on_top_pick"))
    decided = [r for r in rows if r.get("winner_name")]
    final_decided = [r for r in decided if r.get("result_is_final")]
    in_top3 = [r for r in rows if isinstance(r.get("formfav_rank_of_velo_pick"), int)]
    return {
        "races": n,
        "agree": agree,
        "agree_pct": round(100.0 * agree / n, 1) if n else None,
        "with_winner": len(decided),
        "with_final_winner": len(final_decided),
        "velo_won": sum(1 for r in decided if r.get("velo_pick_won")),
        "formfav_won": sum(1 for r in decided if r.get("formfav_pick_won")),
        "velo_won_final": sum(1 for r in final_decided if r.get("velo_pick_won")),
        "formfav_won_final": sum(1 for r in final_decided if r.get("formfav_pick_won")),
        "velo_pick_in_formfav_top3": sum(1 for r in in_top3 if r["formfav_rank_of_velo_pick"] <= 3),
        "sample_note": "Small sample: treat as a lead, not an edge." if len(decided) < 100 else None,
    }
