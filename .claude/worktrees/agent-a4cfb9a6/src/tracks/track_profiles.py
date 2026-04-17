"""
VÉLØ Oracle Prime — Phase 1: Track Profile Database
=====================================================

Module: src/tracks/track_profiles.py
Purpose: Pre-loaded intelligence for every UK racecourse. Queried
         automatically before every analysis to provide structural
         context that was missing at Wolverhampton.

Day 1 Lesson: "The system had zero track-specific intelligence for
Wolverhampton. It treated a tight, sharp, left-handed Tapeta track
the same as a galloping right-handed turf course. This is why the
chaos track won."

Architecture: Integrates with existing SQLite memory engine (WAL mode).
              New table: track_profiles.
              Pre-loaded with 40+ UK track profiles.

Author: VÉLØ Oracle Prime — Phase 1 Build
Date: 2026-02-16
"""

import sqlite3
import json
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Tuple


# ---------------------------------------------------------------------------
# Data Classes
# ---------------------------------------------------------------------------

@dataclass
class TrackProfile:
    """Complete profile for a UK racecourse.

    Attributes:
        track_name: Official track name.
        surface: turf / AW / mixed.
        aw_surface_type: Specific AW surface (Tapeta/Polytrack/Fibresand) or None.
        circuit_type: flat / undulating / sharp / galloping / stiff.
        direction: left-handed / right-handed.
        draw_bias_description: General draw bias description.
        draw_bias_distances: Dict mapping distance range → bias description.
        pace_bias: front / hold-up / neutral.
        rail_position_notes: Notes on rail movements and their effects.
        altitude: Approximate altitude in feet.
        drainage: Drainage quality description.
        official_distances: List of official race distances available.
        key_characteristics: List of key track characteristics.
        chaos_rating: 1-5 chaos rating (5 = maximum unpredictability).
        last_updated: ISO-8601 timestamp.
    """
    track_name: str
    surface: str
    aw_surface_type: Optional[str] = None
    circuit_type: str = "flat"
    direction: str = "left-handed"
    draw_bias_description: str = ""
    draw_bias_distances: Dict[str, str] = field(default_factory=dict)
    pace_bias: str = "neutral"
    rail_position_notes: str = ""
    altitude: int = 0
    drainage: str = ""
    official_distances: List[str] = field(default_factory=list)
    key_characteristics: List[str] = field(default_factory=list)
    chaos_rating: int = 2
    last_updated: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


# ---------------------------------------------------------------------------
# Pre-loaded Track Data — 40+ UK Tracks
# ---------------------------------------------------------------------------

def _get_preloaded_profiles() -> List[Dict[str, Any]]:
    """Return pre-loaded track profiles for all major UK racecourses.

    Returns:
        List of dicts, each representing a track profile.
    """
    profiles = [
        # ================================================================
        # ALL-WEATHER TRACKS (Priority — chaos tracks)
        # ================================================================
        {
            "track_name": "Wolverhampton",
            "surface": "AW",
            "aw_surface_type": "Tapeta",
            "circuit_type": "sharp",
            "direction": "left-handed",
            "draw_bias_description": "Low draws favoured in sprints (5f-6f). Less significant over longer trips.",
            "draw_bias_distances": {
                "5f": "Low draw significant advantage (stalls 1-4)",
                "6f": "Low draw moderate advantage",
                "7f": "Slight low draw advantage",
                "1m": "Minimal bias",
                "1m1f": "Minimal bias",
                "1m4f": "No significant bias"
            },
            "pace_bias": "front",
            "rail_position_notes": "Tight bends favour those racing prominently. Wide runners lose ground on turns.",
            "altitude": 450,
            "drainage": "All-weather — drainage not applicable",
            "official_distances": ["5f 21y", "5f 216y", "6f 20y", "7f 36y", "1m 142y", "1m 1f 104y", "1m 4f 51y", "1m 6f 166y", "2m 120y"],
            "key_characteristics": [
                "Tight, sharp track — favours handy, agile horses",
                "Tapeta surface — consistent but can ride differently in extreme cold",
                "Floodlit — evening meetings common",
                "Small field sizes frequent — increases chaos factor",
                "Front-runners heavily advantaged on sharp bends",
                "Day 1 failure track — RPD-C layer failed here (0/7)"
            ],
            "chaos_rating": 4,
        },
        {
            "track_name": "Kempton",
            "surface": "AW",
            "aw_surface_type": "Polytrack",
            "circuit_type": "flat",
            "direction": "right-handed",
            "draw_bias_description": "Generally fair track. Slight low draw advantage in sprints on the straight course.",
            "draw_bias_distances": {
                "5f": "Slight low draw advantage on straight course",
                "6f": "Slight low draw advantage on straight course",
                "7f": "Minimal bias (round course)",
                "1m": "No significant bias",
                "1m2f": "No significant bias",
                "1m4f": "No significant bias"
            },
            "pace_bias": "neutral",
            "rail_position_notes": "Fair track with sweeping bends. Less positional bias than sharper tracks.",
            "altitude": 50,
            "drainage": "All-weather — drainage not applicable",
            "official_distances": ["5f", "6f", "7f", "1m", "1m 2f", "1m 3f", "1m 4f", "2m"],
            "key_characteristics": [
                "Flat, fair, right-handed — one of the fairest AW tracks",
                "Polytrack surface — consistent and predictable",
                "Triangular layout with sweeping bends",
                "Good-quality fields — attracts competitive runners",
                "Also hosts NH racing on separate turf course"
            ],
            "chaos_rating": 2,
        },
        {
            "track_name": "Lingfield",
            "surface": "AW",
            "aw_surface_type": "Polytrack",
            "circuit_type": "sharp",
            "direction": "left-handed",
            "draw_bias_description": "Inner draw bias in sprints. Sharp bends amplify positional advantage.",
            "draw_bias_distances": {
                "5f": "Low draw significant advantage",
                "6f": "Low draw moderate advantage",
                "7f": "Slight low draw advantage",
                "1m": "Minimal bias",
                "1m2f": "No significant bias",
                "1m4f": "No significant bias"
            },
            "pace_bias": "front",
            "rail_position_notes": "Sharp bends favour front-runners and those drawn low. Wide runners lose significant ground.",
            "altitude": 200,
            "drainage": "All-weather — drainage not applicable",
            "official_distances": ["5f 6y", "6f 1y", "7f 1y", "1m 1y", "1m 2f", "1m 3f 133y", "1m 4f", "2m"],
            "key_characteristics": [
                "Sharp, left-handed — similar characteristics to Wolverhampton",
                "Front-runners advantaged on sharp bends",
                "Polytrack surface — generally consistent",
                "Also hosts turf racing (separate course)",
                "Sprint races heavily influenced by draw"
            ],
            "chaos_rating": 3,
        },
        {
            "track_name": "Newcastle",
            "surface": "AW",
            "aw_surface_type": "Tapeta",
            "circuit_type": "galloping",
            "direction": "left-handed",
            "draw_bias_description": "Generally fair draw. Slight advantage to those drawn centrally in large-field sprints.",
            "draw_bias_distances": {
                "5f": "Central draw slight advantage in large fields",
                "6f": "Minimal bias",
                "7f": "No significant bias",
                "1m": "No significant bias",
                "1m2f": "No significant bias",
                "2m": "No significant bias"
            },
            "pace_bias": "neutral",
            "rail_position_notes": "Galloping track with long straight. Hold-up horses advantaged at longer trips.",
            "altitude": 300,
            "drainage": "All-weather — drainage not applicable",
            "official_distances": ["5f", "6f", "7f 14y", "1m", "1m 2f 42y", "1m 4f 98y", "1m 5f", "2m 56y"],
            "key_characteristics": [
                "Galloping, left-handed — fairest AW track in UK",
                "Tapeta surface — large, sweeping track",
                "Long home straight — rewards strong finishers",
                "High-quality racing — hosts valuable AW fixtures",
                "Hold-up horses advantaged at longer trips"
            ],
            "chaos_rating": 2,
        },
        {
            "track_name": "Chelmsford",
            "surface": "AW",
            "aw_surface_type": "Polytrack",
            "circuit_type": "flat",
            "direction": "left-handed",
            "draw_bias_description": "Low draw slight advantage, particularly in sprints.",
            "draw_bias_distances": {
                "5f": "Low draw slight advantage",
                "6f": "Low draw slight advantage",
                "7f": "Minimal bias",
                "1m": "No significant bias",
                "1m2f": "No significant bias",
                "1m6f": "No significant bias"
            },
            "pace_bias": "neutral",
            "rail_position_notes": "Relatively flat with gentle bends. Fair track overall.",
            "altitude": 100,
            "drainage": "All-weather — drainage not applicable",
            "official_distances": ["5f", "6f", "7f", "1m", "1m 2f", "1m 6f", "2m"],
            "key_characteristics": [
                "Flat, left-handed — modern AW venue",
                "Polytrack surface — consistent",
                "Good facilities — attracts competitive fields",
                "Relatively fair track with minimal biases"
            ],
            "chaos_rating": 2,
        },
        {
            "track_name": "Southwell",
            "surface": "AW",
            "aw_surface_type": "Fibresand",
            "circuit_type": "sharp",
            "direction": "left-handed",
            "draw_bias_description": "Front-runners heavily advantaged. Low draw helps in sprints.",
            "draw_bias_distances": {
                "5f": "Low draw advantage",
                "6f": "Low draw moderate advantage",
                "7f": "Slight low draw advantage",
                "1m": "Minimal bias",
                "1m3f": "No significant bias",
                "2m": "No significant bias"
            },
            "pace_bias": "front",
            "rail_position_notes": "Tight track — front-runners rarely caught. Unique Fibresand surface is demanding.",
            "altitude": 100,
            "drainage": "All-weather — drainage not applicable",
            "official_distances": ["4f 214y", "5f", "6f 16y", "7f 14y", "1m 13y", "1m 3f", "1m 6f 21y", "2m"],
            "key_characteristics": [
                "Tight, sharp, left-handed — specialist track",
                "Fibresand surface — UNIQUE in UK, very demanding",
                "Front-runners heavily advantaged — rarely caught",
                "Specialists thrive — course form critical",
                "Low-grade racing — high chaos factor",
                "Also hosts NH racing on separate turf course"
            ],
            "chaos_rating": 4,
        },
        {
            "track_name": "Dundalk",
            "surface": "AW",
            "aw_surface_type": "Polytrack",
            "circuit_type": "flat",
            "direction": "left-handed",
            "draw_bias_description": "Generally fair. Slight low draw advantage in sprints.",
            "draw_bias_distances": {
                "5f": "Low draw slight advantage",
                "6f": "Minimal bias",
                "7f": "No significant bias",
                "1m": "No significant bias",
                "1m2f": "No significant bias"
            },
            "pace_bias": "neutral",
            "rail_position_notes": "Flat, fair track. Irish AW venue — different competitive landscape.",
            "altitude": 50,
            "drainage": "All-weather — drainage not applicable",
            "official_distances": ["5f", "6f", "7f", "1m", "1m 2f 150y", "1m 4f", "2m"],
            "key_characteristics": [
                "Flat, left-handed — Ireland's only AW track",
                "Polytrack surface — consistent",
                "Different competitive landscape to UK AW",
                "Attracts UK raiders for specific targets"
            ],
            "chaos_rating": 2,
        },

        # ================================================================
        # TURF TRACKS — Major Flat Venues
        # ================================================================
        {
            "track_name": "Ascot",
            "surface": "turf",
            "circuit_type": "galloping",
            "direction": "right-handed",
            "draw_bias_description": "Straight course: high draw advantage when ground is soft on stands side. Round course: minimal bias.",
            "draw_bias_distances": {
                "5f": "High draw advantage (stands side) on soft ground",
                "6f": "High draw advantage (stands side) on soft ground",
                "7f": "Minimal bias (round course)",
                "1m": "Minimal bias",
                "1m2f": "No significant bias",
                "1m4f": "No significant bias",
                "2m4f": "No significant bias"
            },
            "pace_bias": "neutral",
            "rail_position_notes": "Stiff uphill finish — stamina test. Ground conditions heavily influence draw bias on straight course.",
            "altitude": 200,
            "drainage": "Good drainage — rarely waterlogged",
            "official_distances": ["5f", "6f", "7f", "1m", "1m 2f", "1m 4f", "2m", "2m 4f"],
            "key_characteristics": [
                "Premier venue — highest quality racing in UK",
                "Stiff uphill finish — stamina at a premium",
                "Straight course separate from round course",
                "Royal Ascot — the pinnacle of flat racing",
                "Draw bias weather-dependent on straight course",
                "Galloping track — suits strong-travelling horses"
            ],
            "chaos_rating": 2,
        },
        {
            "track_name": "Cheltenham",
            "surface": "turf",
            "circuit_type": "undulating",
            "direction": "left-handed",
            "draw_bias_description": "NH track — no draw. Pace and stamina are key factors.",
            "draw_bias_distances": {},
            "pace_bias": "hold-up",
            "rail_position_notes": "Undulating with famous hill. New course and Old course have different characteristics.",
            "altitude": 400,
            "drainage": "Variable — can become testing in winter",
            "official_distances": ["2m", "2m 4f", "2m 5f", "3m", "3m 1f", "3m 2f", "3m 6f", "4m"],
            "key_characteristics": [
                "Premier NH venue — The Festival is the pinnacle",
                "Famous uphill finish — tests stamina and courage",
                "New Course and Old Course — different characteristics",
                "Undulating — rewards athletic, balanced jumpers",
                "Hold-up horses often advantaged — strong finish required",
                "High-class fields — form is generally reliable"
            ],
            "chaos_rating": 2,
        },
        {
            "track_name": "Aintree",
            "surface": "turf",
            "circuit_type": "galloping",
            "direction": "left-handed",
            "draw_bias_description": "NH track — no draw. Flat track — minimal bias.",
            "draw_bias_distances": {},
            "pace_bias": "neutral",
            "rail_position_notes": "Flat, galloping track. Grand National course has unique fences.",
            "altitude": 50,
            "drainage": "Good drainage — flat terrain",
            "official_distances": ["2m", "2m 4f", "3m", "3m 1f", "4m 2f"],
            "key_characteristics": [
                "Home of the Grand National — iconic venue",
                "Flat, galloping track — suits long-striding horses",
                "Grand National course has unique, demanding fences",
                "Mildmay Course for standard NH racing",
                "High-quality fields at major meetings"
            ],
            "chaos_rating": 3,
        },
        {
            "track_name": "York",
            "surface": "turf",
            "circuit_type": "galloping",
            "direction": "left-handed",
            "draw_bias_description": "Straight course: low draw advantage on soft ground (far side). Round course: minimal.",
            "draw_bias_distances": {
                "5f": "Low draw advantage on soft ground",
                "6f": "Low draw advantage on soft ground",
                "7f": "Minimal bias",
                "1m": "No significant bias",
                "1m2f": "No significant bias",
                "1m4f": "No significant bias",
                "1m6f": "No significant bias"
            },
            "pace_bias": "neutral",
            "rail_position_notes": "Wide, galloping track. Knavesmire — one of the fairest tracks in UK.",
            "altitude": 30,
            "drainage": "Good — flat terrain aids drainage",
            "official_distances": ["5f", "5f 89y", "6f", "6f 1y", "7f", "7f 192y", "1m", "1m 2f 56y", "1m 4f", "1m 6f", "2m 56y"],
            "key_characteristics": [
                "Premier flat venue — Ebor Festival, Dante Stakes",
                "Wide, galloping track — very fair",
                "Long home straight — rewards strong finishers",
                "High-quality fields — form is reliable",
                "Draw bias mainly on soft ground (straight course)"
            ],
            "chaos_rating": 1,
        },
        {
            "track_name": "Newmarket (Rowley Mile)",
            "surface": "turf",
            "circuit_type": "galloping",
            "direction": "right-handed",
            "draw_bias_description": "Stands side (high draw) often favoured in large-field sprints. Dip can catch out front-runners.",
            "draw_bias_distances": {
                "5f": "High draw advantage (stands side)",
                "6f": "High draw advantage (stands side)",
                "7f": "Slight high draw advantage",
                "1m": "Minimal bias",
                "1m2f": "No significant bias",
                "1m4f": "No significant bias"
            },
            "pace_bias": "neutral",
            "rail_position_notes": "Famous Dip — front-runners can be caught. Wide, straight track with no bends for most races.",
            "altitude": 100,
            "drainage": "Good — chalk downland drains well",
            "official_distances": ["5f", "6f", "7f", "1m", "1m 1f", "1m 2f", "1m 4f", "1m 6f", "2m 2f"],
            "key_characteristics": [
                "HQ of British flat racing — Guineas, Champions Day",
                "Straight course — no bends for races up to 1m",
                "Famous Dip — stamina test in final 2f",
                "Wide track — draw bias in sprints",
                "High-class fields — form very reliable",
                "Rowley Mile used in spring and autumn"
            ],
            "chaos_rating": 1,
        },
        {
            "track_name": "Newmarket (July Course)",
            "surface": "turf",
            "circuit_type": "galloping",
            "direction": "right-handed",
            "draw_bias_description": "Stands side often favoured. Less pronounced than Rowley Mile.",
            "draw_bias_distances": {
                "5f": "Stands side slight advantage",
                "6f": "Stands side slight advantage",
                "7f": "Minimal bias",
                "1m": "No significant bias",
                "1m2f": "No significant bias"
            },
            "pace_bias": "neutral",
            "rail_position_notes": "Undulating finish — less severe than Rowley Mile Dip.",
            "altitude": 100,
            "drainage": "Good — chalk downland",
            "official_distances": ["5f", "6f", "7f", "1m", "1m 2f", "1m 4f"],
            "key_characteristics": [
                "Summer course at Newmarket — July Festival",
                "Slightly different characteristics to Rowley Mile",
                "Less severe finish — not as stamina-demanding",
                "High-quality summer racing"
            ],
            "chaos_rating": 1,
        },
        {
            "track_name": "Epsom",
            "surface": "turf",
            "circuit_type": "undulating",
            "direction": "left-handed",
            "draw_bias_description": "High draw advantage in sprints (5f). Camber on home bend favours agile horses.",
            "draw_bias_distances": {
                "5f": "High draw significant advantage",
                "6f": "Slight high draw advantage",
                "7f": "Minimal bias",
                "1m": "No significant bias",
                "1m2f": "No significant bias (Derby course)",
                "1m4f": "No significant bias"
            },
            "pace_bias": "neutral",
            "rail_position_notes": "Severe downhill run to Tattenham Corner. Camber on home bend — horses drift wide.",
            "altitude": 500,
            "drainage": "Good — elevated position aids drainage",
            "official_distances": ["5f", "6f", "7f", "1m 114y", "1m 2f 17y", "1m 4f 6y"],
            "key_characteristics": [
                "Home of The Derby — unique, iconic track",
                "Severe undulations — downhill to Tattenham Corner",
                "Camber on home bend — horses drift wide",
                "Requires balanced, agile horses — not for plodders",
                "Unique test — Derby form not always transferable"
            ],
            "chaos_rating": 3,
        },
        {
            "track_name": "Goodwood",
            "surface": "turf",
            "circuit_type": "undulating",
            "direction": "right-handed",
            "draw_bias_description": "Significant draw bias at many distances. Low draw favoured on straight course when ground is soft.",
            "draw_bias_distances": {
                "5f": "Low draw advantage (far side) on soft ground",
                "6f": "Low draw advantage on soft ground",
                "7f": "Slight low draw advantage",
                "1m": "Minimal bias",
                "1m1f": "No significant bias",
                "1m4f": "No significant bias",
                "2m": "No significant bias"
            },
            "pace_bias": "neutral",
            "rail_position_notes": "Undulating with downhill run into straight. Ground conditions heavily influence draw.",
            "altitude": 600,
            "drainage": "Variable — exposed hilltop position",
            "official_distances": ["5f", "6f", "7f", "1m", "1m 1f 192y", "1m 4f", "1m 6f", "2m", "2m 5f"],
            "key_characteristics": [
                "Glorious Goodwood — premier summer festival",
                "Undulating, tricky track — requires experience",
                "Draw bias significant — especially on soft ground",
                "Elevated position — exposed to elements",
                "Quirky track — course form valuable"
            ],
            "chaos_rating": 3,
        },
        {
            "track_name": "Sandown",
            "surface": "turf",
            "circuit_type": "galloping",
            "direction": "right-handed",
            "draw_bias_description": "Minimal draw bias on round course. Sprint course (5f) — high draw slight advantage.",
            "draw_bias_distances": {
                "5f": "High draw slight advantage",
                "7f": "No significant bias",
                "1m": "No significant bias",
                "1m2f": "No significant bias",
                "1m4f": "No significant bias",
                "2m": "No significant bias"
            },
            "pace_bias": "neutral",
            "rail_position_notes": "Stiff uphill finish — tests stamina. Good-quality track for both flat and NH.",
            "altitude": 150,
            "drainage": "Good drainage",
            "official_distances": ["5f 6y", "7f 16y", "1m 14y", "1m 2f 7y", "1m 4f", "1m 6f", "2m"],
            "key_characteristics": [
                "Quality dual-purpose track — Eclipse Stakes venue",
                "Stiff uphill finish — stamina required",
                "Fair track — minimal biases",
                "NH course has testing fences"
            ],
            "chaos_rating": 2,
        },
        {
            "track_name": "Newbury",
            "surface": "turf",
            "circuit_type": "galloping",
            "direction": "left-handed",
            "draw_bias_description": "Generally fair. Slight low draw advantage in large-field sprints.",
            "draw_bias_distances": {
                "5f": "Slight low draw advantage in large fields",
                "6f": "Minimal bias",
                "7f": "No significant bias",
                "1m": "No significant bias",
                "1m2f": "No significant bias",
                "1m4f": "No significant bias"
            },
            "pace_bias": "neutral",
            "rail_position_notes": "Wide, galloping track. One of the fairest in the country.",
            "altitude": 400,
            "drainage": "Good — well-maintained",
            "official_distances": ["5f 34y", "6f 8y", "7f", "1m", "1m 2f 6y", "1m 4f 5y", "1m 5f 61y", "2m"],
            "key_characteristics": [
                "Premier dual-purpose venue — Lockinge, Hennessy",
                "Wide, galloping track — very fair",
                "Good-quality fields — form reliable",
                "Well-drained — rarely waterlogged"
            ],
            "chaos_rating": 1,
        },
        {
            "track_name": "Doncaster",
            "surface": "turf",
            "circuit_type": "galloping",
            "direction": "left-handed",
            "draw_bias_description": "Straight course: stands side (high draw) often favoured. Round course: minimal bias.",
            "draw_bias_distances": {
                "5f": "High draw advantage (stands side)",
                "6f": "High draw advantage (stands side)",
                "7f": "Slight high draw advantage",
                "1m": "Minimal bias (round course)",
                "1m2f": "No significant bias",
                "1m4f": "No significant bias",
                "1m6f": "No significant bias"
            },
            "pace_bias": "neutral",
            "rail_position_notes": "Wide, flat track. Straight mile is one of the longest in UK.",
            "altitude": 20,
            "drainage": "Can become testing — low-lying",
            "official_distances": ["5f", "5f 3y", "6f 2y", "7f 6y", "1m", "1m 2f 60y", "1m 4f", "1m 6f 132y", "2m 110y"],
            "key_characteristics": [
                "Historic venue — St Leger, Lincoln",
                "Wide, galloping, flat track",
                "Long straight — draw bias in sprints",
                "Low-lying — can become soft quickly",
                "High-quality fields at major meetings"
            ],
            "chaos_rating": 2,
        },
        {
            "track_name": "Chester",
            "surface": "turf",
            "circuit_type": "sharp",
            "direction": "left-handed",
            "draw_bias_description": "EXTREME low draw advantage — one of the most draw-biased tracks in UK.",
            "draw_bias_distances": {
                "5f": "Low draw EXTREME advantage",
                "6f": "Low draw EXTREME advantage",
                "7f": "Low draw significant advantage",
                "1m": "Low draw significant advantage",
                "1m2f": "Low draw moderate advantage",
                "1m4f": "Low draw slight advantage",
                "2m": "Minimal bias"
            },
            "pace_bias": "front",
            "rail_position_notes": "Tightest flat track in UK — essentially a circle. Low draw saves ground on every bend.",
            "altitude": 50,
            "drainage": "Can become testing — riverside location",
            "official_distances": ["5f 16y", "6f 17y", "7f 1y 122y", "1m 2f 70y", "1m 4f 63y", "1m 5f 89y", "2m 2f 147y"],
            "key_characteristics": [
                "Tightest flat track in UK — essentially circular",
                "EXTREME draw bias — low draw critical",
                "Front-runners heavily advantaged",
                "May Festival — high-quality but draw-dependent",
                "Course form essential — specialists thrive",
                "Small circumference amplifies all biases"
            ],
            "chaos_rating": 3,
        },
        {
            "track_name": "Haydock",
            "surface": "turf",
            "circuit_type": "galloping",
            "direction": "left-handed",
            "draw_bias_description": "Slight low draw advantage in sprints. Generally fair.",
            "draw_bias_distances": {
                "5f": "Slight low draw advantage",
                "6f": "Minimal bias",
                "7f": "No significant bias",
                "1m": "No significant bias",
                "1m2f": "No significant bias",
                "1m6f": "No significant bias"
            },
            "pace_bias": "neutral",
            "rail_position_notes": "Flat, galloping track. Good-quality surface.",
            "altitude": 100,
            "drainage": "Good — well-maintained",
            "official_distances": ["5f", "6f", "7f 37y", "1m 37y", "1m 2f 120y", "1m 3f 200y", "1m 6f", "2m 45y"],
            "key_characteristics": [
                "Quality dual-purpose venue — Sprint Cup, Betfair Chase",
                "Flat, galloping track — fair",
                "Good-quality fields",
                "Well-maintained surface"
            ],
            "chaos_rating": 2,
        },

        # ================================================================
        # TURF TRACKS — NH Specialist Venues
        # ================================================================
        {
            "track_name": "Wetherby",
            "surface": "turf",
            "circuit_type": "galloping",
            "direction": "left-handed",
            "draw_bias_description": "NH track — no draw.",
            "draw_bias_distances": {},
            "pace_bias": "neutral",
            "rail_position_notes": "Galloping track with testing fences. Fair course.",
            "altitude": 150,
            "drainage": "Good — well-drained",
            "official_distances": ["2m", "2m 3f", "3m", "3m 1f"],
            "key_characteristics": [
                "Quality NH venue — Charlie Hall Chase",
                "Galloping track — suits strong stayers",
                "Testing fences — jumping ability important",
                "Fair track — form reliable"
            ],
            "chaos_rating": 2,
        },
        {
            "track_name": "Catterick",
            "surface": "turf",
            "circuit_type": "sharp",
            "direction": "left-handed",
            "draw_bias_description": "Low draw advantage in sprints. Sharp track amplifies positional bias.",
            "draw_bias_distances": {
                "5f": "Low draw advantage",
                "5f 212y": "Low draw advantage",
                "7f": "Slight low draw advantage",
                "1m": "Minimal bias"
            },
            "pace_bias": "front",
            "rail_position_notes": "Sharp, undulating track. Front-runners favoured — hard to make up ground.",
            "altitude": 250,
            "drainage": "Variable — can become testing",
            "official_distances": ["5f", "5f 212y", "7f 6y", "1m 3f 214y", "1m 5f 192y"],
            "key_characteristics": [
                "Sharp, undulating track — specialist venue",
                "Front-runners heavily advantaged",
                "Low draw important in sprints",
                "Lower-grade racing — higher chaos factor",
                "Dual-purpose — flat and NH"
            ],
            "chaos_rating": 3,
        },
        {
            "track_name": "Carlisle",
            "surface": "turf",
            "circuit_type": "undulating",
            "direction": "right-handed",
            "draw_bias_description": "Slight high draw advantage in sprints. Stiff uphill finish.",
            "draw_bias_distances": {
                "5f": "Slight high draw advantage",
                "5f 193y": "Slight high draw advantage",
                "6f": "Minimal bias",
                "7f": "No significant bias",
                "1m": "No significant bias",
                "1m1f": "No significant bias"
            },
            "pace_bias": "neutral",
            "rail_position_notes": "Stiff uphill finish — stamina test. Undulating course.",
            "altitude": 200,
            "drainage": "Variable — northern exposure",
            "official_distances": ["5f", "5f 193y", "6f 195y", "7f 214y", "1m 1f 61y", "1m 3f 206y", "1m 6f 32y"],
            "key_characteristics": [
                "Undulating, right-handed — stiff finish",
                "Day 1 SUCCESS track — 75% Top Strike (6/8)",
                "Conventional track — form reliable",
                "Dual-purpose — flat and NH",
                "Northern venue — smaller fields common"
            ],
            "chaos_rating": 2,
        },
        {
            "track_name": "Musselburgh",
            "surface": "turf",
            "circuit_type": "flat",
            "direction": "right-handed",
            "draw_bias_description": "Low draw advantage in sprints. Tight track amplifies draw bias.",
            "draw_bias_distances": {
                "5f": "Low draw significant advantage",
                "7f": "Slight low draw advantage",
                "1m": "Minimal bias",
                "1m4f": "No significant bias",
                "2m": "No significant bias"
            },
            "pace_bias": "front",
            "rail_position_notes": "Tight, flat track. Front-runners favoured.",
            "altitude": 20,
            "drainage": "Can become testing — low-lying, coastal",
            "official_distances": ["5f 1y", "7f 33y", "1m", "1m 4f", "1m 6f", "2m"],
            "key_characteristics": [
                "Tight, flat, right-handed — Scottish venue",
                "Draw bias significant in sprints",
                "Front-runners favoured",
                "Dual-purpose — flat and NH",
                "Can become very testing in winter"
            ],
            "chaos_rating": 3,
        },
        {
            "track_name": "Ayr",
            "surface": "turf",
            "circuit_type": "galloping",
            "direction": "left-handed",
            "draw_bias_description": "Generally fair. Slight low draw advantage in large-field sprints.",
            "draw_bias_distances": {
                "5f": "Slight low draw advantage in large fields",
                "6f": "Minimal bias",
                "7f": "No significant bias",
                "1m": "No significant bias",
                "1m2f": "No significant bias"
            },
            "pace_bias": "neutral",
            "rail_position_notes": "Galloping track — one of the best in Scotland.",
            "altitude": 50,
            "drainage": "Good — well-drained",
            "official_distances": ["5f", "6f", "7f 50y", "1m", "1m 2f", "1m 5f 13y", "2m"],
            "key_characteristics": [
                "Premier Scottish venue — Ayr Gold Cup",
                "Galloping track — fair",
                "Good-quality fields at major meetings",
                "Dual-purpose — flat and NH"
            ],
            "chaos_rating": 2,
        },
        {
            "track_name": "Hamilton",
            "surface": "turf",
            "circuit_type": "undulating",
            "direction": "right-handed",
            "draw_bias_description": "Low draw advantage, especially over 5f-6f. Uphill finish.",
            "draw_bias_distances": {
                "5f": "Low draw advantage",
                "6f": "Low draw moderate advantage",
                "1m": "Slight low draw advantage",
                "1m1f": "Minimal bias",
                "1m3f": "No significant bias",
                "1m5f": "No significant bias"
            },
            "pace_bias": "neutral",
            "rail_position_notes": "Undulating with stiff uphill finish. Loop course — no straight races.",
            "altitude": 300,
            "drainage": "Good — elevated position",
            "official_distances": ["5f 4y", "6f 5y", "1m 65y", "1m 1f 36y", "1m 3f 16y", "1m 5f 9y"],
            "key_characteristics": [
                "Undulating, right-handed — stiff uphill finish",
                "Loop course — all races on the bend",
                "Low draw advantage in sprints",
                "Lower-grade flat racing",
                "Scottish venue — summer flat only"
            ],
            "chaos_rating": 3,
        },
        {
            "track_name": "Beverley",
            "surface": "turf",
            "circuit_type": "undulating",
            "direction": "right-handed",
            "draw_bias_description": "High draw advantage in sprints (far side). Significant bias.",
            "draw_bias_distances": {
                "5f": "High draw significant advantage",
                "7f": "Slight high draw advantage",
                "1m": "Minimal bias",
                "1m1f": "No significant bias",
                "1m3f": "No significant bias",
                "2m": "No significant bias"
            },
            "pace_bias": "neutral",
            "rail_position_notes": "Undulating with stiff uphill finish. Draw bias well-documented.",
            "altitude": 100,
            "drainage": "Variable",
            "official_distances": ["5f", "7f 96y", "1m 100y", "1m 1f 207y", "1m 3f 216y", "2m 35y"],
            "key_characteristics": [
                "Undulating, right-handed — stiff finish",
                "Significant draw bias in sprints",
                "Lower-grade flat racing",
                "Course form valuable"
            ],
            "chaos_rating": 3,
        },
        {
            "track_name": "Thirsk",
            "surface": "turf",
            "circuit_type": "flat",
            "direction": "left-handed",
            "draw_bias_description": "Low draw advantage in sprints. Tight track.",
            "draw_bias_distances": {
                "5f": "Low draw advantage",
                "6f": "Slight low draw advantage",
                "7f": "Minimal bias",
                "1m": "No significant bias",
                "1m4f": "No significant bias",
                "2m": "No significant bias"
            },
            "pace_bias": "front",
            "rail_position_notes": "Tight, flat track. Front-runners favoured.",
            "altitude": 100,
            "drainage": "Good",
            "official_distances": ["5f", "6f", "7f", "1m", "1m 4f", "2m"],
            "key_characteristics": [
                "Tight, flat, left-handed — sharp track",
                "Front-runners favoured",
                "Low draw advantage in sprints",
                "Lower-grade flat racing"
            ],
            "chaos_rating": 3,
        },
        {
            "track_name": "Ripon",
            "surface": "turf",
            "circuit_type": "undulating",
            "direction": "right-handed",
            "draw_bias_description": "High draw advantage in sprints. Well-documented bias.",
            "draw_bias_distances": {
                "5f": "High draw advantage",
                "6f": "Slight high draw advantage",
                "1m": "Minimal bias",
                "1m1f": "No significant bias",
                "1m4f": "No significant bias",
                "2m": "No significant bias"
            },
            "pace_bias": "neutral",
            "rail_position_notes": "Undulating with testing finish. Right-handed oval.",
            "altitude": 100,
            "drainage": "Good",
            "official_distances": ["5f", "6f", "1m", "1m 1f 170y", "1m 4f 10y", "2m"],
            "key_characteristics": [
                "Undulating, right-handed — Garden Racecourse",
                "Draw bias in sprints — high draw favoured",
                "Lower-grade flat racing",
                "Attractive venue — good atmosphere"
            ],
            "chaos_rating": 2,
        },
        {
            "track_name": "Pontefract",
            "surface": "turf",
            "circuit_type": "undulating",
            "direction": "left-handed",
            "draw_bias_description": "Low draw advantage over shorter trips. Unique figure-of-eight-like layout.",
            "draw_bias_distances": {
                "5f": "Low draw advantage",
                "6f": "Slight low draw advantage",
                "1m": "Minimal bias",
                "1m2f": "No significant bias",
                "1m4f": "No significant bias",
                "2m": "No significant bias"
            },
            "pace_bias": "neutral",
            "rail_position_notes": "Undulating with long uphill finish. Unique layout — course knowledge valuable.",
            "altitude": 200,
            "drainage": "Variable",
            "official_distances": ["5f 3y", "6f", "1m 4y", "1m 2f 6y", "1m 4f 8y", "2m 1f 166y", "2m 5f 122y"],
            "key_characteristics": [
                "Unique undulating layout — long uphill finish",
                "Course knowledge very valuable",
                "Stamina test — uphill finish demanding",
                "Lower-grade flat racing"
            ],
            "chaos_rating": 3,
        },
        {
            "track_name": "Redcar",
            "surface": "turf",
            "circuit_type": "flat",
            "direction": "left-handed",
            "draw_bias_description": "Low draw advantage in sprints. Straight course for shorter races.",
            "draw_bias_distances": {
                "5f": "Low draw advantage",
                "6f": "Slight low draw advantage",
                "7f": "Minimal bias",
                "1m": "No significant bias",
                "1m2f": "No significant bias",
                "1m6f": "No significant bias"
            },
            "pace_bias": "neutral",
            "rail_position_notes": "Flat, left-handed with straight course for sprints.",
            "altitude": 20,
            "drainage": "Can become testing — coastal, low-lying",
            "official_distances": ["5f", "6f", "7f", "1m", "1m 2f", "1m 6f 19y", "2m"],
            "key_characteristics": [
                "Flat, left-handed — seaside venue",
                "Straight course for sprints",
                "Can become very testing in winter",
                "Lower-grade racing"
            ],
            "chaos_rating": 2,
        },
        {
            "track_name": "Nottingham",
            "surface": "turf",
            "circuit_type": "galloping",
            "direction": "left-handed",
            "draw_bias_description": "Generally fair. Slight low draw advantage in large-field sprints.",
            "draw_bias_distances": {
                "5f": "Slight low draw advantage in large fields",
                "6f": "Minimal bias",
                "1m": "No significant bias",
                "1m2f": "No significant bias",
                "1m6f": "No significant bias"
            },
            "pace_bias": "neutral",
            "rail_position_notes": "Galloping track — fair. Good trial ground for bigger races.",
            "altitude": 100,
            "drainage": "Good",
            "official_distances": ["5f 8y", "6f 18y", "1m 75y", "1m 2f 50y", "1m 6f 15y", "2m"],
            "key_characteristics": [
                "Galloping, left-handed — fair track",
                "Good trial ground — form often franked",
                "Flat racing only",
                "Moderate-quality fields"
            ],
            "chaos_rating": 2,
        },
        {
            "track_name": "Leicester",
            "surface": "turf",
            "circuit_type": "undulating",
            "direction": "right-handed",
            "draw_bias_description": "Slight high draw advantage in sprints. Stiff uphill finish.",
            "draw_bias_distances": {
                "5f": "Slight high draw advantage",
                "6f": "Minimal bias",
                "7f": "No significant bias",
                "1m": "No significant bias",
                "1m2f": "No significant bias"
            },
            "pace_bias": "neutral",
            "rail_position_notes": "Undulating with stiff uphill finish. Stamina test.",
            "altitude": 250,
            "drainage": "Good",
            "official_distances": ["5f 2y", "6f", "7f 9y", "1m 53y", "1m 1f 218y", "1m 3f 179y"],
            "key_characteristics": [
                "Undulating, right-handed — stiff finish",
                "Good trial ground",
                "Flat racing only",
                "Moderate-quality fields"
            ],
            "chaos_rating": 2,
        },
        {
            "track_name": "Warwick",
            "surface": "turf",
            "circuit_type": "sharp",
            "direction": "left-handed",
            "draw_bias_description": "NH track primarily — minimal flat draw data.",
            "draw_bias_distances": {},
            "pace_bias": "front",
            "rail_position_notes": "Sharp, left-handed. Front-runners favoured.",
            "altitude": 200,
            "drainage": "Variable",
            "official_distances": ["2m", "2m 3f", "2m 5f", "3m", "3m 1f"],
            "key_characteristics": [
                "Sharp, left-handed — NH specialist",
                "Front-runners favoured on tight bends",
                "Classic Chase venue",
                "Lower-grade NH racing mostly"
            ],
            "chaos_rating": 3,
        },
        {
            "track_name": "Stratford",
            "surface": "turf",
            "circuit_type": "sharp",
            "direction": "left-handed",
            "draw_bias_description": "NH track — no draw.",
            "draw_bias_distances": {},
            "pace_bias": "front",
            "rail_position_notes": "Sharp, flat track. Front-runners favoured.",
            "altitude": 100,
            "drainage": "Can become testing — riverside",
            "official_distances": ["2m", "2m 2f", "2m 6f", "3m", "3m 2f"],
            "key_characteristics": [
                "Sharp, flat, left-handed — summer NH venue",
                "Front-runners favoured",
                "Lower-grade NH racing",
                "Summer jumping specialist"
            ],
            "chaos_rating": 3,
        },
        {
            "track_name": "Plumpton",
            "surface": "turf",
            "circuit_type": "sharp",
            "direction": "left-handed",
            "draw_bias_description": "NH track — no draw.",
            "draw_bias_distances": {},
            "pace_bias": "front",
            "rail_position_notes": "Very tight, sharp track. Front-runners heavily favoured.",
            "altitude": 200,
            "drainage": "Variable — can become testing",
            "official_distances": ["2m", "2m 1f", "2m 4f", "3m 1f"],
            "key_characteristics": [
                "Very tight, sharp — one of the sharpest NH tracks",
                "Front-runners heavily favoured",
                "Lower-grade NH racing",
                "Specialist track — course form essential"
            ],
            "chaos_rating": 4,
        },
        {
            "track_name": "Fontwell",
            "surface": "turf",
            "circuit_type": "sharp",
            "direction": "left-handed",
            "draw_bias_description": "NH track — no draw.",
            "draw_bias_distances": {},
            "pace_bias": "front",
            "rail_position_notes": "Unique figure-of-eight chase course. Hurdle course is left-handed oval.",
            "altitude": 50,
            "drainage": "Variable",
            "official_distances": ["2m 1f", "2m 3f", "2m 6f", "3m 1f", "3m 3f"],
            "key_characteristics": [
                "Unique figure-of-eight chase course",
                "Hurdle course is separate left-handed oval",
                "Front-runners favoured",
                "Lower-grade NH racing",
                "Specialist track — unique layout"
            ],
            "chaos_rating": 3,
        },
        {
            "track_name": "Wincanton",
            "surface": "turf",
            "circuit_type": "galloping",
            "direction": "right-handed",
            "draw_bias_description": "NH track — no draw.",
            "draw_bias_distances": {},
            "pace_bias": "neutral",
            "rail_position_notes": "Galloping track with testing fences. Fair course.",
            "altitude": 300,
            "drainage": "Good — elevated position",
            "official_distances": ["2m", "2m 4f", "2m 5f", "3m 1f", "3m 2f"],
            "key_characteristics": [
                "Galloping, right-handed — quality NH venue",
                "Testing fences — jumping ability important",
                "Kingwell Hurdle — Champion Hurdle trial",
                "Fair track — form reliable"
            ],
            "chaos_rating": 2,
        },
        {
            "track_name": "Taunton",
            "surface": "turf",
            "circuit_type": "flat",
            "direction": "right-handed",
            "draw_bias_description": "NH track — no draw.",
            "draw_bias_distances": {},
            "pace_bias": "neutral",
            "rail_position_notes": "Flat, right-handed. Fair track.",
            "altitude": 50,
            "drainage": "Can become testing — low-lying",
            "official_distances": ["2m", "2m 3f", "2m 7f", "3m", "3m 2f"],
            "key_characteristics": [
                "Flat, right-handed — NH venue",
                "Fair track — form reliable",
                "Lower-grade NH racing",
                "Can become very testing in winter"
            ],
            "chaos_rating": 2,
        },
        {
            "track_name": "Exeter",
            "surface": "turf",
            "circuit_type": "undulating",
            "direction": "right-handed",
            "draw_bias_description": "NH track — no draw.",
            "draw_bias_distances": {},
            "pace_bias": "neutral",
            "rail_position_notes": "Undulating with stiff uphill finish. Stamina test.",
            "altitude": 300,
            "drainage": "Good — elevated position",
            "official_distances": ["2m", "2m 1f", "2m 3f", "2m 5f", "3m", "3m 1f"],
            "key_characteristics": [
                "Undulating, right-handed — stiff finish",
                "Stamina test — uphill finish demanding",
                "Quality NH venue — Haldon Gold Cup",
                "Good drainage — elevated position"
            ],
            "chaos_rating": 2,
        },
        {
            "track_name": "Chepstow",
            "surface": "turf",
            "circuit_type": "undulating",
            "direction": "left-handed",
            "draw_bias_description": "Slight low draw advantage in flat sprints. NH track primarily.",
            "draw_bias_distances": {
                "5f": "Slight low draw advantage",
                "6f": "Minimal bias",
                "1m": "No significant bias"
            },
            "pace_bias": "neutral",
            "rail_position_notes": "Undulating with long home straight. Welsh Grand National venue.",
            "altitude": 200,
            "drainage": "Variable — can become very testing",
            "official_distances": ["5f 16y", "6f 16y", "1m 14y", "1m 2f 36y", "1m 4f 23y", "2m", "2m 3f", "3m 2f", "3m 5f"],
            "key_characteristics": [
                "Undulating, left-handed — dual-purpose",
                "Welsh Grand National — major NH fixture",
                "Long home straight — rewards strong finishers",
                "Can become very testing — heavy ground common",
                "Dual-purpose — flat and NH"
            ],
            "chaos_rating": 2,
        },
        {
            "track_name": "Ffos Las",
            "surface": "turf",
            "circuit_type": "galloping",
            "direction": "left-handed",
            "draw_bias_description": "Generally fair. Limited data — newer track.",
            "draw_bias_distances": {
                "5f": "Minimal bias",
                "6f": "No significant bias",
                "1m": "No significant bias",
                "1m4f": "No significant bias"
            },
            "pace_bias": "neutral",
            "rail_position_notes": "Galloping track — modern venue. Fair course.",
            "altitude": 400,
            "drainage": "Good — purpose-built drainage",
            "official_distances": ["5f", "6f", "1m", "1m 2f", "1m 4f", "1m 6f", "2m", "2m 4f", "3m"],
            "key_characteristics": [
                "Modern venue — opened 2009",
                "Galloping, left-handed — fair track",
                "Dual-purpose — flat and NH",
                "Welsh venue — smaller fields common",
                "Good drainage — purpose-built"
            ],
            "chaos_rating": 2,
        },
        {
            "track_name": "Bangor-on-Dee",
            "surface": "turf",
            "circuit_type": "flat",
            "direction": "left-handed",
            "draw_bias_description": "NH track — no draw.",
            "draw_bias_distances": {},
            "pace_bias": "front",
            "rail_position_notes": "Flat, left-handed. Front-runners favoured on flat track.",
            "altitude": 100,
            "drainage": "Can become testing — riverside location",
            "official_distances": ["2m 1f", "2m 3f", "2m 4f", "3m", "3m 2f"],
            "key_characteristics": [
                "Flat, left-handed — NH venue",
                "Front-runners favoured",
                "Lower-grade NH racing",
                "Can become testing — riverside"
            ],
            "chaos_rating": 3,
        },

        # ================================================================
        # Additional Turf Tracks for comprehensive coverage
        # ================================================================
        {
            "track_name": "Kempton (NH)",
            "surface": "turf",
            "circuit_type": "flat",
            "direction": "right-handed",
            "draw_bias_description": "NH track — no draw.",
            "draw_bias_distances": {},
            "pace_bias": "neutral",
            "rail_position_notes": "Flat, right-handed. Fair track for NH racing.",
            "altitude": 50,
            "drainage": "Good",
            "official_distances": ["2m", "2m 5f", "3m"],
            "key_characteristics": [
                "King George VI Chase — premier NH fixture",
                "Flat, right-handed — fair track",
                "Christmas meeting — iconic",
                "Separate course from AW track"
            ],
            "chaos_rating": 2,
        },
        {
            "track_name": "Windsor",
            "surface": "turf",
            "circuit_type": "flat",
            "direction": "right-handed",
            "draw_bias_description": "Low draw advantage over shorter trips. Figure-of-eight layout.",
            "draw_bias_distances": {
                "5f": "Low draw advantage",
                "6f": "Slight low draw advantage",
                "1m": "Minimal bias",
                "1m2f": "No significant bias",
                "1m3f": "No significant bias"
            },
            "pace_bias": "neutral",
            "rail_position_notes": "Figure-of-eight layout — unique. Flat track.",
            "altitude": 50,
            "drainage": "Can become testing — riverside",
            "official_distances": ["5f 10y", "6f 12y", "1m 67y", "1m 2f 6y", "1m 3f 99y"],
            "key_characteristics": [
                "Figure-of-eight layout — unique",
                "Flat track — evening meetings popular",
                "Moderate-quality flat racing",
                "Riverside location — can become testing"
            ],
            "chaos_rating": 2,
        },
        {
            "track_name": "Kempton (Flat)",
            "surface": "turf",
            "circuit_type": "flat",
            "direction": "right-handed",
            "draw_bias_description": "Generally fair. Minimal bias on round course.",
            "draw_bias_distances": {
                "6f": "Minimal bias",
                "7f": "No significant bias",
                "1m": "No significant bias",
                "1m2f": "No significant bias"
            },
            "pace_bias": "neutral",
            "rail_position_notes": "Flat, fair track. Jubilee course for flat racing.",
            "altitude": 50,
            "drainage": "Good",
            "official_distances": ["6f", "7f", "1m", "1m 2f", "1m 4f"],
            "key_characteristics": [
                "Flat, right-handed — Jubilee course",
                "Fair track — minimal biases",
                "September Stakes and other quality races",
                "Separate from AW and NH courses"
            ],
            "chaos_rating": 2,
        },
        {
            "track_name": "Salisbury",
            "surface": "turf",
            "circuit_type": "undulating",
            "direction": "right-handed",
            "draw_bias_description": "High draw advantage in sprints. Straight course with uphill finish.",
            "draw_bias_distances": {
                "5f": "High draw advantage",
                "6f": "Slight high draw advantage",
                "1m": "Minimal bias",
                "1m2f": "No significant bias",
                "1m4f": "No significant bias",
                "1m6f": "No significant bias"
            },
            "pace_bias": "neutral",
            "rail_position_notes": "Straight course with stiff uphill finish. Stamina test.",
            "altitude": 300,
            "drainage": "Good — chalk downland",
            "official_distances": ["5f", "6f", "6f 212y", "1m", "1m 1f 201y", "1m 4f 5y", "1m 6f 21y"],
            "key_characteristics": [
                "Straight course — no bends for most races",
                "Stiff uphill finish — stamina required",
                "Draw bias in sprints",
                "Good trial ground — form often franked",
                "Chalk downland — drains well"
            ],
            "chaos_rating": 2,
        },
        {
            "track_name": "Bath",
            "surface": "turf",
            "circuit_type": "undulating",
            "direction": "left-handed",
            "draw_bias_description": "Low draw advantage in sprints. Tight, undulating track.",
            "draw_bias_distances": {
                "5f": "Low draw advantage",
                "5f 161y": "Low draw advantage",
                "1m": "Minimal bias",
                "1m2f": "No significant bias",
                "1m3f": "No significant bias"
            },
            "pace_bias": "neutral",
            "rail_position_notes": "Undulating with tight bends. Course form valuable.",
            "altitude": 600,
            "drainage": "Good — elevated position",
            "official_distances": ["5f 11y", "5f 161y", "1m 46y", "1m 2f 46y", "1m 3f 137y", "1m 5f 22y"],
            "key_characteristics": [
                "Undulating, left-handed — highest flat track in UK",
                "Tight bends — course form valuable",
                "Lower-grade flat racing",
                "Evening meetings popular",
                "Elevated position — can be windy"
            ],
            "chaos_rating": 3,
        },
        {
            "track_name": "Brighton",
            "surface": "turf",
            "circuit_type": "undulating",
            "direction": "left-handed",
            "draw_bias_description": "Low draw advantage. Horseshoe-shaped track — unique.",
            "draw_bias_distances": {
                "5f": "Low draw advantage",
                "6f": "Slight low draw advantage",
                "7f": "Minimal bias",
                "1m": "No significant bias",
                "1m2f": "No significant bias"
            },
            "pace_bias": "neutral",
            "rail_position_notes": "Horseshoe-shaped, undulating. Downhill then uphill finish.",
            "altitude": 300,
            "drainage": "Good — chalk downland",
            "official_distances": ["5f 60y", "5f 215y", "6f 210y", "7f 216y", "1m 1f 209y", "1m 3f 196y"],
            "key_characteristics": [
                "Unique horseshoe shape — no other track like it",
                "Severely undulating — downhill then uphill",
                "Lower-grade flat racing",
                "Seaside venue — summer racing",
                "Specialist track — course form essential"
            ],
            "chaos_rating": 4,
        },
    ]

    return profiles


# ---------------------------------------------------------------------------
# Track Profile Database
# ---------------------------------------------------------------------------

class TrackProfileDB:
    """Pre-loaded intelligence for every UK racecourse.

    Queried automatically before every analysis to provide structural
    context. This was the missing piece at Wolverhampton — the system
    had zero track-specific intelligence.

    Usage:
        >>> db = TrackProfileDB(db_path="velo.db")
        >>> profile = db.get_profile("Wolverhampton")
        >>> chaos = db.get_chaos_rating("Wolverhampton")
        >>> brief = db.pre_race_context("Wolverhampton", "5f 21y", "Standard")
    """

    def __init__(self, db_path: str = "velo_oracle.db",
                 auto_load: bool = True):
        """Initialise the Track Profile Database.

        Args:
            db_path: Path to the SQLite database file.
            auto_load: Whether to auto-load pre-built profiles on init.
        """
        self.db_path = db_path
        self._init_db()
        if auto_load:
            self._load_profiles()

    # ------------------------------------------------------------------
    # Database
    # ------------------------------------------------------------------

    def _get_conn(self) -> sqlite3.Connection:
        """Get a database connection with WAL mode."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Create the track_profiles table."""
        conn = self._get_conn()
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS track_profiles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    track_name TEXT UNIQUE NOT NULL,
                    surface TEXT NOT NULL,
                    aw_surface_type TEXT,
                    circuit_type TEXT,
                    direction TEXT,
                    draw_bias_description TEXT,
                    draw_bias_distances TEXT,
                    pace_bias TEXT DEFAULT 'neutral',
                    rail_position_notes TEXT,
                    altitude INTEGER DEFAULT 0,
                    drainage TEXT,
                    official_distances TEXT,
                    key_characteristics TEXT,
                    chaos_rating INTEGER DEFAULT 2,
                    last_updated TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_track_profiles_name
                ON track_profiles(track_name)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_track_profiles_surface
                ON track_profiles(surface)
            """)
            conn.commit()
        finally:
            conn.close()

    def _load_profiles(self) -> None:
        """Load pre-built track profiles into the database."""
        profiles = _get_preloaded_profiles()
        conn = self._get_conn()
        try:
            for p in profiles:
                conn.execute("""
                    INSERT OR REPLACE INTO track_profiles (
                        track_name, surface, aw_surface_type, circuit_type,
                        direction, draw_bias_description, draw_bias_distances,
                        pace_bias, rail_position_notes, altitude, drainage,
                        official_distances, key_characteristics, chaos_rating,
                        last_updated
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    p["track_name"],
                    p["surface"],
                    p.get("aw_surface_type"),
                    p.get("circuit_type", "flat"),
                    p.get("direction", "left-handed"),
                    p.get("draw_bias_description", ""),
                    json.dumps(p.get("draw_bias_distances", {})),
                    p.get("pace_bias", "neutral"),
                    p.get("rail_position_notes", ""),
                    p.get("altitude", 0),
                    p.get("drainage", ""),
                    json.dumps(p.get("official_distances", [])),
                    json.dumps(p.get("key_characteristics", [])),
                    p.get("chaos_rating", 2),
                    datetime.now(timezone.utc).isoformat()
                ))
            conn.commit()
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Query Methods
    # ------------------------------------------------------------------

    def get_profile(self, track_name: str) -> Optional[Dict[str, Any]]:
        """Return the full track profile for a given track.

        Args:
            track_name: Name of the track (case-insensitive search).

        Returns:
            Dict with full track profile, or None if not found.
        """
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM track_profiles WHERE LOWER(track_name) = LOWER(?)",
                (track_name,)
            ).fetchone()
            if row:
                profile = dict(row)
                profile["draw_bias_distances"] = json.loads(
                    profile.get("draw_bias_distances", "{}") or "{}"
                )
                profile["official_distances"] = json.loads(
                    profile.get("official_distances", "[]") or "[]"
                )
                profile["key_characteristics"] = json.loads(
                    profile.get("key_characteristics", "[]") or "[]"
                )
                return profile
            return None
        finally:
            conn.close()

    def get_draw_bias(self, track_name: str,
                      distance: str) -> Optional[str]:
        """Return draw bias for a specific track and distance.

        Args:
            track_name: Name of the track.
            distance: Race distance (e.g., "5f", "1m", "1m2f").

        Returns:
            Draw bias description string, or None.
        """
        profile = self.get_profile(track_name)
        if not profile:
            return None

        draw_distances = profile.get("draw_bias_distances", {})

        # Try exact match first
        if distance in draw_distances:
            return draw_distances[distance]

        # Try normalised match (remove spaces, lowercase)
        norm_dist = distance.lower().replace(" ", "")
        for key, value in draw_distances.items():
            if key.lower().replace(" ", "") == norm_dist:
                return value

        # Return general description
        return profile.get("draw_bias_description", "No data available")

    def get_pace_bias(self, track_name: str) -> Optional[str]:
        """Return pace bias classification for a track.

        Args:
            track_name: Name of the track.

        Returns:
            Pace bias string (front/hold-up/neutral), or None.
        """
        profile = self.get_profile(track_name)
        if profile:
            return profile.get("pace_bias", "neutral")
        return None

    def get_chaos_rating(self, track_name: str) -> Optional[int]:
        """Return the chaos rating (1-5) for a track.

        Args:
            track_name: Name of the track.

        Returns:
            Integer chaos rating 1-5, or None if track not found.
        """
        profile = self.get_profile(track_name)
        if profile:
            return profile.get("chaos_rating", 2)
        return None

    def pre_race_context(self, track_name: str, distance: str,
                         going: str) -> str:
        """Generate a formatted pre-race intelligence brief.

        Args:
            track_name: Name of the track.
            distance: Race distance.
            going: Official going description.

        Returns:
            Formatted string with pre-race track intelligence.
        """
        profile = self.get_profile(track_name)
        if not profile:
            return (
                f"⚠ NO TRACK PROFILE FOUND FOR '{track_name}'. "
                f"Operating without track intelligence — elevated "
                f"uncertainty. Treat as CHAOS RATING 3/5."
            )

        draw_bias = self.get_draw_bias(track_name, distance)
        characteristics = profile.get("key_characteristics", [])
        chaos = profile.get("chaos_rating", 2)

        lines = [
            f"═══ PRE-RACE TRACK INTELLIGENCE: {track_name.upper()} ═══",
            f"Surface: {profile['surface']}"
            + (f" ({profile['aw_surface_type']})" if profile.get('aw_surface_type') else ""),
            f"Circuit: {profile['circuit_type']} | Direction: {profile['direction']}",
            f"Distance: {distance} | Going: {going}",
            f"Chaos Rating: {'★' * chaos}{'☆' * (5 - chaos)} ({chaos}/5)",
            "",
            f"DRAW BIAS ({distance}): {draw_bias or 'No specific data'}",
            f"PACE BIAS: {profile['pace_bias'].upper()}",
            "",
            "KEY CHARACTERISTICS:",
        ]
        for char in characteristics:
            lines.append(f"  • {char}")

        if profile.get("rail_position_notes"):
            lines.append(f"\nRAIL NOTES: {profile['rail_position_notes']}")

        if chaos >= 4:
            lines.append(
                "\n⚠ HIGH CHAOS TRACK — RPD-C layer MANDATORY. "
                "Reduce Top Strike confidence. Consider S8 scenario."
            )
        elif chaos >= 3:
            lines.append(
                "\n⚠ ELEVATED CHAOS — RPD-C layer recommended. "
                "Review all dismissals carefully."
            )

        return "\n".join(lines)

    def update_profile(self, track_name: str, field_name: str,
                       value: Any) -> bool:
        """Update a specific field in a track profile.

        Args:
            track_name: Name of the track.
            field_name: Column name to update.
            value: New value for the field.

        Returns:
            True if update was successful, False otherwise.
        """
        allowed_fields = {
            "surface", "aw_surface_type", "circuit_type", "direction",
            "draw_bias_description", "draw_bias_distances", "pace_bias",
            "rail_position_notes", "altitude", "drainage",
            "official_distances", "key_characteristics", "chaos_rating"
        }
        if field_name not in allowed_fields:
            return False

        # Serialise complex types
        if field_name in ("draw_bias_distances", "official_distances",
                          "key_characteristics"):
            value = json.dumps(value)

        conn = self._get_conn()
        try:
            result = conn.execute(
                f"UPDATE track_profiles SET {field_name} = ?, "
                f"last_updated = ? WHERE LOWER(track_name) = LOWER(?)",
                (value, datetime.now(timezone.utc).isoformat(), track_name)
            )
            conn.commit()
            return result.rowcount > 0
        finally:
            conn.close()

    def compare_tracks(self, track1: str,
                       track2: str) -> Dict[str, Any]:
        """Compare two tracks and return similarity analysis.

        Args:
            track1: Name of first track.
            track2: Name of second track.

        Returns:
            Dict with comparison results.
        """
        p1 = self.get_profile(track1)
        p2 = self.get_profile(track2)

        if not p1 or not p2:
            missing = []
            if not p1:
                missing.append(track1)
            if not p2:
                missing.append(track2)
            return {"error": f"Profile(s) not found: {', '.join(missing)}"}

        similarities = []
        differences = []

        # Surface
        if p1["surface"] == p2["surface"]:
            similarities.append(f"Same surface: {p1['surface']}")
            if p1.get("aw_surface_type") == p2.get("aw_surface_type"):
                similarities.append(
                    f"Same AW surface type: {p1.get('aw_surface_type')}"
                )
            elif p1.get("aw_surface_type") and p2.get("aw_surface_type"):
                differences.append(
                    f"Different AW surface: {p1.get('aw_surface_type')} "
                    f"vs {p2.get('aw_surface_type')}"
                )
        else:
            differences.append(
                f"Different surface: {p1['surface']} vs {p2['surface']}"
            )

        # Circuit type
        if p1.get("circuit_type") == p2.get("circuit_type"):
            similarities.append(f"Same circuit type: {p1.get('circuit_type')}")
        else:
            differences.append(
                f"Different circuit: {p1.get('circuit_type')} "
                f"vs {p2.get('circuit_type')}"
            )

        # Direction
        if p1.get("direction") == p2.get("direction"):
            similarities.append(f"Same direction: {p1.get('direction')}")
        else:
            differences.append(
                f"Different direction: {p1.get('direction')} "
                f"vs {p2.get('direction')}"
            )

        # Pace bias
        if p1.get("pace_bias") == p2.get("pace_bias"):
            similarities.append(f"Same pace bias: {p1.get('pace_bias')}")
        else:
            differences.append(
                f"Different pace bias: {p1.get('pace_bias')} "
                f"vs {p2.get('pace_bias')}"
            )

        # Chaos rating
        chaos_diff = abs(
            (p1.get("chaos_rating") or 2) - (p2.get("chaos_rating") or 2)
        )
        if chaos_diff == 0:
            similarities.append(
                f"Same chaos rating: {p1.get('chaos_rating')}/5"
            )
        else:
            differences.append(
                f"Chaos rating: {p1.get('chaos_rating')}/5 "
                f"vs {p2.get('chaos_rating')}/5"
            )

        similarity_score = len(similarities) / max(
            len(similarities) + len(differences), 1
        )

        return {
            "track1": track1,
            "track2": track2,
            "similarity_score": round(similarity_score, 2),
            "similarities": similarities,
            "differences": differences,
            "recommendation": (
                f"Form from {track1} is {'likely' if similarity_score > 0.6 else 'unlikely'} "
                f"to be transferable to {track2}."
            )
        }

    def get_aw_tracks(self) -> List[Dict[str, Any]]:
        """Return all all-weather track profiles.

        Returns:
            List of dicts with AW track profiles.
        """
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM track_profiles WHERE UPPER(surface) = 'AW' "
                "ORDER BY track_name"
            ).fetchall()
            results = []
            for row in rows:
                profile = dict(row)
                profile["draw_bias_distances"] = json.loads(
                    profile.get("draw_bias_distances", "{}") or "{}"
                )
                profile["official_distances"] = json.loads(
                    profile.get("official_distances", "[]") or "[]"
                )
                profile["key_characteristics"] = json.loads(
                    profile.get("key_characteristics", "[]") or "[]"
                )
                results.append(profile)
            return results
        finally:
            conn.close()

    def search_by_characteristic(self,
                                 characteristic: str) -> List[Dict[str, Any]]:
        """Find tracks matching a characteristic keyword.

        Args:
            characteristic: Keyword to search for in key_characteristics.

        Returns:
            List of matching track profiles.
        """
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM track_profiles WHERE "
                "LOWER(key_characteristics) LIKE LOWER(?)",
                (f"%{characteristic}%",)
            ).fetchall()
            results = []
            for row in rows:
                profile = dict(row)
                profile["draw_bias_distances"] = json.loads(
                    profile.get("draw_bias_distances", "{}") or "{}"
                )
                profile["official_distances"] = json.loads(
                    profile.get("official_distances", "[]") or "[]"
                )
                profile["key_characteristics"] = json.loads(
                    profile.get("key_characteristics", "[]") or "[]"
                )
                results.append(profile)
            return results
        finally:
            conn.close()

    def get_all_tracks(self) -> List[str]:
        """Return a list of all track names in the database.

        Returns:
            List of track name strings.
        """
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT track_name FROM track_profiles ORDER BY track_name"
            ).fetchall()
            return [row["track_name"] for row in rows]
        finally:
            conn.close()

    def get_track_count(self) -> int:
        """Return the number of tracks in the database.

        Returns:
            Integer count of tracks.
        """
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM track_profiles"
            ).fetchone()
            return row["cnt"] if row else 0
        finally:
            conn.close()
