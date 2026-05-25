# Racing Post Archive Database Status

Updated: 2026-05-25

## Policy

Racing Post account data is archive/context only. It may be captured, parsed, and stored for historical intelligence, but it must not feed VÉLØ scoring, VP, improvement score, model inputs, router, staking, Telegram picks, Playbook G, or live learning.

RPR policy is locked as `RPR_ARCHIVE_ONLY_EXCLUDED_FROM_VELO`.

## Current Capture Status

| Area | Status | Notes |
| --- | --- | --- |
| Today racecards | In progress | 2026-05-25 race pages captured and parsed. |
| Tomorrow racecards | In progress | 2026-05-26 race pages captured and parsed. |
| Tue-Sat racecards | In progress | 2026-05-27 through 2026-05-30 index/race pages captured where available. |
| Horse profiles | In progress | 2026-05-25 form profile URLs captured for 59 runners. |
| All profile tabs | Prepared | Form/entries/stats/quotes/pedigree/sales/notes URL list prepared for 2026-05-25. |
| US Racing | Started | US Racing index captured; runner/profile extraction remains pending. |
| Big Race Entries | Pending | Add to next capture batch. |

## Parsed Archive Outputs

| Output | Purpose | Scoring Impact |
| --- | --- | --- |
| `data/racing_post_account_parsed/YYYY-MM-DD/racecard_injection.json` | Archive-only race/runner context from RP race pages. | None |
| `data/racing_post_account_parsed/YYYY-MM-DD/horse_profiles.json` | Archive-only horse profile context. | None |
| `data/racing_post_account_parsed/YYYY-MM-DD/horse_dossiers.json` | Archive-only horse intelligence dossiers. | None |
| `data/racing_post_account_parsed/YYYY-MM-DD/race_dossiers.json` | Archive-only race shape/context dossiers. | None |

## Current Parsed Counts

| Date | Races | Runners | Horse Dossiers | Race Dossiers | Notes |
| --- | ---: | ---: | ---: | ---: | --- |
| 2026-05-25 | 8 | 59 | 59 | 8 | Today archive parsed. |
| 2026-05-26 | 8 | 70 | 70 | 8 | Tomorrow archive parsed. |
| 2026-05-27 | 7 | 91 | 91 | 7 | Future archive parsed. |
| 2026-05-28 | 7 | 150 | 146 | 7 | Duplicate/blank runner identities deduped in horse dossiers. |
| 2026-05-29 | 7 | 109 | 106 | 7 | Duplicate/blank runner identities deduped in horse dossiers. |
| 2026-05-30 | 0 | 0 | 0 | 0 | Page captured, runner payload not available/declared enough yet. |

Totals currently parsed: 37 races, 479 runners, 472 horse dossiers, 37 race dossiers.

The next-week watchlist currently contains 472 archive-only items.

## RPR Boundary

RPR is stored only as `rp_rpr_archive_only` in RP archive outputs. Every archive race/runner payload must keep:

- `trust_policy = ARCHIVE_CONTEXT_ONLY_NOT_SCORING`
- `velo_scoring_allowed = false`
- `rpr_policy = RPR_ARCHIVE_ONLY_EXCLUDED_FROM_VELO`
- `rp_rpr_velo_allowed = false`

The guard script is:

```bash
python scripts/audit_rpr_scoring_boundary.py
```

Expected verdict:

```text
PASS_RPR_ARCHIVE_ONLY
```

## Next Capture Command

Use the logged-in account profile and local raw-first collector only:

```bash
python scripts/ops/racing_post_account_collector.py capture --date YYYY-MM-DD --url-list data/racing_post_url_lists/LIST.txt --screenshot --headed --execute
```

No unauthorized scraping. No credentials in code. No scoring integration.
