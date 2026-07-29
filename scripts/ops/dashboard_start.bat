@echo off
REM Start the VELO dashboard server on port 8000
REM Run this once at startup — access at http://localhost:8000

wsl -e bash -c "pkill -f 'new_build_dashboard_server' 2>/dev/null; sleep 1; cd /mnt/c/Users/puror/velo-oracle-prime && nohup bash -c 'PYTHONPATH=. venv/bin/python scripts/ops/new_build_dashboard_server.py' >> /tmp/dashboard.log 2>&1 &"
echo Dashboard started at http://localhost:8000
start http://localhost:8000
