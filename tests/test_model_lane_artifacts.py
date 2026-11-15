"""Release check: a model lane's files must be in git, or be listed as missing with a repair.

`models/**/*.pkl` and `data/new_build/` are git-ignored. A model trained on the laptop therefore
runs there and is absent from the Railway image unless it is force-added. That is how No-RPR
produced no output until 2026-11-05, and how the Mid-Price specialist, New Build Lane C and the
Radical Shadow gates were still absent on 2026-11-15.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from scripts.ops import check_model_lane_artifacts as check

ROOT = Path(__file__).resolve().parents[1]
LANES = check.load_manifest()


def _tracked() -> set[str]:
    try:
        out = subprocess.run(
            ["git", "ls-files", "models", "data/new_build/models"],
            cwd=ROOT, check=True, capture_output=True, text=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("not a git checkout")
    return set(out.splitlines())


def test_every_shipped_lane_file_is_tracked_in_git() -> None:
    tracked = _tracked()
    untracked = {
        lane["lane"]: [p for p in lane["artifacts"] if p not in tracked]
        for lane in LANES
        if lane["status"] == check.SHIPPED
    }
    untracked = {lane: paths for lane, paths in untracked.items() if paths}
    assert not untracked, f"these lanes will fail in the cloud image, their files are not in git: {untracked}"


def test_a_lane_listed_as_missing_really_is_and_says_how_to_repair_it() -> None:
    tracked = _tracked()
    for lane in LANES:
        if lane["status"] != check.KNOWN_MISSING:
            continue
        assert lane.get("impact") and lane.get("repair") and lane.get("since"), lane["lane"]
        arrived = [p for p in lane["artifacts"] if p in tracked]
        assert len(arrived) < len(lane["artifacts"]), (
            f"{lane['lane']}: every file is now in git. Set its status to SHIPPED in config/model_lane_artifacts.json."
        )


def test_statuses_are_known() -> None:
    assert {lane["status"] for lane in LANES} <= {check.SHIPPED, check.KNOWN_MISSING}


@pytest.mark.parametrize("lane", LANES, ids=[lane["lane"] for lane in LANES])
def test_the_manifest_names_the_file_the_loader_opens(lane: dict) -> None:
    """The manifest cannot drift from the code: each file name appears in its loader's source."""
    source = (ROOT / lane["loader"]).read_text(encoding="utf-8")
    for artifact in lane["artifacts"]:
        name = Path(artifact).name
        registry_names_it = name in (ROOT / "data/new_build/models/champion/champion_registry.json").read_text(
            encoding="utf-8"
        )
        assert name in source or (lane["loader"].endswith("paper_scorer.py") and registry_names_it), (
            f"{lane['loader']} does not mention {name}"
        )


def test_the_morning_runner_lanes_that_load_a_model_are_all_listed() -> None:
    """A new lane added to run_full_raceday.py with its own model must be added to the manifest."""
    runner = (ROOT / "scripts/ops/run_full_raceday.py").read_text(encoding="utf-8")
    loaders = {lane["loader"] for lane in LANES}
    for script in (
        "scripts/ops/run_midprice_shadow_today.py",
        "scripts/ops/run_radical_shadow_today.py",
        "scripts/ops/run_horse_history_shadow.py",
        "scripts/ops/new_build_two_lane_score.py",
    ):
        assert script in runner, f"{script} is no longer a morning step; update this test and the manifest"
        assert script in loaders


def test_a_shipped_lane_with_no_file_is_reported_broken(tmp_path: Path) -> None:
    lanes = [{"lane": "X", "loader": "x.py", "artifacts": ["models/x.pkl"], "status": check.SHIPPED}]
    assert check.check_lanes(lanes, tmp_path)[0]["state"] == "BROKEN"
    (tmp_path / "models").mkdir()
    (tmp_path / "models" / "x.pkl").write_bytes(b"x")
    assert check.check_lanes(lanes, tmp_path)[0]["state"] == "OK"


def test_a_known_gap_is_reported_with_impact_and_repair_and_flags_its_own_arrival(tmp_path: Path) -> None:
    lanes = [
        {
            "lane": "Y", "loader": "y.py", "artifacts": ["models/y.pkl"], "status": check.KNOWN_MISSING,
            "impact": "no output", "repair": "ship the file",
        }
    ]
    finding = check.check_lanes(lanes, tmp_path)[0]
    assert finding["state"] == "KNOWN_MISSING"
    text = check.format_finding(finding)
    assert "WHAT FAILED" in text and "no output" in text and "ship the file" in text and "y.py" in text
    (tmp_path / "models").mkdir()
    (tmp_path / "models" / "y.pkl").write_bytes(b"y")
    assert check.check_lanes(lanes, tmp_path)[0]["state"] == "NOW_PRESENT"
