from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "evaluate_horse_journey_matched_controls",
    ROOT / "scripts" / "ops" / "evaluate_horse_journey_matched_controls.py",
)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def _packet(race_id: str, horse_id: str, *, tags: list[str] | None = None, eligible: bool = True, preoff: bool = True) -> dict:
    return {
        "race_id": race_id,
        "horse_id": horse_id,
        "feature_families": {
            "horse_journey_facts": {
                "training_eligible": eligible,
                "captured_before_off": preoff,
                "factual_tags": tags or [],
            }
        },
    }


def test_uses_only_preoff_eligible_journey_packet_universe_without_name_fallback():
    tags, candidates, coverage = module.build_evaluation_inputs([
        _packet("r1", "a", tags=["JOURNEY_HANDICAP_RELEASE_PATTERN"]),
        _packet("r1", "b"),
        _packet("r1", "c", tags=["JOURNEY_HANDICAP_RELEASE_PATTERN"], preoff=False),
        {"race_id": "r2", "horse_id": "d", "feature_families": {}},
        _packet("", "e"),
    ])

    assert tags == [{"race_id": "r1", "horse_id": "a", "tag": "JOURNEY_HANDICAP_RELEASE_PATTERN"}]
    assert candidates == [{"race_id": "r1", "horse_id": "a"}, {"race_id": "r1", "horse_id": "b"}]
    assert coverage == {
        "packets_read": 5,
        "packets_missing_journey_family": 1,
        "packets_invalid_identity": 1,
        "journey_packets_not_preoff_or_ineligible": 1,
        "journey_eligible_packets": 2,
        "journey_tag_rows": 1,
    }


def test_eod_and_artifact_persistence_are_wired_for_journey_report():
    eod_source = (ROOT / "scripts" / "ops" / "run_full_raceday_eod.py").read_text(encoding="utf-8")
    persistence_source = (ROOT / "scripts" / "ops" / "persist_daily_artifacts.py").read_text(encoding="utf-8")
    assert "evaluate_horse_journey_matched_controls.py" in eod_source
    assert '"horse_journey_matched_control"' in persistence_source
