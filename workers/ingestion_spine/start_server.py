#!/usr/bin/env python3
"""
Diagnostic startup script for Railway deployment.
Prints explicit checkpoints so Railway logs show exactly where failure occurs.
"""
import sys, os

# Flush immediately after every print
def log(msg):
    print(f"[VELO] {msg}", flush=True)

log(f"Python {sys.version}")
log(f"PYTHONPATH={os.environ.get('PYTHONPATH', 'NOT SET')}")
log(f"PORT={os.environ.get('PORT', 'NOT SET')}")
log(f"CWD={os.getcwd()}")
log(f"SUPABASE_URL set: {bool(os.environ.get('SUPABASE_URL'))}")
log(f"SUPABASE_SERVICE_ROLE_KEY set: {bool(os.environ.get('SUPABASE_SERVICE_ROLE_KEY'))}")

try:
    import uvicorn
    log("uvicorn imported OK")
except Exception as e:
    log(f"FATAL: failed to import uvicorn: {e}")
    sys.exit(1)

try:
    import ingestion_spine.main
    log("ingestion_spine.main imported OK")
except Exception as e:
    log(f"FATAL: failed to import ingestion_spine.main: {e}")
    import traceback
    traceback.print_exc(file=sys.stdout)
    sys.stdout.flush()
    sys.exit(1)

port = int(os.environ.get("PORT", 8000))
log(f"Starting uvicorn on 0.0.0.0:{port}")

uvicorn.run(
    "ingestion_spine.main:app",
    host="0.0.0.0",
    port=port,
    log_level="info",
    access_log=False,
)
