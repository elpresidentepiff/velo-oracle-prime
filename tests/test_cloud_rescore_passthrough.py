from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_cloud_runner_forwards_authorised_rescore_reason():
    source = (ROOT / "scripts" / "ops" / "rp_cloud_raceday.py").read_text(encoding="utf-8")
    assert '"--authorised-rescore-reason"' in source
    assert 'default=os.getenv("VELO_AUTHORISED_RESCORE_REASON")' in source
    assert 'score.extend(["--authorised-rescore-reason", args.authorised_rescore_reason])' in source


def test_full_raceday_bypasses_skip_only_with_explicit_reason():
    source = (ROOT / "scripts" / "ops" / "run_full_raceday.py").read_text(encoding="utf-8")
    assert "if already_scored and not args.authorised_rescore_reason:" in source
    assert '["--authorised-rescore-reason", args.authorised_rescore_reason]' in source
