import logging
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
    AEGIS Product Assignment Router v2 — D/X Intelligence Layer.

    v2 changes vs v1:
      - D and X tiers no longer immediately PASS. They enter a dedicated
        intelligence layer built from 84-race forensic analysis.
      - 7 evidence-based rules derived from historical D/X winner profiles.
      - New route_verdict inputs: field_size, race_type, going, is_handicap,
        fav_sp, velo_prime_prob, archetype.
    """

    def __init__(self):
        self.FORTRESS_MIN_GAP = 0.08
        self.CLUSTER_MAX_GAP = 0.04
        self.FORTRESS_MAX_SP = 5.0
        self.DECOY_MAX_MDS = 0.10
        self.TIGHT_TRACKS = ["Chester", "Lingfield", "Wolverhampton", "Kempton"]

        # D/X thresholds (from forensic analysis)
        self.DX_EDGE_MIN = 2.0  # velo_prime_prob × field_size must clear this
        self.DX_SP_DEAD_LO = 8.0  # SP 8–14 = 0% WR dead zone
        self.DX_SP_DEAD_HI = 14.0
        self.DX_SP_MAX = 25.0  # SP > 25 too thin
        self.DX_FAV_DOMINANCE_SP = 3.0  # fav < 3.0 = race is sewn up
        self.DX_LG_FIELD = 12  # large field threshold
        self.DX_GOING_BLOCK = {"Good", "Firm", "Hard"}
        self.DX_JUMP_TYPES = {"Hurdle", "Chase", "NH Flat"}

    # ─────────────────────────────────────────────────────────────────────────
    def route_verdict(self, verdict: dict) -> dict:
        tier = verdict.get("decision_tier", "X")
        raw_conf = verdict.get("confidence_level", "NORMAL")
        conf = str(raw_conf).upper() if raw_conf else "NORMAL"

        market_sp = float(verdict.get("actual_winner_sp") or 0)
        prob_gap = float(verdict.get("prob_gap") or 0)
        mds = float(verdict.get("market_deception_score") or 0)
        track = verdict.get("track", "") or ""
        draw = verdict.get("top_horse_draw")

        # v2 context fields
        field_size = int(verdict.get("field_size") or 0)
        race_type = str(verdict.get("race_type") or "?").strip()
        going = str(verdict.get("going") or "?").strip()
        is_handicap = bool(verdict.get("is_handicap") or False)
        fav_sp = float(verdict.get("fav_sp") or 0)
        velo_prime_prob = float(verdict.get("velo_prime_prob") or 0)
        archetype = str(verdict.get("archetype") or "?").strip()

        edge = velo_prime_prob * field_size if field_size > 0 else 0

        # ── C tier: unchanged PASS ────────────────────────────────────────────
        if tier == "C":
            return self._finalize(VeloProduct.PASS, ["TIER_ROT"])

        # ── D / X tier: intelligence layer ───────────────────────────────────
        if tier in ("D", "X"):
            return self._route_dx(
                tier=tier,
                market_sp=market_sp,
                mds=mds,
                edge=edge,
                field_size=field_size,
                race_type=race_type,
                going=going,
                is_handicap=is_handicap,
                fav_sp=fav_sp,
                archetype=archetype,
            )

        # ── A / B tier: existing logic (unchanged) ────────────────────────────
        if market_sp >= 12.0:
            return self._finalize(VeloProduct.PASS, ["PRICE_NOISE_ZONE"])

        if prob_gap < 0.03:
            return self._finalize(VeloProduct.PASS, ["WEAK_MARGIN"])

        if mds > self.DECOY_MAX_MDS and tier != "A":
            return self._finalize(VeloProduct.PASS, ["HIGH_DECOY_RISK"])

        if track in self.TIGHT_TRACKS and draw:
            try:
                if int(draw) > 8:
                    return self._finalize(VeloProduct.PASS, ["GEOMETRY_BLOCKER"])
            except (ValueError, TypeError):
                pass

        if tier == "A" and conf == "HIGH" and market_sp < self.FORTRESS_MAX_SP and prob_gap >= self.FORTRESS_MIN_GAP:
            return self._finalize(VeloProduct.WIN_ONLY, ["GOLD_STANDARD_ALIGNMENT"])

        if tier in ("A", "B") and 5.0 <= market_sp <= 12.0:
            if prob_gap < self.CLUSTER_MAX_GAP:
                return self._finalize(VeloProduct.FRAME_ONLY, ["COMPETITIVE_CLUSTER"])
            return self._finalize(VeloProduct.EW_CANDIDATE, ["MID_PRICE_VISION"])

        if tier in ("A", "B"):
            return self._finalize(VeloProduct.VISION_ONLY, ["UNAUTHORISED_SELECTION"])

        return self._finalize(VeloProduct.PASS, ["FALLTHROUGH_PROTECTION"])

    # ─────────────────────────────────────────────────────────────────────────
    def _route_dx(
        self,
        tier: str,
        market_sp: float,
        mds: float,
        edge: float,
        field_size: int,
        race_type: str,
        going: str,
        is_handicap: bool,
        fav_sp: float,
        archetype: str,
    ) -> dict:
        """
        D/X Intelligence Layer.

        Evidence base: 84 historical D/X races, 11 winners, forensic analysis
        of winner vs loser signal profiles.

        Hard blocks first (removes dead-weight), then upgrade paths (surfaces
        genuine value). Each rule carries a traceable reason code.
        """

        # ── HARD BLOCKS ──────────────────────────────────────────────────────

        # SP dead zone: 8.0–14.0 = 0 wins in 21 races
        if market_sp > 0 and self.DX_SP_DEAD_LO <= market_sp <= self.DX_SP_DEAD_HI:
            return self._finalize(VeloProduct.PASS, ["DX_SP_DEAD_ZONE"])

        # SP too thin: > 25 = 0 wins, no EW value
        if market_sp > self.DX_SP_MAX:
            return self._finalize(VeloProduct.PASS, ["DX_SP_TOO_THIN"])

        # Dominant favourite: fav < 3.0 SP, D/X wins 4% of those races
        if fav_sp > 0 and fav_sp < self.DX_FAV_DOMINANCE_SP:
            return self._finalize(VeloProduct.PASS, ["DX_FAV_DOMINANCE"])

        # Going blocker: Good/Firm/Hard ground = 5% WR (20 races)
        if going in self.DX_GOING_BLOCK:
            return self._finalize(VeloProduct.PASS, ["DX_GOING_BLOCKER"])

        # Jump non-handicap: model has no structural read, 0% WR in large fields
        if race_type in self.DX_JUMP_TYPES and not is_handicap:
            return self._finalize(VeloProduct.PASS, ["DX_JUMP_NHCAP_BLOCK"])

        # Unknown archetype in small field: model flying blind
        if archetype in ("?", "", "None") and field_size > 0 and field_size < 12:
            return self._finalize(VeloProduct.PASS, ["DX_BLIND_SMALL_FIELD"])

        # ── UPGRADE PATHS ────────────────────────────────────────────────────

        # Compression archetype: 43% WR regardless of tier
        # Tight markets where VELO edge concentrates — promote unconditionally
        if archetype == "Compression":
            return self._finalize(VeloProduct.VISION_ONLY, ["DX_COMPRESSION_UPGRADE"])

        # Large field handicap flat: 21% WR = 2.5× random
        # The weights level the field; edge_multiple becomes real
        if field_size >= self.DX_LG_FIELD and is_handicap and edge >= self.DX_EDGE_MIN and race_type == "Flat":
            return self._finalize(
                VeloProduct.VISION_ONLY,
                [f"DX_LG_FLAT_HCAP_E{edge:.1f}"],
            )

        # Large field Chase handicap: 82% placed rate = each-way factory
        if field_size >= self.DX_LG_FIELD and is_handicap and edge >= self.DX_EDGE_MIN and race_type == "Chase":
            return self._finalize(
                VeloProduct.EW_CANDIDATE,
                [f"DX_CHASE_EW_E{edge:.1f}"],
            )

        # MDS overlay flip: in D/X, high MDS = market obscuring a real signal
        # (opposite polarity to A/B where high MDS = decoy risk)
        if mds > self.DECOY_MAX_MDS:
            return self._finalize(VeloProduct.VISION_ONLY, ["DX_MDS_OVERLAY"])

        # SP value zones: 4–8 (24% WR, ROI +0.36) or 14–25 (18% WR, ROI +2.82)
        # Only activate when edge clears the minimum threshold
        if edge >= self.DX_EDGE_MIN and market_sp > 0:
            if 4.0 <= market_sp <= 8.0:
                return self._finalize(
                    VeloProduct.VISION_ONLY,
                    [f"DX_SP_VALUE_4_8_E{edge:.1f}"],
                )
            if 14.0 < market_sp <= self.DX_SP_MAX:
                return self._finalize(
                    VeloProduct.VISION_ONLY,
                    [f"DX_SP_VALUE_14_25_E{edge:.1f}"],
                )

        # No actionable signal found
        return self._finalize(VeloProduct.PASS, ["DX_NO_SIGNAL"])

    # ─────────────────────────────────────────────────────────────────────────
    def _finalize(self, product: VeloProduct, reasons: list[str]) -> dict:
        return {
            "assigned_product": product.value,
            "router_reasons": reasons,
            "execution_allowed": product
            in (
                VeloProduct.WIN_ONLY,
                VeloProduct.FRAME_ONLY,
                VeloProduct.EW_CANDIDATE,
            ),
        }
