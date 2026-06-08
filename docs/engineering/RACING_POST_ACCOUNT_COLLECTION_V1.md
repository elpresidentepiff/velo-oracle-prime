# Racing Post Account Collection V1

## Purpose

Use an operator-owned Racing Post account to capture pages the operator can view,
without using a Racing Post API and without storing credentials in VELO.

This is a raw capture lane. Parsing and scoring are separate.

## Guardrails

- No usernames or passwords in code.
- No proxy rotation.
- No CAPTCHA bypass.
- No hidden endpoint mining.
- No bulk crawling.
- No live scoring writes.
- No Telegram.
- No Playbook G or learning state mutation.
- Raw first, parse later.

Racing Post terms pages describe that site/subscription use is governed by their
user terms and Racing Post+ terms. Treat captured content as licensed/account
material and keep it inside VELO unless we have explicit redistribution rights.

References:

- https://help.racingpost.com/hc/en-us/articles/208996085-Terms-and-conditions
- https://help.racingpost.com/hc/en-us/articles/211977465-Racing-Post-services-terms-and-conditions

## Setup

Install optional tooling:

```bash
source venv/bin/activate
pip install -r requirements_scrapegraph.txt
python -m playwright install chromium
```

Create a manual login browser profile:

```bash
python scripts/ops/racing_post_account_collector.py init-login --execute
```

Log in inside the opened browser. Press Enter in the terminal after login.

On this Windows workstation the repo venv is a WSL/Linux venv, so run the live
collector commands from WSL:

```powershell
wsl bash -lc "cd /mnt/c/Users/puror/velo-oracle-prime && source venv/bin/activate && python scripts/ops/racing_post_account_collector.py init-login --execute"
```

## Capture URLs

Create a URL list, for example:

```text
# data/racing_post_url_lists/2026-05-24.txt
https://www.racingpost.com/racecards/...
https://www.racingpost.com/racecards/...
```

Dry run:

```bash
python scripts/ops/racing_post_account_collector.py capture \
  --date 2026-05-24 \
  --url-list data/racing_post_url_lists/2026-05-24.txt
```

Execute:

```bash
python scripts/ops/racing_post_account_collector.py capture \
  --date 2026-05-24 \
  --url-list data/racing_post_url_lists/2026-05-24.txt \
  --screenshot \
  --headed \
  --execute
```

WSL form:

```powershell
wsl bash -lc "cd /mnt/c/Users/puror/velo-oracle-prime && source venv/bin/activate && python scripts/ops/racing_post_account_collector.py capture --date 2026-05-24 --url-list data/racing_post_url_lists/2026-05-24.txt --screenshot --headed --execute"
```

Raw output:

```text
data/racing_post_account_raw/YYYY-MM-DD/
  manifest.json
  *.html
  *.json
  *.png
```

Each per-page metadata file records `source_url`, `final_url`, `http_status`,
`url_sha256`, `html_sha256`, capture timestamps, and raw file paths.

## Next Parser Lane

After raw capture, parse supported account pages:

```bash
python scripts/ops/parse_racing_post_account_capture.py \
  --date 2026-05-24 \
  --execute
```

Output:

```text
data/racing_post_account_parsed/YYYY-MM-DD/horse_profiles.json
```

The parser currently supports horse profile pages that expose
`window.PRELOADED_STATE`.

For fallback extraction, use `scripts/ops/scrapegraph_local_extract.py` or the
existing RacingPostAdapter parser to extract:

- race time
- course
- race name
- horse
- Spotlight
- Postdata
- Topspeed
- RP Ratings
- OR/TS/RPR fields when present

All extracted rows must carry:

- `source = racing_post_account_capture`
- `raw_source_file`
- `capture_date`
- `requires_audit = true`
