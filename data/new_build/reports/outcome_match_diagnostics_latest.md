# New Build Outcome Match Diagnostics

- Bridge rows: 473
- Result rows: 25987
- Bridge date range: 2026-05-24 to 2026-05-29
- Result date range: 2026-03-15 to 2026-05-25
- Primary blocker: RESULT_DATE_MISSING
- Recommended next step: IMPORT_RESULTS_FOR_RP_ARCHIVE_DATES

## Reason Counts
- RESULT_DATE_MISSING: 413
- HORSE_NAME_MISSING_IN_RESULT_COURSE: 40
- LINKED: 9
- RESULT_COURSE_MISSING_FOR_DATE: 6
- STRICT_KEYS_PRESENT_BUT_NO_MATCH: 5

## Sample Unmatched
- 2026-05-25 Huntingdon 2026-05-25T12:30:00+01:00 — Another Day Out — RESULT_COURSE_MISSING_FOR_DATE — verify course naming and result coverage for this date
- 2026-05-25 Huntingdon 2026-05-25T12:30:00+01:00 — Alan Bresil — RESULT_COURSE_MISSING_FOR_DATE — verify course naming and result coverage for this date
- 2026-05-25 Huntingdon 2026-05-25T12:30:00+01:00 — Geordie Night — RESULT_COURSE_MISSING_FOR_DATE — verify course naming and result coverage for this date
- 2026-05-25 Huntingdon 2026-05-25T12:30:00+01:00 — The Wise Traveller — RESULT_COURSE_MISSING_FOR_DATE — verify course naming and result coverage for this date
- 2026-05-25 Huntingdon 2026-05-25T12:30:00+01:00 — Juggernaut — RESULT_COURSE_MISSING_FOR_DATE — verify course naming and result coverage for this date
- 2026-05-25 Windsor 2026-05-25T14:08:00+01:00 — Seventy — HORSE_NAME_MISSING_IN_RESULT_COURSE — inspect identity bridge aliases before any fuzzy match
- 2026-05-25 Windsor 2026-05-25T14:08:00+01:00 — Imperial Cult — HORSE_NAME_MISSING_IN_RESULT_COURSE — inspect identity bridge aliases before any fuzzy match
- 2026-05-25 Windsor 2026-05-25T14:08:00+01:00 — Opera Wave — HORSE_NAME_MISSING_IN_RESULT_COURSE — inspect identity bridge aliases before any fuzzy match
- 2026-05-25 Windsor 2026-05-25T14:08:00+01:00 — Sea Of Charm — HORSE_NAME_MISSING_IN_RESULT_COURSE — inspect identity bridge aliases before any fuzzy match
- 2026-05-25 Windsor 2026-05-25T14:08:00+01:00 — Free World — HORSE_NAME_MISSING_IN_RESULT_COURSE — inspect identity bridge aliases before any fuzzy match

Live VELO untouched. Shadow VELO untouched. No match rules relaxed.
