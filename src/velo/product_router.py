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
        D/X Intelligence Layer — LOCKED FOR CONTAINMENT.
        Always returns PASS to prevent unauthorized tier upgrades.
        """
        return self._finalize(VeloProduct.PASS, ["DX_CONTAINMENT_LOCK_ACTIVE"])

    # ─────────────────────────────────────────────────────────────────────────
    # ─────────────────────────────────────────────────────────────────────────
    def candidate_route(self, verdict: dict) -> dict:
        """
        Candidate Execution Router v1 — shadow mode only.

        Evaluates whether a verdict matches a proven attack lane based on
        Innovation Protocol analysis (708 scored races, segmented by class,
        archetype, field size, VP, SP, going).

        Does NOT replace execution_allowed. Runs in parallel for simulation.
        Wire to live staking only after shadow validation confirms edge.

        Attack lane criteria (derived from Phase 1 segmentation):
          - class 3 or 4
          - archetype == Structure
          - field_size <= 12
          - velo_prime_prob >= 0.30
          - sp_decimal 2.0–4.0 (evens/2s bleed -14.9%; 4/1+ bleed -50%+)
          - going != Heavy
          - archetype != Chaos
          - macro_chaos_mode != True

        Hard no-bet conditions (confirmed 0-edge zones):
          - going == Heavy (0% SR in 15 races)
          - class 6 (11.5% SR, below random)
          - field_size >= 17 (10% SR, noise only)
          - sp_decimal > 4.0 (10.5% SR, -50.8% ROI in 4s-7s; worse beyond)
          - sp_decimal < 2.0 (SR=57% but -14.9% ROI — bookie margin eats edge)
          - Chaos archetype (5% SR, model has no structural read)

        SP 2.0–4.0 gate rationale (Phase 1 tightening, 2026-04-27):
          - n=32 with results, SR=37.5%, Placed=84.4%, P&L=£2.46, ROI=+7.7%
          - STATUS: EXECUTION_ROUTER_V1_SHADOW_APPROVED
        """
        vp            = float(verdict.get("velo_prime_prob") or 0)
        field_size    = int(verdict.get("field_size") or 0)
        archetype     = str(verdict.get("archetype") or "").strip()
        going         = str(verdict.get("going") or "").strip()
        macro_chaos   = bool(verdict.get("macro_chaos_mode") or False)
        class_num     = int(verdict.get("class_num") or 0)
        sp_decimal    = float(verdict.get("sp_decimal") or 0)
        arch_suppress = bool(verdict.get("archetype_suppression") or False)

        blockers = []

        # ── Hard no-bet gates ─────────────────────────────────────────────
        if "heavy" in going.lower():
            blockers.append("NO_BET_HEAVY_GOING")
        if class_num == 6:
            blockers.append("NO_BET_CLASS_6")
        if field_size >= 17:
            blockers.append("NO_BET_LARGE_FIELD_17PLUS")
        if sp_decimal > 0 and sp_decimal > 4.0:
            blockers.append(f"NO_BET_SP_ABOVE_4_{sp_decimal:.1f}")
        if sp_decimal > 0 and sp_decimal < 2.0:
            blockers.append(f"NO_BET_SP_BELOW_2_{sp_decimal:.2f}")
        if archetype == "Chaos":
            blockers.append("NO_BET_CHAOS_ARCHETYPE")
        if macro_chaos:
            blockers.append("NO_BET_MACRO_CHAOS")

        if blockers:
            return {
                "candidate_execution_allowed": False,
                "candidate_execution_reason": blockers,
                "candidate_execution_lane": "NO_BET",
            }

        # ── Attack lane filters ───────────────────────────────────────────
        lane_blockers = []

        if class_num not in (3, 4):
            lane_blockers.append(f"LANE_CLASS_MISS_{class_num or 'UNKNOWN'}")
        if archetype != "Structure":
            lane_blockers.append(f"LANE_ARCHETYPE_MISS_{archetype or 'UNKNOWN'}")
        if field_size > 12:
            lane_blockers.append(f"LANE_FIELD_SIZE_{field_size}")
        if vp < 0.30:
            lane_blockers.append(f"LANE_VP_LOW_{vp:.3f}")
        if arch_suppress:
            lane_blockers.append("LANE_ARCHETYPE_SUPPRESSED")

        if lane_blockers:
            return {
                "candidate_execution_allowed": False,
                "candidate_execution_reason": lane_blockers,
                "candidate_execution_lane": "ATTACK_LANE_MISS",
            }

        return {
            "candidate_execution_allowed": True,
            "candidate_execution_reason": ["ATTACK_LANE_PASS"],
            "candidate_execution_lane": f"CL{class_num}_STRUCTURE_VP{vp:.2f}",
        }

    # ─────────────────────────────────────────────────────────────────────────
    def _finalize(self, product: VeloProduct, reasons: list[str]) -> dict:
        return {
            "assigned_product": product.value,
            "router_reasons": reasons,
            "legacy_execution_allowed": product
            in (
                VeloProduct.WIN_ONLY,
                VeloProduct.FRAME_ONLY,
                VeloProduct.EW_CANDIDATE,
            ),
            # Keep backward-compat alias so existing code reading execution_allowed still works
            "execution_allowed": product
            in (
                VeloProduct.WIN_ONLY,
                VeloProduct.FRAME_ONLY,
                VeloProduct.EW_CANDIDATE,
            ),
        }
