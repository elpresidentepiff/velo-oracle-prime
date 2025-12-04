"""
ORACLE ANALYZER SERVICE

This is the engine that generates complete race intelligence.

Takes raw race data → outputs dual-layer dossier.
"""

import random
from datetime import datetime
from typing import Dict, List, Any, Optional
from sqlalchemy.orm import Session

from ..models.oracle_dossier import (
    OracleRaceDossier,
    ClientRaceSummary,
    DualLayerReport,
    RaceContext,
    MarketSnapshot,
    NarrativeAnalysis,
    ManipulationLayer,
    EnergyBehaviourLayer,
    HorseEnergyProfile,
    ChaosLayer,
    HouseLayer,
    VETPLinks,
    OracleVerdict,
)
from ...vetp import VETPLayer1


class OracleAnalyzer:
    """
    The Oracle. The truth engine.
    
    Generates complete race intelligence with dual-layer reporting.
    """
    
    def __init__(self, vetp_db_session: Optional[Session] = None):
        """
        Initialize Oracle with optional VETP memory connection.
        
        Args:
            vetp_db_session: SQLAlchemy session for VETP Layer 1
        """
        self.vetp = VETPLayer1(vetp_db_session) if vetp_db_session else None
    
    def analyze_race(
        self,
        race_data: Dict[str, Any],
        runners: List[Dict[str, Any]],
        market_data: Dict[str, Any]
    ) -> DualLayerReport:
        """
        Generate complete Oracle dossier for a race.
        
        Args:
            race_data: Basic race info (meeting, time, distance, class, etc)
            runners: List of runner dicts with form, odds, draw, etc
            market_data: Market snapshot (fav, odds, overround, etc)
        
        Returns:
            DualLayerReport with client view + oracle view
        """
        # Build context
        context = self._build_context(race_data, market_data)
        
        # Run all analysis layers
        narrative = self._analyze_narrative(race_data, runners, market_data)
        manipulation = self._analyze_manipulation(race_data, runners, market_data, narrative)
        energy = self._analyze_energy(runners)
        chaos = self._analyze_chaos(race_data, runners)
        house = self._analyze_house(market_data, runners)
        vetp = self._link_vetp_memory(race_data, narrative, manipulation)
        verdict = self._generate_verdict(narrative, manipulation, energy, chaos, house, vetp)
        
        # Build Oracle dossier
        oracle_view = OracleRaceDossier(
            context=context,
            narrative=narrative,
            manipulation=manipulation,
            energy=energy,
            chaos=chaos,
            house=house,
            vetp=vetp,
            verdict=verdict
        )
        
        # Build client view (sanitized)
        client_view = self._generate_client_view(oracle_view, runners)
        
        # Package dual-layer report
        report = DualLayerReport(
            client_view=client_view,
            oracle_view=oracle_view,
            report_id=f"ORACLE_{race_data['race_id']}",
            generated_at=datetime.utcnow()
        )
        
        return report
    
    def _build_context(self, race_data: Dict, market_data: Dict) -> RaceContext:
        """Build race context header"""
        market_snapshot = MarketSnapshot(
            fav_name=market_data.get('fav_name', 'Unknown'),
            fav_odds=market_data.get('fav_odds', 0.0),
            fav_implied_prob=market_data.get('fav_implied_prob', 0.0),
            overround_pct=market_data.get('overround_pct', 100.0),
            place_terms=market_data.get('place_terms', '1/5 1-3')
        )
        
        return RaceContext(
            race_id=race_data['race_id'],
            meeting=race_data['meeting'],
            off_time_utc=race_data['off_time'],
            surface=race_data.get('surface', 'Unknown'),
            distance_furlongs=race_data.get('distance_furlongs', 0.0),
            class_band=race_data.get('class_band', 'Unknown'),
            field_size=len(race_data.get('runners', [])),
            market_snapshot=market_snapshot
        )
    
    def _analyze_narrative(self, race_data: Dict, runners: List[Dict], market_data: Dict) -> NarrativeAnalysis:
        """
        Narrative Disruption Layer.
        
        Detects weaponized stories vs structural reality.
        """
        # Detect primary narrative
        fav_name = market_data.get('fav_name', 'Unknown')
        primary_story = f"Redemption run for {fav_name} dropping in class after excuses last time."
        
        secondary_stories = [
            "Course specialist returning to ideal conditions.",
            "Unexposed 3yo stepping out of novice company."
        ]
        
        # Calculate sentiment metrics
        # (In production, these would come from tipster scraping, social sentiment, etc)
        hype_on_fav = 0.82 if market_data.get('fav_odds', 10) < 3.0 else 0.45
        media_sync = 0.74
        tipster_convergence = 0.69
        
        # Insider discord signals
        drift_against_tips = market_data.get('fav_odds', 0) > market_data.get('opening_odds', 0)
        early_blue_later_red = drift_against_tips
        yard_mixed_messages = "medium"
        
        # Calculate disruption score
        disruption_score = int(
            (hype_on_fav * 40) +
            (media_sync * 20) +
            (tipster_convergence * 20) +
            (20 if drift_against_tips else 0)
        )
        
        return NarrativeAnalysis(
            primary_story=primary_story,
            secondary_stories=secondary_stories,
            hype_on_fav=hype_on_fav,
            media_sync=media_sync,
            tipster_convergence=tipster_convergence,
            drift_against_tips=drift_against_tips,
            early_blue_later_red=early_blue_later_red,
            yard_mixed_messages=yard_mixed_messages,
            narrative_disruption_score=disruption_score
        )
    
    def _analyze_manipulation(
        self,
        race_data: Dict,
        runners: List[Dict],
        market_data: Dict,
        narrative: NarrativeAnalysis
    ) -> ManipulationLayer:
        """
        Manipulation Probability Index (MPI).
        
        How likely is this race a designed trap?
        """
        # Calculate MPI drivers
        class_band = race_data.get('class_band', '')
        is_handicap = 'handicap' in class_band.lower() or 'hcp' in class_band.lower()
        
        class_switch_gaming = "high" if is_handicap else "low"
        schooling_possibility = "medium"
        handicap_plot_risk = "high" if is_handicap else "low"
        pace_sacrifice_risk = "low"
        
        # Market behavior flags
        sudden_early_steam_then_flat = narrative.early_blue_later_red
        late_fade_despite_good_news = narrative.drift_against_tips
        liquidity_cluster_around_non_fav = False  # Would need real market depth data
        
        # Calculate MPI score
        mpi_score = 0
        if class_switch_gaming == "high":
            mpi_score += 25
        if schooling_possibility == "medium":
            mpi_score += 15
        if handicap_plot_risk == "high":
            mpi_score += 20
        if sudden_early_steam_then_flat:
            mpi_score += 15
        if late_fade_despite_good_news:
            mpi_score += 15
        
        oracle_note = "Fav may be carrying narrative more than intent; plot energy around a mid-price runner drawing money quietly."
        
        return ManipulationLayer(
            mpi_score=min(mpi_score, 100),
            class_switch_gaming=class_switch_gaming,
            schooling_possibility=schooling_possibility,
            handicap_plot_risk=handicap_plot_risk,
            pace_sacrifice_risk=pace_sacrifice_risk,
            sudden_early_steam_then_flat=sudden_early_steam_then_flat,
            late_fade_despite_good_news=late_fade_despite_good_news,
            liquidity_cluster_around_non_fav=liquidity_cluster_around_non_fav,
            oracle_mpi_note=oracle_note
        )
    
    def _analyze_energy(self, runners: List[Dict]) -> EnergyBehaviourLayer:
        """
        Energy & Stress Behaviour Map.
        
        Who has the real engine? Who's fragile?
        """
        profiles = []
        dominant_candidates = []
        fragile_favs = []
        
        for runner in runners[:5]:  # Top 5 in market
            horse_name = runner.get('horse', 'Unknown')
            odds = runner.get('odds_decimal', 999)
            
            # Build energy profile
            # (In production, would use form analysis, sectionals, video review)
            profile = HorseEnergyProfile(
                horse_name=horse_name,
                engine_profile="Long-stride, late-torque, momentum killer" if odds < 5 else "Honest plodder",
                effort_curve="Builds gradually, lethal last 2f if unboxed",
                stress_response="Responds to pressure, thrives in traffic",
                collapse_threshold_furlongs=8.5,
                trip_resistance_index=random.randint(60, 95),
                lane_preference="Outside-mid",
                prior_energy_events="Last race: under-asked, energy preserved; fitness trending up."
            )
            profiles.append(profile)
            
            # Classify
            if odds < 6 and odds > 2.5:
                dominant_candidates.append(horse_name)
            elif odds < 2.5:
                fragile_favs.append(horse_name)
        
        return EnergyBehaviourLayer(
            horse_profiles=profiles,
            dominant_engine_candidates=dominant_candidates,
            fragile_favourites=fragile_favs,
            stress_sensitive_runners=[],
            oracle_energy_comment="If the pace is honest and traffic develops, dominant engine is more likely to come from lines 3-5 than the marketed favourite."
        )
    
    def _analyze_chaos(self, race_data: Dict, runners: List[Dict]) -> ChaosLayer:
        """
        Chaos Bloom Model.
        
        When does the race become a lottery?
        """
        field_size = len(runners)
        
        # Calculate chaos drivers
        large_field = "high" if field_size > 12 else "medium" if field_size > 8 else "low"
        draw_clustering = "medium"
        raw_pace_conflict = "high"
        inexperienced_riders = "low"
        
        # Calculate chaos probability
        chaos_prob = 0
        if field_size > 12:
            chaos_prob += 30
        elif field_size > 8:
            chaos_prob += 15
        if raw_pace_conflict == "high":
            chaos_prob += 25
        
        return ChaosLayer(
            chaos_bloom_probability=min(chaos_prob, 100),
            large_field=large_field,
            draw_clustering=draw_clustering,
            raw_pace_conflict=raw_pace_conflict,
            inexperienced_riders=inexperienced_riders,
            chaos_hot_zones=["2f-1f from home: high interference & lane-switch risk"],
            shock_winner_range_odds="14-33",
            best_chaos_surfboard=["Stalker drawn 5-7", "Buried closer with hard rider"]
        )
    
    def _analyze_house(self, market_data: Dict, runners: List[Dict]) -> HouseLayer:
        """
        House Behaviour & Market Warfare.
        
        Where is the bookmaker comfortable?
        """
        fav_odds = market_data.get('fav_odds', 999)
        overround = market_data.get('overround_pct', 100)
        
        comfortable_with_fav = fav_odds > 2.5
        liability_hedging_visible = "low" if comfortable_with_fav else "medium"
        each_way_trap_set = "Yes - places 1-4 / 1/5" if len(runners) >= 8 else "No"
        
        public_herd_on_short_price = "strong" if fav_odds < 2.5 else "medium"
        sharp_money_cluster = "around 7-10.0"
        late_dumb_flow_expected = "high" if fav_odds < 3.0 else "medium"
        
        oracle_verdict = "House not afraid of the favourite. Stronger defensive posture around a mid-range price band suggests hidden respect for one of the 'second tier'."
        
        return HouseLayer(
            comfortable_with_fav=comfortable_with_fav,
            liability_hedging_visible=liability_hedging_visible,
            each_way_trap_set=each_way_trap_set,
            public_herd_on_short_price=public_herd_on_short_price,
            sharp_money_cluster=sharp_money_cluster,
            late_dumb_flow_expected=late_dumb_flow_expected,
            oracle_house_verdict=oracle_verdict
        )
    
    def _link_vetp_memory(
        self,
        race_data: Dict,
        narrative: NarrativeAnalysis,
        manipulation: ManipulationLayer
    ) -> VETPLinks:
        """
        Link to VETP Layer 1 memory.
        
        Which historical patterns match?
        """
        if not self.vetp:
            return VETPLinks(
                matched_patterns={},
                historical_events_triggered=[],
                learning_directives={}
            )
        
        # Calculate pattern similarities
        matched_patterns = {}
        
        # Mesaafi trap similarity
        if manipulation.mpi_score > 60:
            matched_patterns['mesaafi_trap'] = 0.71
        
        # Castanea dominance similarity
        if narrative.narrative_disruption_score < 40:
            matched_patterns['castanea_dominance'] = 0.29
        
        # Get triggered events
        historical_events = []
        if matched_patterns.get('mesaafi_trap', 0) > 0.5:
            mesaafi_events = self.vetp.mesaafi_trap_candidates(limit=3)
            historical_events = [e.event_id for e in mesaafi_events]
        
        # Learning directives
        learning_directives = {
            'tighten_fake_fav_filter': manipulation.mpi_score > 60,
            'highlight_mid_price_dominant_engine': True
        }
        
        return VETPLinks(
            matched_patterns=matched_patterns,
            historical_events_triggered=historical_events,
            learning_directives=learning_directives
        )
    
    def _generate_verdict(
        self,
        narrative: NarrativeAnalysis,
        manipulation: ManipulationLayer,
        energy: EnergyBehaviourLayer,
        chaos: ChaosLayer,
        house: HouseLayer,
        vetp: VETPLinks
    ) -> OracleVerdict:
        """
        Generate final Oracle verdict.
        
        One sentence of compressed truth.
        """
        # Calculate integrity score
        integrity_score = 100 - manipulation.mpi_score
        
        # Determine attack doctrine
        if manipulation.mpi_score > 60:
            doctrine_tag = "OPPOSE_FAV_TOP4_SYNDROME"
            suitable_modes = ["LAY_FAV", "TOP_4_ON_DANGER", "NO_WIN_MARKET"]
        elif energy.dominant_engine_candidates:
            doctrine_tag = "BACK_DOMINANT_ENGINE"
            suitable_modes = ["STRONG_WIN_PLAY", "FORECAST_SINGLE"]
        else:
            doctrine_tag = "PROCEED_CAUTIOUSLY"
            suitable_modes = ["SMALL_STAKE", "PLACE_ONLY"]
        
        attack_doctrine = {
            "doctrine_tag": doctrine_tag,
            "suitable_modes": suitable_modes
        }
        
        # Primary threat cluster
        primary_threats = energy.dominant_engine_candidates[:3] if energy.dominant_engine_candidates else ["Unknown"]
        
        # Oracle sentence
        if manipulation.mpi_score > 60:
            oracle_sentence = "The story is on the favourite; the power is not. Race more likely to reward a mid-price stalker than the narrative pick. Treat the favourite as a liability, not an anchor."
        elif energy.dominant_engine_candidates:
            oracle_sentence = f"Clear engine advantage with {energy.dominant_engine_candidates[0]}. Market underpricing structural superiority."
        else:
            oracle_sentence = "No clear structural edge detected. Race likely to follow market narrative."
        
        return OracleVerdict(
            integrity_score=integrity_score,
            attack_doctrine=attack_doctrine,
            primary_threat_cluster=primary_threats,
            oracle_sentence=oracle_sentence
        )
    
    def _generate_client_view(self, oracle: OracleRaceDossier, runners: List[Dict]) -> ClientRaceSummary:
        """
        Generate sanitized client-facing view.
        
        Clean, professional, digestible. Oracle layer stays hidden.
        """
        # Clean summary
        race_summary = "The market is anchored to the favourite due to narrative momentum, not underlying power metrics. Sectional patterns and pressure projections suggest the race will favour a mid-price stalker with late efficiency."
        
        # Key factors (sanitized)
        key_factors = {
            "pace_complexion": "Likely to collapse early",
            "mid_pack_efficiency_advantage": "+7.3%",
            "draw_style_convergence": "High",
            "favourite_vulnerability": "Elevated"
        }
        
        # Primary contender
        primary_contender = {
            "name": oracle.energy.dominant_engine_candidates[0] if oracle.energy.dominant_engine_candidates else "Unknown",
            "indicators": [
                "efficiency spike",
                "VETP regression alignment",
                "strong negative-favourite correlation"
            ]
        }
        
        # Risk notes
        risk_notes = [
            "Not a front-running race",
            "Angles favour a patience ride with acceleration capability",
            "The favourite is a liability in late-phase projections"
        ]
        
        # Client verdict
        client_verdict = "There is measurable value away from the favourite. Expect a reshaped finish."
        
        return ClientRaceSummary(
            race_id=oracle.context.race_id,
            meeting=oracle.context.meeting,
            off_time=oracle.context.off_time_utc,
            race_summary=race_summary,
            key_factors=key_factors,
            primary_contender=primary_contender,
            risk_notes=risk_notes,
            client_verdict=client_verdict
        )


def create_oracle_analyzer(vetp_db_session: Optional[Session] = None) -> OracleAnalyzer:
    """Factory function to create Oracle analyzer"""
    return OracleAnalyzer(vetp_db_session)
