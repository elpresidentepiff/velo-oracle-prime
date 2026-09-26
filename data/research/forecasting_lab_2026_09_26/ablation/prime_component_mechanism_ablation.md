# Prime Component Mechanism Ablation

- Classification: **ANALYSIS ONLY**
- Locked selection: **sqpe_plus_mds**
- Holdout readout: **RECONSTRUCTED_SUBSET_BEATS_STORED_G_ON_HOLDOUT**
- Reconstruction excludes macro modifiers; stored Base/G remain direct comparison anchors.

## Untouched holdout

| Variant | Top-1 | Top-3 | Log loss | Brier | ROI | Winner rank | Pairwise |
|---|---:|---:|---:|---:|---:|---:|---:|
| stored_base | 23.19% | 51.76% | 2.1288 | 0.8536 | -20.00% | 4.29 | 64.35% |
| stored_g | 23.19% | 52.77% | 2.1223 | 0.8522 | -20.00% | 4.24 | 64.80% |
| sqpe_only | 23.53% | 53.11% | 2.1552 | 0.8511 | -18.69% | 4.21 | 65.10% |
| sqpe_plus_improvement | 23.36% | 51.76% | 2.1411 | 0.8558 | -19.11% | 4.29 | 64.31% |
| sqpe_plus_mds | 23.36% | 52.94% | 2.1162 | 0.8501 | -19.48% | 4.19 | 65.22% |
| sqpe_plus_improvement_mds | 23.19% | 51.76% | 2.1362 | 0.8543 | -20.00% | 4.30 | 64.27% |

## Model versus late market

On 326 disagreements, the model pick won 42 and the market pick won 82; neither won 202.

## Interpretation

Every beta was fitted on the early block, the variant was selected on the middle block, and the final block was opened only after lock. These counterfactuals diagnose score composition; they do not authorize a live weight change or model promotion.
