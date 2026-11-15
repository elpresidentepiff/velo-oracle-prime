"""The race day's working state lives in Supabase, not on one machine's disk.

Before 2026-11-15 the passport bank and the per-run form history existed in full only on the
operator's laptop. A Railway container read the git copies from 2026-08-04, captured new horses
every morning and lost them when it exited.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.ops import cloud_state as state

ROOT = Path(__file__).resolve().parents[1]


def _passport(uid: int, last_run: str, runs: int, **extra) -> dict:
    return {"horse_rp_uid": uid, "horse_name": f"Horse {uid}", "last_run_date": last_run, "career_runs": runs, **extra}


# ── passports ────────────────────────────────────────────────────────────────


def test_merge_keeps_every_horse_and_the_fresher_passport_of_each() -> None:
    local = [_passport(1, "2026-08-01", 5), _passport(2, "2026-11-10", 9, tag="local")]
    remote = [
        _passport(1, "2026-10-17", 7, tag="supabase"),
        _passport(2, "2026-09-01", 8),
        _passport(3, "2026-10-01", 2),
    ]

    merged = {row["horse_rp_uid"]: row for row in state.merge_passports(local, remote)}

    assert set(merged) == {1, 2, 3}
    assert merged[1]["tag"] == "supabase"  # git copy was older
    assert merged[2]["tag"] == "local"  # this morning's capture beats the stored row


def test_merge_keeps_the_local_row_on_a_tie_and_orders_by_runs_when_dates_match() -> None:
    assert (
        state.merge_passports(
            [_passport(1, "2026-10-01", 4, tag="local")], [_passport(1, "2026-10-01", 4, tag="remote")]
        )[0]["tag"]
        == "local"
    )
    assert (
        state.merge_passports([_passport(1, "2026-10-01", 4)], [_passport(1, "2026-10-01", 5, tag="remote")])[0]["tag"]
        == "remote"
    )


def test_hydrate_merges_supabase_into_the_bank_and_remembers_what_supabase_held(tmp_path, monkeypatch) -> None:
    bank = tmp_path / "horse_passports_v1.jsonl"
    bank.write_text(json.dumps(_passport(1, "2026-08-01", 5)) + "\n", encoding="utf-8")
    remote = [_passport(1, "2026-10-17", 7), _passport(2, "2026-10-01", 3)]
    monkeypatch.setattr(state, "fetch_passport_rows", lambda: remote)

    result = state.hydrate_passports(bank)

    assert result == {"local_before": 1, "supabase": 2, "bank_after": 2}
    rows = [json.loads(line) for line in bank.read_text(encoding="utf-8").splitlines()]
    assert {(r["horse_rp_uid"], r["career_runs"]) for r in rows} == {(1, 7), (2, 3)}
    hashes = json.loads((tmp_path / state.HYDRATED_HASHES.name).read_text(encoding="utf-8"))
    assert hashes == {"1": state.passport_hash(remote[0]), "2": state.passport_hash(remote[1])}


def test_persist_uploads_only_the_passports_that_changed(tmp_path, monkeypatch) -> None:
    from scripts.ops import persist_daily_artifacts as daily

    unchanged, updated, new = (
        _passport(1, "2026-10-17", 7),
        _passport(2, "2026-11-14", 4),
        _passport(3, "2026-11-14", 1),
    )
    bank = tmp_path / "horse_passports_v1.jsonl"
    bank.write_text("\n".join(json.dumps(r) for r in (unchanged, updated, new)) + "\n", encoding="utf-8")
    (tmp_path / state.HYDRATED_HASHES.name).write_text(
        json.dumps({"1": state.passport_hash(unchanged), "2": state.passport_hash(_passport(2, "2026-10-01", 3))}),
        encoding="utf-8",
    )
    sent: list[dict] = []
    monkeypatch.setattr(
        daily,
        "build_passports",
        lambda: [{"horse_rp_uid": r["horse_rp_uid"], "passport": r} for r in (unchanged, updated, new)],
    )
    monkeypatch.setattr(daily, "_upsert", lambda table, rows, conflict, batch=200: sent.extend(rows) or len(rows))

    result = state.persist_passports(bank)

    assert result == {"upserted": 2, "changed": 2}
    assert sorted(r["horse_rp_uid"] for r in sent) == [2, 3]
    # A second persist with nothing new sends nothing.
    sent.clear()
    assert state.persist_passports(bank) == {"upserted": 0, "changed": 0}
    assert sent == []


def test_a_bank_that_was_never_merged_with_supabase_is_not_pushed(tmp_path, monkeypatch) -> None:
    """A stale git copy must not overwrite newer rows in Supabase."""
    from scripts.ops import persist_daily_artifacts as daily

    bank = tmp_path / "horse_passports_v1.jsonl"
    bank.write_text(json.dumps(_passport(1, "2026-08-01", 5)) + "\n", encoding="utf-8")
    monkeypatch.setattr(daily, "_upsert", lambda *a, **k: pytest.fail("must not write"))
    assert state.persist_passports(bank) == {"upserted": 0, "skipped": "NOT_HYDRATED"}


# ── form history ─────────────────────────────────────────────────────────────


def _fake_storage(monkeypatch, objects: dict[str, bytes]) -> list[str]:
    uploads: list[str] = []

    def fake_list(prefix: str) -> list[str]:
        return sorted(p.rsplit("/", 1)[1] for p in objects if p.rsplit("/", 1)[0] == prefix)

    def fake_upload(path: str, data: bytes) -> None:
        objects[path] = data
        uploads.append(path)

    monkeypatch.setattr(state, "list_objects", fake_list)
    monkeypatch.setattr(state, "download_object", lambda path: objects[path])
    monkeypatch.setattr(state, "upload_object", fake_upload)
    monkeypatch.setattr(state, "_git_tracked", lambda directory: {"form_history_2026-05-24.json"})
    return uploads


def test_hydrate_downloads_the_archive_seed_and_newer_cloud_captures(tmp_path, monkeypatch) -> None:
    objects = {
        f"{state.SEED_PREFIX}/form_history_2026-05-24.json": b"seed-old",
        f"{state.SEED_PREFIX}/form_history_2026-09-18.json": b"seed",
        f"{state.SEED_PREFIX}/form_history_latest.json": b"skip",
        f"{state.STATE_PREFIX}/form_history_passport-topup-2026-11-16.json": b"cloud",
    }
    _fake_storage(monkeypatch, objects)
    (tmp_path / "form_history_2026-05-24.json").write_bytes(b"from-git")

    result = state.hydrate_form_history(tmp_path)

    assert result == {"stored": 3, "downloaded": 2, "on_disk": 3}
    assert (tmp_path / "form_history_2026-05-24.json").read_bytes() == b"from-git"  # already on disk
    assert (tmp_path / "form_history_2026-09-18.json").read_bytes() == b"seed"
    assert (tmp_path / "form_history_passport-topup-2026-11-16.json").read_bytes() == b"cloud"
    assert not (tmp_path / "form_history_latest.json").exists()


def test_persist_uploads_only_this_runs_capture_and_never_touches_the_archive(tmp_path, monkeypatch) -> None:
    objects = {f"{state.SEED_PREFIX}/form_history_2026-09-18.json": b"seed"}
    uploads = _fake_storage(monkeypatch, objects)
    state.hydrate_form_history(tmp_path)
    (tmp_path / "form_history_2026-05-24.json").write_bytes(b"git-tracked")
    (tmp_path / "form_history_passport-topup-2026-11-16.json").write_bytes(b"today")

    result = state.persist_form_history(tmp_path)

    assert result == {"uploaded": 1, "files": ["form_history_passport-topup-2026-11-16.json"]}
    assert uploads == [f"{state.STATE_PREFIX}/form_history_passport-topup-2026-11-16.json"]
    assert all(not path.startswith("velo-archive/") for path in uploads)
    assert state.persist_form_history(tmp_path)["uploaded"] == 0  # idempotent


def test_form_history_is_not_uploaded_without_a_hydrate(tmp_path, monkeypatch) -> None:
    _fake_storage(monkeypatch, {})
    (tmp_path / "form_history_x.json").write_bytes(b"x")
    assert state.persist_form_history(tmp_path) == {"uploaded": 0, "skipped": "NOT_HYDRATED"}


def test_supabase_being_down_does_not_stop_the_day(monkeypatch, capsys) -> None:
    def boom():
        raise RuntimeError("SUPABASE_URL and a Supabase service key are required")

    result = state._attempt("hydrate passport bank", boom)
    assert result["status"] == "FAILED" and "service key" in result["error"]
    assert "[CLOUD-STATE] hydrate passport bank" in capsys.readouterr().out


# ── the rebuild never replaces a passport with an older one ──────────────────


def test_passport_rebuild_keeps_a_newer_existing_row() -> None:
    from scripts.ops import new_build_horse_passports as rebuild

    src = (ROOT / "scripts/ops/new_build_horse_passports.py").read_text(encoding="utf-8")
    assert "_freshness(existing) > _freshness(built)" in src
    assert "combined_by_key.update(built_by_key)" not in src  # the unconditional overwrite is gone
    from_supabase, rebuilt_from_old_files = _passport(1, "2026-10-17", 7), _passport(1, "2026-08-01", 9)
    assert rebuild._freshness(from_supabase) > rebuild._freshness(rebuilt_from_old_files)
    assert rebuild._freshness(_passport(1, "2026-10-17", 8)) > rebuild._freshness(from_supabase)


# ── the morning run is wired ─────────────────────────────────────────────────


def test_the_morning_run_hydrates_first_and_persists_after_the_capture() -> None:
    src = (ROOT / "scripts/ops/run_full_raceday.py").read_text(encoding="utf-8")
    hydrate = src.index('"scripts/ops/cloud_state.py", "--hydrate"')
    feed = src.index('"Step 6: New Build current-card feed"')
    rebuild = src.index('"Passport top-up: rebuild passport bank (merge-in-place)"')
    persist = src.index('"scripts/ops/cloud_state.py", "--persist"')
    refeed = src.index('"Step 6b: New Build current-card feed (after passport top-up)"')
    scoring = src.index('"Step 9: Live scoring (run_prime_today.py)"')
    assert hydrate < feed < rebuild < persist < refeed < scoring


# ── Lane C runs from the copy that is in git ─────────────────────────────────


def test_lane_c_uses_the_champion_copy_only_while_the_soft_label_model_is_champion(tmp_path) -> None:
    from scripts.ops import new_build_two_lane_score as lanes

    laptop_copy, champion, registry = tmp_path / "soft.pkl", tmp_path / "champion.pkl", tmp_path / "registry.json"
    assert lanes.resolve_lane_c_pkl(laptop_copy, champion, registry) is None

    champion.write_bytes(b"model")
    registry.write_text(json.dumps({"promoted_from": "soft_label_challenger"}), encoding="utf-8")
    assert lanes.resolve_lane_c_pkl(laptop_copy, champion, registry) == champion

    registry.write_text(json.dumps({"promoted_from": "something_else"}), encoding="utf-8")
    assert lanes.resolve_lane_c_pkl(laptop_copy, champion, registry) is None  # never the wrong model

    laptop_copy.write_bytes(b"model")
    assert lanes.resolve_lane_c_pkl(laptop_copy, champion, registry) == laptop_copy


def test_lane_c_resolves_in_this_checkout() -> None:
    from scripts.ops import new_build_two_lane_score as lanes

    assert lanes.resolve_lane_c_pkl() is not None


# ── no hard-coded laptop folder off the laptop ───────────────────────────────


def test_the_pdf_inbox_is_inside_the_checkout_when_the_laptop_folder_is_absent() -> None:
    from scripts.ops import auto_ingest_pdf_inbox, fetch_rp_meeting_pdfs

    for module in (auto_ingest_pdf_inbox, fetch_rp_meeting_pdfs):
        if not module.LAPTOP_INBOX.is_dir():
            assert module.DEFAULT_INBOX == ROOT / "data" / "pdf_inbox"


def test_the_pdf_fetch_does_not_sign_in_unless_the_operator_switches_it_on(monkeypatch) -> None:
    """Sheets arriving would change three of Prime's inputs. A deploy alone must not do that."""
    from scripts.ops import fetch_rp_meeting_pdfs as fetch

    class Context:
        def new_page(self):
            raise AssertionError("must not open Racing Post")

    monkeypatch.setenv("RP_EMAIL", "someone@example.invalid")
    monkeypatch.setenv("RP_PASSWORD", "x")
    monkeypatch.delenv("VELO_PDF_FETCH_SIGN_IN", raising=False)
    assert fetch._sign_in_if_configured(Context()) is None

    monkeypatch.setenv("VELO_PDF_FETCH_SIGN_IN", "1")
    monkeypatch.delenv("RP_EMAIL")
    assert fetch._sign_in_if_configured(Context()) == "SKIPPED_NO_CREDENTIALS"
