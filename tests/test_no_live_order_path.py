"""CI guard: only the Betfair client may call place_order(s); nothing may enable LIVE.

Replaces the shallow import scan in app/core/safety_guards.py for the question
that matters: can any other code path reach a real order?
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {".git", "archive", "quarantine", "node_modules", "mlruns", "venv", ".venv", "tests", "data", "docs"}
ORDER_CALLS = {"place_order", "place_orders"}
ALLOWED = {"app/integrations/betfair_client.py"}


def _py_files():
    for p in ROOT.rglob("*.py"):
        if not (set(p.relative_to(ROOT).parts) & SKIP_DIRS):
            yield p


def test_only_the_betfair_client_calls_place_order() -> None:
    offenders = []
    for p in _py_files():
        rel = p.relative_to(ROOT).as_posix()
        if rel in ALLOWED:
            continue
        try:
            tree = ast.parse(p.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                fn = node.func
                name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
                if name in ORDER_CALLS:
                    offenders.append(f"{rel}:{node.lineno}")
    assert not offenders, f"place_order reachable outside the Betfair client: {offenders}"


def test_no_deploy_config_enables_live_modes() -> None:
    pat = re.compile(r"(BETFAIR_MODE|VELO_EXECUTION_MODE)\s*[=:]\s*[\"']?LIVE", re.I)
    hits = []
    for name in ("railway.toml", "railway.scoring.toml", "docker-compose.yml", ".env.example", ".env.template"):
        f = ROOT / name
        if f.exists() and pat.search(f.read_text(encoding="utf-8", errors="ignore")):
            hits.append(name)
    for f in list(ROOT.glob("Dockerfile*")) + list((ROOT / ".github" / "workflows").glob("*.yml")):
        if pat.search(f.read_text(encoding="utf-8", errors="ignore")):
            hits.append(f.name)
    assert not hits, f"LIVE mode enabled in config: {hits}"
