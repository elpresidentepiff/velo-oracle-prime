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

# The date each phase is *about*, which is not always today.
#
# The 22:00 EOD reconciles the day that has just finished racing. If the machine
# is asleep at 22:00, StartWhenAvailable catches the run up the next morning —
# and taking today's date then asks for results of races that have not been run.
# That is exactly what happened on 2026-09-02: the EOD fired at 07:40, looked
# for 2026-09-02 results, and died at Step 10A while 2026-09-01 went
# unreconciled entirely.
#
# So a catch-up EOD running before the day's racing has finished is still about
# yesterday. After 18:00 it is about today. An explicit second argument always
# wins, for reruns.
if [ -n "${2:-}" ]; then
  DATE="$2"
elif [ "${PHASE}" = "eod" ] && [ "$(date +%H)" -lt 18 ]; then
  DATE="$(date -d 'yesterday' +%Y-%m-%d)"
  LATE_EOD="CAUGHT_UP_FOR_PREVIOUS_DAY"
else
  DATE="$(date +%Y-%m-%d)"
fi
LATE_EOD="${LATE_EOD:-}"
LOG_DIR="data/reports"
LOG="${LOG_DIR}/velo_daily_${DATE}.log"
STATUS_FILE="${LOG_DIR}/velo_daily_status.json"
mkdir -p "${LOG_DIR}"

log() { echo "$(date -Is)  $*" | tee -a "${LOG}"; }

notify() {
  # Never fatal: a missed toast must not change the outcome of a run.
  #
  # This is the shallow channel. It vanishes in 15 seconds, reaches one machine,
  # and leaves no trace - so an unseen toast and an unsent one look identical.
  # Between 2026-09-04 and 2026-09-07 it fired six times into an empty room
  # while three race days were lost. Anything that matters must ALSO go through
  # alert(), which persists and reaches a phone.
  powershell.exe -NoProfile -WindowStyle Hidden -Command \
    "Add-Type -AssemblyName System.Windows.Forms;\$n = New-Object System.Windows.Forms.NotifyIcon;\$n.Icon = [System.Drawing.SystemIcons]::Information;\$n.Visible = \$true;\$n.ShowBalloonTip(15000, '$1', '$2', 'Info');Start-Sleep -Seconds 12; \$n.Dispose()" \
    >/dev/null 2>&1 || true
}

alert() {
  # The deep channel: Telegram, and a written record of whether it landed.
  # Never fatal - but never silent about its own failure either.
  #   alert <severity> <title> <body>
  PYTHONPATH=. venv/bin/python scripts/ops/velo_alert.py \
    --severity "$1" --title "$2" --body "$3" >>"${LOG}" 2>&1 || true
}

write_status() {
  # A machine-readable record of each phase, so "did it run?" is answerable
  # without reading logs - and so a phase that stops firing entirely is visible
  # as a stale timestamp rather than as silence.
  #
  # It also counts. The file used to hold only the LAST run of each phase, which
  # is why six consecutive aborts across four days were indistinguishable from
  # the first one: every toast said the same thing and nothing knew it was the
  # sixth. Day one is an annoyance, day four is an emergency, and a system that
  # cannot tell them apart cannot escalate. consecutive_failures is that memory.
  #
  # Echoes the resulting streak so the caller can escalate on it.
  PHASE="$PHASE" DATE="$DATE" OUTCOME="$1" DETAIL="${2:-}" STATUS_FILE="$STATUS_FILE" \
  venv/bin/python - <<'PY' 2>/dev/null || echo 0
import json, os, pathlib, datetime
p = pathlib.Path(os.environ["STATUS_FILE"])
try:
    state = json.loads(p.read_text())
except Exception:
    state = {}

phase = os.environ["PHASE"]
outcome = os.environ["OUTCOME"]
date = os.environ["DATE"]
prior = state.get(phase) or {}
failed = outcome != "OK"

if failed:
    streak = int(prior.get("consecutive_failures") or 0) + 1
    first_failure = prior.get("first_failure_date") or date
    last_ok = prior.get("last_ok_date")
else:
    streak = 0
    first_failure = None
    last_ok = date

state[phase] = {
    "date": date,
    "outcome": outcome,
    "detail": os.environ["DETAIL"],
    "finished_at": datetime.datetime.now().astimezone().isoformat(),
    "consecutive_failures": streak,
    "first_failure_date": first_failure,
    "last_ok_date": last_ok,
}
p.write_text(json.dumps(state, indent=2))
print(streak)
PY
}

# Validate the phase before anything expensive: a typo should cost nothing and
# must not leave a junk entry in the status file that looks like a real phase.
case "${PHASE}" in
  morning|eod) ;;
  *) echo "Unknown phase '${PHASE}'. Use 'morning' or 'eod'." >&2; exit 64 ;;
esac

log "===== velo_daily ${PHASE} fired for ${DATE} ====="
if [ -n "${LATE_EOD}" ]; then
  log "[WARN] EOD did not run at 22:00 and is catching up. Reconciling ${DATE}, not today."
fi

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
  STREAK="$(write_status "ABORTED_SESSION" "${STATUS}")"
  STREAK="${STREAK:-1}"

  # The whole point of counting. One abort is a bad morning; a run of them is a
  # dead system nobody has noticed, and it must not read the same either time.
  if [ "${STREAK}" -ge 2 ]; then
    SEVERITY="critical"
    HEADLINE="VELO ${PHASE} has not run ${STREAK} times in a row"
    log "[ABORT] This is consecutive failure #${STREAK} for the ${PHASE} phase."
  else
    SEVERITY="warning"
    HEADLINE="VELO ${PHASE} did not run"
  fi

  DETAIL="Racing Post session is ${STATUS}.

Nothing was captured for ${DATE}. Predictions for a day that has already run
cannot be recreated - that window is gone once the racing is over.

Fix:
  cd /mnt/c/Users/puror/velo-oracle-prime
  PYTHONPATH=. venv/bin/python scripts/ops/_init_login_timed.py
  PYTHONPATH=. venv/bin/python scripts/ops/check_rp_session_health.py

The probe must report PASS before the next run will launch."

  notify "${HEADLINE}" "Racing Post session is ${STATUS}. Log in again, or the day is lost."
  alert "${SEVERITY}" "${HEADLINE}" "${DETAIL}"
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

log "===== ${PHASE} finished rc=${RC} ${LATE} ${LATE_EOD} ====="
if [ "${RC}" -eq 0 ]; then
  # Capture the streak BEFORE it is reset, so a recovery can name what it ended.
  PRIOR_STREAK="$(venv/bin/python -c "
import json,sys
try:
    print(int((json.load(open('${STATUS_FILE}')).get('${PHASE}') or {}).get('consecutive_failures') or 0))
except Exception:
    print(0)
" 2>/dev/null || echo 0)"
  write_status "OK" "${LATE} ${LATE_EOD}" >/dev/null
  if [ "${PRIOR_STREAK}" -ge 2 ]; then
    # Recovery is worth saying out loud. A run of failures that simply stops
    # being reported leaves you unsure whether it was fixed or just gave up.
    alert "info" "VELO ${PHASE} is running again" \
      "Recovered after ${PRIOR_STREAK} consecutive failures. ${DATE} completed rc=0."
  fi
else
  STREAK="$(write_status "FAILED" "rc=${RC} ${LATE} ${LATE_EOD}")"
  STREAK="${STREAK:-1}"
  if [ "${STREAK}" -ge 2 ]; then
    SEVERITY="critical"
    HEADLINE="VELO ${PHASE} has failed ${STREAK} times in a row"
  else
    SEVERITY="warning"
    HEADLINE="VELO ${PHASE} failed"
  fi
  notify "VELO ${PHASE} failed" "Exit ${RC}. See data/reports/velo_daily_${DATE}.log"
  alert "${SEVERITY}" "${HEADLINE}" \
    "Exit code ${RC} for ${DATE}.
See data/reports/velo_daily_${DATE}.log"
fi

# The bug that let a dead scheduler report green for weeks: propagate the code.
exit "${RC}"
