"""
Tests for src.velo.verdict_loader -- the shared verdict-loading module that
replaced 12+ hand-copied instances of the generated_at write-date-vs-race-date
bug across the codebase (2026-07-23/24 sweep).

These tests exist specifically to stop that bug class from ever coming back
silently: if load_verdicts() regresses to preferring generated_at over
race_id, or a caller starts hand-rolling `.gte("generated_at", ...)` again
instead of importing this module, these should catch it.
"""

from __future__ import annotations

import json
from unittest.mock import patch

from src.velo.verdict_loader import known_race_ids_for_date, load_verdicts


def _write_racecard(root, date_str, race_ids, wrapped=False):
    path = root / "data" / f"racecards_{date_str.replace('-', '_')}_standard.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    races = [{"race_id": rid, "course": "Test"} for rid in race_ids]
    payload = {"racecards": races} if wrapped else races
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_known_race_ids_handles_bare_list_shape(tmp_path):
    _write_racecard(tmp_path, "2026-07-24", ["923037", "923038"], wrapped=False)
    assert known_race_ids_for_date("2026-07-24", root=tmp_path) == ["923037", "923038"]


def test_known_race_ids_handles_wrapped_racecards_shape(tmp_path):
    _write_racecard(tmp_path, "2026-05-01", ["rac_1", "rac_2"], wrapped=True)
    assert known_race_ids_for_date("2026-05-01", root=tmp_path) == ["rac_1", "rac_2"]


def test_known_race_ids_missing_cache_returns_empty(tmp_path):
    assert known_race_ids_for_date("2026-01-01", root=tmp_path) == []


def test_load_verdicts_prefers_race_id_path_when_cache_and_data_exist(tmp_path):
    _write_racecard(tmp_path, "2026-07-24", ["923037"])
    with patch("src.velo.verdict_loader._get") as mock_get:
        mock_get.return_value = [{"race_id": "923037", "generated_at": "2026-07-23T20:00:00"}]
        rows, method = load_verdicts("2026-07-24", root=tmp_path)
    assert method == "race_id"
    assert rows == [{"race_id": "923037", "generated_at": "2026-07-23T20:00:00"}]
    # The evening-before generated_at timestamp must not have blocked the match --
    # that's the entire point of this module existing.
    called_params = mock_get.call_args_list[0][0][1]
    assert "race_id" in called_params
    assert "generated_at" not in called_params


def test_load_verdicts_falls_back_to_generated_at_when_no_cache(tmp_path):
    with patch("src.velo.verdict_loader._get") as mock_get:
        mock_get.return_value = [{"race_id": "923037", "generated_at": "2026-07-24T10:00:00"}]
        rows, method = load_verdicts("2026-07-24", root=tmp_path)
    assert method == "generated_at"
    assert len(rows) == 1


def test_load_verdicts_falls_back_to_local_file_when_supabase_empty(tmp_path):
    local_path = tmp_path / "data" / "velo_prime_verdicts_2026_07_24.json"
    local_path.parent.mkdir(parents=True, exist_ok=True)
    local_path.write_text(json.dumps([{"race_id": "923037"}]), encoding="utf-8")

    with patch("src.velo.verdict_loader._get") as mock_get:
        mock_get.return_value = []
        rows, method = load_verdicts("2026-07-24", root=tmp_path)
    assert method == "local_file"
    assert rows == [{"race_id": "923037"}]


def test_load_verdicts_returns_none_method_when_nothing_found(tmp_path):
    with patch("src.velo.verdict_loader._get") as mock_get:
        mock_get.return_value = []
        rows, method = load_verdicts("2026-07-24", root=tmp_path, local_fallback=False)
    assert method == "none"
    assert rows == []


def test_load_verdicts_chunks_large_race_id_lists(tmp_path):
    race_ids = [str(i) for i in range(120)]
    _write_racecard(tmp_path, "2026-07-24", race_ids)
    with patch("src.velo.verdict_loader._get") as mock_get:
        mock_get.return_value = [{"race_id": "1"}]
        load_verdicts("2026-07-24", root=tmp_path)
    # 120 race_ids at chunk size 50 -> 3 calls
    assert mock_get.call_count == 3


def test_load_verdicts_uses_caller_supplied_race_ids_over_cache(tmp_path):
    # Cache says one thing, caller explicitly supplies a different (already
    # known-reliable) race_id list -- the caller-supplied list should win.
    _write_racecard(tmp_path, "2026-07-24", ["999999"])
    with patch("src.velo.verdict_loader._get") as mock_get:
        mock_get.return_value = [{"race_id": "923037"}]
        rows, method = load_verdicts("2026-07-24", root=tmp_path, race_ids=["923037"])
    assert method == "race_id"
    assert rows == [{"race_id": "923037"}]
    called_params = mock_get.call_args_list[0][0][1]
    assert called_params["race_id"] == "in.(923037)"
