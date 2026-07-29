# COURSE-00 — External Source Field Map

Generated: 2026-07-01 01:17 UTC
Status: REPORT_ONLY

No external URL calls made in this audit. All source assessments are static knowledge.

---

## draw

- **Local status:** LOCAL_MISSING
- **BHA status:** SECTION_EXISTS_NOT_PROVEN
- **RP status:** SECTION_EXISTS_NOT_PROVEN
- **Login required:** yes_rp
- **Paywall risk:** no
- **Automation safe:** yes_with_rp_account
- **Notes:** RP racecard shows draw by runner. Already captured via rp_account_collector when full racecard parsed.

## course_draw_bias_direction

- **Local status:** STATIC_IN_COURSE_EYES
- **BHA status:** NOT_NEEDED
- **RP status:** NOT_NEEDED
- **Login required:** no
- **Paywall risk:** no
- **Automation safe:** yes_static_lookup
- **Notes:** Available in _COURSE_EYES registry. Shadow field only. No live scoring.

## pace_rating_front_runner

- **Local status:** LOCAL_MISSING
- **BHA status:** NOT_AVAILABLE
- **RP status:** PARTIAL_INCONSISTENT
- **Login required:** yes_rp
- **Paywall risk:** medium
- **Automation safe:** no_inconsistent_coverage
- **Notes:** RP pace ratings exist but coverage is inconsistent. Consider proxy from in-running comment post-race.

## course_speed_figure

- **Local status:** LOCAL_MISSING
- **BHA status:** NOT_AVAILABLE
- **RP status:** YES_BEHIND_PAYWALL
- **Login required:** yes_rp_premium
- **Paywall risk:** high
- **Automation safe:** no
- **Notes:** Timeform/Raceform speed figures behind paywall. Not automatable without subscription.

## trainer_course_win_rate

- **Local status:** PARTIAL_JTCD
- **BHA status:** SECTION_EXISTS_NOT_PROVEN
- **RP status:** SECTION_EXISTS_NOT_PROVEN
- **Login required:** yes_rp
- **Paywall risk:** no
- **Automation safe:** yes_with_rp_account
- **Notes:** JTC-D tables already built locally. RP trainer course stats exist as supplement.

## jockey_course_win_rate

- **Local status:** PARTIAL_JTCD
- **BHA status:** NOT_AVAILABLE
- **RP status:** SECTION_EXISTS_NOT_PROVEN
- **Login required:** yes_rp
- **Paywall risk:** no
- **Automation safe:** yes_with_rp_account
- **Notes:** JTC-D tables partially built. Supplement with RP jockey course stats.

## going

- **Local status:** PARTIAL_IN_SIGMA
- **BHA status:** YES_OFFICIAL_GOING
- **RP status:** YES_IN_RACECARD
- **Login required:** no_public
- **Paywall risk:** no
- **Automation safe:** yes
- **Notes:** Going string available in sigma.going where populated. Also in RP racecard without login.

## distance_furlongs

- **Local status:** PARTIAL_IN_SIGMA
- **BHA status:** YES
- **RP status:** YES_IN_RACECARD
- **Login required:** no_public
- **Paywall risk:** no
- **Automation safe:** yes
- **Notes:** sigma.distance field. Parse to furlongs float for distance bucket comparison.

## field_size

- **Local status:** PARTIAL_IN_SIGMA
- **BHA status:** NOT_NEEDED
- **RP status:** YES_IN_RACECARD
- **Login required:** no_public
- **Paywall risk:** no
- **Automation safe:** yes
- **Notes:** sigma.field_size where populated. RP racecard runner count as fallback.

## aw_surface_subtype

- **Local status:** STATIC_IN_COURSE_EYES
- **BHA status:** YES_OFFICIAL
- **RP status:** YES_IN_COURSE_PROFILE
- **Login required:** no
- **Paywall risk:** no
- **Automation safe:** yes_static_lookup
- **Notes:** Static knowledge in _COURSE_EYES. Rarely changes. Fibresand/Polytrack/Tapeta.

## race_type

- **Local status:** PARTIAL_IN_SIGMA
- **BHA status:** YES
- **RP status:** YES_IN_RACECARD
- **Login required:** no_public
- **Paywall risk:** no
- **Automation safe:** yes
- **Notes:** sigma.race_type where populated. Flat/Hurdle/Chase distinction important for model baseline.

## in_running_position

- **Local status:** LOCAL_MISSING
- **BHA status:** NOT_AVAILABLE
- **RP status:** PARTIAL_POST_RACE
- **Login required:** yes_rp
- **Paywall risk:** no
- **Automation safe:** partial_post_race_only
- **Notes:** Only available post-race from RP result comments. Not prospective. Shadow backfill only.
