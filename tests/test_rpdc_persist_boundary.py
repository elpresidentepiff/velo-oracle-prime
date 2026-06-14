"""RPDC persist boundary — genuine RPDC fields must survive persistence.

Regression guard for the hijack introduced in fda78d4 (2026-04-21), where
the persist payload overwrote rpdc_* columns with PDF plot-conviction and
intent-signal data. Operator mandate 2026-06-10: RPDC fields carry RPDC
data; PDF intelligence lives in full_analysis["pdf_plot"].

These tests intercept the payload at the table-insert boundary. No network,
no Supabase writes.
"""
import sys
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _fixture_top() -> dict:
    """A top pick the way run_prime_today builds it: genuine RPDC attached,
    PDF plot intelligence present, both with distinct values."""
    return {
        "horse": "Viscountess Nelson",
        "horse_id": "7436509",
        "velo_prime_prob": 0.31,
        "confidence_level": "MEDIUM",
        # Genuine RPDC (from runner_release_candidates via _attach_rpdc_from_row)
        "rpdc_release_score": 0.80,
        "rpdc_cash_window_flag": False,
        "rpdc_primary_tag": "PLACE_FORM",
        "rpdc_tags": ["PLACE_FORM"],
        "rpdc_tag_count": 1,
        "rpdc_lookup_status": "attached",
        # PDF intelligence (separate feature — must NOT enter rpdc_* columns)
        "plot_conviction": 0.9,
        "intent_signals": ["CLASS_DROP", "MONEY_SIGNAL"],
        "active_components": ["sqpe_v17", "improvement_score", "market_deception_score"],
        "excluded_from_ensemble": ["place_prob", "longshot_score"],
        "router_reasons": [],
    }


def _capture_persisted_row():
    """Run persist_race_predictions with the supabase client mocked out;
    return the row it tried to insert."""
    from app.services import velo_prime_service as vps

    race = {"race_id": "920147", "region": "UK", "runners": [{}] * 9}
    top = _fixture_top()
    captured = {}

    fake_table = mock.MagicMock()

    def capture_insert(row, **kwargs):
        captured.update(row)
        result = mock.MagicMock()
        result.execute.return_value = mock.MagicMock(data=[row])
        return result

    fake_table.upsert.side_effect = capture_insert
    fake_client = mock.MagicMock()
    fake_client.table.return_value = fake_table

    with mock.patch.dict(
        "os.environ",
        {"SUPABASE_URL": "https://example.test", "SUPABASE_SERVICE_KEY": "test-key"},
    ), mock.patch("supabase.create_client", return_value=fake_client):
        vps.persist_race_predictions(race, [top], decision_tier="B", commit_sha="deadbeef")

    assert captured, "persist_race_predictions never reached the insert boundary"
    return captured


def test_genuine_rpdc_fields_survive_persist():
    row = _capture_persisted_row()
    assert row["rpdc_primary_tag"] == "PLACE_FORM"
    assert row["rpdc_tags"] == ["PLACE_FORM"]
    assert row["rpdc_tag_count"] == 1
    assert row["rpdc_release_score"] == 0.80
    assert row["rpdc_cash_window_flag"] is False


def test_pdf_intelligence_does_not_overwrite_rpdc():
    row = _capture_persisted_row()
    # The old hijack symptoms — none may return:
    assert row["rpdc_primary_tag"] != "PDF_PLOT"
    assert "CLASS_DROP" not in row["rpdc_tags"]
    assert not any(str(t).startswith("PLOT:") for t in row["rpdc_tags"])
    assert row["rpdc_release_score"] != 0.9  # plot_conviction must not leak in


def test_pdf_intelligence_preserved_in_full_analysis():
    row = _capture_persisted_row()
    pdf = row["full_analysis"]["plot_intel"]
    assert pdf["plot_conviction"] == 0.9
    assert pdf["pdf_plot_flag"] is True
    assert pdf["intent_signals"] == ["CLASS_DROP", "MONEY_SIGNAL"]


def test_no_rpdc_data_persists_as_empty_not_invented():
    from app.services import velo_prime_service as vps

    race = {"race_id": "920148", "region": "UK", "runners": [{}] * 5}
    top = _fixture_top()
    for k in ("rpdc_release_score", "rpdc_cash_window_flag", "rpdc_primary_tag", "rpdc_tags", "rpdc_tag_count"):
        top.pop(k)
    captured = {}
    fake_table = mock.MagicMock()

    def capture_insert(row, **kwargs):
        captured.update(row)
        result = mock.MagicMock()
        result.execute.return_value = mock.MagicMock(data=[row])
        return result

    fake_table.upsert.side_effect = capture_insert
    fake_client = mock.MagicMock()
    fake_client.table.return_value = fake_table
    with mock.patch.dict(
        "os.environ",
        {"SUPABASE_URL": "https://example.test", "SUPABASE_SERVICE_KEY": "test-key"},
    ), mock.patch("supabase.create_client", return_value=fake_client):
        vps.persist_race_predictions(race, [top], decision_tier="C", commit_sha="deadbeef")

    assert captured["rpdc_primary_tag"] is None
    assert captured["rpdc_tags"] == []
    assert captured["rpdc_tag_count"] == 0
    assert captured["rpdc_release_score"] == 0.0
