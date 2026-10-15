from __future__ import annotations

from app.world_dashboard import SHADOW_BOUNDARY, summarise_velo_vs_formfav, valid_date


def test_valid_date_blocks_query_injection() -> None:
    assert valid_date("2026-10-15")
    for bad in (None, "", "2026-10-15&select=*", "2026-10-1", "x' or 1=1", "2026-10-15 "):
        assert not valid_date(bad)


def test_summary_counts_only_decided_races_for_wins() -> None:
    rows = [
        {"agree_on_top_pick": True, "winner_name": "A", "result_is_final": True,
         "velo_pick_won": True, "formfav_pick_won": True, "formfav_rank_of_velo_pick": 1},
        {"agree_on_top_pick": False, "winner_name": "B", "result_is_final": False,
         "velo_pick_won": False, "formfav_pick_won": True, "formfav_rank_of_velo_pick": 4},
        {"agree_on_top_pick": False, "winner_name": None, "result_is_final": None,
         "velo_pick_won": None, "formfav_pick_won": None, "formfav_rank_of_velo_pick": 2},
    ]
    s = summarise_velo_vs_formfav(rows)
    assert (s["races"], s["agree"], s["agree_pct"]) == (3, 1, 33.3)
    assert (s["with_winner"], s["with_final_winner"]) == (2, 1)
    assert (s["velo_won"], s["formfav_won"], s["velo_won_final"], s["formfav_won_final"]) == (1, 2, 1, 1)
    assert s["velo_pick_in_formfav_top3"] == 2 and s["sample_note"]


def test_empty_summary_and_boundary_flags() -> None:
    s = summarise_velo_vs_formfav([])
    assert s["races"] == 0 and s["agree_pct"] is None
    assert SHADOW_BOUNDARY["production_influence"] is False and SHADOW_BOUNDARY["stake_authorised"] is False
