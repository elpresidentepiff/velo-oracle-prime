# Racing Post Next Week Archive Runbook

Purpose: prepare the Racing Post archive book before VÉLØ scores independently.

## Daily Cadence

1. Capture racecard indexes for today, tomorrow, Tue, Wed, Thu, Fri, Sat, Big Race Entries, and US Racing.
2. Build racecard URL lists from captured index pages.
3. Capture race pages raw-first with the account collector.
4. Parse racecard injection artifacts.
5. Build horse profile URL lists from race pages.
6. Capture form/entries/stats/quotes/pedigree/sales/notes tabs where available.
7. Parse horse profiles.
8. Build horse dossiers.
9. Build race dossiers.
10. Build next-week watchlist.
11. Compare official VÉLØ predictions to archive context after predictions are locked.

## Commands

```bash
python scripts/ops/build_racing_post_racecard_url_list.py --date YYYY-MM-DD --target-date YYYY-MM-DD --execute
python scripts/ops/racing_post_account_collector.py capture --date YYYY-MM-DD --url-list data/racing_post_url_lists/rp_racecards_YYYY-MM-DD.txt --screenshot --headed --execute
python scripts/ops/parse_racing_post_racecard_capture.py --date YYYY-MM-DD --execute
python scripts/ops/build_racing_post_profile_url_list.py --date YYYY-MM-DD --tabs form entries stats quotes pedigree sales notes --execute
python scripts/ops/racing_post_account_collector.py capture --date YYYY-MM-DD --url-list data/racing_post_url_lists/rp_profiles_YYYY-MM-DD_all_tabs.txt --screenshot --headed --execute
python scripts/ops/parse_racing_post_account_capture.py --date YYYY-MM-DD --execute
python scripts/ops/build_rp_horse_dossiers.py --date YYYY-MM-DD --execute
python scripts/ops/build_rp_race_dossiers.py --date YYYY-MM-DD --execute
python scripts/ops/build_rp_next_week_watchlist.py --start-date YYYY-MM-DD --end-date YYYY-MM-DD --execute
```

## Boundary

Racing Post archive data does not change VÉLØ scoring. RPR remains archive-only. The archive advantage is preparation, contradiction intelligence, and operator context.
