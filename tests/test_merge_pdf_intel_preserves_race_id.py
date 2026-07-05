"""Regression test: merging PDF intel into an injection-based racecard_merged
file must preserve the real numeric race_id and must not drop/replace the
runner list — only overlay PDF-derived per-horse fields by name match.

This guards against the 2026-07-05 bug where running ingest_racecard_pdfs.py
directly against data/racecard_merged/racecard_{VENUE}_{date}.json clobbered
the real race_id with a from-scratch, race_id-less structure, forcing
run_prime_today.py to fall back to synthetic race_ids (rp_{venue}_{date}_{time}).
"""
import json

import scripts.ops.merge_pdf_intel_into_racecard_merged as mod


def test_merge_preserves_race_id_and_attaches_pdf_fields(tmp_path, monkeypatch):
    merged_dir = tmp_path / "data" / "racecard_merged"
    merged_dir.mkdir(parents=True)
    merged_path = merged_dir / "racecard_TST_2026-07-05.json"
    merged_path.write_text(json.dumps({
        "venue": "Test",
        "venue_code": "TST",
        "date": "2026-07-05",
        "races": {
            "2.11": {
                "race_id": 922291,
                "race_info": {"going": "Good"},
                "horses": [
                    {"horse_name": "Test Horse", "horse_id": "123456",
                     "or_compression_score": 0.0, "plot_conviction": 0.0},
                ],
            }
        },
    }), encoding="utf-8")

    monkeypatch.setattr(mod, "ROOT", tmp_path)
    monkeypatch.setattr(mod, "find_pdfs_in_dir", lambda d, v, dt: {
        "or": "fake_or.pdf", "ts": None, "spotlight": None, "postdata": None,
    })
    monkeypatch.setattr(mod, "parse_or_pdf", lambda p: {})
    monkeypatch.setattr(mod, "parse_ts_pdf", lambda p: {})
    monkeypatch.setattr(mod, "parse_spotlight_pdf", lambda p: {})
    monkeypatch.setattr(mod, "parse_postdata_pdf", lambda p: {})
    monkeypatch.setattr(mod, "merge_race_data", lambda *a, **k: {
        "2.11": {
            "horses": [
                {"horse_name": "Test Horse", "or_compression_score": 0.62, "plot_conviction": 0.81},
            ]
        }
    })

    result = mod.merge_pdf_intel(tmp_path, "TST", "2026-07-05", execute=True)

    assert result["status"] == "PASS"
    assert result["races_matched_to_pdf"] == 1
    assert result["horses_pdf_attached"] == 1

    updated = json.loads(merged_path.read_text(encoding="utf-8"))
    race = updated["races"]["2.11"]
    assert race["race_id"] == 922291
    assert race["race_info"] == {"going": "Good"}
    horse = race["horses"][0]
    assert horse["horse_id"] == "123456"
    assert horse["or_compression_score"] == 0.62
    assert horse["plot_conviction"] == 0.81
