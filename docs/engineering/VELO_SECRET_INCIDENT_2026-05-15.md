# VELO Secret Incident Report — 2026-05-15

## Classification
`TELEGRAM_SECRET_INCIDENT_OPEN`

## Affected File
- Original path: `scripts/send_telegram_summary.py`
- File state at discovery: untracked
- Current state: quarantined outside the repo executable path

## Commit / Push Status
- Tracked by git at discovery: `NO`
- Committed to branch: `NO`
- Pushed from repo history: `NO` to the best available local git evidence

## Secret Type
- Telegram bot credentials
- Telegram chat delivery credentials

## Containment Action
- The file was removed from `scripts/` and moved to a quarantine location outside the repository working tree.
- It is no longer available on the normal repo execution path.
- It was not staged.
- It was not committed.

## Exposure Risk
Even untracked, this file is a real incident because it could have leaked through:
- local execution
- terminal history or logs
- agent inspection
- accidental staging later
- screenshots or shared output

## Required Remediation
- Treat the Telegram bot token as compromised unless the operator can prove it was never exposed beyond the local machine.
- Rotate the Telegram bot token if there is any chance of exposure to logs, agents, screenshots, or shared output.
- Reissue any dependent local configuration using environment variables only.

## Guardrail Follow-up
- `scripts/send_telegram_summary.py` is now ignored by git.
- broader secret-like Telegram artifact patterns were added to `.gitignore`.
- secret values are redacted and are not printed in this report.

## Operator Truth
- Secret values were not copied into repo docs.
- Secret values were not echoed back into this thread response.
- This incident remains open until the operator confirms token rotation or confirms the credentials were safely disposable test values.
