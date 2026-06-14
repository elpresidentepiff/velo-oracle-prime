# Final Report: Rolling JTC-D V1 Rebuild

## A. Source Audit Summary
- **Primary Source:** `data/new_build/training/core_v0_historical_dataset.parquet`
- **Secondary Source (for class_num):** `data/raceform_v17_features.parquet`
- **Date Range:** 2015-01-01 to 2025-07-05
- **Rows:** 1,162,031
- **Columns Available:** date, trainer, jockey, course, dist_f, going_code, won, class_num.

## B. Rows Built
- **Total Sidecar Rows:** 1,162,031
- **Date Range:** 2015-01-01 to 2025-07-05
- **Format:** Parquet sidecar (`race_id`, `horse`, `as_of_date`, + features)

## C. Coverage per Key (w365)
| Key | LTD Coverage | w365 Has Sample (n>=5) |
|-----|--------------|------------------------|
| tj (Trainer-Jockey) | 100.00% | 15.65% |
| tc (Trainer-Course) | 100.00% | 29.83% |
| td (Trainer-Distance) | 100.00% | 61.34% |
| jc (Jockey-Course) | 100.00% | 34.61% |
| jd (Jockey-Distance) | 100.00% | 65.48% |
| tg (Trainer-Going) | 100.00% | 58.11% |
| jg (Jockey-Going) | 100.00% | 61.39% |
| th (Trainer-Class) | 100.00% | 68.21% |
| tf (Trainer-Form) | 100.00% | 85.34% |

## D. Leakage Tests
| Test ID | Description | Status |
|---------|-------------|--------|
| T1 | No same-day data | **PASS** |
| T2 | 14d window boundary | **PASS** |
| T3 | 365d window excludes older | **PASS** |
| T4 | Lifetime-to-date strictly prior | **PASS** |
| T5 | Trainer_jockey key presence | **PASS** |
| T6 | Trainer_course key presence | **PASS** |
| T7 | Null safety (trainer) | **PASS** |
| T8 | Null safety (going) | **PASS** |
| T9 | No RPR column present | **PASS** |
| T10 | No SP column present | **PASS** |
| T11 | has_sample flag (n=5) | **PASS** |

## E. Sidecar Metrics (Held-out Test)
| Metric | Config A (Base) | Config B (Base+JTCD) | Config C (JTCD Only) |
|--------|-----------------|----------------------|----------------------|
| AUC | 0.6913 | 0.6903 | 0.5079 |
| Brier | 0.0766 | 0.0767 | 0.0906 |
| Top-pick SR | 23.93% | 23.91% | 11.83% |
| Top-3 Frame | 49.33% | 49.23% | 29.21% |

## F. Classification Verdict
**Verdict:** `ROLLING_JTCD_NO_LIFT`
- The rolling JTC-D features provided no performance lift over the Challenger V1 base.
- Config C (JTCD Only) performance (AUC 0.5079) confirms that the features on their own are essentially noise.

## G. Observation on Previous Leakage
The previous version of JTC-D (non-rolling) showed an AUC of ~0.83. This version, which strictly enforces `historical_date < target_race_date`, shows almost zero signal. This empirically confirms that the apparent strength of the original JTC-D sidecar was almost entirely derived from **temporal leakage** (using future wins to predict current races).

## H. Recommendations
1. **Accept the Loss:** The simple rolling averages of trainer/jockey combos do not provide predictive power in a temporally safe environment for this model configuration.
2. **Feature Engineering:** Consider more complex features (e.g., ELO ratings for trainers/jockeys, or adjusting for strength of field) rather than raw win rates.
3. **RP Stats Scraping:** While the rolling local data failed to provide lift, RP statistics pages might contain different aggregations (e.g. profitable trainer/jockey angles) that we haven't captured here. However, based on this ablation, basic combo win rates are not worth the scraping effort for New Build V1.

**Next recommended action:** Abandon JTC-D V1 and focus on other sidecars (e.g., Pedigree or Advanced Form).
