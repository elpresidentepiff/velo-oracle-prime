"""End-to-end: merged racecard (current dict format) -> loader -> history -> candidate -> shadow JSON.
History fetch is faked; everything else is the real code path."""
import importlib.util
import json
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load_shadow():
    spec = importlib.util.spec_from_file_location("shadow", ROOT / "scripts/ops/run_horse_history_shadow.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _merged(root: Path, date: str):
    d = root / "data" / "racecard_merged"
    d.mkdir(parents=True, exist_ok=True)
    race = {
        "race_info": {"distance_furlongs": 8.0, "going": "Good to Firm", "race_class": "4",
                      "race_type": "Flat", "country": "GB"},
        "horses": [
            {"horse": "Alpha", "age": 4, "draw": 3, "weight": "9-7", "current_or": 80},
            {"horse": "Beta", "age": 5, "draw": 7, "weight": "10-0", "current_or": 72},
        ],
    }
    doc = {"venue": "Ascot", "date": date, "races": {"14:00": race}}
    (d / f"racecard_ASCOT_{date}.json").write_text(json.dumps(doc))


@pytest.mark.skipif(not (ROOT / "models/horse_history_candidate/model.pkl").exists(),
                    reason="candidate model not present")
def test_shadow_scores_runners_and_writes_ok(tmp_path, monkeypatch):
    shadow = _load_shadow()
    date = "2026-11-20"
    _merged(tmp_path, date)
    monkeypatch.setattr(shadow, "ROOT", tmp_path)
    monkeypatch.setattr(shadow, "OUT_DIR", tmp_path / "out")
    hist = pd.DataFrame([{
        "horse": "Alpha (IRE)", "date": "2025-10-01", "course": "Ascot", "dist": "1m",
        "going": "Good", "class_raw": "Class 4", "type": "Flat", "pos": "1",
        "or_rating": "79", "ran": "8", "draw": "2", "age": "4", "wgt": "9-7", "sp": "5/1",
        "dist_f": None, "source": "raceform",
    }])
    monkeypatch.setattr(shadow, "fetch_history", lambda names: hist)
    import sys
    monkeypatch.setattr(sys, "argv", ["x", "--date", date])
    assert shadow.main() == 0
    out = json.loads((tmp_path / "out" / f"{date}.json").read_text())
    assert out["status"] == "OK", out.get("detail")
    assert out["production_influence"] is False
    horses = {r["horse"]: r for r in out["runners"]}
    assert set(horses) == {"alpha", "beta"}
    assert horses["alpha"]["history_known"] is True
    assert horses["beta"]["history_known"] is False
    probs = [r["prob"] for r in out["runners"]]
    assert all(0.0 < p < 1.0 for p in probs)
