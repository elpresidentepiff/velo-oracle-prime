from __future__ import annotations

import asyncio

from app.world_dashboard import SHADOW_BOUNDARY, summarise_velo_vs_formfav, valid_date


def test_valid_date_blocks_query_injection() -> None:
    assert valid_date("2026-10-15")
    for bad in (None, "", "2026-10-15&select=*", "2026-10-1", "x' or 1=1", "2026-10-15 "):
        assert not valid_date(bad)


def test_summary_counts_only_decided_races_for_wins() -> None:
    rows = [
        {
            "agree_on_top_pick": True,
            "winner_name": "A",
            "result_is_final": True,
            "velo_pick_won": True,
            "formfav_pick_won": True,
            "formfav_rank_of_velo_pick": 1,
        },
        {
            "agree_on_top_pick": False,
            "winner_name": "B",
            "result_is_final": False,
            "velo_pick_won": False,
            "formfav_pick_won": True,
            "formfav_rank_of_velo_pick": 4,
        },
        {
            "agree_on_top_pick": False,
            "winner_name": None,
            "result_is_final": None,
            "velo_pick_won": None,
            "formfav_pick_won": None,
            "formfav_rank_of_velo_pick": 2,
        },
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
    rich_context_challenger_overlay,
    summarise_rich_context,
)


def _pick(model, race, horse, *, tie="CLEAN", rows=1, agrees=False, pos=None, win=None, off=900, prime="A"):
    return {
        "model_name": model,
        "race_id": race,
        "top_horse": horse,
        "tie_status": tie,
        "rank1_rows": rows,
        "agrees_with_prime": agrees,
        "result_position": pos,
        "win": win,
        "off_minutes": off,
        "off_time": "3.00",
        "course": "Ascot",
        "prime_horse": prime,
        "lane_name": "x",
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
        {
            "runners": 10,
            "history_before": 0,
            "history_now": 10,
            "spotlight_before": 0,
            "spotlight_now": 4,
            "formfav_now": 10,
            "packet_batches": 2,
            "latest_packet_at": "2026-11-07T11:30:00Z",
        },
        {
            "runners": 10,
            "history_before": 5,
            "history_now": 5,
            "spotlight_before": 0,
            "spotlight_now": 0,
            "formfav_now": 10,
            "packet_batches": 2,
            "latest_packet_at": "2026-11-07T11:31:00Z",
        },
    ]
    s = summarise_rich_context(rows)
    assert (s["races"], s["runners"]) == (2, 20)
    assert (s["history_before_pct"], s["history_now_pct"]) == (25.0, 75.0)
    assert (s["spotlight_before_pct"], s["spotlight_now_pct"]) == (0.0, 20.0)
    assert s["formfav_now_pct"] == 100.0 and s["packet_batches"] == 2
    assert s["latest_packet_at"] == "2026-11-07T11:31:00Z"
    assert summarise_rich_context([])["history_now_pct"] is None


def test_fitted_overlay_joins_all_859_rows_by_packet_hash_without_mutating_packets() -> None:
    packets = []
    scores = []
    runners = []
    for i in range(859):
        race = str(930000 + (i % 46))
        horse = str(5_000_000 + i)
        digest = f"{i:064x}"
        packets.append({"race_id": race, "horse_id": horse, "input_sha256": digest})
        scores.append(
            {
                "race_id": race,
                "horse_id": horse,
                "packet_input_sha256": digest,
                "model_version": "rich_context_challenger_v1_fit_20261108",
                "challenger_probability": 0.51 if i < 46 else 0.1,
                "challenger_rank": 1 + i // 46,
                "production_influence": False,
                "paper_sim_only": True,
                "scored_at": "2026-11-08T10:31:05Z",
            }
        )
        runners.append(
            {
                "race_id": race,
                "horse_id": horse,
                "horse_name": f"Horse {i}",
                "created_at": "2026-11-07T08:00:00Z",
            }
        )
    frozen_packets = [dict(row) for row in packets]
    out = rich_context_challenger_overlay(packets, scores, runners)
    assert out["status"] == "SHADOW_FITTED"
    assert out["model_version"] == "rich_context_challenger_v1_fit_20261108"
    assert (out["packet_rows"], out["score_rows"], out["linked_rows"]) == (859, 859, 859)
    assert (out["immutable_packet_rows"], out["version_score_rows"], out["current_score_rows"]) == (
        859,
        859,
        859,
    )
    assert out["linked_current_rows"] == 859 and out["current_coverage_pct"] == 100.0
    assert (out["races"], out["rank_one_rows"], out["ranked_rows"]) == (46, 46, 859)
    assert out["coverage_pct"] == 100.0
    assert out["orphan_scores"] == 0 and out["unsafe_rows"] == 0
    assert all(row["production_influence"] is False for row in out["runners"])
    assert all(row["paper_sim_only"] is True for row in out["runners"])
    assert packets == frozen_packets


def test_overlay_never_blends_versions_or_displays_unsafe_or_identity_mismatched_rows() -> None:
    packet = {"race_id": "1", "horse_id": "10", "input_sha256": "a" * 64}
    base = {
        "race_id": "1",
        "horse_id": "10",
        "packet_input_sha256": "a" * 64,
        "challenger_probability": 0.4,
        "challenger_rank": 1,
        "production_influence": False,
        "paper_sim_only": True,
    }
    scores = [
        {**base, "model_version": "v1", "scored_at": "2026-11-08T10:00:00Z"},
        {**base, "model_version": "v2", "scored_at": "2026-11-08T11:00:00Z"},
        {
            **base,
            "model_version": "v2",
            "race_id": "2",
            "horse_id": "WRONG",
            "packet_input_sha256": "b" * 64,
            "scored_at": "2026-11-08T11:00:00Z",
        },
        {
            **base,
            "model_version": "v2",
            "production_influence": True,
            "scored_at": "2026-11-08T11:00:00Z",
        },
    ]
    out = rich_context_challenger_overlay([packet], scores)
    assert out["model_version"] == "v2" and out["score_rows"] == 2
    assert out["linked_rows"] == 1 and out["orphan_scores"] == 1
    assert out["unsafe_rows"] == 1
    assert len(out["selections"]) == 1


def test_same_version_repeated_race_batches_use_only_latest_timestamp() -> None:
    packets = [
        {"race_id": "1", "horse_id": "10", "input_sha256": "a" * 64},
        {"race_id": "1", "horse_id": "11", "input_sha256": "b" * 64},
        {"race_id": "1", "horse_id": "10", "input_sha256": "c" * 64},
        {"race_id": "1", "horse_id": "11", "input_sha256": "d" * 64},
    ]

    def score(packet: int, horse: str, rank: int, at: str, probability: float):
        return {
            "race_id": "1",
            "horse_id": horse,
            "packet_input_sha256": packets[packet]["input_sha256"],
            "model_version": "same-model-version",
            "challenger_probability": probability,
            "challenger_rank": rank,
            "production_influence": False,
            "paper_sim_only": True,
            "scored_at": at,
        }

    scores = [
        score(0, "10", 1, "2026-11-08T09:00:00Z", 0.7),
        score(1, "11", 2, "2026-11-08T09:00:00Z", 0.3),
        score(2, "10", 2, "2026-11-08T10:00:00Z", 0.4),
        score(3, "11", 1, "2026-11-08T10:00:00Z", 0.6),
    ]
    out = rich_context_challenger_overlay(packets, scores)
    assert out["status"] == "SHADOW_FITTED"
    assert out["immutable_packet_rows"] == 4
    assert out["version_score_rows"] == 4
    assert out["current_score_rows"] == 2
    assert out["linked_current_rows"] == 2
    assert out["superseded_rows"] == 2
    assert out["current_coverage_pct"] == 100.0
    assert out["rank_one_rows"] == 1
    assert out["selections"][0]["horse_id"] == "11"
    assert out["selections"][0]["scored_at"] == "2026-11-08T10:00:00Z"


def test_indistinguishable_or_incoherent_latest_batch_fails_without_a_partial_pick() -> None:
    packets = [
        {"race_id": "1", "horse_id": "10", "input_sha256": "a" * 64},
        {"race_id": "1", "horse_id": "11", "input_sha256": "b" * 64},
    ]
    scores = [
        {
            "race_id": "1",
            "horse_id": packet["horse_id"],
            "packet_input_sha256": packet["input_sha256"],
            "model_version": "v1",
            "challenger_probability": 0.5,
            "challenger_rank": 1,
            "production_influence": False,
            "paper_sim_only": True,
            "scored_at": "2026-11-08T10:00:00Z",
        }
        for packet in packets
    ]
    out = rich_context_challenger_overlay(packets, scores)
    assert out["status"] == "OVERLAY_INTEGRITY_FAILED"
    assert out["ambiguous_batch_races"] == 1
    assert out["runners"] == [] and out["selections"] == []
    assert out["coverage_pct"] is None


def test_all_invalid_score_metadata_is_integrity_failure_not_no_scores() -> None:
    packet = {"race_id": "1", "horse_id": "10", "input_sha256": "a" * 64}
    base = {
        "race_id": "1",
        "horse_id": "10",
        "packet_input_sha256": "a" * 64,
        "challenger_probability": 0.6,
        "challenger_rank": 1,
        "production_influence": False,
        "paper_sim_only": True,
    }
    invalid_timestamp = rich_context_challenger_overlay(
        [packet],
        [{**base, "model_version": "v1", "scored_at": None}],
    )
    missing_version = rich_context_challenger_overlay(
        [packet],
        [{**base, "model_version": None, "scored_at": "2026-11-08T10:00:00Z"}],
    )
    for out in (invalid_timestamp, missing_version):
        assert out["status"] == "OVERLAY_INTEGRITY_FAILED"
        assert out["invalid_batch_rows"] == 1
        assert out["status"] != "NO_SCORES_FOR_DATE"
        assert out["observed_score_rows"] == 1
        assert out["selections"] == [] and out["current_coverage_pct"] is None


def test_no_score_date_is_honest_and_does_not_invent_a_fitted_pick() -> None:
    packet = {"race_id": "1", "horse_id": "10", "input_sha256": "a" * 64}
    out = rich_context_challenger_overlay([packet], [], [])
    assert out["status"] == "NO_SCORES_FOR_DATE"
    assert out["model_version"] is None
    assert out["packet_rows"] == 1 and out["score_rows"] == 0
    assert out["runners"] == [] and out["selections"] == []


def test_packet_or_score_read_failure_never_becomes_empty_or_partial_truth() -> None:
    packet = {"race_id": "1", "horse_id": "10", "input_sha256": "a" * 64}
    score = {
        "race_id": "1",
        "horse_id": "10",
        "packet_input_sha256": "a" * 64,
        "model_version": "v1",
        "challenger_probability": 0.6,
        "challenger_rank": 1,
        "production_influence": False,
        "paper_sim_only": True,
        "scored_at": "2026-11-08T10:00:00Z",
    }
    packet_failed = rich_context_challenger_overlay(None, [score], packet_read_status="READ_FAILED")
    score_failed = rich_context_challenger_overlay([packet], None, score_read_status="READ_FAILED")
    for out, expected in ((packet_failed, "packets"), (score_failed, "scores")):
        assert out["status"] == "OVERLAY_UNAVAILABLE"
        assert expected in out["read_failures"]
        assert out["packet_rows"] is None and out["score_rows"] is None
        assert out["selections"] == [] and out["coverage_pct"] is None


def test_runner_label_read_failure_degrades_only_the_label() -> None:
    packet = {"race_id": "1", "horse_id": "10", "input_sha256": "a" * 64}
    score = {
        "race_id": "1",
        "horse_id": "10",
        "packet_input_sha256": "a" * 64,
        "model_version": "v1",
        "challenger_probability": 0.6,
        "challenger_rank": 1,
        "production_influence": False,
        "paper_sim_only": True,
        "scored_at": "2026-11-08T10:00:00Z",
    }
    out = rich_context_challenger_overlay([packet], [score], None, runner_read_status="READ_FAILED")
    assert out["status"] == "SHADOW_FITTED"
    assert out["read_availability"]["runner_labels"] == "READ_FAILED"
    assert out["selections"][0]["horse_name"] is None


def test_panel_reads_the_score_overlay_and_remains_read_only_shadow_only() -> None:
    root = Path(__file__).parents[1]
    html = (root / "app" / "static" / "dashboard" / "index.html").read_text(encoding="utf-8")
    main = (root / "app" / "main.py").read_text(encoding="utf-8")
    assert 'id="rc-panel"' in html and "loadRichContext();" in html
    assert "SHADOW FITTED" in html and "NEVER REPLACES PRIME" in html
    assert "CURRENT BATCH LINKED" in html and "VERSION SCORE ROWS" in html
    assert "OVERLAY UNAVAILABLE" in html and "no partial selection or coverage is displayed" in html
    assert "ev.races || 0" in html and "ev.runners || 0" in html
    assert "!rc.packet_rows && !rcFailure" in html
    assert "RICH CONTEXT HAS NO MODEL YET" not in html and "PICKS NOTHING" not in html
    route = main[main.index('@app.get("/api/rich-context")') : main.index('@app.get("/api/llm-brief")')]
    assert "rich_context_challenger_scores" in route and "rich_context_shadow_packets" in route
    assert "packet_input_sha256" in route and "rich_context_challenger_overlay" in route
    for write in ('method="POST"', ".insert(", ".upsert(", ".delete(", "supabase_write"):
        assert write not in route


def test_rich_context_api_returns_exact_fitted_version_and_shadow_pick(monkeypatch) -> None:
    import app.main as main

    packet_hash = "a" * 64

    def rest(path: str):
        if path.startswith("rich_context_shadow_packets?"):
            return [{"race_id": "1", "horse_id": "10", "input_sha256": packet_hash}]
        if path.startswith("rich_context_challenger_scores?"):
            return [
                {
                    "race_id": "1",
                    "horse_id": "10",
                    "packet_input_sha256": packet_hash,
                    "model_version": "rich_context_challenger_v1_fit_20261108",
                    "challenger_probability": 0.6,
                    "challenger_rank": 1,
                    "production_influence": False,
                    "paper_sim_only": True,
                    "scored_at": "2026-11-08T10:31:05Z",
                }
            ]
        if path.startswith("runners?"):
            return [
                {
                    "race_id": "1",
                    "horse_id": "10",
                    "horse_name": "Exact Identity",
                    "created_at": "2026-11-07T08:00:00Z",
                }
            ]
        return []

    monkeypatch.setattr(main, "_sb_rest_rows", rest)
    out = asyncio.run(main.rich_context("2026-11-07"))
    assert out["rich_context_status"] == "SHADOW_FITTED"
    assert out["rich_context_ranks_anything"] is True
    challenger = out["rich_context_challenger"]
    assert challenger["model_version"] == "rich_context_challenger_v1_fit_20261108"
    assert challenger["selections"][0]["horse_name"] == "Exact Identity"
    assert challenger["selections"][0]["challenger_probability"] == 0.6
    assert out["production_influence"] is False and out["stake_authorised"] is False


def test_rich_context_api_preserves_packet_and_score_read_failures(monkeypatch) -> None:
    import app.main as main

    packet = {"race_id": "1", "horse_id": "10", "input_sha256": "a" * 64}
    score = {
        "race_id": "1",
        "horse_id": "10",
        "packet_input_sha256": "a" * 64,
        "model_version": "v1",
        "challenger_probability": 0.6,
        "challenger_rank": 1,
        "production_influence": False,
        "paper_sim_only": True,
        "scored_at": "2026-11-08T10:00:00Z",
    }

    def run_with_failure(failed_table: str):
        def rest(path: str):
            if path.startswith("rich_context_shadow_packets?"):
                return None if failed_table == "packets" else [packet]
            if path.startswith("rich_context_challenger_scores?"):
                return None if failed_table == "scores" else [score]
            return []

        monkeypatch.setattr(main, "_sb_rest_rows", rest)
        return asyncio.run(main.rich_context("2026-11-07"))

    for failed_table in ("packets", "scores"):
        out = run_with_failure(failed_table)
        challenger = out["rich_context_challenger"]
        assert challenger["status"] == "OVERLAY_UNAVAILABLE"
        assert failed_table in challenger["read_failures"]
        assert challenger["selections"] == [] and challenger["coverage_pct"] is None
        assert out["available"] is True


def test_bounded_supabase_pagination_is_complete_or_fails_explicitly(monkeypatch) -> None:
    import app.main as main

    def complete(path: str):
        if "offset=0" in path:
            return [{"id": 1}, {"id": 2}]
        if "offset=2" in path:
            return [{"id": 3}]
        raise AssertionError(path)

    monkeypatch.setattr(main, "_sb_rest_rows", complete)
    rows, meta = main._sb_rest_rows_paged("scores?order=id.asc", page_size=2, max_pages=3)
    assert [row["id"] for row in rows] == [1, 2, 3]
    assert meta == {"status": "OK", "pages_read": 2, "rows_read": 3, "truncated": False}

    monkeypatch.setattr(main, "_sb_rest_rows", lambda _path: [{"id": 1}, {"id": 2}])
    rows, meta = main._sb_rest_rows_paged("scores?order=id.asc", page_size=2, max_pages=2)
    assert rows is None
    assert meta["status"] == "MAX_PAGES_EXCEEDED" and meta["truncated"] is True


def test_bounded_supabase_pagination_discards_partial_rows_on_page_failure(monkeypatch) -> None:
    import app.main as main

    def rest(path: str):
        return [{"id": 1}, {"id": 2}] if "offset=0" in path else None

    monkeypatch.setattr(main, "_sb_rest_rows", rest)
    rows, meta = main._sb_rest_rows_paged("scores?order=id.asc", page_size=2, max_pages=3)
    assert rows is None
    assert meta == {"status": "READ_FAILED", "pages_read": 1, "rows_read": 2, "truncated": False}


def test_score_overlay_migration_enforces_paper_only_append_only_rows() -> None:
    root = Path(__file__).parents[1]
    sql = (root / "supabase" / "migrations" / "20261108105325_harden_rich_context_challenger_scores.sql").read_text(
        encoding="utf-8"
    ).lower()
    assert "check (production_influence = false)" in sql
    assert "check (paper_sim_only = true)" in sql
    assert "check (challenger_probability between 0.0 and 1.0)" in sql
    assert "foreign key (race_id, horse_id, packet_input_sha256)" in sql
    assert "references public.rich_context_shadow_packets (race_id, horse_id, input_sha256)" in sql
    assert "before update or delete on public.rich_context_challenger_scores" in sql
    assert "rich_context_challenger_scores is append-only" in sql


# --- WAKE-VELO-DASH-02: today's enriched suggestions ----------------------------------------------
from app.world_dashboard import enriched_suggestions, evidence_grade  # noqa: E402


def _sug(race, pick="A", **kw):
    row = {
        "race_id": race,
        "pick": pick,
        "morning_pick": pick,
        "pick_changed": False,
        "morning_prob": 0.40,
        "now_prob": 0.40,
        "prob_delta": 0.0,
        "field_morning": 8,
        "field_now": 8,
        "withdrawn": 0,
        "history": {"runs": 3},
        "pace": {"runningStyle": "L"},
        "class_fit": {"assessment": "comfort_zone"},
        "spotlight_families": None,
        "run_at": "2026-11-07T11:14:13Z",
    }
    row.update(kw)
    return row


def test_evidence_grade_describes_coverage_not_quality() -> None:
    assert evidence_grade(_sug("1", spotlight_families=["pace_position"])) == "FULL"
    assert evidence_grade(_sug("1")) == "HISTORY"
    assert evidence_grade(_sug("1", history={}, spotlight_families=["pace_position"])) == "SPOTLIGHT"
    assert evidence_grade(_sug("1", history={})) == "FORMFAV ONLY"
    # JSON null from the view is treated as missing, not as evidence
    assert evidence_grade(_sug("1", history=None, spotlight_families=None)) == "FORMFAV ONLY"


def test_enriched_suggestions_counts_changes_and_tolerates_json_null() -> None:
    rows = [
        _sug("1"),
        _sug(
            "2",
            pick="B",
            morning_pick="A",
            pick_changed=True,
            prob_delta=0.08,
            now_prob=0.48,
            withdrawn=2,
            spotlight_families=["pace_position"],
        ),
        _sug("3", history=None, pace=None, class_fit=None),
    ]
    out = enriched_suggestions(rows)
    s = out["summary"]
    assert (s["races"], s["pick_changed"], s["pick_probability_moved"]) == (3, 1, 1)
    assert (s["with_history"], s["with_spotlight"], s["with_withdrawal"]) == (2, 1, 1)
    assert s["run_at"] == "2026-11-07T11:14:13Z"
    assert out["races"][2]["history"] == {} and out["races"][2]["pace"] == {} and out["races"][2]["class_fit"] == {}
    assert enriched_suggestions([])["summary"]["races"] == 0


def test_suggestions_are_wired_read_only_and_say_the_pick_is_primes() -> None:
    root = Path(__file__).parents[1]
    html = (root / "app" / "static" / "dashboard" / "index.html").read_text(encoding="utf-8")
    main = (root / "app" / "main.py").read_text(encoding="utf-8")
    assert 'id="rc-suggest"' in html and "TODAY'S SUGGESTIONS" in html
    assert "The pick in this table is Prime" in html
    assert "never replaces Prime" in html
    route = main[main.index('@app.get("/api/rich-context")') : main.index('@app.get("/api/llm-brief")')]
    assert "wake_velo_enriched_picks" in route and "enriched_suggestions" in route


# --- WORLD-PICKS-01: VELO's frozen World pick per race ---------------------------------------------
from datetime import UTC, datetime  # noqa: E402

from app.world_dashboard import world_picks  # noqa: E402

_NOW = datetime(2026, 11, 7, 18, 12, tzinfo=UTC)


def _wp(track="Rosehill", n=1, country="au", start="2026-11-07T01:25:00+00:00", pick="Horse A", **kw):
    row = {
        "country": country,
        "track": track,
        "race_number": n,
        "start_time": start,
        "pick_name": pick,
        "tied_top": False,
        "rank1_rows": 1,
        "price_state": "REAL",
        "pick_price": 2.5,
        "pick_is_shortest_price": True,
        "result_basis": None,
        "won": None,
        "framed": None,
        "finish_position": None,
        "winner_names": None,
    }
    row.update(kw)
    return row


def test_world_picks_flag_ties_duplicate_rank_and_missing_market_as_not_a_clean_read() -> None:
    out = world_picks(
        [
            _wp("A", 1, pick="Clean"),
            _wp(
                "B", 2, pick="Tied", tied_top=True, price_state="MISSING", pick_price=None, pick_is_shortest_price=False
            ),
            _wp("C", 3, pick="Dup", rank1_rows=2),
        ],
        [],
        now=_NOW,
    )
    by = {r["pick_name"]: r for r in out["races"]}
    assert by["Clean"]["clean"] and by["Clean"]["flags"] == []
    assert not by["Tied"]["clean"] and by["Tied"]["flags"] == ["TIED", "NO_MARKET"]
    assert not by["Dup"]["clean"] and "DUP_RANK" in by["Dup"]["flags"]
    s = out["summary"]
    assert (s["races"], s["priced"], s["no_market"], s["tied"], s["dup_rank"]) == (3, 2, 1, 1, 1)


def test_world_picks_settle_only_final_results_into_the_win_count() -> None:
    out = world_picks(
        [
            _wp("A", 1, result_basis="final", won=True, framed=True, finish_position=1),
            _wp("B", 2, result_basis="final", won=False, framed=True, finish_position=3, winner_names=["X"]),
            _wp("C", 3, result_basis="final", won=False, framed=False, finish_position=9, tied_top=True),
            _wp("D", 4, result_basis="provisional", won=True, framed=True, finish_position=1),
            _wp("E", 5, result_basis="no_result"),
            _wp("F", 6),
        ],
        [],
        now=_NOW,
    )
    outcomes = {r["track"]: r["outcome"] for r in out["races"]}
    assert outcomes == {"A": "WON", "B": "PLACED", "C": "LOST", "D": "WON", "E": "NO_RESULT", "F": "PENDING"}
    s = out["summary"]
    assert (s["settled_final"], s["won_final"], s["placed_final"]) == (3, 1, 2)
    assert (s["settled_provisional"], s["no_result"]) == (1, 1)
    # the tied race is settled but is not a clean read, so it stays out of the clean count
    assert (s["clean_settled_final"], s["clean_won_final"]) == (2, 1)


def test_world_picks_put_races_still_to_run_first_and_match_formfav_by_race_not_position() -> None:
    out = world_picks(
        [
            _wp("Old", 1, start="2026-11-07T01:25:00+00:00", pick="Early"),
            _wp("Soon", 2, country="us", start="2026-11-07T18:19:00+00:00", pick="O'Hearn"),
            _wp("Later", 3, country="us", start="2026-11-07T21:14:00+00:00", pick="Drayden"),
        ],
        [
            {"country": "us", "track": "later", "race_number": 3, "off_uk": "21:14", "pick1_name": "Crazy Busted (Ny)"},
            {"country": "us", "track": "soon", "race_number": 2, "off_uk": "18:19", "pick1_name": "O'Hearn (Ire)"},
        ],
        now=_NOW,
    )
    assert [r["track"] for r in out["races"]] == ["Soon", "Later", "Old"]
    by = {r["track"]: r for r in out["races"]}
    assert by["Soon"]["upcoming"] and by["Later"]["upcoming"] and not by["Old"]["upcoming"]
    assert by["Soon"]["agrees_with_formfav"] is True and by["Soon"]["off_label"] == "18:19"
    assert by["Later"]["agrees_with_formfav"] is False
    assert by["Old"]["agrees_with_formfav"] is None  # FormFav has no pick for it: unknown, not a disagreement
    assert (out["summary"]["agree_with_formfav"], out["summary"]["with_formfav"]) == (1, 2)


def test_world_picks_say_how_often_a_priced_pick_is_just_the_shortest_price() -> None:
    out = world_picks(
        [
            _wp("A", 1),
            _wp("B", 2),
            _wp("C", 3, pick_is_shortest_price=False, pick_price=4.0),
            _wp("D", 4, price_state="MISSING", pick_price=None, pick_is_shortest_price=False),
        ],
        [],
        now=_NOW,
    )
    s = out["summary"]
    assert (s["priced"], s["priced_pick_is_shortest"], s["no_market"]) == (3, 2, 1)
    assert "favourite" in s["note"] and "not evidence of skill" in s["note"]


def test_world_picks_empty_day_is_empty_not_an_error() -> None:
    out = world_picks([], [], now=_NOW)
    assert out["races"] == [] and out["summary"]["races"] == 0 and out["summary"]["settled_final"] == 0


def test_world_picks_panel_is_wired_read_only_and_never_calls_itself_a_tip() -> None:
    root = Path(__file__).parents[1]
    html = (root / "app" / "static" / "dashboard" / "index.html").read_text(encoding="utf-8")
    main = (root / "app" / "main.py").read_text(encoding="utf-8")
    sql = (root / "supabase" / "migrations" / "20261107190000_world_velo_picks.sql").read_text(encoding="utf-8")
    assert 'id="wp-panel"' in html and "loadWorldPicks();" in html
    assert "NOT A TIP" in html and "NO STAKING" in html and "NO MARKET (PRICE-BLIND)" in html
    route = main[main.index('@app.get("/api/world-picks")') : main.index('@app.get("/api/rich-context")')]
    assert "world_velo_picks" in route and "world_picks(" in route
    for write in ('method="POST"', ".insert(", ".upsert(", ".delete(", "supabase_write"):
        assert write not in route
    assert "security_invoker = true" in sql and "grant select on public.world_velo_picks to service_role" in sql
    assert "FIRST_COMPLETE" in sql  # reads the frozen first-complete pick, never a later rewrite
    for verb in ("insert into", "update public", "delete from"):
        assert verb not in sql.lower()


def test_world_picks_view_only_counts_a_verified_price_as_the_shortest() -> None:
    # Earlier days stored the scorer's 10.0 default on every price-blind row; comparing those defaults to
    # each other made "pick is the shortest price" true for all of them (120 of 120 on 2026-11-05).
    root = Path(__file__).parents[1]
    sql = (root / "supabase" / "migrations" / "20261107190000_world_velo_picks.sql").read_text(encoding="utf-8")
    assert "min(case when b.ps = 'REAL' then b.captured_price end)" in sql
    assert "(t1.ps = 'REAL' and t1.captured_price = t1.shortest_price) as pick_is_shortest_price" in sql


# --- WAKE-VELO-SETTLE-01 follow-up: results read from the ingested Racing Post results ------------
def test_scoreboard_counts_results_read_from_ingested_results_and_says_so() -> None:
    from app.world_dashboard import model_scoreboard

    def row(race, model, pos, win, source, **kw):
        base = {
            "race_id": race,
            "model_name": model,
            "top_horse": f"H{race}",
            "tie_status": "N/A",
            "rank1_rows": 1,
            "result_position": pos,
            "win": win,
            "result_source": source,
            "agrees_with_prime": False,
            "lane_name": "x",
        }
        base.update(kw)
        return base

    board = {
        b["model"]: b
        for b in model_scoreboard(
            [
                row("1", "MAIN_VELO_PRIME", 1, True, "scorecard"),
                row("2", "MAIN_VELO_PRIME", 5, False, "scorecard"),
                row("1", "CHAMPION_INTENT_SHADOW", 2, False, "ingested_results"),
                row("2", "CHAMPION_INTENT_SHADOW", 1, True, "ingested_results"),
                row("3", "CHAMPION_INTENT_SHADOW", None, None, None),
                row("4", "CHAMPION_INTENT_SHADOW", 1, True, "ingested_results", rank1_rows=2),  # multi-pick: not clean
            ]
        )
    }
    assert board["MAIN_VELO_PRIME"]["settled"] == 2 and board["MAIN_VELO_PRIME"]["settled_from_ingested"] == 0
    champ = board["CHAMPION_INTENT_SHADOW"]
    assert (champ["settled"], champ["settled_from_ingested"], champ["won"], champ["top3"]) == (2, 2, 1, 2)
    assert champ["unclean"] == 1  # the multi-pick race is still excluded from the read


def test_ingested_results_fallback_is_exact_id_only_and_the_scorecard_wins() -> None:
    root = Path(__file__).parents[1]
    sql = (root / "supabase" / "migrations" / "20261108020000_wake_velo_model_picks_ingested_results.sql").read_text(
        encoding="utf-8"
    )
    assert "i.race_id = t.race_id and i.horse_id = t.horse_id" in sql  # never a name join
    assert "coalesce(t.result_position, i.position_int)" in sql  # the scorecard's own result takes precedence
    assert "when t.result_position is not null then t.win" in sql
    assert "result_source" in sql and "security_invoker = true" in sql
    for verb in ("insert into", "update public", "delete from"):
        assert verb not in sql.lower()
    html = (root / "app" / "static" / "dashboard" / "index.html").read_text(encoding="utf-8")
    assert "settled_from_ingested" in html and "read from the ingested Racing Post results" in html
