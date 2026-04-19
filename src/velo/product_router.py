import logging
from typing import Dict, List, Optional
from enum import Enum

logger = logging.getLogger("ProductRouter")

class VeloProduct(Enum):
    WIN_ONLY = "WIN_ONLY"
    FRAME_ONLY = "FRAME_ONLY"
    EW_CANDIDATE = "EW_CANDIDATE"
    VISION_ONLY = "VISION_ONLY"
    PASS = "PASS"

class ProductRouter:
    """
    AEGIS Product Assignment Router v1 (Live-Safe).
    Strictly uses pre-off features. No hindsight.
    """
    def __init__(self):
        # Recalibrated Thresholds for Live-Safe Inputs
        self.FORTRESS_MIN_GAP = 0.08
        self.CLUSTER_MAX_GAP = 0.04
        self.FORTRESS_MAX_SP = 5.0
        self.DECOY_MAX_MDS = 0.10 # Max Deception Score allowed for Win bets
        self.TIGHT_TRACKS = ["Chester", "Lingfield", "Wolverhampton", "Kempton"]

    def route_verdict(self, verdict: Dict) -> Dict:
        """
        Determines the optimal product for a given race verdict.
        Inputs MUST be pre-off features only.
        """
        tier = verdict.get("decision_tier", "X")
        raw_conf = verdict.get("confidence_level", "NORMAL")
        conf = str(raw_conf).upper() if raw_conf else "NORMAL"
        
        # Pre-off Price Proxy (In live, this is current market price)
        market_sp = float(verdict.get("actual_winner_sp") or 0) 
        
        # Real-time Signals
        prob_gap = float(verdict.get("prob_gap") or 0)
        mds = float(verdict.get("market_deception_score") or 0)
        track = verdict.get("track", "")
        draw = verdict.get("top_horse_draw")

        # ── 1. LIVE-SAFE KILL LANE ─────────────────────────────────────────
        if tier in ["C", "D"]:
            return self._finalize(VeloProduct.PASS, ["TIER_ROT"])
        
        if market_sp >= 12.0:
            return self._finalize(VeloProduct.PASS, ["PRICE_NOISE_ZONE"])
        
        if prob_gap < 0.03:
            return self._finalize(VeloProduct.PASS, ["WEAK_MARGIN"])

        if mds > self.DECOY_MAX_MDS and tier != "A":
            return self._finalize(VeloProduct.PASS, ["HIGH_DECOY_RISK"])

        if track in self.TIGHT_TRACKS and draw and int(draw) > 8:
             return self._finalize(VeloProduct.PASS, ["GEOMETRY_BLOCKER"])

        # ── 2. FORTRESS LANE (Win-Only) ────────────────────────────────────
        if tier == "A" and conf == "HIGH" and market_sp < self.FORTRESS_MAX_SP and prob_gap >= self.FORTRESS_MIN_GAP:
            return self._finalize(VeloProduct.WIN_ONLY, ["GOLD_STANDARD_ALIGNMENT"])

        # ── 3. FRAME / EW LANES (Vision Capture) ───────────────────────────
        if tier in ["A", "B"] and 5.0 <= market_sp <= 12.0:
            if prob_gap < self.CLUSTER_MAX_GAP:
                return self._finalize(VeloProduct.FRAME_ONLY, ["COMPETITIVE_CLUSTER"])
            return self._finalize(VeloProduct.EW_CANDIDATE, ["MID_PRICE_VISION"])

        # ── 4. VISION ONLY (Intelligence) ──────────────────────────────────
        if tier in ["A", "B"]:
            return self._finalize(VeloProduct.VISION_ONLY, ["UNAUTHORISED_SELECTION"])

        return self._finalize(VeloProduct.PASS, ["FALLTHROUGH_PROTECTION"])

    def _finalize(self, product: VeloProduct, reasons: List[str]) -> Dict:
        return {
            "assigned_product": product.value,
            "router_reasons": reasons,
            "execution_allowed": product in [VeloProduct.WIN_ONLY, VeloProduct.FRAME_ONLY, VeloProduct.EW_CANDIDATE]
        }
