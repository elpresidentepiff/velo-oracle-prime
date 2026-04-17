"""
VETP LAYER 1 SERVICE – Event Memory / Ledger of Pain & Victory

This is the bit that actually does something:
- Logs events
- Retrieves patterns
- Feeds higher layers with lived experience

Every time they shaft you or you torch them, VÉLØ gets smarter
instead of you just getting angrier.
"""

from typing import List, Optional
from sqlalchemy.orm import Session
from datetime import date

from ..vetp_event import VETPEvent
from ..schemas.vetp import VETPEventIn, VETPEventOut, VETPEventSummary


class VETPLayer1:
    """
    VETP LAYER 1 – Event Memory / Ledger of Pain & Victory.

    Responsibilities:
    - Persist every key race we live through
    - Provide retrieval APIs for pattern engines (Mesaafi trap, Castanea pattern, etc.)
    - Enforce that an event_id is unique per race
    - Turn lived experience into queryable data
    """

    def __init__(self, db: Session):
        self.db = db

    # ========== CORE LOGGING ==========

    def log_event(self, payload: VETPEventIn) -> VETPEventOut:
        """
        Create or update a VETP event by event_id.
        
        This is how every race gets immortalized.
        """
        obj = (
            self.db.query(VETPEvent)
            .filter(VETPEvent.event_id == payload.event_id)
            .one_or_none()
        )

        if obj is None:
            obj = VETPEvent(event_id=payload.event_id)
            self.db.add(obj)

        # Update all fields
        for field, value in payload.model_dump().items():
            if field == "event_id":
                continue
            setattr(obj, field, value)

        self.db.commit()
        self.db.refresh(obj)
        return VETPEventOut.model_validate(obj)

    # ========== RETRIEVAL HELPERS ==========

    def get_event(self, event_id: str) -> Optional[VETPEventOut]:
        """Get a single event by ID"""
        obj = (
            self.db.query(VETPEvent)
            .filter(VETPEvent.event_id == event_id)
            .one_or_none()
        )
        if not obj:
            return None
        return VETPEventOut.model_validate(obj)

    def recent_events(
        self,
        limit: int = 50,
        code: Optional[str] = None,
        emotion_tag: Optional[str] = None,
    ) -> List[VETPEventOut]:
        """
        Get recent events, optionally filtered.
        
        Args:
            limit: Max number of events
            code: Filter by race code (Flat-AW, Hurdle, etc)
            emotion_tag: Filter by emotion (rage, smug, etc)
        """
        q = self.db.query(VETPEvent).order_by(
            VETPEvent.date.desc(), 
            VETPEvent.id.desc()
        )
        
        if code:
            q = q.filter(VETPEvent.code == code)
        if emotion_tag:
            q = q.filter(VETPEvent.emotion_tag == emotion_tag)
        
        objs = q.limit(limit).all()
        return [VETPEventOut.model_validate(o) for o in objs]

    def get_all_events(self) -> List[VETPEventSummary]:
        """Get all events (summary only)"""
        objs = self.db.query(VETPEvent).order_by(
            VETPEvent.date.desc()
        ).all()
        return [VETPEventSummary.model_validate(o) for o in objs]

    # ========== PATTERN RECOGNITION HOOKS ==========

    def mesaafi_trap_candidates(self, limit: int = 200) -> List[VETPEventOut]:
        """
        Find AW handicaps with short favs where we tagged fake_fav / non_trier_suspected.
        
        This is the "NEVER ALL-IN ON PRETTY AW FIGS" pattern.
        
        These are the races where:
        - Market said: "Safe jolly, strong numbers, low risk"
        - Reality said: "Horse never really asked, designed trap"
        
        This dataset feeds feature weights for fake favorite detection.
        """
        flags = ["fake_fav", "non_trier_suspected"]
        q = (
            self.db.query(VETPEvent)
            .filter(VETPEvent.code.like("Flat-AW%"))
            .filter(VETPEvent.behaviour_flags.isnot(None))
        )
        
        objs = [
            e
            for e in q.order_by(VETPEvent.date.desc()).limit(limit).all()
            if any(f in (e.behaviour_flags or []) for f in flags)
        ]
        return [VETPEventOut.model_validate(o) for o in objs]

    def castanea_dominance_cases(self, limit: int = 200) -> List[VETPEventOut]:
        """
        Find events flagged 'dominant_engine' where we were correct.
        
        This is the "DOMINANT ENGINE IN WEAK JOCKEY ROOM" pattern.
        
        These are the races where:
        - One horse had BOTH the highest figures AND cleanest profile
        - Opposition was mostly exposed
        - We correctly identified it as domination, not "open"
        
        Used to calibrate when to be pro-fav instead of auto-laying.
        """
        q = (
            self.db.query(VETPEvent)
            .filter(VETPEvent.behaviour_flags.isnot(None))
            .filter(VETPEvent.read_race_right == "Yes")
        )
        
        objs = [
            e
            for e in q.order_by(VETPEvent.date.desc()).limit(limit).all()
            if "dominant_engine" in (e.behaviour_flags or [])
        ]
        return [VETPEventOut.model_validate(o) for o in objs]

    def small_field_hype_traps(self, limit: int = 200) -> List[VETPEventOut]:
        """
        Find small-field graded jumps with media monsters that went wrong.
        
        This is the "CONSTITUTION HILL / SMALL-FIELD LIQUIDITY TRAP" pattern.
        
        These are the races where:
        - Field ≤ 6
        - Media hype massive
        - Shorty gets turned over by 20/1+ rag
        
        Used to avoid "free money" narratives in hyped small fields.
        """
        q = (
            self.db.query(VETPEvent)
            .filter(VETPEvent.field_size <= 6)
            .filter(VETPEvent.behaviour_flags.isnot(None))
        )
        
        objs = [
            e
            for e in q.order_by(VETPEvent.date.desc()).limit(limit).all()
            if "media_hype" in (e.behaviour_flags or []) or 
               "small_field_fall_risk" in (e.behaviour_flags or [])
        ]
        return [VETPEventOut.model_validate(o) for o in objs]

    def spray_and_pray_disasters(self, limit: int = 200) -> List[VETPEventOut]:
        """
        Find races where we backed multiple horses with no clear edge.
        
        This is the "SPRAY & PRAY" anti-pattern.
        
        These are the races where:
        - We backed >2 runners in same market
        - Justification was narrative, not structural edge
        - Result: fragmented stakes, zero edge, emotional coverage
        
        Used to flag "SPRAY MODE" and recommend no bet.
        """
        q = (
            self.db.query(VETPEvent)
            .filter(VETPEvent.behaviour_flags.isnot(None))
        )
        
        objs = [
            e
            for e in q.order_by(VETPEvent.date.desc()).limit(limit).all()
            if "no_clear_edge" in (e.behaviour_flags or []) or
               "emotional_coverage" in (e.behaviour_flags or []) or
               "overtrading" in (e.behaviour_flags or [])
        ]
        return [VETPEventOut.model_validate(o) for o in objs]

    def kempton_kickers(self, limit: int = 200) -> List[VETPEventOut]:
        """
        Find Kempton races where a horse with true turn of foot beat one-paced grinders.
        
        This is the "KICK VS STATIC SPEED" pattern.
        
        Used to upgrade kickers and downgrade honest plodders at Kempton.
        """
        q = (
            self.db.query(VETPEvent)
            .filter(VETPEvent.course == "Kempton")
            .filter(VETPEvent.code.like("Flat-AW%"))
            .filter(VETPEvent.behaviour_flags.isnot(None))
        )
        
        objs = [
            e
            for e in q.order_by(VETPEvent.date.desc()).limit(limit).all()
            if "strong_turn_of_foot" in (e.behaviour_flags or [])
        ]
        return [VETPEventOut.model_validate(o) for o in objs]

    # ========== STATISTICS ==========

    def get_stats(self) -> dict:
        """Get overall VETP statistics"""
        total = self.db.query(VETPEvent).count()
        
        wins = self.db.query(VETPEvent).filter(
            VETPEvent.pnl_units > 0
        ).count()
        
        losses = self.db.query(VETPEvent).filter(
            VETPEvent.pnl_units < 0
        ).count()
        
        total_pnl = self.db.query(VETPEvent).with_entities(
            VETPEvent.pnl_units
        ).all()
        total_pnl = sum([p[0] for p in total_pnl if p[0] is not None])
        
        emotions = self.db.query(
            VETPEvent.emotion_tag
        ).filter(
            VETPEvent.emotion_tag.isnot(None)
        ).all()
        emotion_counts = {}
        for (tag,) in emotions:
            emotion_counts[tag] = emotion_counts.get(tag, 0) + 1
        
        return {
            "total_events": total,
            "winning_events": wins,
            "losing_events": losses,
            "total_pnl_units": round(total_pnl, 2),
            "emotion_distribution": emotion_counts,
        }
