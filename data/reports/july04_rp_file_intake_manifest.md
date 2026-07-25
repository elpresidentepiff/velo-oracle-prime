# July 4 2026 — RP File Intake Manifest (for Steven)

Drop RP source material for **2026-07-04** into:

```
data/racing_post_account_raw/2026-07-04/
```

This directory has been created and is **gitignored — local-only, never committed**. Nothing placed here reaches GitHub or Supabase automatically; it's raw material for Claude to build passports/racecards from in a later ingest step.

## What to put there

- RP racecard PDFs, if you're capturing via PDF export
- RP racecard HTML, if you're saving pages directly (View Source / Save Page As)
- Race-by-race pages if the card doesn't come as one combined file
- Any downloadable card format RP offers (CSV/JSON export, if available)

## Filename guidance

- Keep original filenames where possible — do not rename if you're not sure what a file is.
- If you do need to rename manually, include **course name and off time** in the filename (e.g. `brighton_1445.pdf`), so it's identifiable without opening it.
- No screenshots unless there is genuinely no other way to capture the page — screenshots can't be parsed as text and require manual re-typing.

## What happens next

Once files are in the dropzone, tell Claude and a separate mission (JULY04-RP-INGEST) will parse/merge them into a racecard, build passport coverage, and only then re-run the readiness gate. No scoring happens until that gate is green.
