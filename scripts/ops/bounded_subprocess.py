"""Run one pipeline step with a time limit that also stops everything the step started.

``subprocess.run(..., timeout=...)`` kills only the direct child. The race-day steps are
themselves orchestrators (``rp_cloud_raceday`` -> ``run_full_raceday`` -> ``run_prime_today``),
so a plain timeout leaves the grandchild running with no parent: it can go on writing verdicts
after the run has been reported as failed. Each step therefore gets its own process group, and
a timeout removes the whole group.

Works on the Railway containers (POSIX) and on the operator's Windows laptop.
"""
from __future__ import annotations

import os
import signal
import subprocess
from pathlib import Path


class StepTimeout(RuntimeError):
    """A step ran past its limit and was stopped, with everything it started."""

    def __init__(self, label: str, timeout: float) -> None:
        super().__init__(f"{label} exceeded {timeout:.0f}s and was stopped")
        self.label = label
        self.timeout = timeout


def timeout_from_env(name: str, default: float) -> float:
    """A positive number of seconds from the environment, or the default when unset or invalid."""
    raw = (os.environ.get(name) or "").strip()
    try:
        value = float(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def _kill_tree(process: subprocess.Popen) -> None:
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/T", "/F", "/PID", str(process.pid)],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    try:
        process.wait(timeout=30)
    except subprocess.TimeoutExpired:
        process.kill()


def run_bounded(
    label: str,
    command: list[str],
    *,
    cwd: str | Path,
    timeout: float,
    env: dict[str, str] | None = None,
) -> int:
    """Run ``command`` and return its exit code. Raise ``StepTimeout`` if it runs past ``timeout``.

    ``env`` is the complete environment for the child; ``None`` inherits this process's.
    """
    group = (
        {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}  # type: ignore[attr-defined]
        if os.name == "nt"
        else {"start_new_session": True}
    )
    process = subprocess.Popen(command, cwd=str(cwd), env=env, **group)
    try:
        return process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        _kill_tree(process)
        raise StepTimeout(label, timeout) from None
    except BaseException:
        # Ctrl-C or a crash in this process must not leave the step running behind it.
        _kill_tree(process)
        raise
