"""
tests/test_sigma_28b_run_prime_today_flags.py
================================================
Focused tests for SIGMA-28B: decoupling verdict persistence from
runner_prediction_snapshots writes in run_prime_today.py.

Pure-function tests only — _resolve_persistence_modes() takes a parsed args
namespace and returns a mode dict. No Supabase, no live scoring, no Telegram.
"""

from __future__ import annotations

from argparse import Namespace

from scripts.ops.run_prime_today import _resolve_persistence_modes


def _args(**overrides) -> Namespace:
    defaults = {
        "dry_run": False,
        "verdicts_only": False,
        "no_runner_snapshots": False,
        "no_notify": False,
    }
    defaults.update(overrides)
    return Namespace(**defaults)


def test_dry_run_disables_verdict_persistence_and_runner_snapshots():
    modes = _resolve_persistence_modes(_args(dry_run=True))
    assert modes["persistence_enabled"] is False
    assert modes["verdict_persistence_enabled"] is False
    assert modes["runner_snapshots_enabled"] is False
    assert modes["telegram_enabled"] is False
    assert modes["mode_label"] == "DRY_RUN"


def test_default_non_dry_run_preserves_existing_behaviour():
    modes = _resolve_persistence_modes(_args())
    assert modes["persistence_enabled"] is True
    assert modes["verdict_persistence_enabled"] is True
    assert modes["runner_snapshots_enabled"] is True
    assert modes["telegram_enabled"] is True
    assert modes["mode_label"] == "STANDARD"


def test_no_runner_snapshots_flag_disables_only_snapshots():
    modes = _resolve_persistence_modes(_args(no_runner_snapshots=True))
    assert modes["verdict_persistence_enabled"] is True
    assert modes["runner_snapshots_enabled"] is False
    assert modes["telegram_enabled"] is True


def test_verdicts_only_disables_snapshots_and_telegram_but_not_verdicts():
    modes = _resolve_persistence_modes(_args(verdicts_only=True))
    assert modes["verdict_persistence_enabled"] is True
    assert modes["runner_snapshots_enabled"] is False
    assert modes["telegram_enabled"] is False
    assert modes["mode_label"] == "VERDICTS_ONLY"


def test_dry_run_wins_over_verdicts_only():
    modes = _resolve_persistence_modes(_args(dry_run=True, verdicts_only=True))
    assert modes["persistence_enabled"] is False
    assert modes["verdict_persistence_enabled"] is False
    assert modes["runner_snapshots_enabled"] is False
    assert modes["telegram_enabled"] is False
    assert modes["mode_label"] == "DRY_RUN"


def test_no_notify_alone_does_not_affect_persistence():
    modes = _resolve_persistence_modes(_args(no_notify=True))
    assert modes["verdict_persistence_enabled"] is True
    assert modes["runner_snapshots_enabled"] is True
    assert modes["telegram_enabled"] is False
