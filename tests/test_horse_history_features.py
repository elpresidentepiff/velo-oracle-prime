"""As-of horse-history features: no leakage, hand-checked values."""
import numpy as np
import pandas as pd

from app.services.horse_history_features import (
    HISTORY_FEATURES,
    compute_history_features,
    normalise_name,
    parse_dist_f,
    parse_going_code,
)


def _rows():
    return pd.DataFrame([
        # horse, date, race_id, course, dist_f, going_code, class_num, pos_n, or_num
        ("Alpha (IRE)", "2024-01-01", "r1", "Ascot", 8.0, 1.0, 3.0, 1, 80.0),
        ("Alpha (IRE)", "2024-02-01", "r2", "Ascot", 8.0, 1.0, 3.0, 5, 82.0),
        ("Alpha (IRE)", "2024-03-01", "r3", "York", 10.0, 1.0, 3.0, 2, 83.0),
        ("Beta", "2024-01-05", "r1", "Ascot", 8.0, 1.0, 4.0, 3, 70.0),
    ], columns=["horse", "date", "race_id", "course", "dist_f", "going_code", "class_num", "pos_n", "or_num"])


def test_first_run_has_no_history_and_later_runs_use_only_the_past():
    out = compute_history_features(_rows()).set_index(["horse", "race_id"])
    a1 = out.loc[("Alpha (IRE)", "r1")]
    a2 = out.loc[("Alpha (IRE)", "r2")]
    a3 = out.loc[("Alpha (IRE)", "r3")]
    assert a1.runs_prior == 0 and a1.win_rate_prior == (0 + 0.1) / 1.0
    assert a2.runs_prior == 1
    assert a2.win_rate_prior == (1 + 0.1) / 2.0          # one prior win
    assert a2.runs_since_win == 0                        # won last time out
    assert a3.runs_prior == 2
    assert a3.runs_since_win == 1                        # one run since the win
    assert a2.course_runs == 1 and a2.course_win_rate == (1 + 0.1) / 2.0  # Ascot: won r1 before r2
    assert a3.course_runs == 0                           # York: first visit
    assert a3.dist_runs == 0                             # 10f never run before
    assert a3.or_last == 82.0 and a3.or_change == 1.0    # 83 vs last 82
    assert a3.or_vs_best == 1.0                          # 83 vs best prior 82


def test_a_runner_result_never_changes_its_own_features():
    base = compute_history_features(_rows())
    changed = _rows()
    changed.loc[1, "pos_n"] = 1  # change the result of Alpha's second run
    after = compute_history_features(changed)
    cols = HISTORY_FEATURES
    # Alpha's first run is unaffected by its later results
    a_first_before = base[(base.horse == "Alpha (IRE)") & (base.race_id == "r1")][cols].iloc[0]
    a_first_after = after[(after.horse == "Alpha (IRE)") & (after.race_id == "r1")][cols].iloc[0]
    assert np.allclose(a_first_before.astype(float), a_first_after.astype(float), equal_nan=True)
    # Alpha's second run uses only its first run, so changing its own result does not change it
    a_second_before = base[(base.horse == "Alpha (IRE)") & (base.race_id == "r2")][cols].iloc[0]
    a_second_after = after[(after.horse == "Alpha (IRE)") & (after.race_id == "r2")][cols].iloc[0]
    assert np.allclose(a_second_before.astype(float), a_second_after.astype(float), equal_nan=True)


def test_appending_a_later_run_does_not_change_earlier_features():
    base = compute_history_features(_rows())
    extra = pd.concat([_rows(), pd.DataFrame([
        ("Alpha (IRE)", "2024-06-01", "r9", "Ascot", 8.0, 1.0, 3.0, np.nan, 90.0)],
        columns=_rows().columns)], ignore_index=True)
    after = compute_history_features(extra)
    for rid in ["r1", "r2", "r3"]:
        b = base[(base.horse == "Alpha (IRE)") & (base.race_id == rid)][HISTORY_FEATURES].iloc[0]
        a = after[(after.horse == "Alpha (IRE)") & (after.race_id == rid)][HISTORY_FEATURES].iloc[0]
        assert np.allclose(b.astype(float), a.astype(float), equal_nan=True), rid


def test_parsers_and_names():
    assert parse_dist_f("1m2f") == 10.0
    assert parse_dist_f("2m4½f") == 20.5
    assert parse_going_code("Good to Firm") == 1.5
    assert parse_going_code("Good to Soft") == 0.5
    assert normalise_name("Letterston Lady (GB)") == normalise_name("letterston lady")


def test_trainer_rate_excludes_same_day_runs():
    rows = pd.DataFrame([
        ("A", "2024-01-01", "r1", "Ascot", 8.0, 1.0, 3.0, 1, 80.0, "J1", "T1"),
        ("B", "2024-01-01", "r1", "Ascot", 8.0, 1.0, 3.0, 2, 70.0, "J2", "T1"),
        ("C", "2024-01-02", "r2", "Ascot", 8.0, 1.0, 3.0, 3, 70.0, "J2", "T1"),
    ], columns=["horse", "date", "race_id", "course", "dist_f", "going_code", "class_num",
                "pos_n", "or_num", "jockey", "trainer"])
    out = compute_history_features(rows).set_index("horse")
    # Horse C on 2 Jan: trainer T1 had 2 runs on 1 Jan, 1 win (A). Same-day runs excluded for B's race.
    assert out.loc["B", "trainer_runs"] == 0          # B's race on 1 Jan: no earlier-day runs
    assert out.loc["C", "trainer_runs"] == 2
    assert out.loc["C", "trainer_win_rate"] == (1 + 0.1) / (2 + 1.0)
    assert out.loc["C", "jockey_changed"] == 0.0 and out.loc["A", "jockey_changed"] == 0.0
