# Live Sidecar Ablation Audit

- Generated at: `2026-05-15T01:29:53.152969Z`
- Latest verdicts: `1785`
- Matched races: `1238`
- Baseline matched top selections: `1105`
- Baseline SR / Frame / ROI: `0.2317 / 0.5312 / -0.0656`

| Component | Weight | Non-null | Avg contrib | Max contrib | VP>0.005 | VP>0.01 | Top changes | VP30 changes | High n | Matched high n | SR high | Frame high | ROI high | Avg SP high | Classification | Action |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| SQPE baseline anchor | 0.45 | 1238 | -0.0970 | 0.5279 | 1180 | 1146 | 307 | 396 | 311 | 261 | 0.2261 | 0.5594 | 0.1905 | 8.7810 | HELPS_FRAME | KEEP_LIVE_BUT_MONITOR |
| improvement_score | 0.12 | 1216 | 0.0130 | 0.1951 | 906 | 742 | 194 | 69 | 305 | 274 | 0.3285 | 0.6496 | -0.1757 | 6.2984 | OVERBET_RISK | BLOCK_CHANGE_PENDING_AUDIT |
| release_day_prob / release_window_score | 0.00 | 1216 | 0.0000 | 0.0000 | 0 | 0 | 0 | 0 | 1216 | 1087 | 0.2300 | 0.5299 | -0.0711 | 9.5314 | HOLD | BLOCK_CHANGE_PENDING_AUDIT |
| MDS | 0.10 | 1216 | 0.0190 | 0.3188 | 690 | 521 | 161 | 76 | 305 | 284 | 0.4120 | 0.7606 | -0.1001 | 3.6782 | OVERBET_RISK | BLOCK_CHANGE_PENDING_AUDIT |
| place_prob | 0.08 | 1216 | 0.0000 | 0.0000 | 0 | 0 | 0 | 0 | 305 | 286 | 0.3706 | 0.7587 | -0.0606 | 4.8382 | OVERBET_RISK | BLOCK_CHANGE_PENDING_AUDIT |
| comment_intel_score | 0.00 | 1216 | 0.0000 | 0.0000 | 0 | 0 | 0 | 0 | 1216 | 1087 | 0.2300 | 0.5299 | -0.0711 | 9.5314 | HOLD | BLOCK_CHANGE_PENDING_AUDIT |
| longshot_score | 0.07 | 1216 | 0.0000 | 0.0000 | 0 | 0 | 0 | 0 | 305 | 278 | 0.3237 | 0.6547 | -0.1514 | 6.6106 | OVERBET_RISK | BLOCK_CHANGE_PENDING_AUDIT |
