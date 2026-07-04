"""
tests/test_sigma_28b_run_prime_today_flags.py
================================================
Focused tests for SIGMA-28B: decoupling verdict persistence from
runner_prediction_snapshots writes in run_prime_today.py.

Pure-function tests only — _resolve_persistence_modes() takes a parsed args
namespace and returns a mode dict. No Supabase, no live scoring, no Telegram.
"""

from __future__ import annotations

import ast
import inspect
from argparse import Namespace

from scripts.ops import run_prime_today
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


def _find_write_runner_snapshots_call_guards(source: str) -> list[bool]:
    """Static check: for every call to _write_runner_snapshots in `source`,
    is it nested inside an `if` (or `if/else`) whose test references
    `runner_snapshots_enabled`?

    Returns one bool per call site found. Guards against the SIGMA-28B-FIX-
    PR110 regression: calling the writer unconditionally and only muting its
    Supabase argument (e.g. supabase_client=None) does NOT count as disabled —
    write_runner_snapshots() always writes a local JSONL file regardless of
    supabase_client, so "disabled" must mean the call itself never executes.
    """
    tree = ast.parse(source)
    guarded_flags: list[bool] = []

    class Visitor(ast.NodeVisitor):
        def __init__(self):
            self.guard_stack: list[bool] = []

        def visit_If(self, node: ast.If):
            test_src = ast.dump(node.test)
            is_snapshot_guard = "runner_snapshots_enabled" in test_src
            self.guard_stack.append(is_snapshot_guard)
            for child in node.body:
                self.visit(child)
            self.guard_stack.pop()
            # else/elif branch: not considered a positive guard for the call
            self.guard_stack.append(False)
            for child in node.orelse:
                self.visit(child)
            self.guard_stack.pop()

        def visit_Call(self, node: ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id == "_write_runner_snapshots":
                guarded_flags.append(any(self.guard_stack))
            self.generic_visit(node)

    Visitor().visit(tree)
    return guarded_flags


def test_write_runner_snapshots_call_is_guarded_not_just_client_muted():
    source = inspect.getsource(run_prime_today)
    guards = _find_write_runner_snapshots_call_guards(source)
    assert guards, "expected to find at least one _write_runner_snapshots call site"
    assert all(guards), (
        "every _write_runner_snapshots call must be inside an "
        "`if runner_snapshots_enabled:` guard — passing supabase_client=None "
        "alone is not sufficient, since the function always writes a local "
        "JSONL file regardless of the Supabase client argument"
    )
