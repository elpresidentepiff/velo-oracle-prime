"""
VÉLØ Oracle Prime — Phase 1: Market Constraint Engine
=====================================================

Module: src/constraints/market_engine.py
Purpose: BSP drift analysis as a HARD GATE on selection decisions.
         Prevents the Wolverhampton failure mode where shortening favourites
         were dismissed without evidence.

Day 1 Lesson: "A shortening favourite is the market screaming 'this horse is
ready'. You cannot dismiss it without 3+ independent counter-signals."

Architecture: Integrates with existing SQLite memory engine (WAL mode).
              Stores all constraint decisions in market_behaviour table.

Author: VÉLØ Oracle Prime — Phase 1 Build
Date: 2026-02-16
"""

import sqlite3
import json
from datetime import datetime, timezone
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional, List, Dict, Any


# ---------------------------------------------------------------------------
# Enums & Data Classes
# ---------------------------------------------------------------------------

class DriftClassification(Enum):
    """Market drift classification for a runner."""
    STEAMER = "STEAMER"        # Shortening > threshold (market says 'ready')
    DRIFTER = "DRIFTER"        # Lengthening > threshold (market says 'avoid')
    STABLE = "STABLE"          # Within normal variance
    VOLATILE = "VOLATILE"      # Multiple direction changes / erratic


class ConstraintVerdict(Enum):
    """Hard-gate constraint verdict on a selection decision."""
    BLOCKED = "BLOCKED"
    WARNING = "WARNING"
    CLEAR = "CLEAR"


@dataclass
class MarketThresholds:
    """Configurable thresholds for market constraint triggers.

    Attributes:
        steam_pct: Percentage shortening to classify as STEAMER (default 15%).
        drift_pct: Percentage lengthening to classify as DRIFTER (default 20%).
        divergence_pct: BSP vs ISP divergence flag threshold (default 20%).
        volatile_changes: Minimum direction changes for VOLATILE (default 3).
        override_counter_signals: Counter-signals required to override a BLOCKED
                                  verdict (default 3).
    """
    steam_pct: float = 15.0
    drift_pct: float = 20.0
    divergence_pct: float = 20.0
    volatile_changes: int = 3
    override_counter_signals: int = 3


@dataclass
class DriftResult:
    """Result of a drift analysis for a single runner.

    Attributes:
        horse: Name of the horse.
        morning_price: Opening / morning price (decimal odds).
        bsp: Betfair Starting Price (decimal odds).
        pct_change: Percentage change from morning to BSP.
        classification: DriftClassification enum value.
        description: Human-readable explanation.
    """
    horse: str
    morning_price: float
    bsp: float
    pct_change: float
    classification: DriftClassification
    description: str


@dataclass
class ConstraintDecision:
    """A constraint verdict with full reasoning chain.

    Attributes:
        horse: Name of the horse.
        verdict: ConstraintVerdict enum value.
        message: Human-readable constraint message.
        drift_result: Associated DriftResult (if any).
        counter_signals: List of counter-signals provided.
        override_allowed: Whether the constraint can be overridden.
        timestamp: ISO-8601 timestamp of the decision.
    """
    horse: str
    verdict: ConstraintVerdict
    message: str
    drift_result: Optional[DriftResult] = None
    counter_signals: List[str] = field(default_factory=list)
    override_allowed: bool = False
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class DivergenceResult:
    """BSP vs ISP divergence analysis.

    Attributes:
        horse: Name of the horse.
        bsp: Betfair Starting Price.
        isp: Industry Starting Price.
        divergence_pct: Absolute percentage divergence.
        direction: 'BSP_SHORTER' or 'BSP_LONGER' or 'ALIGNED'.
        flagged: Whether divergence exceeds threshold.
        interpretation: Human-readable interpretation.
    """
    horse: str
    bsp: float
    isp: float
    divergence_pct: float
    direction: str
    flagged: bool
    interpretation: str


# ---------------------------------------------------------------------------
# Market Constraint Engine
# ---------------------------------------------------------------------------

class MarketConstraintEngine:
    """BSP drift analysis as a HARD GATE on selection decisions.

    This engine prevents the Wolverhampton Day 1 failure mode where
    shortening favourites were dismissed without evidence. It enforces
    market-based constraints on every selection decision.

    Key Principles (from SIGMA-02):
        - Principle 9: "A shortening favourite is the market screaming
          'this horse is ready'."
        - Principle 10: "You cannot dismiss a market signal without
          3+ independent counter-signals."

    Usage:
        >>> engine = MarketConstraintEngine(db_path="velo.db")
        >>> drift = engine.analyse_drift("Cressida Wildes", 12.0, 9.71)
        >>> decision = engine.apply_constraint(selection, market_data)
    """

    def __init__(self, db_path: str = "velo_oracle.db",
                 thresholds: Optional[MarketThresholds] = None):
        """Initialise the Market Constraint Engine.

        Args:
            db_path: Path to the SQLite database file.
            thresholds: Optional custom MarketThresholds; uses defaults if None.
        """
        self.db_path = db_path
        self.thresholds = thresholds or MarketThresholds()
        self._init_db()

    # ------------------------------------------------------------------
    # Database Initialisation
    # ------------------------------------------------------------------

    def _get_conn(self) -> sqlite3.Connection:
        """Get a database connection with WAL mode enabled."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Create or migrate the market_behaviour table."""
        conn = self._get_conn()
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS market_behaviour (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    horse TEXT NOT NULL,
                    race_id TEXT,
                    track TEXT,
                    race_date TEXT,
                    morning_price REAL,
                    bsp REAL,
                    isp REAL,
                    drift_pct REAL,
                    drift_classification TEXT,
                    constraint_verdict TEXT,
                    constraint_message TEXT,
                    counter_signals TEXT,
                    override_allowed INTEGER DEFAULT 0,
                    divergence_pct REAL,
                    divergence_flagged INTEGER DEFAULT 0,
                    raw_data TEXT,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_market_behaviour_horse
                ON market_behaviour(horse)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_market_behaviour_race
                ON market_behaviour(race_id)
            """)
            conn.commit()
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Core Analysis Methods
    # ------------------------------------------------------------------

    def analyse_drift(self, horse: str, morning_price: float,
                      bsp: float) -> DriftResult:
        """Analyse the drift between morning price and BSP.

        In decimal odds, a LOWER number means SHORTER (more fancied).
        A horse going from 12.0 → 9.71 has SHORTENED (steamer).
        A horse going from 3.0 → 4.5 has DRIFTED (drifter).

        Percentage change is calculated as:
            pct = ((morning_price - bsp) / morning_price) * 100
        Positive pct → shortened (steamer).
        Negative pct → lengthened (drifter).

        Args:
            horse: Name of the horse.
            morning_price: Opening / morning decimal odds.
            bsp: Betfair Starting Price (decimal odds).

        Returns:
            DriftResult with classification and explanation.
        """
        if morning_price <= 0 or bsp <= 0:
            return DriftResult(
                horse=horse,
                morning_price=morning_price,
                bsp=bsp,
                pct_change=0.0,
                classification=DriftClassification.STABLE,
                description="Invalid price data — cannot classify drift."
            )

        # In decimal odds: lower = shorter = more fancied
        # pct_change > 0 means shortened, < 0 means drifted
        pct_change = ((morning_price - bsp) / morning_price) * 100.0

        if pct_change >= self.thresholds.steam_pct:
            classification = DriftClassification.STEAMER
            desc = (f"{horse} SHORTENED by {pct_change:.1f}% "
                    f"({morning_price:.2f} → {bsp:.2f}). "
                    f"Market says this horse is READY.")
        elif pct_change <= -self.thresholds.drift_pct:
            classification = DriftClassification.DRIFTER
            desc = (f"{horse} DRIFTED by {abs(pct_change):.1f}% "
                    f"({morning_price:.2f} → {bsp:.2f}). "
                    f"Market confidence weakening.")
        else:
            classification = DriftClassification.STABLE
            desc = (f"{horse} price movement within normal range "
                    f"({pct_change:+.1f}%). No significant drift.")

        return DriftResult(
            horse=horse,
            morning_price=morning_price,
            bsp=bsp,
            pct_change=round(pct_change, 2),
            classification=classification,
            description=desc
        )

    def apply_constraint(self, selection: Dict[str, Any],
                         market_data: Dict[str, Any]) -> ConstraintDecision:
        """Apply market constraint gate to a selection decision.

        This is the HARD GATE. If a horse is shortening significantly
        and the selection attempts to dismiss it (e.g., as a false
        favourite), the constraint engine BLOCKS the dismissal unless
        3+ counter-signals are provided.

        Args:
            selection: Dict with keys: horse, role (e.g., 'dismiss',
                       'false_favourite', 'top_strike'), rpd_tag,
                       counter_signals (optional list).
            market_data: Dict with keys: morning_price, bsp,
                         is_favourite (bool).

        Returns:
            ConstraintDecision with verdict and reasoning.
        """
        horse = selection.get("horse", "Unknown")
        role = selection.get("role", "").lower()
        counter_signals = selection.get("counter_signals", [])

        morning_price = market_data.get("morning_price", 0)
        bsp = market_data.get("bsp", 0)
        is_favourite = market_data.get("is_favourite", False)

        drift = self.analyse_drift(horse, morning_price, bsp)

        # HARD GATE: Cannot dismiss a shortening favourite
        dismissal_roles = {"dismiss", "false_favourite", "false_fav",
                           "rejected", "excluded"}
        is_dismissal = role in dismissal_roles

        if (drift.classification == DriftClassification.STEAMER
                and is_favourite and is_dismissal):
            if len(counter_signals) >= self.thresholds.override_counter_signals:
                decision = ConstraintDecision(
                    horse=horse,
                    verdict=ConstraintVerdict.WARNING,
                    message=(
                        f"Override accepted for {horse} with "
                        f"{len(counter_signals)} counter-signals. "
                        f"Market constraint noted but not enforced. "
                        f"Signals: {', '.join(counter_signals)}"
                    ),
                    drift_result=drift,
                    counter_signals=counter_signals,
                    override_allowed=True
                )
            else:
                needed = self.thresholds.override_counter_signals - len(counter_signals)
                decision = ConstraintDecision(
                    horse=horse,
                    verdict=ConstraintVerdict.BLOCKED,
                    message=(
                        f"Cannot dismiss {horse} as false favourite — "
                        f"BSP shortened >{self.thresholds.steam_pct:.0f}% "
                        f"from morning price. Override requires "
                        f"{self.thresholds.override_counter_signals}+ "
                        f"counter-signals ({needed} more needed)."
                    ),
                    drift_result=drift,
                    counter_signals=counter_signals,
                    override_allowed=False
                )
        elif drift.classification == DriftClassification.STEAMER and is_dismissal:
            decision = ConstraintDecision(
                horse=horse,
                verdict=ConstraintVerdict.WARNING,
                message=(
                    f"Market divergence detected for {horse}. "
                    f"Horse is shortening ({drift.pct_change:+.1f}%) — "
                    f"review selection confidence before dismissal."
                ),
                drift_result=drift,
                counter_signals=counter_signals,
                override_allowed=True
            )
        elif drift.classification == DriftClassification.DRIFTER:
            decision = ConstraintDecision(
                horse=horse,
                verdict=ConstraintVerdict.WARNING,
                message=(
                    f"Market divergence detected for {horse}. "
                    f"Horse is drifting ({drift.pct_change:+.1f}%) — "
                    f"review selection confidence."
                ),
                drift_result=drift,
                counter_signals=counter_signals,
                override_allowed=True
            )
        else:
            decision = ConstraintDecision(
                horse=horse,
                verdict=ConstraintVerdict.CLEAR,
                message=f"No market constraint triggered for {horse}.",
                drift_result=drift,
                counter_signals=counter_signals,
                override_allowed=True
            )

        # Store the decision
        self._store_decision(decision, market_data)
        return decision

    def favourite_override_check(self, horse: str, rpd_tag: str,
                                 market_data: Dict[str, Any]) -> ConstraintDecision:
        """Specific check: market favourite + shortening cannot be tagged E
        or assigned False Favourite threat without explicit documented evidence.

        Day 1 Lesson: At Wolverhampton, Alondra was tagged E (Exhausted)
        despite being the shortening favourite. She finished 2nd. The E tag
        was narrative convenience, not physiological evidence.

        Args:
            horse: Name of the horse.
            rpd_tag: Proposed RPD-C tag (P/T/E/H/S).
            market_data: Dict with keys: morning_price, bsp, is_favourite.

        Returns:
            ConstraintDecision — BLOCKED if attempting E tag on shortening fav.
        """
        morning_price = market_data.get("morning_price", 0)
        bsp = market_data.get("bsp", 0)
        is_favourite = market_data.get("is_favourite", False)

        drift = self.analyse_drift(horse, morning_price, bsp)

        blocked_tags = {"E", "e", "exhausted"}
        tag_upper = rpd_tag.strip().upper()

        if (drift.classification == DriftClassification.STEAMER
                and is_favourite and tag_upper in {"E"}):
            decision = ConstraintDecision(
                horse=horse,
                verdict=ConstraintVerdict.BLOCKED,
                message=(
                    f"BLOCKED: Cannot assign '{rpd_tag}' (Exhausted) to "
                    f"{horse} — horse is market favourite AND shortening "
                    f"({drift.pct_change:+.1f}%). Exhausted requires "
                    f"physiological evidence, not narrative convenience. "
                    f"Market says this horse is READY."
                ),
                drift_result=drift,
                override_allowed=False
            )
        elif (drift.classification == DriftClassification.STEAMER
              and tag_upper in {"E"}):
            decision = ConstraintDecision(
                horse=horse,
                verdict=ConstraintVerdict.WARNING,
                message=(
                    f"WARNING: Assigning '{rpd_tag}' (Exhausted) to "
                    f"{horse} while horse is shortening ({drift.pct_change:+.1f}%). "
                    f"Market contradicts exhaustion narrative. "
                    f"Provide documented physiological evidence."
                ),
                drift_result=drift,
                override_allowed=True
            )
        else:
            decision = ConstraintDecision(
                horse=horse,
                verdict=ConstraintVerdict.CLEAR,
                message=(
                    f"No favourite-override constraint triggered for "
                    f"{horse} with tag '{rpd_tag}'."
                ),
                drift_result=drift,
                override_allowed=True
            )

        self._store_decision(decision, market_data)
        return decision

    def bsp_isp_divergence(self, horse: str, bsp: float,
                           isp: float) -> DivergenceResult:
        """Flag when BSP vs ISP divergence exceeds threshold.

        Large divergence indicates late smart money movement.
        Day 1 example: Faster Bee ISP 13 → BSP 21.42 = 64.8% divergence.

        Args:
            horse: Name of the horse.
            bsp: Betfair Starting Price (decimal odds).
            isp: Industry Starting Price (decimal odds).

        Returns:
            DivergenceResult with flag status and interpretation.
        """
        if isp <= 0 or bsp <= 0:
            return DivergenceResult(
                horse=horse, bsp=bsp, isp=isp,
                divergence_pct=0.0, direction="INVALID",
                flagged=False,
                interpretation="Invalid price data."
            )

        # Divergence as percentage of ISP
        divergence_pct = abs((bsp - isp) / isp) * 100.0

        if bsp < isp:
            direction = "BSP_SHORTER"
            interp = (f"{horse}: BSP ({bsp:.2f}) shorter than ISP ({isp:.2f}) "
                      f"by {divergence_pct:.1f}%. Late exchange money "
                      f"supporting this horse.")
        elif bsp > isp:
            direction = "BSP_LONGER"
            interp = (f"{horse}: BSP ({bsp:.2f}) longer than ISP ({isp:.2f}) "
                      f"by {divergence_pct:.1f}%. Late exchange money "
                      f"opposing this horse — possible smart money exit.")
        else:
            direction = "ALIGNED"
            interp = f"{horse}: BSP and ISP aligned. No divergence."

        flagged = divergence_pct >= self.thresholds.divergence_pct

        if flagged:
            interp += (f" ⚠ FLAGGED: Divergence exceeds "
                       f"{self.thresholds.divergence_pct:.0f}% threshold.")

        return DivergenceResult(
            horse=horse, bsp=bsp, isp=isp,
            divergence_pct=round(divergence_pct, 2),
            direction=direction, flagged=flagged,
            interpretation=interp
        )

    def generate_market_report(self, race_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a pre-race market constraint summary for all runners.

        Args:
            race_data: Dict with keys:
                - race_id (str): Unique race identifier.
                - track (str): Track name.
                - race_date (str): Date of the race.
                - runners (list of dict): Each runner dict has:
                    - horse (str)
                    - morning_price (float)
                    - bsp (float, may be estimated pre-race)
                    - isp (float, optional)
                    - is_favourite (bool)

        Returns:
            Dict with: race_id, track, timestamp, runner_reports (list),
            summary (str), constraint_count (dict).
        """
        runners = race_data.get("runners", [])
        race_id = race_data.get("race_id", "unknown")
        track = race_data.get("track", "unknown")

        runner_reports = []
        blocked_count = 0
        warning_count = 0
        steamers = []
        drifters = []

        for runner in runners:
            horse = runner.get("horse", "Unknown")
            morning_price = runner.get("morning_price", 0)
            bsp = runner.get("bsp", 0)
            isp = runner.get("isp")

            # Drift analysis
            drift = self.analyse_drift(horse, morning_price, bsp)

            # Divergence analysis (if ISP available)
            divergence = None
            if isp and isp > 0:
                divergence = self.bsp_isp_divergence(horse, bsp, isp)

            # Track steamers/drifters
            if drift.classification == DriftClassification.STEAMER:
                steamers.append(horse)
            elif drift.classification == DriftClassification.DRIFTER:
                drifters.append(horse)

            report = {
                "horse": horse,
                "morning_price": morning_price,
                "bsp": bsp,
                "drift_classification": drift.classification.value,
                "drift_pct": drift.pct_change,
                "drift_description": drift.description,
            }
            if divergence:
                report["divergence_pct"] = divergence.divergence_pct
                report["divergence_flagged"] = divergence.flagged
                report["divergence_interpretation"] = divergence.interpretation

            runner_reports.append(report)

        # Build summary
        summary_parts = [
            f"MARKET CONSTRAINT REPORT — {track} — Race {race_id}",
            f"Runners analysed: {len(runners)}",
        ]
        if steamers:
            summary_parts.append(
                f"STEAMERS (shortening >{self.thresholds.steam_pct:.0f}%): "
                f"{', '.join(steamers)}"
            )
        if drifters:
            summary_parts.append(
                f"DRIFTERS (lengthening >{self.thresholds.drift_pct:.0f}%): "
                f"{', '.join(drifters)}"
            )
        if not steamers and not drifters:
            summary_parts.append("No significant market movements detected.")

        return {
            "race_id": race_id,
            "track": track,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "runner_reports": runner_reports,
            "summary": "\n".join(summary_parts),
            "constraint_counts": {
                "steamers": len(steamers),
                "drifters": len(drifters),
                "total_runners": len(runners),
            }
        }

    # ------------------------------------------------------------------
    # Storage
    # ------------------------------------------------------------------

    def _store_decision(self, decision: ConstraintDecision,
                        market_data: Optional[Dict[str, Any]] = None) -> None:
        """Persist a constraint decision to the market_behaviour table.

        Args:
            decision: The ConstraintDecision to store.
            market_data: Optional raw market data dict for archival.
        """
        conn = self._get_conn()
        try:
            morning_price = None
            bsp = None
            isp = None
            drift_pct = None
            drift_class = None

            if decision.drift_result:
                morning_price = decision.drift_result.morning_price
                bsp = decision.drift_result.bsp
                drift_pct = decision.drift_result.pct_change
                drift_class = decision.drift_result.classification.value

            if market_data:
                isp = market_data.get("isp")

            conn.execute("""
                INSERT INTO market_behaviour (
                    horse, morning_price, bsp, isp,
                    drift_pct, drift_classification,
                    constraint_verdict, constraint_message,
                    counter_signals, override_allowed,
                    raw_data, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                decision.horse,
                morning_price,
                bsp,
                isp,
                drift_pct,
                drift_class,
                decision.verdict.value,
                decision.message,
                json.dumps(decision.counter_signals),
                1 if decision.override_allowed else 0,
                json.dumps(market_data) if market_data else None,
                decision.timestamp,
            ))
            conn.commit()
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Query Methods
    # ------------------------------------------------------------------

    def get_horse_market_history(self, horse: str) -> List[Dict[str, Any]]:
        """Retrieve all market behaviour records for a horse.

        Args:
            horse: Name of the horse.

        Returns:
            List of dicts with market behaviour records.
        """
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM market_behaviour WHERE horse = ? "
                "ORDER BY created_at DESC", (horse,)
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_race_constraints(self, race_id: str) -> List[Dict[str, Any]]:
        """Retrieve all constraint decisions for a race.

        Args:
            race_id: Unique race identifier.

        Returns:
            List of dicts with constraint records.
        """
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM market_behaviour WHERE race_id = ? "
                "ORDER BY created_at DESC", (race_id,)
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()
