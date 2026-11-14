"""Paged read of raceform from Supabase: every row once, id order, stops on a short page."""
from app.services.raceform_source import COLUMNS, PAGE, iter_pages, load_raceform


def _fake_table(n):
    rows = [{c: None for c in COLUMNS} | {"id": i, "horse": f"h{i}", "date": "2024-01-01"} for i in range(1, n + 1)]

    def get(path):
        after = int(path.split("id=gt.")[1].split("&")[0])
        return [r for r in rows if r["id"] > after][:PAGE]
    return get


def test_pages_cover_every_row_once():
    get = _fake_table(2 * PAGE + 17)
    df = load_raceform(get)
    assert len(df) == 2 * PAGE + 17
    assert df["id"].is_unique
    assert list(df["id"]) == sorted(df["id"])


def test_empty_table_is_empty_frame():
    df = load_raceform(lambda p: [])
    assert len(df) == 0 and list(df.columns) == COLUMNS


def test_stops_on_short_page():
    calls = []

    def get(path):
        calls.append(path)
        return [{c: None for c in COLUMNS} | {"id": 1}] if len(calls) == 1 else []
    list(iter_pages(get))
    assert len(calls) == 1
