#!/usr/bin/env bash
# VELO daily automation — the single entrypoint both Windows tasks call.
#
#   velo_daily.sh morning   Steps 1-9.6  (capture, score, dashboards)
#   velo_daily.sh eod       Steps 10A-21 (results, sigma, learning, passport bank)
#
# Every failure mode this guards against is one that actually happened and cost
# race days. They are recorded in docs/current/ONE_TRUTH.md; the short version:
#
#   1. A dead scheduler reported green for weeks, because the .bat it called did
#      not propagate an exit code. Every path here ends in an explicit exit.
#   2. WSL crontab fired ZERO times on 2026-07-28/29 and lost the 28th
#      permanently, because WSL was not awake. Task Scheduler with
#      StartWhenAvailable is the only thing on this machine proven to fire.
#   3. Two of four morning runs fired hours late (09:52, 11:08). A catch-up that
#      lands after cards have started still captures - but RP drops a course
#      from its index the moment that course finishes, so the coverage is gone
#      and nothing said so. Late runs now proceed AND raise a flag, because a
#      partial day that knows it is partial is worth having; one that does not
#      is how silent garbage reaches the learning gates.
#   4. Launching against a logged-out RP session burns the whole capture window.
#      The session is probed before anything expensive starts.
set -u
cd /mnt/c/Users/puror/velo-oracle-prime || exit 1

PHASE="${1:-morning}"
DATE="${2:-$(date +%Y-%m-%d)}"
LOG_DIR="data/reports"
LOG="${LOG_DIR}/velo_daily_${DATE}.log"
STATUS_FILE="${LOG_DIR}/velo_daily_status.json"
mkdir -p "${LOG_DIR}"

log() { echo "$(date -Is)  $*" | tee -a "${LOG}"; }

notify() {
  # Never fatal: a missed toast must not change the outcome of a run.
  powershell.exe -NoProfile -WindowStyle Hidden -Command \
    "Add-Type -AssemblyName System.Windows.Forms;\$n = New-Object System.Windows.Forms.NotifyIcon;\$n.Icon = [System.Drawing.SystemIcons]::Information;\$n.Visible = \$true;\$n.ShowBalloonTip(15000, '$1', '$2', 'Info');Start-Sleep -Seconds 12; \$n.Dispose()" \
    >/dev/null 2>&1 || true
}

write_status() {
  # A machine-readable record of the last run of each phase, so "did it run?"
  # is answerable without reading logs - and so a phase that stops firing
  # entirely is visible as a stale timestamp rather than as silence.
  PHASE="$PHASE" DATE="$DATE" OUTCOME="$1" DETAIL="${2:-}" STATUS_FILE="$STATUS_FILE" \
  venv/bin/python - <<'PY' 2>/dev/null || true
import json, os, pathlib, datetime
p = pathlib.Path(os.environ["STATUS_FILE"])
try:
    state = json.loads(p.read_text())
except Exception:
    state = {}
state[os.environ["PHASE"]] = {
    "date": os.environ["DATE"],
    "outcome": os.environ["OUTCOME"],
    "detail": os.environ["DETAIL"],
    "finished_at": datetime.datetime.now().astimezone().isoformat(),
}
p.write_text(json.dumps(state, indent=2))
PY
}

# Validate the phase before anything expensive: a typo should cost nothing and
# must not leave a junk entry in the status file that looks like a real phase.
case "${PHASE}" in
  morning|eod) ;;
  *) echo "Unknown phase '${PHASE}'. Use 'morning' or 'eod'." >&2; exit 64 ;;
esac

log "===== velo_daily ${PHASE} fired for ${DATE} ====="

# ── The RP session gate ───────────────────────────────────────────────────────
# Both phases capture from Racing Post, so both are worthless without a live
# session. Probing costs ~30s and saves the entire window.
log "RP session probe..."
PROBE="$(PYTHONPATH=. timeout 240 venv/bin/python scripts/ops/check_rp_session_health.py 2>&1)"
echo "${PROBE}" >> "${LOG}"
STATUS="$(printf '%s' "${PROBE}" | venv/bin/python -c 'import sys,json,re
raw = sys.stdin.read()
m = re.search(r"\{.*\}", raw, re.S)
print(json.loads(m.group(0)).get("status", "UNKNOWN") if m else "UNKNOWN")' 2>/dev/null || echo UNKNOWN)"

if [ "${STATUS}" != "PASS" ]; then
  log "[ABORT] RP session probe returned ${STATUS} — not launching ${PHASE}."
  write_status "ABORTED_SESSION" "${STATUS}"
  notify "VELO ${PHASE} did not run" "Racing Post session is ${STATUS}. Log in again, or the day is lost."
  exit 2
fi
log "RP session OK."

# ── Morning lateness flag ─────────────────────────────────────────────────────
LATE=""
if [ "${PHASE}" = "morning" ]; then
  HOUR=$(date +%H)
  if [ "${HOUR}" -ge 10 ]; then
    LATE="LATE_START"
    log "[WARN] Morning run started at $(date +%H:%M). Courses that have already"
    log "[WARN] finished are gone from the RP index — coverage will be partial."
    notify "VELO morning run is late" "Started $(date +%H:%M). Coverage for finished courses is unrecoverable."
  fi
fi

# ── Run the phase ─────────────────────────────────────────────────────────────
case "${PHASE}" in
  morning)
    log "Launching run_full_raceday.py (Steps 1-9.6)"
    PYTHONPATH=. venv/bin/python scripts/ops/run_full_raceday.py \
      --date "${DATE}" --execute >> "${LOG}" 2>&1
    RC=$?
    ;;
  eod)
    # Step 21 (passport bank refresh) runs as part of this by default. It is
    # the daily horse-passport gather: ~500 profile URLs queued and captured.
    log "Launching run_full_raceday_eod.py (Steps 10A-21, incl. passport refresh)"
    PYTHONPATH=. venv/bin/python scripts/ops/run_full_raceday_eod.py \
      --date "${DATE}" --execute >> "${LOG}" 2>&1
    RC=$?
    ;;
esac

log "===== ${PHASE} finished rc=${RC} ${LATE} ====="
if [ "${RC}" -eq 0 ]; then
  write_status "OK" "${LATE}"
else
  write_status "FAILED" "rc=${RC} ${LATE}"
  notify "VELO ${PHASE} failed" "Exit ${RC}. See data/reports/velo_daily_${DATE}.log"
fi

# The bug that let a dead scheduler report green for weeks: propagate the code.
exit "${RC}"
