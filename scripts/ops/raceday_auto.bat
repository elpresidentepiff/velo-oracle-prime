@echo off
REM VELO daily raceday pipeline — Task Scheduler entry point
REM Runs Steps 1-9.6: capture -> parse -> validate -> passport -> two-lane -> PDFs -> RPDC -> all 4 models
REM PDFs must already be staged to data\incoming_pdfs\YYYY-MM-DD\ before this runs

setlocal
set VELO=C:\Users\puror\velo-oracle-prime
set LOG=%VELO%\logs\raceday_auto_%date:~-4,4%%date:~-7,2%%date:~0,2%.log
if not exist "%VELO%\logs" mkdir "%VELO%\logs"

echo [%date% %time%] Starting VELO raceday pipeline >> "%LOG%"
wsl -e bash -c "cd /mnt/c/Users/puror/velo-oracle-prime && PYTHONPATH=. venv/bin/python scripts/ops/run_full_raceday.py >> /tmp/raceday_auto.log 2>&1"
echo [%date% %time%] Pipeline complete. Exit: %errorlevel% >> "%LOG%"
endlocal
