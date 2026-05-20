# HARDCODED PATH REPAIR QUEUE

| File | Line | Current Path | Recommended Replacement | Risk | Priority |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `app/ml/vetp_enhanced_predictor.py` | 13 | `/home/ubuntu/velo-oracle/models/sqpe_v15/sqpe_v15.pkl` | `Path(__file__).resolve().parents[2] / "models" / "sqpe_v15" / "sqpe_v15.pkl"` | Medium | P2 |
| `app/ml/vetp_enhanced_predictor.py` | 14 | `/home/ubuntu/velo-oracle/data/vetp_memory.db` | `Path(__file__).resolve().parents[2] / "data" / "vetp_memory.db"` | Medium | P2 |
| `app/scrapers/racing_post_scraper.py` | 45 | `/home/ubuntu/velo_races_{today}.json` | `Path.home() / f"velo_races_{today}.json"` or temp dir | Low | P2 |
| `src/features/armory_v11.py` | 655 | `/home/ubuntu/velo-oracle/velo_racing.db` | `Path(__file__).resolve().parents[2] / "velo_racing.db"` | Medium | P2 |
| `src/train_model.py` | 245 | `/home/ubuntu/velo-oracle-prime/models` | `Path(__file__).resolve().parent.parent / "models"` | Low | P2 |
| `src/velo_pipeline.py` | 38 | `/home/ubuntu/velo-oracle-prime/models/velo_predictor_v1.pkl` | `Path(__file__).resolve().parent.parent / "models" / "velo_predictor_v1.pkl"` | Medium | P2 |
| `tests/acceptance_gates.py` | 22 | `/home/ubuntu/velo-oracle-prime` | `Path(__file__).resolve().parents[1]` | Low | P2 |

*Note: Paths in `archive/dead_scripts/` are excluded from high-priority repair.*
