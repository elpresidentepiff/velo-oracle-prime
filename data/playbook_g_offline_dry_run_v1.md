# Playbook G Offline Dry-Run v1

Generated: `2026-04-27T11:59:55.219595+00:00`

Strictly offline research only. No live deployment, no Playbook E, no production model promotion, no HFS mutation, and no `training_eligible` changes were made.

## Scope
- Eligible races: `1697`
- Eligible runners: `18575`
- Split counts: `train=1060 races / 11757 runners`, `validation=523 / 5804`, `test=114 / 1014`

## Guards
- Leakage audit: `pass`
- Outcome-field exclusion audit: `pass`
- Feature vector: `37` only, NaN=`0`, inf=`0`

## Out-of-Time Test Benchmarks
- Market baseline: `log_loss=1.725229, brier=0.085483, top1=0.359649, top3=0.692982`
- SP-rank baseline: `log_loss=1.804541, brier=0.088262`
- Market-only logistic: `log_loss=1.717572, brier=0.085573, top1=0.315789, top3=0.692982`
- Candidate: `log_loss=1.607494, brier=0.072212, top1=0.482456, top3=0.833333`

## Verdict
- `FAIL`
- Candidate does not clear the strict beyond-market gate on the out-of-time test.

## Notes
- Candidate vs market lift (test): `{"brier_score_delta": -0.013270813117931213, "ece_delta": -0.009689094234245934, "top_1_hit_rate_delta": 0.12280701754385964, "top_3_containment_delta": 0.14035087719298245, "winner_multiclass_log_loss_delta": -0.11773507158045682}`
- Candidate vs market-only logistic lift (test): `{"brier_score_delta": -0.013360804156012637, "ece_delta": -0.004673170275990891, "top_1_hit_rate_delta": 0.16666666666666669, "top_3_containment_delta": 0.14035087719298245, "winner_multiclass_log_loss_delta": -0.11007757239483351}`
- Overfit warning: `{"relative_brier_increase_test_vs_train": 0.6812046069310375, "relative_brier_increase_validation_vs_train": 0.30197810013194837, "relative_log_loss_increase_test_vs_train": 0.6350321880802616, "relative_log_loss_increase_validation_vs_train": 0.4461606321434031, "status": "high"}`
- ROI research only: `{"0.03": {"bets": 99, "hit_rate": 0.5151515151515151, "profit_units": 92.85555599999999, "roi": 0.937934909090909, "turnover_units": 99.0, "wins": 51}, "0.05": {"bets": 90, "hit_rate": 0.5444444444444444, "profit_units": 98.75555599999998, "roi": 1.0972839555555554, "turnover_units": 90.0, "wins": 49}, "0.08": {"bets": 73, "hit_rate": 0.6027397260273972, "profit_units": 97.35555599999999, "roi": 1.3336377534246575, "turnover_units": 73.0, "wins": 44}}`
