"""
VÉLØ Oracle - FastAPI Main Application
Production-ready with CORS, health checks, and API routing
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Header, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from datetime import datetime
import asyncio
import logging
import os
import json
import urllib.request
import urllib.error

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


_sentient_state: dict | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load models once at startup, release on shutdown."""
    global _sentient_state
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
    allow_origins=["*"],  # Allow all origins
    allow_credentials=True,
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

# Environment
ENV = os.getenv("ENV", "production")
API_KEY = os.getenv("API_KEY", "")

# API Key validation
async def verify_api_key(x_api_key: str = Header(None)):
    """Verify API key from header"""
    if not API_KEY:
        # API_KEY env var not set — refuse all requests rather than silently bypass
        logger.warning("API_KEY not configured — rejecting request")
        raise HTTPException(status_code=503, detail="API key not configured on this server")

    if x_api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")

    return True


# Health check endpoint - CRITICAL for Railway
@app.get("/health")
async def health_check():
    """
    Real health check — fails if DB unreachable or last scoring run is stale.
    Returns HTTP 503 on any critical failure so Railway detects the problem.
    """
    import urllib.request, urllib.error, json as _json, os as _os

    issues = []
    details: dict = {
        "app": "VÉLØ Oracle",
        "version": "v1.0",
        "environment": ENV,
        "timestamp": datetime.utcnow().isoformat(),
    }

    # ── 1. Supabase reachability ──────────────────────────────────────────────
    sb_url = _os.getenv("SUPABASE_URL", "")
    sb_key = _os.getenv("SUPABASE_SERVICE_ROLE_KEY") or _os.getenv("SUPABASE_SERVICE_KEY", "")
    if not sb_url or not sb_key:
        issues.append("SUPABASE_URL or SUPABASE_SERVICE_KEY env vars missing")
        details["db"] = "UNCONFIGURED"
    else:
        try:
            req = urllib.request.Request(
                f"{sb_url}/rest/v1/pipeline_runs?select=id&limit=1",
                headers={
                    "apikey": sb_key,
                    "Authorization": f"Bearer {sb_key}",
                    "Accept": "application/json",
                }
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
                }
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
                    last_ts = datetime.fromisoformat(last_ts_str.rstrip("Z"))
                    age_hours = (datetime.utcnow() - last_ts).total_seconds() / 3600
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
    if issues:
        details["status"] = "FAIL"
        details["issues"] = issues
        return JSONResponse(status_code=503, content=details)

    details["status"] = "ok"
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
    import subprocess, sys, pathlib

    trigger_secret = os.getenv("TRIGGER_SCORE_SECRET", "")
    if not trigger_secret:
        logger.error("TRIGGER_SCORE_SECRET not configured — trigger endpoint disabled")
        raise HTTPException(status_code=503, detail="Trigger not configured on this server")
    if x_trigger_secret != trigger_secret:
        logger.warning("Trigger attempt with invalid secret")
        raise HTTPException(status_code=401, detail="Invalid trigger secret")

    body: dict = {}
    try:
        body = await request.json()
    except Exception:
        pass

    trigger_source = body.get("trigger_source") or "api_manual"
    target_date    = body.get("target_date") or ""

    script_path = pathlib.Path(__file__).parent.parent / "scripts" / "run_prime_today.py"
    if not script_path.exists():
        raise HTTPException(status_code=500, detail=f"Scoring script not found: {script_path}")

    env = os.environ.copy()
    env["TRIGGER_SOURCE"] = trigger_source

    cmd = [sys.executable, str(script_path)]
    if target_date:
        cmd += ["--date", target_date]

    proc = subprocess.Popen(
        cmd,
        env=env,
        cwd=str(script_path.parent.parent),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    logger.info(
        "Scoring triggered — source=%s pid=%d target_date=%s",
        trigger_source, proc.pid, target_date or "today",
    )

    return JSONResponse(status_code=202, content={
        "status":         "triggered",
        "trigger_source": trigger_source,
        "target_date":    target_date or "today",
        "pid":            proc.pid,
    })


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "VÉLØ Oracle API",
        "version": "v1.0",
        "docs": "/docs",
        "health": "/health"
    }


# API v1 endpoints
@app.get("/api/v1/status")
async def api_status(authorized: bool = Depends(verify_api_key)):
    """API status endpoint"""
    return {
        "status": "operational",
        "version": "v1.0",
        "timestamp": datetime.utcnow().isoformat()
    }


# Prediction endpoints
@app.post("/api/v1/predict/quick")
async def predict_quick(
    race_data: dict,
    authorized: bool = Depends(verify_api_key)
):
    """
    Quick single-runner prediction (SQPE v17 + VELO_PRIME_prob where available).

    Accepts: {"runner": {...}, "race": {...}}
    Returns: probability, velo_prime_prob, overlay, model_version
    """
    try:
        from app.services.model_manager import get_model_manager
        from workers.racing_api_normalizer import normalize_runner, normalize_race

        mm     = get_model_manager()
        runner = race_data.get("runner", {})
        race   = race_data.get("race", {})

        # Normalize inputs through canonical schema
        norm_runner = normalize_runner(runner)
        norm_race   = normalize_race({**race, "runners": [runner]})

        sqpe_prob = mm.predict_sqpe(runner=norm_runner, race=norm_race)

        odds    = norm_runner.get("best_odds_decimal") or 0
        overlay = mm.detect_overlay(sqpe_prob, float(odds)) if odds else {"is_overlay": False, "edge": 0.0}

        return {
            "probability":     round(sqpe_prob, 4),
            "velo_prime_prob": round(sqpe_prob, 4),   # same as SQPE for single-runner; use /predict/race for full ensemble
            "overlay":         overlay,
            "model_version":   mm.model_versions.get("sqpe", "unknown"),
            "ensemble_version": "sqpe_only_single_runner",
        }

    except Exception as e:
        logger.error(f"Prediction failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/predict/race")
async def predict_race(
    race_data: dict,
    persist: bool = False,
    authorized: bool = Depends(verify_api_key)
):
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
        from workers.racing_api_normalizer import normalize_race
        from app.services.velo_prime_service import score_race_velo_prime, persist_race_predictions

        # Accept either pre-normalized or raw racecard
        if "runners" not in race_data:
            raise HTTPException(status_code=400, detail="race_data must contain 'runners' list")

        norm_race   = normalize_race(race_data)
        predictions = score_race_velo_prime(norm_race, sentient_state=_sentient_state)

        if persist:
            persist_race_predictions(norm_race, predictions)

        return {
            "race_id":          norm_race.get("race_id"),
            "course":           norm_race.get("course"),
            "off_time":         norm_race.get("off_time"),
            "field_size":       len(norm_race.get("runners", [])),
            "ensemble_version": "velo_prime_v1",
            "predictions":      predictions,
            "top_pick":         predictions[0] if predictions else None,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Race prediction failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/predict/full")
async def predict_full(
    race_data: dict,
    authorized: bool = Depends(verify_api_key)
):
    """
    Full prediction with intelligence layers — NOT YET IMPLEMENTED.
    Use /api/v1/predict/race for the live scoring path.
    """
    raise HTTPException(
        status_code=501,
        detail="Not implemented — use /api/v1/predict/race for live scoring"
    )


# Intelligence endpoints
@app.get("/api/v1/intel/narrative/{race_id}")
async def get_narrative(
    race_id: str,
    authorized: bool = Depends(verify_api_key)
):
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
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/intel/market/{race_id}")
async def get_market_intel(
    race_id: str,
    authorized: bool = Depends(verify_api_key)
):
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
        raise HTTPException(status_code=500, detail=str(e))


# System endpoints
@app.get("/api/v1/system/models")
async def get_models(authorized: bool = Depends(verify_api_key)):
    """Get loaded models and versions"""
    try:
        from app.ml.model_ops.loader import get_loaded_models
        
        models = get_loaded_models()
        
        return {
            "models": models,
            "count": len(models),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Get models failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── Telegram Bot Webhook ──────────────────────────────────────────────────────
# velo_agent_bot — conversational intelligence via VoxAgent
# Token: TELEGRAM_BOT_TOKEN  |  Webhook set at startup

_TG_TOKEN  = os.getenv("TELEGRAM_BOT_TOKEN", "")
_TG_BOT_URL = os.getenv("RAILWAY_SERVICE_VELO_ORACLE_URL", "")

# Per-user VoxAgent instances (maintains conversation history)
_vox_agents: dict[int, object] = {}


def _get_vox_agent(user_id: int):
    if user_id not in _vox_agents:
        try:
            from workers.velo_vox.agent_loop import VoxAgent
            _vox_agents[user_id] = VoxAgent(user_id=user_id)
        except Exception as e:
            logger.error(f"[bot] VoxAgent init failed for user {user_id}: {e}")
            return None
    return _vox_agents[user_id]


def _tg_send(chat_id: int, text: str) -> bool:
    """Send a message via the bot token (sync, stdlib only)."""
    if not _TG_TOKEN:
        return False
    try:
        body = json.dumps({"chat_id": chat_id, "text": text[:4096]}).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{_TG_TOKEN}/sendMessage",
            data=body, headers={"Content-Type": "application/json"}
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
        logger.warning("[bot] Skipping webhook registration — TELEGRAM_BOT_TOKEN or RAILWAY_SERVICE_VELO_ORACLE_URL not set")
        return
    webhook_url = f"https://{_TG_BOT_URL}/telegram/webhook"
    try:
        body = json.dumps({"url": webhook_url, "drop_pending_updates": True}).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{_TG_TOKEN}/setWebhook",
            data=body, headers={"Content-Type": "application/json"}
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

    chat_id  = message.get("chat", {}).get("id")
    user_id  = message.get("from", {}).get("id")
    text     = message.get("text", "").strip()

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
        _tg_send(chat_id,
            "VELO Agent online.\n\n"
            "Ask me about today's races, a horse, trainer, or tomorrow's card.\n"
            "Talk naturally — no commands needed."
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
        _tg_send(chat_id, response[i:i + 4096])

    return JSONResponse(status_code=200, content={"ok": True})


# Error handlers
@app.exception_handler(404)
async def not_found_handler(request, exc):
    """Handle 404 errors"""
    return JSONResponse(
        status_code=404,
        content={
            "error": "Not found",
            "path": str(request.url),
            "timestamp": datetime.utcnow().isoformat()
        }
    )


@app.exception_handler(500)
async def server_error_handler(request, exc):
    """Handle 500 errors"""
    logger.error(f"Server error: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "timestamp": datetime.utcnow().isoformat()
        }
    )


# Startup/shutdown are handled by the lifespan context manager above.


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
        reload=ENV != "production"
    )
