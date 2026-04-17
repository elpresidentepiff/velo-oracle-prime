from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APPROVED_ENV_BOOTSTRAP = {
    ROOT / "app" / "core" / "runtime_env.py",
}
OPERATIONAL_PATHS = [
    ROOT / "app" / "main.py",
    ROOT / "app" / "services" / "velo_prime_service.py",
    ROOT / "scripts" / "run_prime_today.py",
    ROOT / "scripts" / "run_results_sigma.py",
    ROOT / "scripts" / "shadow_lab.py",
    ROOT / "workers" / "daily_pipeline.py",
]
MONITORED_LEGACY_PATHS = [
    ROOT / "scripts" / "velo_ops_check.py",
    ROOT / "scripts" / "build_rpdc_profiles.py",
    ROOT / "scripts" / "ingest_racing_profiles.py",
    ROOT / "scripts" / "ingest_rp_stats.py",
]


def test_no_datetime_utcnow_in_operational_paths():
    violations: list[str] = []
    for path in OPERATIONAL_PATHS:
        text = path.read_text(encoding="utf-8", errors="ignore")
        if "datetime.utcnow(" in text:
            violations.append(str(path.relative_to(ROOT)))
    assert not violations, f"Replace datetime.utcnow() with timezone-aware helpers: {violations}"


def test_no_ad_hoc_env_bootstrap_in_operational_paths():
    violations: list[str] = []
    for path in OPERATIONAL_PATHS:
        if path in APPROVED_ENV_BOOTSTRAP:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if "load_dotenv(" in text:
            violations.append(str(path.relative_to(ROOT)))
    assert not violations, f"Use app.core.runtime_env for env bootstrap in operational paths: {violations}"


def test_no_hardcoded_secret_patterns_in_operational_paths():
    secret_markers = ("sk-or-v1-", "sb_secret_", "sb_publishable_", "eyJhbGciOiJIUzI1Ni")
    violations: list[str] = []
    for path in OPERATIONAL_PATHS:
        text = path.read_text(encoding="utf-8", errors="ignore")
        if any(marker in text for marker in secret_markers):
            violations.append(str(path.relative_to(ROOT)))
    assert not violations, f"Hardcoded secret-like patterns found in operational paths: {violations}"


def test_monitored_legacy_paths_inventory_is_present():
    missing = [str(path.relative_to(ROOT)) for path in MONITORED_LEGACY_PATHS if not path.exists()]
    assert not missing, f"Legacy monitoring inventory references missing paths: {missing}"
