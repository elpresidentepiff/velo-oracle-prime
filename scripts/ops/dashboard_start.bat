@echo off
REM Start the VELO dashboard server on port 8000
REM Run this once at startup — access at http://localhost:8000
REM
REM Delegates to dashboard_start.sh so the launch command lives in one tracked
REM place instead of being quoted three levels deep inside this .bat.
REM Until 2026-08-02 this launched new_build_dashboard_server.py, which
REM docs/current/ONE_TRUTH.md forbids running standalone (missing routes).
REM It now starts the canonical app/main.py with .env loaded first.

wsl -e bash /mnt/c/Users/puror/velo-oracle-prime/scripts/ops/dashboard_start.sh
echo Dashboard started at http://localhost:8000
start http://localhost:8000
