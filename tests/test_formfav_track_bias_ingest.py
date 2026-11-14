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
    fw._persist_track_bias(client, "uk:ascot:2026-11-14:1", {"track": "Ascot"},
                           {"distance": "1m", "condition": "Good"}, "GB", now)
    assert client.calls[0]["venue"] == "Ascot" and client.calls[0]["window"] == 90
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
