# Playbook G V2 Ablation Dry Run

- Eligible races / runners: `1697 / 18575`
- Best model by log loss: `ratings_plus_doctrine`
- Best model by Brier: `ratings_only`
- Best model by top-1: `ratings_plus_doctrine`
- Best model by top-3: `market_plus_ratings`
- Doctrine improves market + ratings: `{'pass': False, 'market_plus_ratings_test': {'log_loss': 1.4816467492541938, 'brier': 0.0766130183864493, 'top1': 0.42105263157894735, 'top3': 0.7894736842105263, 'ece': 0.020558192369501044, 'market_rank_lift': 0.47368421052631576, 'n_races': 114, 'n_runners': 1014}, 'market_plus_ratings_plus_doctrine_test': {'log_loss': 1.5070779508442058, 'brier': 0.0773362892349502, 'top1': 0.40350877192982454, 'top3': 0.7456140350877193, 'ece': 0.021632245112657548, 'market_rank_lift': 0.35964912280701755, 'n_races': 114, 'n_runners': 1014}, 'log_loss_delta': 0.025431201590011998, 'brier_delta': 0.0007232708485009065}`
- HK failure fixed or reduced: `{'pass': True, 'v1_hk_market_log_loss': 2.004304, 'v1_hk_candidate_log_loss': 2.413058, 'v1_hk_gap': 0.40875400000000006, 'v2_hk_market_log_loss': 2.0043041687607603, 'v2_hk_mrd_log_loss': 1.7555038268052852, 'v2_hk_gap': -0.24880034195547518}`
- FR remains positive: `{'pass': True, 'market_log_loss': 1.6292902317692781, 'mrd_log_loss': 1.4166241349835713}`
- 2025 unstable: `{'status': True, 'market': {'log_loss': 1.6319770727552103, 'brier': 0.07327465464143125, 'top1': 0.46153846153846156, 'top3': 0.7307692307692307, 'ece': 0.027429739047059663, 'market_rank_lift': 0.0, 'n_races': 26, 'n_runners': 244}, 'mrd': {'log_loss': 1.5780139330761904, 'brier': 0.06514423291156499, 'top1': 0.5, 'top3': 0.7692307692307693, 'ece': 0.02895714165363716, 'market_rank_lift': 0.34615384615384615, 'n_races': 26, 'n_runners': 244}}`
- Final verdict: `FAIL`

## Overall Test Metrics
- `market_only`: log loss `1.725229`, Brier `0.085483`, top-1 `35.96%`, top-3 `69.30%`, ECE `0.01758`
- `ratings_only`: log loss `1.501237`, Brier `0.074551`, top-1 `46.49%`, top-3 `78.07%`, ECE `0.03932`
- `doctrine_only`: log loss `2.107233`, Brier `0.097886`, top-1 `13.16%`, top-3 `39.47%`, ECE `0.00498`
- `market_plus_ratings`: log loss `1.481647`, Brier `0.076613`, top-1 `42.11%`, top-3 `78.95%`, ECE `0.02056`
- `market_plus_doctrine`: log loss `1.651119`, Brier `0.083357`, top-1 `33.33%`, top-3 `70.18%`, ECE `0.01901`
- `ratings_plus_doctrine`: log loss `1.481028`, Brier `0.077519`, top-1 `50.88%`, top-3 `78.07%`, ECE `0.03593`
- `market_plus_ratings_plus_doctrine`: log loss `1.507078`, Brier `0.077336`, top-1 `40.35%`, top-3 `74.56%`, ECE `0.02163`
- `hk_only_diagnostic`: log loss `1.071064`, Brier `0.050025`, top-1 `51.72%`, top-3 `93.10%`, ECE `0.04583`
- `fr_only_diagnostic`: log loss `1.421238`, Brier `0.085019`, top-1 `45.24%`, top-3 `80.95%`, ECE `0.03503`
- `jurisdiction_specific_calibration`: log loss `1.514801`, Brier `0.078542`, top-1 `38.60%`, top-3 `77.19%`, ECE `0.02936`
