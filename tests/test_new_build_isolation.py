from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from new_build_velo.spine import LEARNING_ROOT, NEW_BUILD_ROOT, learn, write_json


ROOT = Path(__file__).resolve().parents[1]
NEW_BUILD_FILES = list((ROOT / "new_build_velo").glob("*.py"))


def _imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.append(node.module)
    return modules


def test_new_build_has_no_live_scoring_imports() -> None:
    forbidden = (
        "app.services.velo_prime_service",
        "scripts.ops.run_prime_today",
        "workers.velo_ops_worker",
        "app.playbooks.playbook_g_sentient_loopback",
    )
    imports = {path.name: _imports(path) for path in NEW_BUILD_FILES}
    flat = "\n".join(module for modules in imports.values() for module in modules)
    for module in forbidden:
        assert module not in flat


def test_new_build_write_json_rejects_outside_data_new_build(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        write_json(ROOT / "data" / "sentient_state.json", {"bad": True})
    allowed = NEW_BUILD_ROOT / "tests" / "write_guard.json"
    write_json(allowed, {"ok": True})
    assert json.loads(allowed.read_text(encoding="utf-8"))["ok"] is True
    allowed.unlink()


def test_new_build_learning_payload_has_no_rpr_feature_values() -> None:
    report = learn(from_date="2026-05-25", to_date="2026-05-29", execute=False)
    encoded = json.dumps(report).lower()
    assert "rpr_archive_only_excluded" in encoded
    assert "rp_rpr_archive_only" not in encoded
    assert "rpr_seen_archive_only" not in encoded
    state_path = Path(report["state_path"]).resolve()
    assert LEARNING_ROOT.resolve() in state_path.parents or state_path == LEARNING_ROOT.resolve()


def test_runtime_new_build_json_is_untracked() -> None:
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8", errors="ignore")
    assert "data/new_build/" in gitignore or "data/" in gitignore
