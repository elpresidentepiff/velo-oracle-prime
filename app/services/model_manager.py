"""
VÉLØ Oracle - Model Manager
Load and manage ML models for prediction
"""
import math
import re
from pathlib import Path
from typing import Dict, Any, Optional
import logging
import numpy as np

logger = logging.getLogger(__name__)


class ModelManager:
    """Manage loading and caching of VÉLØ prediction models"""
    
    def __init__(self):
        self.models: Dict[str, Any] = {}
        self.model_versions: Dict[str, str] = {}
        self._initialized = False
    
    def initialize(self) -> bool:
        """Initialize and load all models"""
        try:
            logger.info("Initializing VÉLØ Model Manager...")
            
            # Load all models
            self.models["sqpe"] = self.load_sqpe()
            self.models["trainer_intent"] = self.load_trainer_intent()
            self.models["longshot"] = self.load_longshot()
            self.models["benter_overlay"] = self.load_benter_overlay()
            
            self._initialized = True
            logger.info(f"Model Manager initialized with {len(self.models)} models")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize Model Manager: {e}")
            return False
    
    def load_all_models(self) -> Dict[str, Any]:
        """Load all VÉLØ models"""
        if not self._initialized:
            self.initialize()
        return self.models
    
    # ── v17 feature column order (must match training) ────────────────────
    V16_FEATURES = [
        "sp_dec", "log_sp", "implied_prob",
        "dist_f", "going_code", "is_aw",
        "class_num", "wgt_lbs",
        "or_num", "rpr_num", "ts_num",
        "or_vs_field", "rpr_vs_field",
        "field_size", "draw_num", "draw_pct",
        "age_num", "sp_rank", "is_fav",
    ]
    V17_DOCTRINE_FEATURES = [
        "runs_since_win", "runs_since_place", "runs_since_mkt_support",
        "curr_or_minus_last_win_or", "curr_or_minus_best_or",
        "mark_compression_score", "release_window_score",
        "course_fit_score", "going_fit_score", "distance_fit_score",
        "quiet_run_score", "trainer_timing_score", "jockey_switch_intent",
        "odds_resilience_score", "odds_contraction_score",
        "decoy_support_flag", "setup_run_flag", "cash_run_flag",
    ]
    ALL_V17_FEATURES = V16_FEATURES + V17_DOCTRINE_FEATURES  # 37

    def load_sqpe(self) -> Any:
        """Load SQPE v17 model from disk using joblib/pickle."""
        import joblib
        model_path = Path("models/sqpe_v17/sqpe_v17.pkl")
        if not model_path.exists():
            # Fallback to v16 if v17 not present
            model_path = Path("models/sqpe_v16/sqpe_v16.pkl")
        if not model_path.exists():
            logger.warning("No SQPE model found at models/sqpe_v17/ or models/sqpe_v16/ — returning None")
            return None
        model = joblib.load(model_path)
        version = "v17" if "v17" in str(model_path) else "v16"
        self.model_versions["sqpe"] = version
        logger.info(f"SQPE {version} loaded from {model_path}")
        return model
    
    def load_trainer_intent(self) -> Dict[str, Any]:
        """
        Load Trainer Intent Engine (TIE) model
        
        Returns:
            Model stub with metadata
        """
        logger.info("Loading Trainer Intent Engine...")
        
        model_stub = {
            "name": "Trainer Intent Engine",
            "version": "v8.2",
            "type": "neural_network",
            "features": [
                "trainer_intent_factor",
                "gear_changes",
                "jockey_booking",
                "equipment_changes",
                "trial_performance"
            ],
            "signal_strength_threshold": 0.75,
            "performance": {
                "precision": 0.82,
                "recall": 0.71,
                "f1_score": 0.76
            },
            "status": "stub",
            "loaded": True
        }
        
        self.model_versions["trainer_intent"] = model_stub["version"]
        logger.info(f"Trainer Intent Engine {model_stub['version']} loaded (stub)")
        
        return model_stub
    
    def load_longshot(self) -> Dict[str, Any]:
        """
        Load Longshot Detection model
        
        Returns:
            Model stub with metadata
        """
        logger.info("Loading Longshot Detection model...")
        
        model_stub = {
            "name": "Longshot Detector",
            "version": "v5.1",
            "type": "random_forest",
            "features": [
                "odds_value_gap",
                "market_move_24h",
                "trainer_intent_factor",
                "form_decay",
                "course_affinity"
            ],
            "odds_threshold": 10.0,  # Minimum odds to be considered longshot
            "confidence_threshold": 0.65,
            "performance": {
                "hit_rate": 0.18,
                "roi": 1.34,
                "avg_odds": 15.2
            },
            "status": "stub",
            "loaded": True
        }
        
        self.model_versions["longshot"] = model_stub["version"]
        logger.info(f"Longshot Detector {model_stub['version']} loaded (stub)")
        
        return model_stub
    
    def load_benter_overlay(self) -> Dict[str, Any]:
        """
        Load Benter-style Overlay Detection model
        
        Returns:
            Model stub with metadata
        """
        logger.info("Loading Benter Overlay model...")
        
        model_stub = {
            "name": "Benter Overlay",
            "version": "v4.3",
            "type": "logistic_regression",
            "features": [
                "final_probability",
                "market_odds",
                "implied_probability",
                "value_edge",
                "confidence"
            ],
            "overlay_threshold": 0.03,  # Minimum edge to be considered overlay
            "kelly_fraction": 0.25,  # Kelly criterion fraction
            "performance": {
                "roi": 1.18,
                "sharpe_ratio": 1.42,
                "max_drawdown": 0.23
            },
            "status": "stub",
            "loaded": True
        }
        
        self.model_versions["benter_overlay"] = model_stub["version"]
        logger.info(f"Benter Overlay {model_stub['version']} loaded (stub)")
        
        return model_stub
    
    def get_model(self, model_name: str) -> Optional[Dict[str, Any]]:
        """Get a specific model by name"""
        if not self._initialized:
            self.initialize()
        return self.models.get(model_name)
    
    def get_model_version(self, model_name: str) -> Optional[str]:
        """Get version of a specific model"""
        return self.model_versions.get(model_name)
    
    def predict_sqpe(self, features: Dict[str, float],
                     runner: Optional[Dict] = None,
                     race: Optional[Dict] = None) -> float:
        """
        Generate SQPE v17 prediction.

        Accepts either a pre-built features dict (must contain all 37 v17 keys)
        or raw runner+race dicts (will build features internally).

        Returns:
            Win probability [0, 1]
        """
        model = self.get_model("sqpe")
        if model is None:
            return 0.5

        # Build feature vector from raw dicts if provided, else use features dict
        if runner is not None and race is not None:
            fvec = self._build_v17_feature_vector(runner, race)
        else:
            fvec = np.array(
                [float(features.get(f, 0.0)) for f in self.ALL_V17_FEATURES],
                dtype=np.float64,
            )

        try:
            prob = model.predict_proba(fvec.reshape(1, -1))[0, 1]
            return float(prob)
        except Exception as e:
            logger.warning("SQPE predict_proba failed: %s", e)
            return 0.5

    # ── v17 feature builder ────────────────────────────────────────────────
    @staticmethod
    def _parse_sp(sp_str) -> float:
        if not sp_str or str(sp_str).strip() in ("", "–", "-"):
            return 10.0
        s = str(sp_str).strip().upper().rstrip("F").rstrip("J").strip()
        if s in ("EVENS", "EVS"):
            return 2.0
        m = re.match(r"^(\d+(?:\.\d+)?)/(\d+(?:\.\d+)?)$", s)
        if m:
            return float(m.group(1)) / float(m.group(2)) + 1.0
        try:
            return float(s) + 1.0
        except ValueError:
            return 10.0

    @staticmethod
    def _parse_dist(dist_str) -> float:
        if not dist_str:
            return 16.0
        s = str(dist_str).strip().lower()
        total = 0.0
        m_miles = re.search(r"(\d+(?:\.\d+)?)m", s)
        m_fur = re.search(r"(\d+(?:\.\d+)?)f", s)
        m_yds = re.search(r"(\d+)y", s)
        if m_miles:
            total += float(m_miles.group(1)) * 8
        if m_fur:
            total += float(m_fur.group(1))
        if m_yds:
            total += float(m_yds.group(1)) / 220
        return total if total > 0 else 16.0

    @staticmethod
    def _parse_going(going_str):
        g = str(going_str or "").strip().upper()
        aw = 1 if any(x in g for x in ["STANDARD", "SLOW", "FAST", "TAPETA", "POLYTRACK"]) else 0
        codes = {
            "FIRM": 2.0, "GOOD TO FIRM": 1.5, "GOOD": 1.0,
            "GOOD TO SOFT": 0.5, "SOFT": 0.0, "HEAVY": -1.0,
            "YIELDING": 0.3, "STANDARD": 1.0,
        }
        for key, val in codes.items():
            if key in g:
                return val, aw
        return 0.5, aw

    @staticmethod
    def _parse_class(class_str) -> float:
        s = str(class_str or "").strip().upper()
        m = re.search(r"CLASS\s*(\d)", s)
        if m:
            return float(m.group(1))
        if "GROUP 1" in s or "GRADE 1" in s:
            return 1.0
        if "GROUP 2" in s or "GRADE 2" in s:
            return 2.0
        if "LISTED" in s:
            return 2.5
        return 4.0

    @staticmethod
    def _parse_wgt(wgt_str) -> float:
        s = str(wgt_str or "").strip()
        m = re.match(r"(\d+)-(\d+)", s)
        if m:
            return float(m.group(1)) * 14 + float(m.group(2))
        try:
            return float(s)
        except ValueError:
            return 126.0

    @staticmethod
    def _parse_num(val) -> float:
        try:
            v = float(str(val).strip())
            return v if not math.isnan(v) else 0.0
        except (ValueError, TypeError):
            return 0.0

    def _build_v17_feature_vector(self, runner: Dict, race: Dict) -> np.ndarray:
        """Build 37-element v17 feature vector from raw runner+race dicts."""
        # ── v16 base (19) ──
        sp_dec = self._parse_sp(runner.get("sp") or runner.get("odds"))
        log_sp = math.log(max(sp_dec, 1.01))
        implied_prob = 1.0 / max(sp_dec, 1.01)
        dist_f = self._parse_dist(race.get("dist") or race.get("distance_f"))
        going_code, is_aw = self._parse_going(race.get("going"))
        class_num = self._parse_class(race.get("class") or race.get("class_raw"))
        wgt_lbs = self._parse_wgt(runner.get("wgt") or runner.get("weight"))
        or_num = self._parse_num(runner.get("or") or runner.get("or_rating") or runner.get("official_rating"))
        rpr_num = self._parse_num(runner.get("rpr"))
        ts_num = self._parse_num(runner.get("ts"))
        field_size = self._parse_num(race.get("ran") or race.get("runners_count", 10))
        draw_num = self._parse_num(runner.get("draw") or runner.get("stall"))
        draw_pct = draw_num / max(field_size, 1)
        age_num = self._parse_num(runner.get("age"))

        # Field-relative features — need full field; use defaults if unavailable
        or_vs_field = self._parse_num(runner.get("or_vs_field", 0.0))
        rpr_vs_field = self._parse_num(runner.get("rpr_vs_field", 0.0))
        sp_rank = self._parse_num(runner.get("sp_rank", 3.0))
        is_fav = 1.0 if sp_rank == 1.0 else 0.0

        v16 = [
            sp_dec, log_sp, implied_prob, dist_f, going_code, float(is_aw),
            class_num, wgt_lbs, or_num, rpr_num, ts_num,
            or_vs_field, rpr_vs_field, field_size, draw_num, draw_pct,
            age_num, sp_rank, is_fav,
        ]

        # ── v17 doctrine (18) — from pre-computed values if present ──
        from app.services.v17_feature_extractor import DEFAULTS
        doctrine = [
            float(runner.get(f, DEFAULTS.get(f, 0.0)))
            for f in self.V17_DOCTRINE_FEATURES
        ]

        return np.array(v16 + doctrine, dtype=np.float64)
    
    def predict_trainer_intent(self, features: Dict[str, float]) -> float:
        """
        Generate Trainer Intent signal
        
        Args:
            features: Engineered features dictionary
            
        Returns:
            Intent signal strength [0, 1]
        """
        model = self.get_model("trainer_intent")
        if not model:
            return 0.5
        
        # Stub prediction: trainer intent factor with boost
        intent = features.get("trainer_intent_factor", 0.5)
        jockey_synergy = features.get("jockey_synergy", 0.5)
        
        signal = (intent * 0.7) + (jockey_synergy * 0.3)
        return min(max(signal, 0.0), 1.0)
    
    def predict_longshot(self, features: Dict[str, float], odds: float) -> float:
        """
        Generate Longshot detection score
        
        Args:
            features: Engineered features dictionary
            odds: Current market odds
            
        Returns:
            Longshot score [0, 1]
        """
        model = self.get_model("longshot")
        if not model or odds < model["odds_threshold"]:
            return 0.0
        
        # Stub prediction: value gap + market movement
        value_gap = features.get("odds_value_gap", 0.5)
        market_move = features.get("market_move_24h", 0.5)
        trainer_intent = features.get("trainer_intent_factor", 0.5)
        
        score = (value_gap * 0.4) + (market_move * 0.3) + (trainer_intent * 0.3)
        return min(max(score, 0.0), 1.0)
    
    def detect_overlay(self, model_prob: float, market_odds: float) -> Dict[str, Any]:
        """
        Detect betting overlay opportunity
        
        Args:
            model_prob: Model probability
            market_odds: Market odds
            
        Returns:
            Overlay analysis dictionary
        """
        model = self.get_model("benter_overlay")
        if not model:
            return {"is_overlay": False, "edge": 0.0}
        
        implied_prob = 1.0 / market_odds if market_odds > 0 else 0.0
        edge = model_prob - implied_prob
        
        is_overlay = edge >= model["overlay_threshold"]
        
        # Kelly criterion bet sizing
        kelly_fraction = model["kelly_fraction"]
        bet_size = kelly_fraction * edge if is_overlay else 0.0
        
        return {
            "is_overlay": is_overlay,
            "edge": edge,
            "model_probability": model_prob,
            "implied_probability": implied_prob,
            "kelly_bet_size": bet_size,
            "expected_value": edge * market_odds if is_overlay else 0.0
        }
    
    def get_status(self) -> Dict[str, Any]:
        """Get model manager status"""
        return {
            "initialized": self._initialized,
            "models_loaded": len(self.models),
            "models": {
                name: {
                    "version": model.get("version"),
                    "type": model.get("type"),
                    "status": model.get("status"),
                    "loaded": model.get("loaded")
                }
                for name, model in self.models.items()
            }
        }


# Global model manager instance
_model_manager: Optional[ModelManager] = None


def get_model_manager() -> ModelManager:
    """Get or create global model manager instance"""
    global _model_manager
    if _model_manager is None:
        _model_manager = ModelManager()
        _model_manager.initialize()
    return _model_manager
