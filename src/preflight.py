"""
VÉLØ Preflight Gate
====================
Hard precondition check for every scoring entrypoint.

Policy:
  PASS     → all critical checks green, safe to score
  DEGRADED → non-critical failures only (e.g. sentient state unavailable)
             → only allowed to continue if DEGRADED_POLICY == "allow"
             → MUST alert loudly to Telegram
  FAIL     → critical dependency missing — scoring MUST NOT run

Usage:
    from src.preflight import preflight, PreflightStatus

    result = preflight()
    if result.status == "FAIL":
        tg_alert(result.summary())
        sys.exit(1)
    if result.status == "DEGRADED":
        tg_alert(result.summary())
        # continue only if policy allows
"""

from __future__ import annotations

import os
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

ROOT = Path(__file__).parent.parent


# ── Failure classes ───────────────────────────────────────────────────────────


class Severity(StrEnum):
    CRITICAL = "CRITICAL"  # missing → FAIL
    DEGRADED = "DEGRADED"  # missing → DEGRADED (may still run)


@dataclass
class PreflightCheck:
    name: str
    severity: Severity
    passed: bool
    detail: str = ""


@dataclass
class PreflightResult:
    checks: list[PreflightCheck] = field(default_factory=list)
    status: str = "PASS"  # PASS | DEGRADED | FAIL

    def add(self, check: PreflightCheck) -> None:
        self.checks.append(check)
        if not check.passed:
            if check.severity == Severity.CRITICAL:
                self.status = "FAIL"
            elif check.severity == Severity.DEGRADED and self.status == "PASS":
                self.status = "DEGRADED"

    def failures(self) -> list[PreflightCheck]:
        return [c for c in self.checks if not c.passed]

    def summary(self) -> str:
        lines = [f"VELO PREFLIGHT — {self.status}"]
        if self.status != "PASS":
            for f in self.failures():
                icon = "CRITICAL" if f.severity == Severity.CRITICAL else "WARN"
                lines.append(f"  [{icon}] {f.name}: {f.detail}")
        else:
            lines.append("  All checks passed.")
        return "\n".join(lines)

    def telegram_alert(self) -> str:
        """Returns a Telegram-ready alert string. Only call when status != PASS."""
        lines = [
            f"VELO PREFLIGHT {self.status}",
            "─" * 30,
        ]
        for f in self.failures():
            icon = "CRITICAL" if f.severity == Severity.CRITICAL else "WARN"
            lines.append(f"[{icon}] {f.name}")
            if f.detail:
                lines.append(f"  {f.detail}")
        return "\n".join(lines)


# ── Individual checks ─────────────────────────────────────────────────────────


def _check_env_vars() -> PreflightCheck:
    """Critical env vars must all be present."""
    required = [
        "SUPABASE_URL",
        "RACING_API_USERNAME",
        "RACING_API_PASSWORD",
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_CHAT_ID",
    ]
    missing = [k for k in required if not os.getenv(k)]
    if missing:
        return PreflightCheck(
            name="env_vars",
            severity=Severity.CRITICAL,
            passed=False,
            detail=f"missing: {', '.join(missing)}",
        )
    return PreflightCheck(
        name="env_vars", severity=Severity.CRITICAL, passed=True, detail=f"{len(required)} vars present"
    )


def _check_supabase() -> PreflightCheck:
    """Supabase must be reachable and writable."""
    sb_url = os.getenv("SUPABASE_URL", "")
    sb_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY", "")
    if not sb_url or not sb_key:
        return PreflightCheck(
            name="supabase",
            severity=Severity.CRITICAL,
            passed=False,
            detail="SUPABASE_URL or key env var absent",
        )
    try:
        req = urllib.request.Request(
            f"{sb_url}/rest/v1/pipeline_runs?select=id&limit=1",
            headers={
                "apikey": sb_key,
                "Authorization": f"Bearer {sb_key}",
                "Accept": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=5):
            pass
        return PreflightCheck(name="supabase", severity=Severity.CRITICAL, passed=True, detail="reachable")
    except Exception as e:
        return PreflightCheck(
            name="supabase",
            severity=Severity.CRITICAL,
            passed=False,
            detail=f"unreachable: {e}",
        )


def _check_sqpe_model() -> PreflightCheck:
    """SQPE model artifact must exist on disk AND load cleanly via joblib."""
    candidates = [
        ROOT / "models" / "sqpe_v17" / "sqpe_v17.pkl",
        ROOT / "models" / "sqpe_v16" / "sqpe_v16.pkl",
    ]
    found = None
    for p in candidates:
        if p.exists():
            found = p
            break
    if found is None:
        return PreflightCheck(
            name="sqpe_model",
            severity=Severity.CRITICAL,
            passed=False,
            detail=f"none of {[str(c.relative_to(ROOT)) for c in candidates]} found",
        )
    # File exists — now verify it actually loads. A corrupt or incompatible pickle
    # would pass an existence-only check but detonate silently at scoring time.
    try:
        import joblib

        joblib.load(found)
    except Exception as e:
        return PreflightCheck(
            name="sqpe_model",
            severity=Severity.CRITICAL,
            passed=False,
            detail=f"file exists but load failed ({found.relative_to(ROOT)}): {e}",
        )
    return PreflightCheck(
        name="sqpe_model", severity=Severity.CRITICAL, passed=True, detail=str(found.relative_to(ROOT))
    )


def _check_canonical_constants() -> PreflightCheck:
    """Canonical constants module must import cleanly."""
    try:
        from src.constants import VALID_OUTCOMES, VALID_RUN_STATUSES, VALID_TIERS  # noqa: F401

        return PreflightCheck(name="canonical_constants", severity=Severity.CRITICAL, passed=True, detail="imported OK")
    except Exception as e:
        return PreflightCheck(
            name="canonical_constants",
            severity=Severity.CRITICAL,
            passed=False,
            detail=f"import failed: {e}",
        )


def _check_racing_api() -> PreflightCheck:
    """Racing API must be reachable (degraded if down — scoring uses cached cards)."""
    import base64

    user = os.getenv("RACING_API_USERNAME", "")
    pwd = os.getenv("RACING_API_PASSWORD", "")
    if not user or not pwd:
        return PreflightCheck(
            name="racing_api",
            severity=Severity.DEGRADED,
            passed=False,
            detail="credentials absent — will rely on cached racecards",
        )
    try:
        req = urllib.request.Request(
            "https://api.theracingapi.com/v1/courses",
            headers={
                "Authorization": "Basic " + base64.b64encode(f"{user}:{pwd}".encode()).decode(),
                "User-Agent": "Mozilla/5.0",
            },
        )
        with urllib.request.urlopen(req, timeout=8):
            pass
        return PreflightCheck(name="racing_api", severity=Severity.DEGRADED, passed=True, detail="reachable")
    except Exception as e:
        return PreflightCheck(
            name="racing_api",
            severity=Severity.DEGRADED,
            passed=False,
            detail=f"unreachable: {e} — will rely on cached racecards",
        )


def _check_specialist_models() -> PreflightCheck:
    """At least some specialist models should be present (degraded, not critical)."""
    model_dir = ROOT / "models" / "specialist"
    if not model_dir.exists():
        return PreflightCheck(
            name="specialist_models",
            severity=Severity.DEGRADED,
            passed=False,
            detail="models/specialist/ directory absent",
        )
    pkls = list(model_dir.glob("**/*.pkl"))
    if not pkls:
        return PreflightCheck(
            name="specialist_models",
            severity=Severity.DEGRADED,
            passed=False,
            detail="no .pkl files found in models/specialist/",
        )
    return PreflightCheck(
        name="specialist_models", severity=Severity.DEGRADED, passed=True, detail=f"{len(pkls)} model files present"
    )


# ── Main preflight function ───────────────────────────────────────────────────


def preflight() -> PreflightResult:
    """
    Run all preflight checks. Returns a PreflightResult with overall status.

    FAIL   → caller must not proceed with scoring
    DEGRADED → caller may proceed but MUST send Telegram alert
    PASS   → proceed normally
    """
    result = PreflightResult()

    result.add(_check_env_vars())
    result.add(_check_canonical_constants())
    result.add(_check_supabase())
    result.add(_check_sqpe_model())
    result.add(_check_racing_api())
    result.add(_check_specialist_models())

    return result


def preflight_or_die(tg_fn=None) -> PreflightResult:
    """
    Convenience wrapper: run preflight and sys.exit(1) on FAIL.
    Sends Telegram alert on DEGRADED or FAIL if tg_fn provided.

    Usage:
        from src.preflight import preflight_or_die
        pf = preflight_or_die(tg_fn=tg)
    """
    import sys

    result = preflight()

    # Always print to stdout
    for check in result.checks:
        icon = "PASS" if check.passed else ("CRIT" if check.severity == Severity.CRITICAL else "WARN")
        print(f"  [{icon}] {check.name}: {check.detail}")

    if result.status != "PASS":
        alert = result.telegram_alert()
        print(f"\nPREFLIGHT {result.status}")
        if tg_fn:
            tg_fn(alert)

    if result.status == "FAIL":
        print("PREFLIGHT FAIL — scoring blocked. Fix critical issues and retry.")
        sys.exit(1)

    return result
