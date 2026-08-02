#!/usr/bin/env bash
# Dashboard launcher for the "VELO Dashboard" Windows task (At logon time).
#
# Until 2026-08-02 dashboard_start.bat launched
# scripts/ops/new_build_dashboard_server.py, which docs/current/ONE_TRUTH.md
# explicitly forbids running standalone: it is missing /api/deep-race-agent,
# /api/radical-shadow and /api/health, and serving from it is the documented
# cause of the 2026-07-08 incident where the Champion Intent panel showed
# "No Champion Intent data" for a whole session because the frontend called a
# route the running server did not have. Every logon started the wrong server,
# so whether the dashboard was correct depended on whether the logon task or a
# manual launch won.
#
# app/main.py is the single canonical server. It MUST be started via
# load_dotenv() first -- plain `uvicorn app.main:app` or `python app/main.py`
# does not load .env and fails Supabase schema verification at startup, because
# neither the module nor its __main__ block calls load_dotenv() itself.
set -u
cd /mnt/c/Users/puror/velo-oracle-prime || exit 1

# Free port 8000 from either server before starting.
pkill -f "new_build_dashboard_server" 2>/dev/null || true
pkill -f "app.main:app" 2>/dev/null || true
sleep 1

nohup env PYTHONPATH=. venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import uvicorn; uvicorn.run('app.main:app', host='0.0.0.0', port=8000)" \
  >> /tmp/dashboard.log 2>&1 &

echo "VELO dashboard (app.main:app) starting on http://localhost:8000"
