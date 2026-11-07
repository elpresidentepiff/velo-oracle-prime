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


# --- WAKE-VELO-DASH-01: all-models panel -------------------------------------------------------
from pathlib import Path  # noqa: E402

from app.world_dashboard import (  # noqa: E402
    is_clean_pick,
    model_scoreboard,
    race_grid,
    summarise_rich_context,
)


def _pick(model, race, horse, *, tie="CLEAN", rows=1, agrees=False, pos=None, win=None, off=900, prime="A"):
    return {
        "model_name": model, "race_id": race, "top_horse": horse, "tie_status": tie, "rank1_rows": rows,
        "agrees_with_prime": agrees, "result_position": pos, "win": win, "off_minutes": off,
        "off_time": "3.00", "course": "Ascot", "prime_horse": prime, "lane_name": "x",
    }


def test_not_applicable_tie_status_is_a_clean_read_but_ties_and_multi_list_are_not() -> None:
    assert is_clean_pick(_pick("M", "1", "A", tie="N/A"))
    assert is_clean_pick(_pick("M", "1", "A", tie="CLEAN"))
    assert not is_clean_pick(_pick("M", "1", "A", tie="TIED_2_WAY"))
    assert not is_clean_pick(_pick("M", "1", "A", tie="TIE_UNRESOLVED"))
    assert not is_clean_pick(_pick("M", "1", "A", rows=2))
    assert not is_clean_pick(_pick("M", "1", None))


def test_scoreboard_counts_each_model_on_its_own_clean_settled_races() -> None:
    picks = [
        _pick("MAIN_VELO_PRIME", "1", "A", agrees=True, pos=1, win=True),
        _pick("MAIN_VELO_PRIME", "2", "B", agrees=True, pos=4, win=False),
        _pick("MAIN_VELO_PRIME", "3", "C", agrees=True),
        _pick("SQPE_NO_RPR_SHADOW", "1", "A", agrees=True, pos=1, win=True),
        _pick("SQPE_NO_RPR_SHADOW", "2", "Z", pos=2, win=False),
        _pick("SQPE_NO_RPR_SHADOW", "3", "Y", tie="TIED_3_WAY"),
        _pick("CHAMPION_INTENT_SHADOW", "1", "A", tie="N/A", rows=2, agrees=True, pos=1, win=True),
    ]
    board = {row["model"]: row for row in model_scoreboard(picks)}
    prime, norpr, champ = board["MAIN_VELO_PRIME"], board["SQPE_NO_RPR_SHADOW"], board["CHAMPION_INTENT_SHADOW"]
    assert (prime["clean"], prime["settled"], prime["won"], prime["top3"]) == (3, 2, 1, 1)
    # the tied race is excluded from every count, so it cannot flatter or hurt the lane
    assert (norpr["races"], norpr["clean"], norpr["unclean"]) == (3, 2, 1)
    assert (norpr["comparable_with_prime"], norpr["agree_with_prime"]) == (2, 1)
    assert (norpr["settled"], norpr["won"], norpr["top3"]) == (2, 1, 2)
    # a lane that wrote several rank-1 rows is not counted as a read at all
    assert (champ["clean"], champ["settled"], champ["won"]) == (0, 0, 0)
    assert [row["model"] for row in model_scoreboard(picks)][0] == "MAIN_VELO_PRIME"


def test_unsettled_day_reports_no_outcomes_instead_of_zero_wins_out_of_zero() -> None:
    board = model_scoreboard([_pick("MAIN_VELO_PRIME", "1", "A", agrees=True)])
    assert (board[0]["settled"], board[0]["won"]) == (0, 0)


def test_race_grid_is_in_card_order_with_a_cell_per_model() -> None:
    picks = [
        _pick("MAIN_VELO_PRIME", "late", "A", off=1020),
        _pick("MAIN_VELO_PRIME", "early", "B", off=715),
        _pick("SQPE_NO_RPR_SHADOW", "early", "C", off=715, tie="TIED_2_WAY"),
    ]
    grid = race_grid(picks)
    assert [r["race_id"] for r in grid] == ["early", "late"]
    assert grid[0]["cells"]["SQPE_NO_RPR_SHADOW"]["clean"] is False
    assert grid[0]["cells"]["MAIN_VELO_PRIME"]["horse"] == "B"


def test_evidence_summary_shows_the_first_batch_against_the_latest() -> None:
    rows = [
        {"runners": 10, "history_before": 0, "history_now": 10, "spotlight_before": 0, "spotlight_now": 4,
         "formfav_now": 10, "packet_batches": 2, "latest_packet_at": "2026-11-07T11:30:00Z"},
        {"runners": 10, "history_before": 5, "history_now": 5, "spotlight_before": 0, "spotlight_now": 0,
         "formfav_now": 10, "packet_batches": 2, "latest_packet_at": "2026-11-07T11:31:00Z"},
    ]
    s = summarise_rich_context(rows)
    assert (s["races"], s["runners"]) == (2, 20)
    assert (s["history_before_pct"], s["history_now_pct"]) == (25.0, 75.0)
    assert (s["spotlight_before_pct"], s["spotlight_now_pct"]) == (0.0, 20.0)
    assert s["formfav_now_pct"] == 100.0 and s["packet_batches"] == 2
    assert s["latest_packet_at"] == "2026-11-07T11:31:00Z"
    assert summarise_rich_context([])["history_now_pct"] is None


def test_panel_is_wired_read_only_and_never_claims_rich_context_ranks() -> None:
    root = Path(__file__).parents[1]
    html = (root / "app" / "static" / "dashboard" / "index.html").read_text(encoding="utf-8")
    main = (root / "app" / "main.py").read_text(encoding="utf-8")
    assert 'id="rc-panel"' in html and "loadRichContext();" in html
    assert "NOT FITTED" in html and "PICKS NOTHING" in html
    route = main[main.index('@app.get("/api/rich-context")'):main.index('@app.get("/api/llm-brief")')]
    assert "wake_velo_model_picks" in route and "rich_context_vs_prime" in route
    for write in ("method=\"POST\"", ".insert(", ".upsert(", ".delete(", "supabase_write"):
        assert write not in route
