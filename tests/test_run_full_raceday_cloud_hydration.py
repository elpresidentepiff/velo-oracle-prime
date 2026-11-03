from scripts.ops import run_full_raceday


def test_missing_archive_is_hydrated_before_downstream(monkeypatch, tmp_path):
    monkeypatch.setattr(run_full_raceday, "ROOT", tmp_path)
    calls = []

    def fake_run(label, cmd, *, critical, results):
        calls.append((label, cmd, critical))
        archive = tmp_path / "data" / "velo_prime_verdicts_2026_11_03.json"
        archive.parent.mkdir()
        archive.write_text("[]", encoding="utf-8")
        return True

    monkeypatch.setattr(run_full_raceday, "run", fake_run)
    results = []

    assert run_full_raceday.ensure_local_verdict_archive("2026-11-03", results)
    assert calls == [
        (
            "Step 9 restore: hydrate local verdict archive from Supabase",
            [run_full_raceday.PY, "scripts/ops/sync_verdicts_from_supabase.py", "--date", "2026-11-03"],
            True,
        )
    ]


def test_existing_archive_is_not_rehydrated(monkeypatch, tmp_path):
    monkeypatch.setattr(run_full_raceday, "ROOT", tmp_path)
    archive = tmp_path / "data" / "velo_prime_verdicts_2026_11_03.json"
    archive.parent.mkdir()
    archive.write_text("[]", encoding="utf-8")
    monkeypatch.setattr(
        run_full_raceday, "run", lambda *a, **k: (_ for _ in ()).throw(AssertionError("unexpected hydration"))
    )

    assert run_full_raceday.ensure_local_verdict_archive("2026-11-03", [])


def test_hydration_command_failure_blocks(monkeypatch, tmp_path):
    monkeypatch.setattr(run_full_raceday, "ROOT", tmp_path)
    monkeypatch.setattr(run_full_raceday, "run", lambda *a, **k: False)

    assert not run_full_raceday.ensure_local_verdict_archive("2026-11-03", [])


def test_hydration_must_materialize_archive(monkeypatch, tmp_path):
    monkeypatch.setattr(run_full_raceday, "ROOT", tmp_path)
    monkeypatch.setattr(run_full_raceday, "run", lambda *a, **k: True)

    assert not run_full_raceday.ensure_local_verdict_archive("2026-11-03", [])
