from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_idempotent_cloud_skip_hydrates_missing_local_verdict_archive():
    source = (ROOT / "scripts" / "ops" / "run_full_raceday.py").read_text(encoding="utf-8")

    skip = source.index("if already_scored:")
    hydrate = source.index("sync_verdicts_from_supabase.py", skip)
    radical = source.index("run_radical_shadow_today.py", hydrate)

    assert skip < hydrate < radical
    assert 'if not local_verdict_archive.exists()' in source[skip:radical]
    assert 'critical=True' in source[hydrate:radical]

