# RP Profile Passport Feature Matrix
Generated: 2026-06-05T00:31:50.640742Z

## Summary
- **Passports converted**: 6168
- **Feature path**: `C:\Users\puror\velo-oracle-prime\data\new_build\features\rp_profile_passport_features_latest.parquet`
- **Classification**: `PASSPORT_FEATURE_BRIDGE_READY`
- **RPR violations**: 0
- **Current-card usability**: 5966 / 6891 (86.58%)

## Feature Coverage
| Feature | Coverage |
|---|---:|
| `pp_career_runs` | 100.0% |
| `pp_win_rate` | 100.0% |
| `pp_place_rate` | 100.0% |
| `pp_days_since_last` | 0.0% |
| `pp_layoff` | 0.0% |
| `pp_avg_sp_last5` | 81.73% |
| `pp_jockey_continuity` | 100.0% |
| `pp_course_seen` | 0.0% |
| `pp_or_change_3` | 73.54% |
| `pp_class_moved_up` | 58.38% |
| `pp_class_moved_down` | 58.38% |

## Schema Match Notes
- Historical passport model columns present: `True`
- Model feature columns present: `11` / 11
- Race-level join key available: `False`
- `pp_course_seen` is intentionally blank at profile level because it needs the target race course.
- No RPR field is emitted as a model-ready feature.