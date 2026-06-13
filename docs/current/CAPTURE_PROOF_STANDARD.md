# VÉLØ Hardened Capture Proof Standard

**Date:** 2026-06-10
**Status:** ACTIVE
**Classification:** OPERATIONAL_SAFETY

## 1. Purpose

The Capture Proof layer exists to eliminate "blind scoring" in VÉLØ. It ensures that every browser-based data capture attempt generates verifiable evidence (screenshots, DOM snapshots, metadata) before any downstream processing (parsing, scoring, training) is permitted.

## 2. Requirements

Every capture operation must produce the following artifacts in `data/capture_proof/YYYY-MM-DD/`:

- **Screenshot (PNG):** A visual capture of the page as rendered by the browser.
- **DOM Snapshot (HTML):** The raw or sanitized HTML content of the page.
- **Metadata (JSON):** Machine-readable details of the capture (URL, timestamp, status, headers).
- **Download Manifest (JSON):** A list of files expected vs. files actually retrieved.

## 3. Explicit Failure States

Silent failures are strictly forbidden. The system must report one of the following states:

- `CAPTURE_OK`: All URLs captured, login verified, DOM populated.
- `CAPTURE_PARTIAL`: Some URLs failed or login status indeterminate.
- `CAPTURE_NO_BROWSER`: Playwright/Chromium failed to launch.
- `CAPTURE_SESSION_MISSING`: Browser profile exists but session cookies are invalid.
- `CAPTURE_LOGIN_UNKNOWN`: Page reached but login indicators not detected.
- `CAPTURE_DOM_EMPTY`: Page reached but returned no content.
- `CAPTURE_SCREENSHOT_FAILED`: HTML captured but visual proof failed.
- `CAPTURE_DOWNLOAD_MISSING`: Manifest expected a file (HTML/PNG) that is missing from disk.
- `CAPTURE_TIMEOUT`: Browser timed out during navigation.
- `CAPTURE_BLOCKED`: Bot detection or IP block detected.
- `CAPTURE_UNKNOWN_ERROR`: Catch-all for unexpected exceptions.

## 4. Redaction Rules

To protect system integrity and privacy, the following redaction rules are active:

- **No Secrets:** Never save raw cookies or local storage tokens in DOM snapshots.
- **No Credentials:** Never print API keys or passwords to logs or reports.
- **Email Masking:** Common email patterns must be redacted from HTML previews.
- **Marking:** If any artifact requires manual redaction, it must be flagged with `redaction_applied: true`.

## 5. Race-Day Chain Integration

Capture Proof is an **Evidence Layer**, not a scoring layer. It sits between raw capture and dry-run:

1. `capture` (raw retrieval)
2. **`capture proof` (evidence verification) ← YOU ARE HERE**
3. `RPDC attach preflight` (data hydration)
4. `dry-run` (safe scoring)
5. `operator approval` (manual gate)
6. `real run` (final scoring)

## 6. Usage

Manually verify capture integrity:

```bash
python scripts/ops/capture_proof.py --date 2026-06-11 --source rp --mode proof-only
```

Audit an existing capture run:

```bash
python scripts/ops/capture_proof.py --date 2026-06-11 --source rp --mode audit --manifest data/racing_post_account_raw/2026-06-11/manifest.json
```

---
*NO NEW LOOP BUILD APPROVED YET — INVENTORY FIRST.*
