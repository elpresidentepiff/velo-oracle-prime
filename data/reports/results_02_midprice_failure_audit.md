# RESULTS-02: Mid-Price Failure Audit

REPORT_ONLY. MIDPRICE_MISSES_NOT_SUPPRESSED.

## Total mid_priced_won misses: 803

## By odds band
{'6-10': 312, '<4': 116, '4-6': 288, '10-16': 65, 'UNKNOWN': 22}

## By race type
{'unknown': 464, 'Flat': 217, 'NH Flat': 11, 'Chase': 47, 'Hurdle': 64}

## By going
{'unknown': 464, 'Good': 124, 'Standard': 66, 'Good To Firm': 15, 'Yielding': 21, 'Standard To Slow': 10, 'Firm': 5, 'Good To Yielding': 7, 'Good To Soft': 44, 'Soft To Heavy': 4, 'Soft': 32, 'Yielding To Soft': 11}

## By decision tier
{'A': 95, 'B': 262, 'C': 275, 'D': 60, 'unknown': 73, 'X': 38}

## Top courses (mid-price misses)
{'Southwell (AW)': 30, 'Bath': 21, 'Doncaster': 20, 'Kempton (AW)': 20, 'Wolverhampton (AW)': 20, 'Beverley': 19, 'Thirsk': 19, 'Pontefract': 16, 'Newmarket': 16, 'Lingfield (AW)': 16, 'Goodwood': 15, 'Haydock': 15, 'Catterick': 14, 'Musselburgh': 14, 'Ascot': 14, 'Yarmouth': 14, 'Chepstow': 14, 'Leicester': 14, 'Nottingham': 14, 'Windsor': 13, 'Ayr': 13, 'Hamilton': 13, 'Epsom': 13, 'Gowran Park (IRE)': 13, 'Ripon': 12}

## Course root cause hypotheses

### Southwell (AW) (n=30)
  - front_runner_bias_not_modelled
  - draw_bias_not_captured

### Bath (n=21)
  - uphill_finish_stamina_gap

### Doncaster (n=20)
  - no_clear_structural_cause_investigate

### Kempton (AW) (n=20)
  - front_runner_bias_not_modelled
  - draw_bias_not_captured

### Wolverhampton (AW) (n=20)
  - front_runner_bias_not_modelled
  - sharp_turns_tactical_speed_gap
  - draw_bias_not_captured

### Beverley (n=19)
  - front_runner_bias_not_modelled
  - uphill_finish_stamina_gap
  - sharp_turns_tactical_speed_gap
  - draw_bias_not_captured

### Thirsk (n=19)
  - front_runner_bias_not_modelled
  - sharp_turns_tactical_speed_gap
  - draw_bias_not_captured

### Pontefract (n=16)
  - uphill_finish_stamina_gap
  - sharp_turns_tactical_speed_gap

### Newmarket (n=16)
  - draw_bias_not_captured

### Lingfield (AW) (n=16)
  - front_runner_bias_not_modelled
  - draw_bias_not_captured

### Goodwood (n=15)
  - sharp_turns_tactical_speed_gap

### Haydock (n=15)
  - no_clear_structural_cause_investigate

### Catterick (n=14)
  - front_runner_bias_not_modelled
  - sharp_turns_tactical_speed_gap
  - draw_bias_not_captured

### Musselburgh (n=14)
  - front_runner_bias_not_modelled
  - sharp_turns_tactical_speed_gap
  - draw_bias_not_captured

### Ascot (n=14)
  - uphill_finish_stamina_gap

### Yarmouth (n=14)
  - front_runner_bias_not_modelled

### Chepstow (n=14)
  - no_clear_structural_cause_investigate

### Leicester (n=14)
  - uphill_finish_stamina_gap

### Nottingham (n=14)
  - no_clear_structural_cause_investigate

### Windsor (n=13)
  - front_runner_bias_not_modelled