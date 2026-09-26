# Playbook G Full-Field Benchmark

- Classification: **ANALYSIS ONLY**
- Races: **2245**; runners: **22203**
- Pick changes: **28 (1.2%)**
- Readout: **INSUFFICIENT_PICK_CHANGES**
- Calibration truth: **BASE_WORSE_THAN_UNIFORM_PROPER_SCORES**

## Metrics

| Variant | N races | Top-1 | Top-3 | Log loss | Brier | Flat ROI | ECE |
|---|---:|---:|---:|---:|---:|---:|---:|
| Base | 2245 | 25.48% | 54.65% | 2.3312 | 0.8877 | -12.31% | 0.0393 |
| Playbook G | 2245 | 25.66% | 55.32% | 2.3285 | 0.8873 | -11.78% | 0.0387 |
| Market implied | 1437 | 30.20% | 61.10% | 1.9339 | 0.8107 | -12.65% | 0.0013 |

## Uniform probability check

Uniform field probabilities: log loss **2.2047**, Brier **0.8795**. Lower is better.

## Same-race market comparison (1437 races)

| Variant | Top-1 | Log loss | Brier | Flat ROI | ECE |
|---|---:|---:|---:|---:|---:|
| Base | 24.29% | 2.3988 | 0.9041 | -13.39% | 0.0487 |
| Playbook G | 24.57% | 2.3945 | 0.9034 | -12.56% | 0.0478 |
| Market implied | 30.20% | 1.9339 | 0.8107 | -12.65% | 0.0013 |

## Safety and interpretation

The harness selects the latest snapshot strictly before exact off time, evaluates every runner, renormalises probabilities inside each race, and evolves a fresh disposable state only after the entire day's forecasts have been evaluated. It does not authorize promotion or change live scoring.
