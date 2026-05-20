"""
VÉLØ Oracle - FastAPI Main Application
Production-ready with CORS, health checks, and API routing
"""

import asyncio
import hmac
import json
import logging
import os
import pathlib
import re
import subprocess
import sys
import urllib.error
import urllib.request
import uuid
from collections import OrderedDict
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import Depends, FastAPI, File, Header, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.runtime_env import resolve_supabase_service_key, resolve_supabase_url, utc_now, utc_now_iso

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


_sentient_state: dict | None = None

_SOFT_SCHEMA_RUNTIME_NAMES = {"local", "dev", "development", "test", "testing"}
_TRIGGER_AGE_GATE_HOURS = 24
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_MAX_TARGET_DATE_LEN = 10
_PIPELINE_TRIGGER_SOURCES = {"manual", "github_actions_scheduled", "github_actions_manual", "api_manual"}
_TRIGGER_SERVICE_CONFIG = {
    "score_daily": {
        "service_name": "velo-prime-scoring",
        "run_type": "daily_scoring",
    },
    "sigma": {
        "service_name": "velo-results-sigma",
        "run_type": "results_reconciliation_light",
    },
    "sigma_daily": {
        "service_name": "velo_sigma_closer",
        "run_type": "results_reconciliation",
    },
}


def _secrets_match(provided: str | None, expected: str | None) -> bool:
    if not provided or not expected:
        return False
    return hmac.compare_digest(provided, expected)


def _validate_target_date_or_empty(target_date: str | None) -> str:
    raw = (target_date or "").strip()
    if not raw:
        return ""
    if len(raw) > _MAX_TARGET_DATE_LEN:
        raise HTTPException(status_code=400, detail="target_date too long; expected YYYY-MM-DD")
    if not _DATE_RE.fullmatch(raw):
        raise HTTPException(status_code=400, detail="Invalid target_date; expected YYYY-MM-DD")
    return raw


def _normalize_pipeline_trigger_source(trigger_source: str) -> str:
    """Map arbitrary ingress labels onto the live pipeline_runs enum surface."""
    raw = (trigger_source or "").strip()
    if raw in _PIPELINE_TRIGGER_SOURCES:
        return raw
    if raw.startswith("github_actions"):
        return "github_actions_scheduled" if "scheduled" in raw else "github_actions_manual"
    logger.warning(
        "Unknown trigger_source '%s' normalized to api_manual for pipeline_runs compatibility",
        raw or "<empty>",
    )
    return "api_manual"


def _spawn_trigger_subprocess(
    *,
    script_path: pathlib.Path,
    trigger_source: str,
    target_date: str,
    service_name: str,
    run_id: str | None = None,
) -> tuple[subprocess.Popen, pathlib.Path]:
    target_date = _validate_target_date_or_empty(target_date)
    env = os.environ.copy()
    env["TRIGGER_SOURCE"] = trigger_source
    if run_id:
        env["PIPELINE_RUN_ID"] = run_id
        env["PIPELINE_SERVICE_NAME"] = service_name

    cmd = [sys.executable, str(script_path)]
    if target_date:
        cmd += ["--date", target_date]

    log_dir = pathlib.Path(__file__).parent.parent / "logs" / "triggers"
    log_dir.mkdir(parents=True, exist_ok=True)
    safe_target = target_date or "today"
    timestamp = utc_now().strftime("%Y%m%dT%H%M%SZ")
    log_path = log_dir / f"{service_name}_{safe_target}_{timestamp}.log"
    log_handle = log_path.open("ab")
    try:
        proc = subprocess.Popen(
            cmd,
            env=env,
            cwd=str(script_path.parent.parent),
            stdout=log_handle,
            stderr=subprocess.STDOUT,
        )
    finally:
        log_handle.close()
    return proc, log_path


def _schema_verification_mode() -> str:
    runtime = (
        settings.API_ENV or os.getenv("API_ENV") or os.getenv("ENV") or os.getenv("RAILWAY_ENVIRONMENT") or "local"
    ).lower()
    if runtime in _SOFT_SCHEMA_RUNTIME_NAMES:
        return "soft"
    return "strict"


def _pipeline_run_api_config() -> tuple[str, str]:
    sb_url = os.getenv("SUPABASE_URL", "").rstrip("/")
    sb_key = (
        os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY", "") or os.getenv("SUPABASE_KEY", "")
    )
    return sb_url, sb_key


def _pipeline_request(method: str, path: str, *, data: dict | None = None) -> tuple[int, bytes]:
    sb_url, sb_key = _pipeline_run_api_config()
    if not sb_url or not sb_key:
        return 0, b"missing Supabase credentials"

    body = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(
        f"{sb_url}/rest/v1/{path}",
        data=body,
        method=method,
        headers={
            "apikey": sb_key,
            "Authorization": f"Bearer {sb_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read() or b""
    except Exception as exc:  # pragma: no cover
        return 0, str(exc).encode()


def _parse_pipeline_rows(payload: bytes) -> list[dict]:
    if not payload:
        return []
    try:
        parsed = json.loads(payload.decode("utf-8"))
    except Exception:
        return []
    return parsed if isinstance(parsed, list) else []


def _parse_iso_utc(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _patch_pipeline_run(run_id: str, patch: dict) -> None:
    status, body = _pipeline_request("PATCH", f"pipeline_runs?id=eq.{run_id}", data=patch)
    if status not in (200, 204):
        raise RuntimeError(f"pipeline_runs patch failed HTTP {status}: {body.decode(errors='replace')[:200]}")


def _write_reject_event(
    *,
    service_name: str,
    source_date: str,
    existing_run_id: str,
    trigger_source: str,
    rejection_reason: str,
) -> None:
    """Durably record a rejected duplicate trigger in trigger_reject_events."""
    row = {
        "event_type": "duplicate_trigger_rejected",
        "service_name": service_name,
        "source_date": source_date,
        "existing_run_id": existing_run_id,
        "incoming_trigger_source": trigger_source,
        "normalized_trigger_source": trigger_source or "unknown",
        "rejection_reason": rejection_reason,
    }
    try:
        status, body = _pipeline_request("POST", "trigger_reject_events", data=row)
        if status not in (200, 201):
            logger.warning(
                "trigger_reject_events write failed HTTP %s for %s/%s: %s",
                status,
                service_name,
                source_date,
                body.decode(errors="replace")[:200],
            )
        else:
            logger.info(
                "trigger_reject_events: recorded duplicate reject for %s/%s run=%s",
                service_name,
                source_date,
                existing_run_id,
            )
    except Exception as exc:
        logger.warning("trigger_reject_events write raised: %s", exc)


def _claim_trigger_run(*, service_name: str, run_type: str, source_date: str, trigger_source: str) -> dict:
    sb_url, sb_key = _pipeline_run_api_config()
    if not sb_url or not sb_key:
        raise HTTPException(status_code=503, detail="Trigger requires durable pipeline_runs access")

    now = utc_now()
    normalized_trigger_source = _normalize_pipeline_trigger_source(trigger_source)
    status, body = _pipeline_request(
        "GET",
        (
            f"pipeline_runs?select=id,started_at,run_state,status"
            f"&service_name=eq.{service_name}&source_date=eq.{source_date}&run_state=eq.running"
            f"&order=started_at.desc&limit=5"
        ),
    )
    if status not in (200, 206):
        raise HTTPException(status_code=503, detail="Unable to verify trigger admission state")

    for row in _parse_pipeline_rows(body):
        started = _parse_iso_utc(row.get("started_at"))
        age_hours = (now - started).total_seconds() / 3600 if started is not None else (_TRIGGER_AGE_GATE_HOURS + 1)
        if age_hours >= _TRIGGER_AGE_GATE_HOURS:
            _patch_pipeline_run(
                row["id"],
                {
                    "run_state": "completed",
                    "status": "FAIL",
                    "finished_at": now.isoformat().replace("+00:00", "Z"),
                    "error_message": f"Closed by trigger age gate ({age_hours:.1f}h stale): superseded by new trigger",
                },
            )
            logger.warning("Trigger age-gate closed stale run %s for %s/%s", row["id"], service_name, source_date)
        else:
            _write_reject_event(
                service_name=service_name,
                source_date=source_date,
                existing_run_id=row["id"],
                trigger_source=normalized_trigger_source,
                rejection_reason=f"run_already_running (age={age_hours:.1f}h)",
            )
            return {
                "status": "duplicate",
                "run_id": row["id"],
                "detail": f"run already running (age={age_hours:.1f}h)",
            }

    run_id = str(uuid.uuid4())
    insert_row = {
        "id": run_id,
        "service_name": service_name,
        "run_type": run_type,
        "source_date": source_date,
        "run_state": "running",
        # Terminal truth only. In-flight rows must keep status NULL until close.
        "status": None,
        "trigger_source": normalized_trigger_source,
        "started_at": now.isoformat().replace("+00:00", "Z"),
        "environment": os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("ENV") or os.getenv("API_ENV") or "production",
        "error_message": None,
    }
    status, body = _pipeline_request("POST", "pipeline_runs", data=insert_row)
    if status in (200, 201):
        return {"status": "created", "run_id": run_id}
    if status in (400, 409):
        dup_status, dup_body = _pipeline_request(
            "GET",
            (
                f"pipeline_runs?select=id,started_at,run_state,status"
                f"&service_name=eq.{service_name}&source_date=eq.{source_date}&run_state=eq.running"
                f"&order=started_at.desc&limit=1"
            ),
        )
        dup_rows = _parse_pipeline_rows(dup_body) if dup_status in (200, 206) else []
        if dup_rows:
            _write_reject_event(
                service_name=service_name,
                source_date=source_date,
                existing_run_id=dup_rows[0]["id"],
                trigger_source=normalized_trigger_source,
                rejection_reason="run_already_running (race condition on insert)",
            )
            return {"status": "duplicate", "run_id": dup_rows[0]["id"], "detail": "run already running"}
    raise HTTPException(status_code=503, detail=f"Unable to claim durable trigger run: HTTP {status}")


# ── Fix 1.2: Schema verification ─────────────────────────────────────────────


async def _verify_schema_at_startup() -> None:
    """
    Fail fast if required tables or columns are absent in Supabase.

    Fatal (raises RuntimeError):
      • race_truth_audits table missing  — truth loop cannot write

    Non-fatal (warning only):
      • shadow_verdicts table missing    — shadow lab optional

    Fatal (raises RuntimeError) if velo_verdicts is reachable but required
    columns are absent:
      • active_components, top_horse_readiness_state,
        race_archetype, g_shadow_multiplier

    Non-fatal (warning only):
      • Supabase env vars missing        — misconfiguration, not schema gap
      • Supabase unreachable             — infra issue, not schema gap
    """
    import urllib.error
    import urllib.request

    sb_url = os.getenv("SUPABASE_URL", "").rstrip("/")
    sb_key = (
        os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY", "") or os.getenv("SUPABASE_KEY", "")
    )

    mode = _schema_verification_mode()
    if not sb_url or not sb_key:
        message = "[startup:schema] SUPABASE_URL or Supabase service key not set"
        if mode == "strict":
            raise RuntimeError(f"{message} — refusing startup because schema truth cannot be verified in live runtime")
        logger.warning("%s — skipping schema verification in soft runtime", message)
        return

    def _sb_get(path: str) -> tuple[int, bytes]:
        """Return (status_code, body) for a Supabase REST GET. Never raises."""
        try:
            req = urllib.request.Request(
                f"{sb_url}/rest/v1/{path}",
                headers={
                    "apikey": sb_key,
                    "Authorization": f"Bearer {sb_key}",
                    "Accept": "application/json",
                },
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                return resp.status, resp.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read() or b""
        except Exception as exc:
            return 0, str(exc).encode()

    errors: list[str] = []

    # ── 1. Required tables (fatal if missing) ─────────────────────────────────
    for table in ("race_truth_audits",):
        status, body = _sb_get(f"{table}?select=id&limit=0")
        if status == 200:
            logger.info("[startup:schema] table %s — PRESENT", table)
        elif status == 0:
            detail = body.decode(errors="replace")
            if mode == "strict":
                errors.append(
                    f"Cannot verify required table '{table}' because Supabase was unreachable: {detail[:200]}"
                )
            else:
                logger.warning(
                    "[startup:schema] Could not reach Supabase to check %s: %s — proceeding in soft runtime",
                    table,
                    detail,
                )
        else:
            msg = body.decode(errors="replace")
            errors.append(f"Required table '{table}' is missing or inaccessible (HTTP {status}): {msg[:200]}")
            logger.error("[startup:schema] MISSING table %s — %s", table, msg[:200])

    # ── 1b. Optional tables (non-fatal if missing) ────────────────────────────
    for table in ("shadow_verdicts",):
        status, body = _sb_get(f"{table}?select=id&limit=0")
        if status == 200:
            logger.info("[startup:schema] optional table %s — PRESENT", table)
        elif status == 0:
            logger.warning(
                "[startup:schema] Could not reach Supabase to check optional table %s: %s",
                table,
                body.decode(errors="replace")[:200],
            )
        else:
            logger.warning(
                "[startup:schema] optional table %s missing or inaccessible (non-fatal) — %s",
                table,
                body.decode(errors="replace")[:200],
            )

    # ── 2. Required columns in velo_verdicts ──────────────────────────────────
    REQUIRED_COLS = "active_components,top_horse_readiness_state,race_archetype,g_shadow_multiplier"
    status, body = _sb_get(f"velo_verdicts?select={REQUIRED_COLS}&limit=1")
    if status == 200:
        logger.info("[startup:schema] velo_verdicts required columns — PRESENT")
    elif status == 0:
        if mode == "strict":
            errors.append(
                f"Cannot verify velo_verdicts required columns because Supabase was unreachable: {body.decode(errors='replace')[:300]}"
            )
        else:
            logger.warning(
                "[startup:schema] Could not reach Supabase to check velo_verdicts columns — proceeding in soft runtime"
            )
    else:
        msg = body.decode(errors="replace")
        # 404 = table missing entirely; 400 = column missing (PostgREST returns details)
        errors.append(
            f"velo_verdicts column check failed (HTTP {status}) — "
            f"run migration to add: {REQUIRED_COLS}. Detail: {msg[:300]}"
        )
        logger.error(
            "[startup:schema] velo_verdicts column check FAILED HTTP %d — %s",
            status,
            msg[:300],
        )

    if errors:
        raise RuntimeError(
            "[startup] Schema verification failed — fix before deploying:\n" + "\n".join(f"  • {e}" for e in errors)
        )

    logger.info("[startup:schema] All required tables and columns verified OK")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load models once at startup, release on shutdown."""
    global _sentient_state

    # ── Fix 1.1: G Shadow mode guard ─────────────────────────────────────────
    # Refuse startup if G shadow is not in safe shadow mode.
    # To promote G to live: VELO_G_SHADOW_MODE=live AND remove this assertion.
    _g_mode = os.getenv("VELO_G_SHADOW_MODE", "shadow").lower()
    if _g_mode == "live":
        raise RuntimeError(
            "[startup] BLOCKED: VELO_G_SHADOW_MODE=live — G shadow multiplier "
            "would apply to all velo_prime_prob values. This is not approved for "
            "live control. Set VELO_G_SHADOW_MODE=shadow to proceed."
        )
    logger.info("[startup] G shadow mode: %s (safe)", _g_mode)

    # ── Fix 1.2: Migration / schema verification ──────────────────────────────
    # Fail fast if required columns or tables are absent.
    # Missing columns → truth loop writes incomplete rows → learning corrupted.
    await _verify_schema_at_startup()

    from app.services.model_manager import get_model_manager

    mm = get_model_manager()
    logger.info(f"Models initialised at startup: {mm.model_versions}")

    # Sentient bridge — Phase 1 (audit only, no scoring change)
    try:
        from app.playbooks.playbook_g_sentient_loopback import SentientLoopbackEngine

        _g = SentientLoopbackEngine()
        _raw = _g.get_evolutionary_state()
        _source = "disk" if _raw.get("total_races_observed", 0) > 0 else "unknown"
        _sentient_state = {**_raw, "_source": _source}
        logger.info(
            "[sentient] G state loaded at startup — source=%s races_observed=%d aggression=%.3f",
            _source,
            _raw.get("total_races_observed", 0),
            _raw.get("appetite_state", {}).get("aggression_level", -1.0),
        )
    except Exception as e:
        _sentient_state = None
        logger.warning("[sentient] G state load failed at startup (non-fatal): %s", e)

    # ── Security hardening validator ─────────────────────────────────────────
    # Permanent guard against DB security regression.
    # Runs on every startup. Logs CRITICAL if hardening has been lost.
    # Non-fatal: app continues to run but operator is alerted immediately.
    # If regression is detected, run: scripts/migrations/002_full_security_hardening.sql
    try:
        from app.services.security_validator import run_security_check

        _sec = run_security_check()
        if _sec.get("status") == "failed":
            logger.critical(
                "[startup] ❌ SECURITY REGRESSION DETECTED — "
                "Run scripts/migrations/002_full_security_hardening.sql immediately. "
                "tables_rls_disabled=%d views_not_invoker=%d "
                "functions_mutable_search_path=%d matviews_exposed=%d",
                _sec.get("tables_rls_disabled", -1),
                _sec.get("views_not_invoker", -1),
                _sec.get("functions_mutable_search_path", -1),
                _sec.get("matviews_exposed", -1),
            )
        elif _sec.get("status") == "partial":
            logger.warning(
                "[startup] SECURITY VALIDATION PARTIAL — checked=%s unchecked=%s detail=%s",
                _sec.get("checked_objects"),
                _sec.get("unchecked_objects"),
                _sec.get("error_detail"),
            )
        elif _sec.get("status") == "skipped":
            logger.info(
                "[startup] Security check skipped — %s",
                _sec.get("error_detail"),
            )
        elif not _sec.get("verified"):
            logger.critical(
                "[startup] SECURITY VERIFICATION INCOMPLETE - "
                "database hardening could not be verified. "
                "status=%s error_code=%s detail=%s",
                _sec.get("status"),
                _sec.get("error_code"),
                _sec.get("error_detail"),
            )
    except Exception as _sec_err:
        logger.warning("[startup] Security validator failed to load (non-fatal): %s", _sec_err)

    # Register Telegram webhook so velo_agent_bot can receive messages
    _register_webhook()

    yield
    logger.info("VÉLØ Oracle API shutting down")


# Create FastAPI app
app = FastAPI(
    title="VÉLØ Oracle API",
    version="v1.0",
    description="Production horse racing prediction engine",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS Middleware - CRITICAL for Cloudflare Worker
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=["*"],  # Allow all methods (GET, POST, OPTIONS, etc.)
    allow_headers=["*"],  # Allow all headers
)

# Import and include routers
try:
    from app.routers.features import router as features_router
    from app.routers.monitoring import router as monitoring_router

    app.include_router(features_router, prefix="/features", tags=["features"])
    app.include_router(monitoring_router, prefix="/monitoring", tags=["monitoring"])
    logger.info("✅ Feast Feature Store and Evidently Monitoring routers loaded")
except ImportError as e:
    logger.warning(f"⚠️  Feature/Monitoring routers not available: {e}")

# Static files — Governed Card Dashboard
_STATIC_DIR = pathlib.Path(__file__).parent / "static"
if _STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

# Environment
ENV = settings.API_ENV
API_KEY = os.getenv("API_KEY", "")


# API Key validation
async def verify_api_key(x_api_key: str = Header(None)):
    """Verify API key from header"""
    if not API_KEY:
        # API_KEY env var not set — refuse all requests rather than silently bypass
        logger.warning("API_KEY not configured — rejecting request")
        raise HTTPException(status_code=503, detail="API key not configured on this server")

    if not _secrets_match(x_api_key, API_KEY):
        raise HTTPException(status_code=403, detail="Invalid API key")

    return True


# Health check endpoint - CRITICAL for Railway
@app.get("/health")
async def health_check():
    """
    Real health check — fails if DB unreachable or last scoring run is stale.
    Returns HTTP 503 on any critical failure so Railway detects the problem.
    """
    import json as _json
    import os as _os
    import urllib.error
    import urllib.request

    issues = []
    details: dict = {
        "app": "VÉLØ Oracle",
        "version": "v1.0",
        "environment": ENV,
        "timestamp": utc_now_iso(),
    }

    # ── 1. Supabase reachability ──────────────────────────────────────────────
    sb_url = _os.getenv("SUPABASE_URL", "")
    sb_key = (
        _os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        or _os.getenv("SUPABASE_SERVICE_KEY", "")
        or _os.getenv("SUPABASE_KEY", "")
    )
    if not sb_url or not sb_key:
        issues.append("SUPABASE_URL or Supabase service key env vars missing")
        details["db"] = "UNCONFIGURED"
    else:
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
                details["db"] = "REACHABLE"
        except Exception as e:
            issues.append(f"Supabase unreachable: {e}")
            details["db"] = "UNREACHABLE"

    # ── 2. Last successful scoring run freshness (must be < 26 hours ago) ────
    STALE_HOURS = 26
    if sb_url and sb_key and "UNREACHABLE" not in details.get("db", ""):
        try:
            req = urllib.request.Request(
                f"{sb_url}/rest/v1/pipeline_runs?select=started_at,status&status=eq.PASS&order=started_at.desc&limit=1",
                headers={
                    "apikey": sb_key,
                    "Authorization": f"Bearer {sb_key}",
                    "Accept": "application/json",
                    "Prefer": "",
                },
            )
            with urllib.request.urlopen(req, timeout=5) as r:
                rows = _json.loads(r.read())
            if not rows:
                issues.append("No PASS pipeline_run found — scoring may never have run successfully")
                details["last_scoring_run"] = "NEVER"
            else:
                last_ts_str = rows[0].get("started_at", "")
                if last_ts_str:
                    # Accept ISO strings with or without trailing Z
                    # Strip timezone info to compare as naive UTC
                    last_ts = datetime.fromisoformat(last_ts_str.rstrip("Z"))
                    if last_ts.tzinfo is None:
                        last_ts = last_ts.replace(tzinfo=UTC)
                    age_hours = (utc_now() - last_ts).total_seconds() / 3600
                    details["last_scoring_run"] = f"{age_hours:.1f}h ago"
                    if age_hours > STALE_HOURS:
                        issues.append(f"Last PASS scoring run is {age_hours:.1f}h ago (threshold: {STALE_HOURS}h)")
                        details["last_scoring_run_status"] = "STALE"
                    else:
                        details["last_scoring_run_status"] = "FRESH"
        except Exception as e:
            issues.append(f"Could not check last scoring run: {e}")
            details["last_scoring_run"] = "UNKNOWN"

    # ── 3. Model artifact present and loadable ───────────────────────────────
    # Mirrors model_manager.load_sqpe() exactly: sqpe_v17 first, sqpe_v16 fallback.
    # File existence is not enough — a corrupt pickle must also fail this check.
    import pathlib as _pathlib

    import joblib as _joblib

    _model_root = _pathlib.Path(__file__).parent.parent / "models"
    _sqpe_candidates = [
        _model_root / "sqpe_v17" / "sqpe_v17.pkl",
        _model_root / "sqpe_v16" / "sqpe_v16.pkl",
    ]
    _sqpe_found = None
    for _p in _sqpe_candidates:
        if _p.exists():
            _sqpe_found = _p
            break
    if _sqpe_found is None:
        issues.append(
            f"SQPE model artifact missing — checked: "
            f"{[str(p.relative_to(_model_root.parent)) for p in _sqpe_candidates]}"
        )
        details["sqpe_model"] = "MISSING"
    else:
        try:
            _joblib.load(_sqpe_found)
            details["sqpe_model"] = f"LOADED ({_sqpe_found.name})"
        except Exception as _e:
            issues.append(f"SQPE model load failed ({_sqpe_found.name}): {_e}")
            details["sqpe_model"] = "CORRUPT"

    # ── Result ───────────────────────────────────────────────────────────────
    # Critical failures (503): DB unreachable, model missing/corrupt.
    # Warnings (200): stale scoring run, unknown last run — service is up but degraded.
    critical_keywords = ("Supabase unreachable", "SUPABASE_URL", "SQPE model")
    critical_issues = [i for i in issues if any(k in i for k in critical_keywords)]
    warning_issues = [i for i in issues if i not in critical_issues]

    if critical_issues:
        details["status"] = "FAIL"
        details["issues"] = issues
        return JSONResponse(status_code=503, content=details)

    if warning_issues:
        details["status"] = "DEGRADED"
        details["issues"] = warning_issues
        return JSONResponse(status_code=200, content=details)

    details["status"] = "healthy"
    return details


# ── Scoring trigger — called by GitHub Actions scheduler ─────────────────────
@app.post("/api/trigger/score-daily", status_code=202)
async def trigger_score_daily(request: Request, x_trigger_secret: str = Header(None)):
    """
    Trigger daily scoring run from an external scheduler (GitHub Actions).
    Returns 202 immediately — scoring runs as a background subprocess.

    Required header: X-Trigger-Secret matching TRIGGER_SCORE_SECRET env var.
    Optional JSON body: {"trigger_source": "...", "target_date": "YYYY-MM-DD"}
    """
    trigger_secret = os.getenv("TRIGGER_SCORE_SECRET", "")
    if not trigger_secret:
        logger.error("TRIGGER_SCORE_SECRET not configured — trigger endpoint disabled")
        raise HTTPException(status_code=503, detail="Trigger not configured on this server")
    if not _secrets_match(x_trigger_secret, trigger_secret):
        logger.warning("Trigger attempt with invalid secret")
        raise HTTPException(status_code=401, detail="Invalid trigger secret")

    body: dict = {}
    try:
        body = await request.json()
    except Exception:
        pass

    trigger_source = body.get("trigger_source") or "api_manual"
    target_date = _validate_target_date_or_empty(body.get("target_date"))

    source_date = target_date or utc_now().strftime("%Y-%m-%d")
    script_path = pathlib.Path(__file__).parent.parent / "scripts" / "ops" / "run_prime_today.py"
    if not script_path.exists():
        raise HTTPException(status_code=500, detail=f"Scoring script not found: {script_path}")

    claim = _claim_trigger_run(
        service_name=_TRIGGER_SERVICE_CONFIG["score_daily"]["service_name"],
        run_type=_TRIGGER_SERVICE_CONFIG["score_daily"]["run_type"],
        source_date=source_date,
        trigger_source=trigger_source,
    )
    if claim["status"] == "duplicate":
        return JSONResponse(
            status_code=409,
            content={
                "status": "already_running",
                "service": "score-daily",
                "trigger_source": trigger_source,
                "target_date": source_date,
                "run_id": claim["run_id"],
                "detail": claim.get("detail"),
            },
        )

    run_id = claim["run_id"]
    try:
        proc, log_path = _spawn_trigger_subprocess(
            script_path=script_path,
            trigger_source=trigger_source,
            target_date=target_date,
            service_name="score_daily",
            run_id=run_id,
        )
    except Exception as exc:
        _patch_pipeline_run(
            run_id,
            {
                "run_state": "completed",
                "status": "FAIL",
                "finished_at": utc_now_iso(),
                "error_message": f"trigger spawn failed: {exc}",
            },
        )
        raise

    logger.info(
        "Scoring triggered — source=%s pid=%d target_date=%s log=%s",
        trigger_source,
        proc.pid,
        target_date or "today",
        log_path,
    )

    return JSONResponse(
        status_code=202,
        content={
            "status": "triggered",
            "service": "score-daily",
            "trigger_source": trigger_source,
            "target_date": source_date,
            "run_id": run_id,
            "pid": proc.pid,
            "log_path": str(log_path),
        },
    )


# ── Sigma trigger — called by GitHub Actions at 21:00 UTC ────────────────────
# /api/trigger/sigma      → run_results_sigma.py  (lightweight stdlib reconciliation)
# /api/trigger/sigma-daily → close_sigma_loops.py (full reconciliation + Zep + G feed)
@app.post("/api/trigger/sigma", status_code=202)
async def trigger_sigma(request: Request, x_trigger_secret: str = Header(None)):
    """
    Trigger sigma reconciliation via run_results_sigma.py.
    Returns 202 immediately — sigma runs as a background subprocess.

    Required header: X-Trigger-Secret matching TRIGGER_SCORE_SECRET env var.
    Optional JSON body: {"trigger_source": "...", "target_date": "YYYY-MM-DD"}
    """
    trigger_secret = os.getenv("TRIGGER_SCORE_SECRET", "")
    if not trigger_secret:
        logger.error("TRIGGER_SCORE_SECRET not configured — sigma trigger disabled")
        raise HTTPException(status_code=503, detail="Trigger not configured on this server")
    if not _secrets_match(x_trigger_secret, trigger_secret):
        logger.warning("Sigma trigger attempt with invalid secret")
        raise HTTPException(status_code=401, detail="Invalid trigger secret")

    body: dict = {}
    try:
        body = await request.json()
    except Exception:
        pass

    trigger_source = body.get("trigger_source") or "api_manual"
    target_date = _validate_target_date_or_empty(body.get("target_date"))

    source_date = target_date or utc_now().strftime("%Y-%m-%d")
    script_path = pathlib.Path(__file__).parent.parent / "scripts" / "run_results_sigma.py"
    if not script_path.exists():
        raise HTTPException(status_code=500, detail=f"Sigma script not found: {script_path}")

    claim = _claim_trigger_run(
        service_name=_TRIGGER_SERVICE_CONFIG["sigma"]["service_name"],
        run_type=_TRIGGER_SERVICE_CONFIG["sigma"]["run_type"],
        source_date=source_date,
        trigger_source=trigger_source,
    )
    if claim["status"] == "duplicate":
        return JSONResponse(
            status_code=409,
            content={
                "status": "already_running",
                "service": "sigma",
                "trigger_source": trigger_source,
                "target_date": source_date,
                "run_id": claim["run_id"],
                "detail": claim.get("detail"),
            },
        )
    run_id = claim["run_id"]
    try:
        proc, log_path = _spawn_trigger_subprocess(
            script_path=script_path,
            trigger_source=trigger_source,
            target_date=target_date,
            service_name="sigma",
            run_id=run_id,
        )
    except Exception as exc:
        _patch_pipeline_run(
            run_id,
            {
                "run_state": "completed",
                "status": "FAIL",
                "finished_at": utc_now_iso(),
                "error_message": f"trigger spawn failed: {exc}",
            },
        )
        raise

    logger.info(
        "Sigma triggered — source=%s pid=%d target_date=%s log=%s",
        trigger_source,
        proc.pid,
        target_date or "today",
        log_path,
    )

    return JSONResponse(
        status_code=202,
        content={
            "status": "triggered",
            "service": "sigma",
            "trigger_source": trigger_source,
            "target_date": source_date,
            "run_id": run_id,
            "pid": proc.pid,
            "log_path": str(log_path),
        },
    )


@app.post("/api/trigger/sigma-daily", status_code=202)
async def trigger_sigma_daily(request: Request, x_trigger_secret: str = Header(None)):
    """
    Trigger full sigma reconciliation via close_sigma_loops.py.
    Writes race_results, runner_results, velo_post_race_reviews, sigma_audits,
    learned_patterns, Playbook G doctrine feed, Zep graph memory.
    Returns 202 immediately — sigma runs as a background subprocess.

    Required header: X-Trigger-Secret matching TRIGGER_SCORE_SECRET env var.
    Optional JSON body: {"trigger_source": "...", "target_date": "YYYY-MM-DD"}
    """
    trigger_secret = os.getenv("TRIGGER_SCORE_SECRET", "")
    if not trigger_secret:
        logger.error("TRIGGER_SCORE_SECRET not configured — sigma trigger endpoint disabled")
        raise HTTPException(status_code=503, detail="Trigger not configured on this server")
    if not _secrets_match(x_trigger_secret, trigger_secret):
        logger.warning("Sigma trigger attempt with invalid secret")
        raise HTTPException(status_code=401, detail="Invalid trigger secret")

    body: dict = {}
    try:
        body = await request.json()
    except Exception:
        pass

    trigger_source = body.get("trigger_source") or "api_manual"
    target_date = _validate_target_date_or_empty(body.get("target_date"))

    source_date = target_date or utc_now().strftime("%Y-%m-%d")
    script_path = pathlib.Path(__file__).parent.parent / "scripts" / "close_sigma_loops.py"
    if not script_path.exists():
        raise HTTPException(status_code=500, detail=f"Sigma script not found: {script_path}")

    claim = _claim_trigger_run(
        service_name=_TRIGGER_SERVICE_CONFIG["sigma_daily"]["service_name"],
        run_type=_TRIGGER_SERVICE_CONFIG["sigma_daily"]["run_type"],
        source_date=source_date,
        trigger_source=trigger_source,
    )
    if claim["status"] == "duplicate":
        return JSONResponse(
            status_code=409,
            content={
                "status": "already_running",
                "service": "sigma-daily",
                "trigger_source": trigger_source,
                "target_date": source_date,
                "run_id": claim["run_id"],
                "detail": claim.get("detail"),
            },
        )
    run_id = claim["run_id"]
    try:
        proc, log_path = _spawn_trigger_subprocess(
            script_path=script_path,
            trigger_source=trigger_source,
            target_date=target_date,
            service_name="sigma_daily",
            run_id=run_id,
        )
    except Exception as exc:
        _patch_pipeline_run(
            run_id,
            {
                "run_state": "completed",
                "status": "FAIL",
                "finished_at": utc_now_iso(),
                "error_message": f"trigger spawn failed: {exc}",
            },
        )
        raise

    logger.info(
        "Sigma reconciliation triggered — source=%s pid=%d target_date=%s log=%s",
        trigger_source,
        proc.pid,
        target_date or "today",
        log_path,
    )

    return JSONResponse(
        status_code=202,
        content={
            "status": "triggered",
            "service": "sigma-daily",
            "trigger_source": trigger_source,
            "target_date": source_date,
            "run_id": run_id,
            "pid": proc.pid,
            "log_path": str(log_path),
        },
    )


# ── Spotlight PDF Upload ──────────────────────────────────────────────────────


@app.post("/api/upload/spotlight", status_code=202)
async def upload_spotlight_pdf(
    file: UploadFile = File(...),
    x_trigger_secret: str = Header(None),
):
    """
    Upload a Racing Post Spotlight PDF (F_0016_XX) for NLP parsing.
    The PDF is saved to data/incoming_pdfs/ and parsed immediately.
    Returns parsed horse count and NLP summary.

    Required header: X-Trigger-Secret matching TRIGGER_SCORE_SECRET env var.
    """
    trigger_secret = os.getenv("TRIGGER_SCORE_SECRET", "")
    if trigger_secret and not _secrets_match(x_trigger_secret, trigger_secret):
        raise HTTPException(status_code=401, detail="Invalid trigger secret")

    if not file.filename or not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF")

    # Save to incoming_pdfs
    incoming_dir = pathlib.Path(__file__).parent.parent / "data" / "incoming_pdfs"
    incoming_dir.mkdir(parents=True, exist_ok=True)
    dest = incoming_dir / file.filename
    content = await file.read()
    dest.write_bytes(content)
    logger.info(f"Spotlight PDF saved: {dest} ({len(content)} bytes)")

    # Parse in background
    script_path = pathlib.Path(__file__).parent.parent / "scripts" / "ingest_spotlight_pdf.py"
    if script_path.exists():
        proc = subprocess.Popen(
            [sys.executable, str(script_path), "--pdf", str(dest)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        logger.info(f"Spotlight parse triggered: pid={proc.pid}")
        return {
            "status": "accepted",
            "filename": file.filename,
            "size_bytes": len(content),
            "parse_pid": proc.pid,
            "message": "PDF saved and parse triggered. Check data/spotlight_parsed/ for output.",
        }
    else:
        return {
            "status": "saved_only",
            "filename": file.filename,
            "size_bytes": len(content),
            "message": "PDF saved but ingest_spotlight_pdf.py not found. Manual parse required.",
        }


# ── Governed Card Dashboard ───────────────────────────────────────────────────


@app.get("/dashboard", include_in_schema=False)
async def dashboard():
    """Serve the Governed Card Dashboard UI."""
    html_path = pathlib.Path(__file__).parent / "static" / "dashboard" / "index.html"
    if not html_path.exists():
        raise HTTPException(status_code=404, detail="Dashboard not found")
    return FileResponse(str(html_path), media_type="text/html")


@app.get("/api/governed-card")
async def governed_card(date: str = Query(default=None), allow_fallback: bool = Query(default=False)):
    """
    Return governed card for a given date.

    Primary source: local velo_prime_verdicts_YYYY_MM_DD.json (has course/horse/off_time).
    Governance overlay: velo_verdicts Supabase table (assigned_product, router_reasons,
    execution_allowed) — merged by race_id where available.
    Falls back gracefully when either source is missing.
    """
    import csv as _csv
    import json as _json
    import subprocess as _sp

    # Date resolution — try today in UTC, fall back to most recent local file
    target_date = date or utc_now().strftime("%Y-%m-%d")
    date_tag = target_date.replace("-", "_")
    root = pathlib.Path(__file__).parent.parent

    def _norm_name(value: str) -> str:
        return (value or "").upper().split("(")[0].strip()

    def _norm_time(value: str) -> str:
        return (value or "").replace(".", ":").strip()

    def _norm_course(value: str) -> str:
        return (value or "").upper().split("(")[0].strip()

    def _load_local_racecard_meta(date_value: str) -> dict[str, dict]:
        """
        Best-effort local metadata fallback for same-day dashboard rendering.

        Some exact-date Supabase verdict rows are flat and omit course/off_time.
        When that happens, resolve by unique horse name from local merged RP cards.
        """
        meta_by_horse: dict[str, dict] = {}
        duplicate_names: set[str] = set()
        for path in sorted((root / "data" / "racecard_merged").glob(f"*{date_value}*.json")):
            try:
                payload = _json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            venue = payload.get("venue") or path.stem.split("_")[1] if isinstance(payload, dict) else ""
            races = payload.get("races") if isinstance(payload, dict) else None
            if not isinstance(races, dict):
                continue
            for race_time, race_blob in races.items():
                if not isinstance(race_blob, dict):
                    continue
                # Keep race titles honest: RP race_info is distance/class metadata,
                # not a true race name, so do not surface it as the dashboard title.
                race_name = race_blob.get("race_name") or ""
                for horse in race_blob.get("horses") or []:
                    if not isinstance(horse, dict):
                        continue
                    horse_name = horse.get("horse_name") or horse.get("horse") or ""
                    key = _norm_name(horse_name)
                    if not key:
                        continue
                    candidate = {
                        "course": horse.get("course") or venue,
                        "off_time": horse.get("race_time") or race_time,
                        "race_name": race_name,
                        "trainer": horse.get("trainer") or "",
                        "jockey": horse.get("jockey") or "",
                    }
                    if key in meta_by_horse:
                        duplicate_names.add(key)
                    else:
                        meta_by_horse[key] = candidate
        for key in duplicate_names:
            meta_by_horse.pop(key, None)
        return meta_by_horse

    cashrun_path = root / "data" / f"cashrun_report_{date_tag}.csv"
    cashrun_rows: list[dict] = []
    cashrun_by_key: dict[tuple[str, str, str], dict] = {}
    cashrun_by_horse: dict[str, dict] = {}
    cashrun_duplicate_horses: set[str] = set()
    cashrun_loaded_date = None
    cashrun_status = "MISSING"
    cashrun_counts = {
        "ready": 0,
        "watch": 0,
        "weak": 0,
        "suppress": 0,
    }
    if cashrun_path.exists():
        try:
            with cashrun_path.open("r", encoding="utf-8") as f:
                reader = _csv.DictReader(f)
                cashrun_rows = list(reader)
            cashrun_loaded_date = target_date
            cashrun_status = "PRESENT"
            for row in cashrun_rows:
                key = (
                    _norm_course(row.get("course", "")),
                    _norm_time(row.get("off_time", "")),
                    _norm_name(row.get("horse", "")),
                )
                if all(key):
                    cashrun_by_key[key] = row
                horse_key = _norm_name(row.get("horse", ""))
                if horse_key:
                    if horse_key in cashrun_by_horse:
                        cashrun_duplicate_horses.add(horse_key)
                    else:
                        cashrun_by_horse[horse_key] = row
                klass = (row.get("cashrun_class") or "").upper()
                if klass == "CASHRUN_READY":
                    cashrun_counts["ready"] += 1
                elif klass == "CASHRUN_WATCH":
                    cashrun_counts["watch"] += 1
                elif klass == "WEAK_SIGNAL":
                    cashrun_counts["weak"] += 1
                elif klass == "SUPPRESS":
                    cashrun_counts["suppress"] += 1
        except Exception as e:
            logger.warning("Could not read cashrun report %s: %s", cashrun_path, e)
            cashrun_status = "ERROR"
            cashrun_rows = []
            cashrun_by_key = {}
            cashrun_by_horse = {}
    for horse_key in cashrun_duplicate_horses:
        cashrun_by_horse.pop(horse_key, None)

    # ── Source 1: local verdict JSON ─────────────────────────────────────────
    verdict_path = root / "data" / f"velo_prime_verdicts_{date_tag}.json"
    if not verdict_path.exists():
        try:
            from sync_verdicts_from_supabase import sync_local_verdict_archive as _sync_local_verdict_archive

            sync_result = _sync_local_verdict_archive(target_date)
            if sync_result.get("status") == "LOCAL_HYDRATED":
                logger.info("Hydrated local verdict archive for %s via Supabase sync", target_date)
        except Exception as e:
            logger.warning("Local verdict archive hydration failed for %s: %s", target_date, e)

    # Never cross-date fallback to a different local verdict file.
    source_label = "local_json_exact"
    loaded_date = target_date

    raw_verdicts = []
    if verdict_path and verdict_path.exists():
        try:
            payload = _json.loads(verdict_path.read_text())
            if isinstance(payload, dict):
                raw_verdicts = payload.get("verdicts") or payload.get("rows") or []
            elif isinstance(payload, list):
                raw_verdicts = payload
            else:
                raw_verdicts = []
        except Exception as e:
            logger.warning("Could not read verdict file %s: %s", verdict_path, e)

    # ── Source 2: Supabase governance overlay ────────────────────────────────
    gov_by_race: dict = {}
    sb_verdict_rows: list[dict] = []
    sb_url = resolve_supabase_url()
    sb_key = resolve_supabase_service_key()
    db = None
    if sb_url and sb_key:
        try:
            from supabase import create_client as _sb_create

            db = _sb_create(sb_url, sb_key)
            resp = (
                db.table("velo_verdicts")
                .select(
                    "race_id, generated_at, decision_tier, velo_prime_prob, "
                    "market_deception_score, improvement_score, place_prob, "
                    "execution_allowed, assigned_product, router_reasons, full_analysis"
                )
                .gte("generated_at", f"{target_date}T00:00:00")
                .lt("generated_at", f"{target_date}T23:59:59")
                .execute()
            )
            sb_verdict_rows = resp.data or []
            for row in sb_verdict_rows:
                gov_by_race[row["race_id"]] = row
        except Exception as e:
            logger.warning("Supabase query failed: %s", e)

    if (not raw_verdicts or loaded_date != target_date) and sb_verdict_rows:
        raw_verdicts = sb_verdict_rows
        loaded_date = target_date
        source_label = "supabase_verdicts_exact"

    fallback_date = None
    fallback_path = None
    if not raw_verdicts:
        candidates = sorted(root.glob("data/velo_prime_verdicts_*.json"), reverse=True)
        fallback_path = candidates[0] if candidates else None
        if fallback_path:
            fallback_date = fallback_path.stem.replace("velo_prime_verdicts_", "").replace("_", "-")

    if not raw_verdicts and allow_fallback and fallback_path:
        try:
            fallback_payload = _json.loads(fallback_path.read_text())
            if isinstance(fallback_payload, dict):
                raw_verdicts = fallback_payload.get("verdicts") or fallback_payload.get("rows") or []
            elif isinstance(fallback_payload, list):
                raw_verdicts = fallback_payload
            else:
                raw_verdicts = []
            loaded_date = fallback_date or target_date
            source_label = "local_json_fallback"
        except Exception as e:
            logger.warning("Could not read fallback verdict file %s: %s", fallback_path, e)

    sidecar_loaded_date = None
    sidecar_status = "MISSING"
    sidecar_date_match = False
    sidecar_metadata_coverage = 0.0
    sidecar_path = root / "app" / "static" / "dashboard" / "sidecar_stack_latest.json"
    if sidecar_path.exists():
        try:
            sidecar_payload = _json.loads(sidecar_path.read_text())
            sidecar_loaded_date = sidecar_payload.get("date")
            sidecar_status = sidecar_payload.get("status", "UNKNOWN")
            sidecar_date_match = sidecar_loaded_date == target_date
            seen = set()
            rows = []
            for stack_rows in (sidecar_payload.get("stacks") or {}).values():
                for row in stack_rows or []:
                    key = (row.get("race_id"), row.get("horse_id") or row.get("horse"))
                    if key in seen:
                        continue
                    seen.add(key)
                    rows.append(row)
            if rows:
                complete = sum(1 for row in rows if row.get("metadata_complete"))
                sidecar_metadata_coverage = round(complete / len(rows), 4)
        except Exception as e:
            logger.warning("Could not read sidecar stack file %s: %s", sidecar_path, e)

    if not raw_verdicts:
        return {
            "meta": {
                "status": "FAIL_DATE_MISMATCH",
                "requested_date": target_date,
                "loaded_date": fallback_date,
                "source": None,
                "message": "Requested date data not available. Refusing stale fallback.",
                "allow_fallback": allow_fallback,
                "date_match": False,
                "stale_data_blocked": True,
                "governed_card_loaded_date": None,
                "governed_card_status": "FAIL_DATE_MISMATCH",
                "sidecar_loaded_date": sidecar_loaded_date,
                "sidecar_status": sidecar_status,
                "sidecar_date_match": sidecar_date_match,
                "cashrun_loaded_date": cashrun_loaded_date,
                "cashrun_status": cashrun_status,
                "cashrun_counts": cashrun_counts,
                "metadata_coverage": sidecar_metadata_coverage,
                "record_count": 0,
                "gov_overlay": len(gov_by_race) > 0,
                "exact_date_file_present": verdict_path.exists(),
            },
            "cashrun": {
                "status": cashrun_status,
                "loaded_date": cashrun_loaded_date,
                "counts": cashrun_counts,
                "rows": cashrun_rows,
            },
            "verdicts": [],
        }

    # ── Merge & shape verdicts ────────────────────────────────────────────────
    verdict_map = {}
    for row in raw_verdicts:
        rid = row.get("race_id", "")
        if not rid:
            continue
        fa = row.get("full_analysis") or []
        verdict_map[rid] = fa if isinstance(fa, list) else []

    meta_map = {}
    if raw_verdicts and db:
        try:
            from src.velo.race_metadata_resolver import RaceMetadataResolver

            resolver = RaceMetadataResolver(date=target_date, sb_client=db)
            race_ids = [row.get("race_id", "") for row in raw_verdicts if row.get("race_id")]
            meta_map = resolver.resolve_batch(race_ids, verdict_map)
        except Exception as e:
            logger.warning("Race metadata resolver failed: %s", e)
    local_meta_by_horse = _load_local_racecard_meta(target_date)

    router = None
    try:
        from src.velo.product_router import ProductRouter

        router = ProductRouter()
    except Exception as e:
        logger.warning("Product router display fallback unavailable: %s", e)

    def _safe_float(value, default: float = 0.0) -> float:
        try:
            return float(value)
        except Exception:
            return default

    def _derive_prob_gap(row_prob: float, analysis: list) -> float:
        if isinstance(analysis, list):
            probs = sorted(
                [
                    _safe_float(item.get("velo_prime_prob"))
                    for item in analysis
                    if isinstance(item, dict) and item.get("velo_prime_prob") is not None
                ],
                reverse=True,
            )
            if len(probs) >= 2:
                return max(probs[0] - probs[1], 0.0)
            if len(probs) == 1:
                return probs[0]
        return row_prob

    def _derive_fav_sp(analysis: list) -> float:
        if not isinstance(analysis, list):
            return 0.0
        sp_vals = sorted(
            [
                _safe_float(
                    item.get("sp_dec") or item.get("sp_decimal") or item.get("market_odds"),
                    0.0,
                )
                for item in analysis
                if isinstance(item, dict)
            ]
        )
        return next((val for val in sp_vals if val > 0), 0.0)

    def _operator_read_profile(tier: str, prob: float) -> tuple[str, list[str]]:
        flags: list[str] = []
        if tier != "A":
            flags.append("NON_A_TIER")
        if prob < 0.30:
            flags.append("SUB_VP30")
        if tier in {"C", "D", "X"}:
            flags.append("LOW_QUALITY_TIER")
        if prob < 0.20:
            flags.append("VERY_LOW_VP")

        if tier == "A" and prob >= 0.30:
            return "CORE_FOCUS", flags
        if tier == "B" and prob >= 0.30:
            return "SECONDARY_FOCUS", flags
        if tier in {"A", "B"} and prob >= 0.20:
            return "WATCH_SKEPTICAL", flags
        return "LOW_QUALITY_SKEPTICAL", flags

    verdicts = []
    for v in raw_verdicts:
        race_id = v.get("race_id", "")
        full_analysis = v.get("full_analysis") or []
        top = v.get("top", {})
        if not top and isinstance(full_analysis, list) and full_analysis and isinstance(full_analysis[0], dict):
            top = full_analysis[0]
        horse_name = top.get("horse") or v.get("horse") or v.get("horse_name") or ""

        top_prob = _safe_float(v.get("velo_prime_prob", top.get("velo_prime_prob", 0)))
        prob_gap = (
            _safe_float(top.get("prob_gap"))
            if top.get("prob_gap") is not None
            else _derive_prob_gap(top_prob, full_analysis)
        )

        # Governance: prefer live Supabase values (post-migration), fall back to top dict
        gov = gov_by_race.get(race_id, {})
        assigned_product = gov.get("assigned_product") or v.get("assigned_product") or top.get("assigned_product")
        router_reasons = gov.get("router_reasons") or v.get("router_reasons") or top.get("router_reasons") or []
        execution_allowed = gov.get("execution_allowed")
        if execution_allowed is None:
            execution_allowed = v.get("execution_allowed")
        if execution_allowed is None:
            execution_allowed = top.get("execution_allowed")
        assigned_product_source = (
            "supabase_governance"
            if gov.get("assigned_product")
            else "verdict_row"
            if v.get("assigned_product")
            else "verdict_top"
            if top.get("assigned_product")
            else "unresolved"
        )
        meta = meta_map.get(race_id)
        local_meta = local_meta_by_horse.get(_norm_name(horse_name), {})
        course = (
            v.get("course", "")
            or top.get("course", "")
            or (meta.course if meta else "")
            or local_meta.get("course", "")
        )
        off_time = (
            v.get("off_time", "")
            or v.get("race_time", "")
            or top.get("off_time", "")
            or top.get("race_time", "")
            or (meta.off_time if meta else "")
            or local_meta.get("off_time", "")
        )
        race_name = (
            v.get("race_name", "")
            or top.get("race_name", "")
            or (meta.race_name if meta else "")
            or local_meta.get("race_name", "")
        )
        tier = v.get("decision_tier") or v.get("tier", "?")
        cashrun_match = cashrun_by_key.get(
            (
                _norm_course(course),
                _norm_time(off_time),
                _norm_name(horse_name),
            )
        )
        if not cashrun_match:
            cashrun_match = cashrun_by_horse.get(_norm_name(horse_name))

        if router and (not assigned_product or execution_allowed is None or not router_reasons):
            route_data = {
                "decision_tier": tier,
                "confidence_level": top.get("confidence_level", "low"),
                # Same-day persisted verdict rows do not always carry SP yet.
                # Keep the router honest by leaving missing price fields at 0.0
                # rather than fabricating a market price.
                "actual_winner_sp": _safe_float(top.get("sp_dec") or top.get("sp_decimal"), 0.0),
                "prob_gap": prob_gap,
                "track": course,
                "top_horse_draw": top.get("draw"),
                "market_deception_score": _safe_float(
                    v.get("market_deception_score", top.get("market_deception_score", 0))
                ),
                "field_size": len(full_analysis) if isinstance(full_analysis, list) else 0,
                "race_type": top.get("race_type") or top.get("type") or "?",
                "going": top.get("going") or "?",
                "is_handicap": bool(top.get("is_handicap") or False),
                "fav_sp": _derive_fav_sp(full_analysis),
                "velo_prime_prob": top_prob,
                "archetype": top.get("race_archetype") or top.get("archetype") or "?",
            }
            routed = router.route_verdict(route_data)
            if not assigned_product:
                assigned_product = routed.get("assigned_product")
            if not router_reasons:
                router_reasons = routed.get("router_reasons") or []
            if execution_allowed is None:
                execution_allowed = routed.get("execution_allowed", False)
            suffix = "product_router_display_fallback"
            assigned_product_source = (
                suffix if assigned_product_source == "unresolved" else f"{assigned_product_source}+{suffix}"
            )

        if execution_allowed is None:
            execution_allowed = False
        assigned_product = assigned_product or "UNKNOWN"
        operator_read_profile, skepticism_flags = _operator_read_profile(tier, top_prob)

        verdicts.append(
            {
                "race_id": race_id,
                "course": course,
                "off_time": off_time,
                "race_name": race_name,
                "horse": horse_name,
                "tier": tier,
                "decision_tier": tier,
                "confidence_level": v.get("confidence_level", top.get("confidence_level", "low")),
                "velo_prime_prob": v.get("velo_prime_prob", top.get("velo_prime_prob", 0)),
                "prob_gap": prob_gap,
                "market_deception_score": v.get("market_deception_score", top.get("market_deception_score", 0)),
                "improvement_score": v.get("improvement_score", top.get("improvement_score", 0)),
                "assigned_product": assigned_product,
                "assigned_product_source": assigned_product_source,
                "router_reasons": router_reasons if isinstance(router_reasons, list) else [router_reasons],
                "execution_allowed": execution_allowed,
                "place_prob": v.get("place_prob", top.get("place_prob", 0)),
                "archetype_label": v.get("archetype_label", top.get("archetype_label", "")),
                "cashrun_class": (cashrun_match or {}).get("cashrun_class"),
                "cashrun_score": (cashrun_match or {}).get("final_cashrun_score"),
                "cashrun_confidence": (cashrun_match or {}).get("confidence_level"),
                "cashrun_operator_read": (cashrun_match or {}).get("final_operator_read"),
                "cash_run_flag": bool((cashrun_match or {}).get("cashrun_class") in ("CASHRUN_READY", "CASHRUN_WATCH")),
                "vp30": top_prob >= 0.30,
                "mds_high": float(v.get("market_deception_score", top.get("market_deception_score", 0)) or 0) > 0.50,
                "improve_high": float(v.get("improvement_score", top.get("improvement_score", 0)) or 0) > 0.40,
                "operator_read_profile": operator_read_profile,
                "operator_skepticism_flags": skepticism_flags,
            }
        )

    # Sort by off_time
    verdicts.sort(key=lambda x: x.get("off_time") or "")
    metadata_complete = sum(1 for row in verdicts if row.get("course") and row.get("off_time") and row.get("horse"))
    metadata_coverage = round(metadata_complete / len(verdicts), 4) if verdicts else 0.0

    # ── Commit SHA ───────────────────────────────────────────────────────────
    try:
        commit = (
            _sp.check_output(
                ["git", "rev-parse", "--short", "HEAD"],
                cwd=root,
                stderr=_sp.DEVNULL,
            )
            .decode()
            .strip()
        )
    except Exception:
        commit = "unknown"

    date_mismatch = loaded_date != target_date
    governed_card_status = "FALLBACK_USED" if date_mismatch else "PASS_EXACT_DATE"

    return {
        "meta": {
            "status": governed_card_status,
            "requested_date": target_date,
            "loaded_date": loaded_date,
            "source": source_label,
            "message": None if not date_mismatch else "Fallback data used for requested date.",
            "allow_fallback": allow_fallback,
            "date_match": not date_mismatch,
            "stale_data_blocked": False,
            "governed_card_loaded_date": loaded_date,
            "governed_card_status": governed_card_status,
            "sidecar_loaded_date": sidecar_loaded_date,
            "sidecar_status": sidecar_status,
            "sidecar_date_match": sidecar_date_match,
            "cashrun_loaded_date": cashrun_loaded_date,
            "cashrun_status": cashrun_status,
            "cashrun_counts": cashrun_counts,
            "metadata_coverage": metadata_coverage,
            "commit_sha": commit,
            "router_version": "ProductRouter v1 (live-safe)",
            "record_count": len(verdicts),
            "date_mismatch": date_mismatch,
            "gov_overlay": len(gov_by_race) > 0,
            "exact_date_file_present": verdict_path.exists(),
        },
        "cashrun": {
            "status": cashrun_status,
            "loaded_date": cashrun_loaded_date,
            "counts": cashrun_counts,
            "rows": cashrun_rows,
        },
        "verdicts": verdicts,
    }


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "VÉLØ Oracle API",
        "version": "v1.0",
        "docs": "/docs",
        "health": "/health",
        "dashboard": "/dashboard",
    }


# API v1 endpoints
@app.get("/api/v1/status")
async def api_status(authorized: bool = Depends(verify_api_key)):
    """API status endpoint"""
    return {"status": "operational", "version": "v1.0", "timestamp": utc_now_iso()}


@app.get("/api/v1/build-fingerprint")
async def build_fingerprint():
    """Deploy probe — resolves commit SHA from Railway runtime env vars.

    Returns the full ``RAILWAY_GIT_COMMIT_SHA`` injected by Railway at deploy
    time.  If the env var is absent (local dev, Docker without build args) the
    response carries an explicit ``"unknown"`` state so callers can distinguish
    a missing value from a stale hardcoded one.
    """
    import os as _os

    raw_sha = _os.getenv("RAILWAY_GIT_COMMIT_SHA", "").strip()
    commit_short = raw_sha[:7] if len(raw_sha) >= 7 else None

    if commit_short:
        commit_status = "resolved"
        commit_value = commit_short
        commit_full = raw_sha
    else:
        commit_status = "unknown"
        commit_value = "unknown"
        commit_full = "unknown"

    return {
        "commit": commit_value,
        "commit_full": commit_full,
        "commit_status": commit_status,
        "railway_service": _os.getenv("RAILWAY_SERVICE_NAME", "unknown"),
        "railway_environment": _os.getenv("RAILWAY_ENVIRONMENT_NAME", "unknown"),
        "has_write_reject_event": True,
        "timestamp": utc_now_iso(),
    }


# Prediction endpoints
@app.post("/api/v1/predict/quick")
async def predict_quick(race_data: dict, authorized: bool = Depends(verify_api_key)):
    """
    Quick single-runner prediction (SQPE v17 + VELO_PRIME_prob where available).

    Accepts: {"runner": {...}, "race": {...}}
    Returns: probability, velo_prime_prob, overlay, model_version
    """
    try:
        from app.services.model_manager import get_model_manager
        from workers.racing_api_normalizer import normalize_race, normalize_runner

        mm = get_model_manager()
        runner = race_data.get("runner", {})
        race = race_data.get("race", {})

        # Normalize inputs through canonical schema
        norm_runner = normalize_runner(runner)
        norm_race = normalize_race({**race, "runners": [runner]})

        sqpe_prob = mm.predict_sqpe(runner=norm_runner, race=norm_race)

        odds = norm_runner.get("best_odds_decimal") or 0
        overlay = mm.detect_overlay(sqpe_prob, float(odds)) if odds else {"is_overlay": False, "edge": 0.0}

        return {
            "probability": round(sqpe_prob, 4),
            "velo_prime_prob": round(
                sqpe_prob, 4
            ),  # same as SQPE for single-runner; use /predict/race for full ensemble
            "overlay": overlay,
            "model_version": mm.model_versions.get("sqpe", "unknown"),
            "ensemble_version": "sqpe_only_single_runner",
        }

    except Exception as e:
        logger.error(f"Prediction failed: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/api/v1/predict/race")
async def predict_race(race_data: dict, persist: bool = False, authorized: bool = Depends(verify_api_key)):
    """
    Full race prediction using VELO_PRIME_prob meta-ensemble.

    Accepts a normalized race dict (output of racing_api_normalizer.normalize_race())
    OR a raw Racing API Standard racecard entry.

    Query param:  ?persist=true  to write top verdict to velo_verdicts in Supabase.

    Returns:
        Ranked list of runners with velo_prime_prob + all specialist scores
        + macro regime context.
    """
    try:
        from app.services.velo_prime_service import persist_race_predictions, score_race_velo_prime
        from workers.racing_api_normalizer import normalize_race

        # Accept either pre-normalized or raw racecard
        if "runners" not in race_data:
            raise HTTPException(status_code=400, detail="race_data must contain 'runners' list")

        norm_race = normalize_race(race_data)
        predictions = score_race_velo_prime(norm_race, sentient_state=_sentient_state)

        if persist:
            persist_race_predictions(norm_race, predictions)

        return {
            "race_id": norm_race.get("race_id"),
            "course": norm_race.get("course"),
            "off_time": norm_race.get("off_time"),
            "field_size": len(norm_race.get("runners", [])),
            "ensemble_version": "velo_prime_v1",
            "predictions": predictions,
            "top_pick": predictions[0] if predictions else None,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Race prediction failed: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/api/v1/predict/full")
async def predict_full(race_data: dict, authorized: bool = Depends(verify_api_key)):
    """
    Full prediction with intelligence layers — NOT YET IMPLEMENTED.
    Use /api/v1/predict/race for the live scoring path.
    """
    raise HTTPException(status_code=501, detail="Not implemented — use /api/v1/predict/race for live scoring")


# Intelligence endpoints
@app.get("/api/v1/intel/narrative/{race_id}")
async def get_narrative(race_id: str, authorized: bool = Depends(verify_api_key)):
    """Get narrative intelligence for race"""
    try:
        from app.intelligence.chains.narrative_chain import run_narrative_chain
        from workers.racing_api_fetcher import RacingAPIFetcher

        fetcher = RacingAPIFetcher()
        race = fetcher.get_race(race_id)
        result = await run_narrative_chain(race)
        return result
    except Exception as e:
        logger.error(f"Narrative analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/v1/intel/market/{race_id}")
async def get_market_intel(race_id: str, authorized: bool = Depends(verify_api_key)):
    """Get market manipulation intelligence"""
    try:
        from app.intelligence.chains.market_chain import run_market_chain
        from workers.racing_api_fetcher import RacingAPIFetcher

        fetcher = RacingAPIFetcher()
        race = fetcher.get_race(race_id)
        result = await run_market_chain(race, odds_history=[])
        return result
    except Exception as e:
        logger.error(f"Market analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


# System endpoints
@app.get("/api/v1/system/models")
async def get_models(authorized: bool = Depends(verify_api_key)):
    """Get loaded models and versions"""
    try:
        from app.ml.model_ops.loader import get_loaded_models

        models = get_loaded_models()

        return {"models": models, "count": len(models), "timestamp": utc_now_iso()}

    except Exception as e:
        logger.error(f"Get models failed: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


# ── Telegram Bot Webhook ──────────────────────────────────────────────────────
# velo_agent_bot — conversational intelligence via VoxAgent
# Token: TELEGRAM_BOT_TOKEN  |  Webhook set at startup

_TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
_TG_BOT_URL = os.getenv("RAILWAY_SERVICE_VELO_ORACLE_URL", "")

# Webhook Memory Guard Configuration
_MAX_VOX_AGENTS = int(os.getenv("MAX_VOX_AGENTS", "50"))
_WHITELISTED_USERS = {int(u.strip()) for u in os.getenv("WHITELISTED_TELEGRAM_USERS", "").split(",") if u.strip()}

# Bounded agent store (LRU cache using OrderedDict)
_vox_agents: OrderedDict[int, object] = OrderedDict()


def _get_vox_agent(user_id: int):
    """Get or create VoxAgent with LRU eviction policy."""
    # 1. Identity Gate (Optional but recommended)
    if _WHITELISTED_USERS and user_id not in _WHITELISTED_USERS:
        logger.warning(f"[bot] Unauthorized user {user_id} blocked by whitelist")
        return None

    # 2. LRU Retrieval/Eviction
    if user_id in _vox_agents:
        # Move to end (most recently used)
        _vox_agents.move_to_end(user_id)
        return _vox_agents[user_id]

    # 3. Size Guard
    if len(_vox_agents) >= _MAX_VOX_AGENTS:
        # Evict oldest (first item)
        oldest_id, _ = _vox_agents.popitem(last=False)
        logger.info(f"[bot] Memory Guard: evicted oldest agent instance {oldest_id}")

    try:
        from workers.velo_vox.agent_loop import VoxAgent

        agent = VoxAgent(user_id=user_id)
        _vox_agents[user_id] = agent
        return agent
    except Exception as e:
        logger.error(f"[bot] VoxAgent init failed for user {user_id}: {e}")
        return None


def _tg_send(chat_id: int, text: str) -> bool:
    """Send a message via the bot token (sync, stdlib only)."""
    if not _TG_TOKEN:
        return False
    try:
        body = json.dumps({"chat_id": chat_id, "text": text[:4096]}).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{_TG_TOKEN}/sendMessage",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except urllib.error.HTTPError as e:
        logger.warning(f"[bot] Telegram send HTTP {e.code}: {e.reason}")
        return False
    except Exception as e:
        logger.warning(f"[bot] Telegram send failed: {e}")
        return False


def _register_webhook() -> None:
    """Tell Telegram to POST updates to our /telegram/webhook endpoint."""
    if not _TG_TOKEN or not _TG_BOT_URL:
        logger.warning(
            "[bot] Skipping webhook registration — TELEGRAM_BOT_TOKEN or RAILWAY_SERVICE_VELO_ORACLE_URL not set"
        )
        return
    webhook_url = f"https://{_TG_BOT_URL}/telegram/webhook"
    try:
        body = json.dumps({"url": webhook_url, "drop_pending_updates": True}).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{_TG_TOKEN}/setWebhook",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read())
            if result.get("ok"):
                logger.info(f"[bot] Webhook registered → {webhook_url}")
            else:
                logger.warning(f"[bot] Webhook registration failed: {result}")
    except Exception as e:
        logger.warning(f"[bot] Webhook registration error: {e}")


@app.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    """Receive Telegram updates. No auth — Telegram posts here directly."""
    try:
        update = await request.json()
    except Exception:
        return JSONResponse(status_code=200, content={"ok": True})

    # Extract message — handle regular messages only
    message = update.get("message") or update.get("edited_message")
    if not message:
        return JSONResponse(status_code=200, content={"ok": True})

    chat_id = message.get("chat", {}).get("id")
    user_id = message.get("from", {}).get("id")
    text = message.get("text", "").strip()

    if not chat_id or not text:
        return JSONResponse(status_code=200, content={"ok": True})

    # /start command
    if text == "/start":
        agent = _get_vox_agent(user_id)
        if agent:
            try:
                agent.reset()
            except Exception:
                pass
        _tg_send(
            chat_id,
            "VELO Agent online.\n\n"
            "Ask me about today's races, a horse, trainer, or tomorrow's card.\n"
            "Talk naturally — no commands needed.",
        )
        return JSONResponse(status_code=200, content={"ok": True})

    # /reset command
    if text == "/reset":
        if user_id in _vox_agents:
            del _vox_agents[user_id]
        _tg_send(chat_id, "Conversation cleared.")
        return JSONResponse(status_code=200, content={"ok": True})

    # All other text → VoxAgent
    agent = _get_vox_agent(user_id)
    if not agent:
        _tg_send(chat_id, "Agent unavailable — check server logs.")
        return JSONResponse(status_code=200, content={"ok": True})

    # Run VoxAgent in thread executor (it's synchronous)
    loop = asyncio.get_event_loop()
    try:
        response = await loop.run_in_executor(None, lambda: agent.chat(text))
    except Exception as e:
        logger.error(f"[bot] VoxAgent error user={user_id}: {e}")
        _tg_send(chat_id, f"Error: {e}")
        return JSONResponse(status_code=200, content={"ok": True})

    # Split long responses at Telegram's 4096 char limit
    for i in range(0, len(response), 4096):
        _tg_send(chat_id, response[i : i + 4096])

    return JSONResponse(status_code=200, content={"ok": True})


# Error handlers
@app.exception_handler(404)
async def not_found_handler(request, exc):
    """Handle 404 errors"""
    return JSONResponse(
        status_code=404,
        content={"error": "Not found", "path": str(request.url), "timestamp": utc_now_iso()},
    )


@app.exception_handler(500)
async def server_error_handler(request, exc):
    """Handle 500 errors — include detail in non-production environments."""
    logger.error(f"Server error: {exc}", exc_info=True)
    detail = str(exc) if os.getenv("API_ENV", "production") != "production" else "Internal server error"
    return JSONResponse(status_code=500, content={"error": detail, "timestamp": utc_now_iso()})


# Startup/shutdown are handled by the lifespan context manager above.


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)), reload=ENV != "production")
