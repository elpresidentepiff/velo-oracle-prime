"""FORMFAV-INGEST-01: track bias is stored as a snapshot; a failure never stops racecard capture."""
import importlib.util
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _worker():
    spec = importlib.util.spec_from_file_location("fw", ROOT / "scripts/ops/formfav_live_worker.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _Client:
    def __init__(self, packet=None, raise_exc=None):
        self.packet, self.raise_exc, self.calls = packet, raise_exc, []

    def track_bias(self, **kw):
        self.calls.append(kw)
        if self.raise_exc:
            raise self.raise_exc
        return self.packet


def test_bias_snapshot_is_inserted(monkeypatch):
    fw = _worker()
    rows = []
    monkeypatch.setattr(fw, "_insert", lambda table, r: rows.append((table, r)))
    packet = {"biasStrength": 0.42, "barrierStats": [{"barrierNumber": 1, "totalStarts": 40}]}
    client = _Client(packet)
    now = datetime(2026, 11, 14, 12, 0, tzinfo=UTC)
    fw._persist_track_bias(client, "uk:ascot:2026-11-14:1", {"track": "Ascot", "meeting_slug": "ascot"},
                           {"distance": "1m", "condition": "Good"}, "GB", now)
    assert client.calls[0]["venue"] == "ascot" and client.calls[0]["distance"] == 1609
    assert client.calls[0]["window"] == 90
    table, data = rows[0]
    assert table == "formfav_track_bias"
    assert data[0]["bias_strength"] == 0.42
    assert data[0]["barrier_stats"][0]["totalStarts"] == 40
    assert data[0]["payload"] == packet


def test_bias_failure_is_soft(monkeypatch, capsys):
    fw = _worker()
    monkeypatch.setattr(fw, "_insert", lambda table, r: (_ for _ in ()).throw(AssertionError("must not insert")))
    client = _Client(raise_exc=RuntimeError("provider down"))
    fw._persist_track_bias(client, "k", {"track": "Ascot"}, {}, "GB", datetime.now(UTC))
    assert "TRACK_BIAS_FAILED" in capsys.readouterr().err


def test_no_venue_means_no_call(monkeypatch):
    fw = _worker()
    client = _Client({"biasStrength": 0.1})
    fw._persist_track_bias(client, "k", {}, {}, "GB", datetime.now(UTC))
    assert client.calls == []


def test_track_bias_distance_parser_accepts_card_formats_and_rejects_invalid_values():
    fw = _worker()
    assert fw._track_bias_distance_metres("3365m") == 3365
    assert fw._track_bias_distance_metres("1m 4f") == 2414
    assert fw._track_bias_distance_metres("1m2f") == 2012
    assert fw._track_bias_distance_metres("six furlongs") is None
    assert fw._track_bias_distance_metres("12000m") is None


def test_track_bias_strength_preserves_provider_meaning_in_numeric_column(monkeypatch):
    fw = _worker()
    rows = []
    monkeypatch.setattr(fw, "_insert", lambda table, r: rows.append((table, r)))
    fw._persist_track_bias(
        _Client({"biasStrength": "moderate", "barrierStats": []}),
        "k", {"track": "Ascot", "meeting_slug": "ascot"}, {"distance": "1600m"}, "GB", datetime.now(UTC),
    )
    assert rows[0][1][0]["bias_strength"] == 0.66
    assert rows[0][1][0]["payload"]["biasStrength"] == "moderate"
    assert fw._track_bias_strength_numeric("none") == 0.0
    assert fw._track_bias_strength_numeric("unknown") is None


def test_bias_failure_has_safe_diagnostic(monkeypatch, capsys):
    fw = _worker()
    monkeypatch.setenv("FORMFAV_API_KEY", "secret-key")
    client = _Client(raise_exc=RuntimeError("HTTP 422 secret-key invalid distance"))
    fw._persist_track_bias(client, "k", {"track": "Ascot", "meeting_slug": "ascot"}, {}, "GB", datetime.now(UTC))
    output = capsys.readouterr().err
    assert "HTTP 422" in output
    assert "secret-key" not in output
