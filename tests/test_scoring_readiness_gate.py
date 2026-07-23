"""Scoring readiness gate: no scoring until passport + PDF ingestion (2026-07-18 hard law)."""
import json

from scripts.ops.check_scoring_readiness_gate import check_passport, check_pdf_ingestion


def _write_racecard_merged(tmp_path, file_code, date_hyphen, races, display_name=None):
    """file_code is the racecard_merged filename token (e.g. "NEW"); display_name
    is the real course name as it appears in the standard cache's "course" field
    (e.g. "Newbury") and in the file's own "venue" field — these two differ for
    several real venues (Newbury->NEW, Cartmel->CARTMEL), which is exactly the
    mismatch check_pdf_ingestion's region-exemption lookup has to bridge."""
    d = tmp_path / "data" / "racecard_merged"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"racecard_{file_code}_{date_hyphen}.json").write_text(
        json.dumps({"venue": display_name or file_code, "date": date_hyphen, "races": races})
    )


def _write_standard_cache(tmp_path, date_us, courses):
    d = tmp_path / "data"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"racecards_{date_us.replace('-', '_')}_standard.json").write_text(
        json.dumps([{"course": c, "region": r} for c, r in courses])
    )


def test_passport_missing(tmp_path, monkeypatch):
    import scripts.ops.check_scoring_readiness_gate as gate
    monkeypatch.setattr(gate, "ROOT", tmp_path)
    ok, msg = check_passport("2026-07-18")
    assert ok is False
    assert "MISSING" in msg


def test_passport_present(tmp_path, monkeypatch):
    import scripts.ops.check_scoring_readiness_gate as gate
    monkeypatch.setattr(gate, "ROOT", tmp_path)
    d = tmp_path / "data" / "new_build" / "current_cards"
    d.mkdir(parents=True, exist_ok=True)
    (d / "current_card_passport_feed_2026_07_18.jsonl").write_text('{"a": 1}\n')
    ok, msg = check_passport("2026-07-18")
    assert ok is True


def test_pdf_ingestion_blocks_on_unenriched_gb_venue(tmp_path, monkeypatch):
    import scripts.ops.check_scoring_readiness_gate as gate
    monkeypatch.setattr(gate, "ROOT", tmp_path)
    _write_standard_cache(tmp_path, "2026-07-18", [("Newbury", "GB")])
    _write_racecard_merged(tmp_path, "NEW", "2026-07-18", {
        "5.30": {"race_id": "923137", "horses": [{"horse_name": "Rizal"}]}
    }, display_name="Newbury")
    ok, ok_venues, missing = check_pdf_ingestion("2026-07-18")
    assert ok is False
    assert "NEW" in missing


def test_pdf_ingestion_passes_when_enriched(tmp_path, monkeypatch):
    import scripts.ops.check_scoring_readiness_gate as gate
    monkeypatch.setattr(gate, "ROOT", tmp_path)
    _write_standard_cache(tmp_path, "2026-07-18", [("Newbury", "GB")])
    _write_racecard_merged(tmp_path, "NEW", "2026-07-18", {
        "5.30": {"race_id": "923137", "horses": [{"horse_name": "Rizal", "postdata_score": 0.4}]}
    }, display_name="Newbury")
    ok, ok_venues, missing = check_pdf_ingestion("2026-07-18")
    assert ok is True
    assert "NEW" in ok_venues


def test_usa_venue_auto_exempted(tmp_path, monkeypatch):
    import scripts.ops.check_scoring_readiness_gate as gate
    monkeypatch.setattr(gate, "ROOT", tmp_path)
    _write_standard_cache(tmp_path, "2026-07-18", [("Saratoga", "USA")])
    _write_racecard_merged(tmp_path, "SARATOGA", "2026-07-18", {
        "6.00": {"race_id": "999999", "horses": [{"horse_name": "Nobody"}]}
    }, display_name="Saratoga")
    ok, ok_venues, missing = check_pdf_ingestion("2026-07-18")
    assert ok is True
    assert missing == []


def test_mixed_venues_only_gb_ire_blocks(tmp_path, monkeypatch):
    import scripts.ops.check_scoring_readiness_gate as gate
    monkeypatch.setattr(gate, "ROOT", tmp_path)
    _write_standard_cache(tmp_path, "2026-07-18", [("Newbury", "GB"), ("Saratoga", "USA")])
    _write_racecard_merged(tmp_path, "NEW", "2026-07-18", {
        "5.30": {"race_id": "923137", "horses": [{"horse_name": "Rizal"}]}
    }, display_name="Newbury")
    _write_racecard_merged(tmp_path, "SARATOGA", "2026-07-18", {
        "6.00": {"race_id": "999999", "horses": [{"horse_name": "Nobody"}]}
    }, display_name="Saratoga")
    ok, ok_venues, missing = check_pdf_ingestion("2026-07-18")
    assert ok is False
    assert missing == ["NEW"]
    assert "SARATOGA" not in missing
