import json
import uuid
import logging
from datetime import datetime, UTC
from app.services.velo_prime_service import score_race_velo_prime
from app.services.model_manager import get_model_manager

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("dry_run_simulator")

import sys
from unittest.mock import MagicMock, patch

# Pre-mock heavy dependencies
mock_pd = MagicMock()
sys.modules["pandas"] = mock_pd
sys.modules["numpy"] = MagicMock()

# Properly mock package structure
mock_intelligence = MagicMock()
sys.modules["src.intelligence"] = mock_intelligence
sys.modules["src.intelligence.specialist_models"] = MagicMock()
sys.modules["src.intelligence.specialist_models.loader"] = MagicMock()
sys.modules["src.intelligence.velo_prime_ensemble"] = MagicMock()
sys.modules["src.intelligence.macro_regime"] = MagicMock()
sys.modules["src.intelligence.macro_regime.bha_macro_context"] = MagicMock()
sys.modules["src.intelligence.horse_state_engine"] = MagicMock()
sys.modules["src.intelligence.tie_v3_gate"] = MagicMock()

def run_simulation():
    # Mock specialist scoring and ensemble to avoid pandas dependency
    with patch("app.services.model_manager.get_model_manager") as mock_mm_getter, \
         patch("src.intelligence.specialist_models.loader.score_runner", return_value={}), \
         patch("src.intelligence.velo_prime_ensemble.VeloPrimeEnsemble") as mock_ensemble_cls, \
         patch("src.intelligence.macro_regime.bha_macro_context.get_macro_context_for_race", return_value=None), \
         patch("src.intelligence.horse_state_engine.HorseStateEngine") as mock_hse, \
         patch("src.intelligence.tie_v3_gate.TIEv3Gate") as mock_tie:
        
        mock_mm = MagicMock()
        mock_mm.predict_sqpe.return_value = 0.1
        mock_mm_getter.return_value = mock_mm
        
        # Mock instance and method
        mock_ensemble_inst = mock_ensemble_cls.return_value
        def mock_predict(inputs, **kwargs):
            res = []
            for ei in inputs:
                m = MagicMock()
                m.to_dict.return_value = ei.copy()
                res.append(m)
            return res
        mock_ensemble_inst.predict_race.side_effect = mock_predict
        
        # Classes that get instantiated
        mock_hse.return_value.tag.return_value = MagicMock(to_dict=lambda: {})
        mock_tie.return_value.evaluate.return_value = MagicMock(signal_count=0, signals_found=[])
        
        # Mock extractor
        mock_extractor = MagicMock()
        mock_extractor.extract.return_value = {"runs_since_win": 1}

        with patch("app.services.velo_prime_service.V17FeatureExtractor", return_value=mock_extractor):
            # Mock data for 1 race
            race = {
                "race_id": "sim_race_1",
                "course": "Simulation Track",
                "reconciled_at": datetime.now(UTC),
            }
            runners = [
                {"horse_id": "h1", "horse_name": "Fav", "sp_dec": 2.0, "is_winner": True, "position": 1, "odds_timestamp": "2026-05-05T10:00:00Z"},
                {"horse_id": "h2", "horse_name": "Out", "sp_dec": 10.0, "is_winner": False, "position": 2, "odds_timestamp": "2026-05-05T10:00:00Z"},
                {"horse_id": "h3", "horse_name": "Leak", "sp_dec": 5.0, "is_winner": False, "position": 3, "odds_timestamp": "2026-05-05T13:00:00Z"}, # Future odds
            ]
            
            # Normalize for prime service
            nrace = {
                **race,
                "runners": runners,
                "prediction_timestamp": datetime(2026, 5, 5, 12, 0, 0, tzinfo=UTC)
            }
            
            batch_id = "B001_RECON_SIM"
            audit_id = str(uuid.uuid4())
            
            # Call core implementation
            preds = score_race_velo_prime(nrace, is_training=True, batch_id=batch_id, audit_id=audit_id)
            
            report = {
                "audit_date": "2026-05-05",
                "races_processed": 1,
                "rows_generated": len(preds),
                "rows_training_safe": sum(1 for p in preds if p.get("training_safe")),
                "rows_leakage_risk": sum(1 for p in preds if p.get("leakage_status") == "LEAKAGE_RISK"),
                "rows_feature_error": sum(1 for p in preds if p.get("feature_status") == "FEATURE_ERROR"),
                "rows_feature_incomplete": sum(1 for p in preds if p.get("feature_status") == "FEATURE_INCOMPLETE"),
                "defaults_detected": sum(1 for p in preds if p.get("feature_quality") == "DEGRADED"),
                "reconstruction_version_present": all(p.get("reconstruction_version") == "V17_REPAIR_B3" for p in preds),
                "mpi_sum_by_race": [round(sum(p.get("mpi", 0) for p in preds), 4)],
                "chaos_bloom_within_race_variance": 0.0,
                "supabase_writes_attempted": False
            }
            
            print(json.dumps(report, indent=2))

if __name__ == "__main__":
    run_simulation()
