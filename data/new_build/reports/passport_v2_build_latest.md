# Passport V2 Build Report

## A. Column Verification
The exact column mappings and dtypes in `passport_features.parquet` were confirmed:
- `pp_career_runs`: int64
- `pp_win_rate`: float64
- `pp_place_rate`: float64
- `pp_days_since_last`: float64
- `pp_layoff`: float64
- `pp_avg_sp_last5`: float64
- `pp_jockey_continuity`: float64
- `pp_course_seen`: float64
- `pp_or_change_3`: float64
- `pp_class_moved_up`: float64
- `pp_class_moved_down`: float64

## B. JSONL Rebuild Result
- **Total Passports:** 1,852
- **V2 Fields Present:** Yes (`win_rate_last3`, `last_run_date`, `beaten_margin_slope`, etc.)

## C. New V2 Fields & Null Rates
Across 1,852 passports:
| Field | Population | Null Rate | Notes |
|---|---|---|---|
| `last_run_date` | 98.5% | 1.5% | Missing only if no parseable dates in history |
| `win_rate_last3` | 100.0% | 0.0% | Defaults to 0.0 if fewer than 3 runs |
| `beaten_margin_slope` | 80.4% | 19.6% | Requires at least 3 runs with margin data |
| `position_trend` | 81.0% | 19.0% | Requires at least 4 runs with position data |
| `career_wins_flat` | 100.0% | 0.0% | |
| `career_wins_aw` | 100.0% | 0.0% | |

## D. Lookup Module
- **File:** `new_build_velo/passport_lookup.py`
- **Signatures:**
  - `lookup_passport_features(horse_rp_uid, horse_name, as_of_date, ...)`
  - `batch_lookup(runners, as_of_date)`

## E. Coverage Logger
- **Class:** `PassportCoverageLogger`
- **Report Path:** `data/new_build/reports/passport_coverage_latest.json`
- **Tracks:** Hits, Misses, Coverage %, and missed horse names (max 50).

## F. Test Results
All 10 tests in `tests/test_passport_v2.py` passed:
- **T1:** V2 fields exist on rebuilt passport — **PASS**
- **T2:** Dynamic days_since — **PASS**
- **T3:** Null features for unknown horse — **PASS**
- **T4:** pp_layoff encodes correctly — **PASS**
- **T5:** batch_lookup returns coverage — **PASS**
- **T6:** No RPR keys in output — **PASS**
- **T7:** No SP keys in output — **PASS**
- **T8:** win_rate_last3 uses only last 3 runs — **PASS**
- **T9:** beaten_margin_slope direction — **PASS**
- **T10:** Passport name fallback — **PASS**

## G. V2 Population Statistics
- **last_run_date populated:** 98.5%
- **beaten_margin_slope populated:** 80.4%
- **win_rate_last3 populated:** 81.0% (count of horses with career_runs >= 3)

## H. Next Recommended Action
Integrate the `batch_lookup` into the `new_build` scoring pipeline to enable live passport features. The coverage instrumentation shows that the bank is ready for use, though continued growth will improve hit rates.
