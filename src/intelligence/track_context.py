"""
VÉLØ Oracle Prime — Track Context Lookup
=========================================

Read-only, zero-dependency track intelligence for 40+ UK racecourses.

Source data extracted from Manus track_profiles.py (2026-02-16).
No SQLite. No external I/O. Pure dict lookup.

Usage:
    from src.intelligence.track_context import get_track_context, resolve_draw_bias

    profile = get_track_context("Wolverhampton")
    draw_note = resolve_draw_bias(profile, "5f")
"""

from typing import Optional

# ---------------------------------------------------------------------------
# Raw profile data — extracted from Manus _get_preloaded_profiles()
# Only fields used by VÉLØ passive enrichment are kept:
#   chaos_rating, pace_bias, draw_bias_distances, key_characteristics
# ---------------------------------------------------------------------------

_PROFILES_RAW = [
    # ================================================================
    # ALL-WEATHER TRACKS
    # ================================================================
    {
        "track_name": "Wolverhampton",
        "chaos_rating": 4,
        "pace_bias": "front",
        "draw_bias_distances": {
            "5f": "Low draw significant advantage (stalls 1-4)",
            "6f": "Low draw moderate advantage",
            "7f": "Slight low draw advantage",
            "1m": "Minimal bias",
            "1m1f": "Minimal bias",
            "1m4f": "No significant bias",
        },
        "key_characteristics": [
            "Tight, sharp track — favours handy, agile horses",
            "Tapeta surface — consistent but can ride differently in extreme cold",
            "Front-runners heavily advantaged on sharp bends",
            "Day 1 failure track — RPD-C layer failed here (0/7)",
        ],
    },
    {
        "track_name": "Kempton",
        "chaos_rating": 2,
        "pace_bias": "neutral",
        "draw_bias_distances": {
            "5f": "Slight low draw advantage on straight course",
            "6f": "Slight low draw advantage on straight course",
            "7f": "Minimal bias (round course)",
            "1m": "No significant bias",
            "1m2f": "No significant bias",
            "1m4f": "No significant bias",
        },
        "key_characteristics": [
            "Flat, fair, right-handed — one of the fairest AW tracks",
            "Polytrack surface — consistent and predictable",
            "Triangular layout with sweeping bends",
        ],
    },
    {
        "track_name": "Lingfield",
        "chaos_rating": 3,
        "pace_bias": "front",
        "draw_bias_distances": {
            "5f": "Low draw significant advantage",
            "6f": "Low draw moderate advantage",
            "7f": "Slight low draw advantage",
            "1m": "Minimal bias",
            "1m2f": "No significant bias",
            "1m4f": "No significant bias",
        },
        "key_characteristics": [
            "Sharp, left-handed — similar characteristics to Wolverhampton",
            "Front-runners advantaged on sharp bends",
            "Sprint races heavily influenced by draw",
        ],
    },
    {
        "track_name": "Newcastle",
        "chaos_rating": 2,
        "pace_bias": "neutral",
        "draw_bias_distances": {
            "5f": "Central draw slight advantage in large fields",
            "6f": "Minimal bias",
            "7f": "No significant bias",
            "1m": "No significant bias",
            "1m2f": "No significant bias",
            "2m": "No significant bias",
        },
        "key_characteristics": [
            "Galloping, left-handed — fairest AW track in UK",
            "Long home straight — rewards strong finishers",
            "Hold-up horses advantaged at longer trips",
        ],
    },
    {
        "track_name": "Chelmsford",
        "chaos_rating": 2,
        "pace_bias": "neutral",
        "draw_bias_distances": {
            "5f": "Low draw slight advantage",
            "6f": "Low draw slight advantage",
            "7f": "Minimal bias",
            "1m": "No significant bias",
            "1m2f": "No significant bias",
            "1m6f": "No significant bias",
        },
        "key_characteristics": [
            "Flat, left-handed — modern AW venue",
            "Relatively fair track with minimal biases",
        ],
    },
    {
        "track_name": "Southwell",
        "chaos_rating": 4,
        "pace_bias": "front",
        "draw_bias_distances": {
            "5f": "Low draw advantage",
            "6f": "Low draw moderate advantage",
            "7f": "Slight low draw advantage",
            "1m": "Minimal bias",
            "1m3f": "No significant bias",
            "2m": "No significant bias",
        },
        "key_characteristics": [
            "Tight, sharp, left-handed — specialist track",
            "Fibresand surface — UNIQUE in UK, very demanding",
            "Front-runners heavily advantaged — rarely caught",
            "Specialists thrive — course form critical",
        ],
    },
    {
        "track_name": "Dundalk",
        "chaos_rating": 2,
        "pace_bias": "neutral",
        "draw_bias_distances": {
            "5f": "Low draw slight advantage",
            "6f": "Minimal bias",
            "7f": "No significant bias",
            "1m": "No significant bias",
            "1m2f": "No significant bias",
        },
        "key_characteristics": [
            "Flat, left-handed — Ireland's only AW track",
            "Different competitive landscape to UK AW",
        ],
    },
    # ================================================================
    # TURF TRACKS — Major Flat Venues
    # ================================================================
    {
        "track_name": "Ascot",
        "chaos_rating": 2,
        "pace_bias": "neutral",
        "draw_bias_distances": {
            "5f": "High draw advantage (stands side) on soft ground",
            "6f": "High draw advantage (stands side) on soft ground",
            "7f": "Minimal bias (round course)",
            "1m": "Minimal bias",
            "1m2f": "No significant bias",
            "1m4f": "No significant bias",
            "2m4f": "No significant bias",
        },
        "key_characteristics": [
            "Premier venue — highest quality racing in UK",
            "Stiff uphill finish — stamina at a premium",
            "Draw bias weather-dependent on straight course",
        ],
    },
    {
        "track_name": "Cheltenham",
        "chaos_rating": 2,
        "pace_bias": "hold-up",
        "draw_bias_distances": {},
        "key_characteristics": [
            "Premier NH venue — The Festival is the pinnacle",
            "Famous uphill finish — tests stamina and courage",
            "Undulating — rewards athletic, balanced jumpers",
            "Hold-up horses often advantaged — strong finish required",
        ],
    },
    {
        "track_name": "Aintree",
        "chaos_rating": 3,
        "pace_bias": "neutral",
        "draw_bias_distances": {},
        "key_characteristics": [
            "Home of the Grand National — iconic venue",
            "Flat, galloping track — suits long-striding horses",
            "Grand National course has unique, demanding fences",
        ],
    },
    {
        "track_name": "York",
        "chaos_rating": 1,
        "pace_bias": "neutral",
        "draw_bias_distances": {
            "5f": "Low draw advantage on soft ground",
            "6f": "Low draw advantage on soft ground",
            "7f": "Minimal bias",
            "1m": "No significant bias",
            "1m2f": "No significant bias",
            "1m4f": "No significant bias",
            "1m6f": "No significant bias",
        },
        "key_characteristics": [
            "Premier flat venue — Ebor Festival, Dante Stakes",
            "Wide, galloping track — very fair",
            "Draw bias mainly on soft ground (straight course)",
        ],
    },
    {
        "track_name": "Newmarket (Rowley Mile)",
        "chaos_rating": 1,
        "pace_bias": "neutral",
        "draw_bias_distances": {
            "5f": "High draw advantage (stands side)",
            "6f": "High draw advantage (stands side)",
            "7f": "Slight high draw advantage",
            "1m": "Minimal bias",
            "1m2f": "No significant bias",
            "1m4f": "No significant bias",
        },
        "key_characteristics": [
            "HQ of British flat racing — Guineas, Champions Day",
            "Famous Dip — stamina test in final 2f",
            "Wide track — draw bias in sprints",
        ],
    },
    {
        "track_name": "Newmarket (July Course)",
        "chaos_rating": 1,
        "pace_bias": "neutral",
        "draw_bias_distances": {
            "5f": "Stands side slight advantage",
            "6f": "Stands side slight advantage",
            "7f": "Minimal bias",
            "1m": "No significant bias",
            "1m2f": "No significant bias",
        },
        "key_characteristics": [
            "Summer course at Newmarket — July Festival",
            "Less severe finish than Rowley Mile",
        ],
    },
    {
        "track_name": "Epsom",
        "chaos_rating": 3,
        "pace_bias": "neutral",
        "draw_bias_distances": {
            "5f": "High draw significant advantage",
            "6f": "Slight high draw advantage",
            "7f": "Minimal bias",
            "1m": "No significant bias",
            "1m2f": "No significant bias (Derby course)",
            "1m4f": "No significant bias",
        },
        "key_characteristics": [
            "Home of The Derby — unique, iconic track",
            "Severe undulations — downhill to Tattenham Corner",
            "Camber on home bend — horses drift wide",
            "Unique test — Derby form not always transferable",
        ],
    },
    {
        "track_name": "Goodwood",
        "chaos_rating": 3,
        "pace_bias": "neutral",
        "draw_bias_distances": {
            "5f": "Low draw advantage (far side) on soft ground",
            "6f": "Low draw advantage on soft ground",
            "7f": "Slight low draw advantage",
            "1m": "Minimal bias",
            "1m1f": "No significant bias",
            "1m4f": "No significant bias",
            "2m": "No significant bias",
        },
        "key_characteristics": [
            "Glorious Goodwood — premier summer festival",
            "Undulating, tricky track — requires experience",
            "Draw bias significant — especially on soft ground",
            "Quirky track — course form valuable",
        ],
    },
    {
        "track_name": "Sandown",
        "chaos_rating": 2,
        "pace_bias": "neutral",
        "draw_bias_distances": {
            "5f": "High draw slight advantage",
            "7f": "No significant bias",
            "1m": "No significant bias",
            "1m2f": "No significant bias",
            "1m4f": "No significant bias",
            "2m": "No significant bias",
        },
        "key_characteristics": [
            "Quality dual-purpose track — Eclipse Stakes venue",
            "Stiff uphill finish — stamina required",
            "Fair track — minimal biases",
        ],
    },
    {
        "track_name": "Newbury",
        "chaos_rating": 1,
        "pace_bias": "neutral",
        "draw_bias_distances": {
            "5f": "Slight low draw advantage in large fields",
            "6f": "Minimal bias",
            "7f": "No significant bias",
            "1m": "No significant bias",
            "1m2f": "No significant bias",
            "1m4f": "No significant bias",
        },
        "key_characteristics": [
            "Premier dual-purpose venue — Lockinge, Hennessy",
            "Wide, galloping track — very fair",
            "Well-drained — rarely waterlogged",
        ],
    },
    {
        "track_name": "Doncaster",
        "chaos_rating": 2,
        "pace_bias": "neutral",
        "draw_bias_distances": {
            "5f": "High draw advantage (stands side)",
            "6f": "High draw advantage (stands side)",
            "7f": "Slight high draw advantage",
            "1m": "Minimal bias (round course)",
            "1m2f": "No significant bias",
            "1m4f": "No significant bias",
            "1m6f": "No significant bias",
        },
        "key_characteristics": [
            "Historic venue — St Leger, Lincoln",
            "Wide, galloping, flat track",
            "Long straight — draw bias in sprints",
        ],
    },
    {
        "track_name": "Chester",
        "chaos_rating": 3,
        "pace_bias": "front",
        "draw_bias_distances": {
            "5f": "Low draw EXTREME advantage",
            "6f": "Low draw EXTREME advantage",
            "7f": "Low draw significant advantage",
            "1m": "Low draw significant advantage",
            "1m2f": "Low draw moderate advantage",
            "1m4f": "Low draw slight advantage",
            "2m": "Minimal bias",
        },
        "key_characteristics": [
            "Tightest flat track in UK — essentially circular",
            "EXTREME draw bias — low draw critical",
            "Front-runners heavily advantaged",
            "Course form essential — specialists thrive",
        ],
    },
    {
        "track_name": "Haydock",
        "chaos_rating": 2,
        "pace_bias": "neutral",
        "draw_bias_distances": {
            "5f": "Slight low draw advantage",
            "6f": "Minimal bias",
            "7f": "No significant bias",
            "1m": "No significant bias",
            "1m2f": "No significant bias",
            "1m6f": "No significant bias",
        },
        "key_characteristics": [
            "Quality dual-purpose venue — Sprint Cup, Betfair Chase",
            "Flat, galloping track — fair",
        ],
    },
    # ================================================================
    # TURF TRACKS — NH Specialist / Regional Venues
    # ================================================================
    {
        "track_name": "Wetherby",
        "chaos_rating": 2,
        "pace_bias": "neutral",
        "draw_bias_distances": {},
        "key_characteristics": [
            "Quality NH venue — Charlie Hall Chase",
            "Galloping track — suits strong stayers",
        ],
    },
    {
        "track_name": "Catterick",
        "chaos_rating": 3,
        "pace_bias": "front",
        "draw_bias_distances": {
            "5f": "Low draw advantage",
            "5f 212y": "Low draw advantage",
            "7f": "Slight low draw advantage",
            "1m": "Minimal bias",
        },
        "key_characteristics": [
            "Sharp, undulating track — specialist venue",
            "Front-runners heavily advantaged",
            "Lower-grade racing — higher chaos factor",
        ],
    },
    {
        "track_name": "Carlisle",
        "chaos_rating": 2,
        "pace_bias": "neutral",
        "draw_bias_distances": {
            "5f": "Slight high draw advantage",
            "5f 193y": "Slight high draw advantage",
            "6f": "Minimal bias",
            "7f": "No significant bias",
            "1m": "No significant bias",
            "1m1f": "No significant bias",
        },
        "key_characteristics": [
            "Undulating, right-handed — stiff finish",
            "Day 1 SUCCESS track — 75% Top Strike (6/8)",
            "Conventional track — form reliable",
        ],
    },
    {
        "track_name": "Musselburgh",
        "chaos_rating": 3,
        "pace_bias": "front",
        "draw_bias_distances": {
            "5f": "Low draw significant advantage",
            "7f": "Slight low draw advantage",
            "1m": "Minimal bias",
            "1m4f": "No significant bias",
            "2m": "No significant bias",
        },
        "key_characteristics": [
            "Tight, flat, right-handed — Scottish venue",
            "Draw bias significant in sprints",
            "Front-runners favoured",
        ],
    },
    {
        "track_name": "Ayr",
        "chaos_rating": 2,
        "pace_bias": "neutral",
        "draw_bias_distances": {
            "5f": "Slight low draw advantage in large fields",
            "6f": "Minimal bias",
            "7f": "No significant bias",
            "1m": "No significant bias",
            "1m2f": "No significant bias",
        },
        "key_characteristics": [
            "Premier Scottish venue — Ayr Gold Cup",
            "Galloping track — fair",
        ],
    },
    {
        "track_name": "Hamilton",
        "chaos_rating": 3,
        "pace_bias": "neutral",
        "draw_bias_distances": {
            "5f": "Low draw advantage",
            "6f": "Low draw moderate advantage",
            "1m": "Slight low draw advantage",
            "1m1f": "Minimal bias",
            "1m3f": "No significant bias",
            "1m5f": "No significant bias",
        },
        "key_characteristics": [
            "Undulating, right-handed — stiff uphill finish",
            "Loop course — all races on the bend",
            "Low draw advantage in sprints",
        ],
    },
    {
        "track_name": "Beverley",
        "chaos_rating": 3,
        "pace_bias": "neutral",
        "draw_bias_distances": {
            "5f": "High draw significant advantage",
            "7f": "Slight high draw advantage",
            "1m": "Minimal bias",
            "1m1f": "No significant bias",
            "1m3f": "No significant bias",
            "2m": "No significant bias",
        },
        "key_characteristics": [
            "Undulating, right-handed — stiff finish",
            "Significant draw bias in sprints",
        ],
    },
    {
        "track_name": "Thirsk",
        "chaos_rating": 3,
        "pace_bias": "front",
        "draw_bias_distances": {
            "5f": "Low draw advantage",
            "6f": "Slight low draw advantage",
            "7f": "Minimal bias",
            "1m": "No significant bias",
            "1m4f": "No significant bias",
            "2m": "No significant bias",
        },
        "key_characteristics": [
            "Tight, flat, left-handed — sharp track",
            "Front-runners favoured",
            "Lower-grade flat racing",
        ],
    },
    {
        "track_name": "Ripon",
        "chaos_rating": 2,
        "pace_bias": "neutral",
        "draw_bias_distances": {
            "5f": "High draw advantage",
            "6f": "Slight high draw advantage",
            "1m": "Minimal bias",
            "1m1f": "No significant bias",
            "1m4f": "No significant bias",
            "2m": "No significant bias",
        },
        "key_characteristics": [
            "Undulating, right-handed — Garden Racecourse",
            "Draw bias in sprints — high draw favoured",
        ],
    },
    {
        "track_name": "Pontefract",
        "chaos_rating": 3,
        "pace_bias": "neutral",
        "draw_bias_distances": {
            "5f": "Low draw advantage",
            "6f": "Slight low draw advantage",
            "1m": "Minimal bias",
            "1m2f": "No significant bias",
            "1m4f": "No significant bias",
        },
        "key_characteristics": [
            "Undulating, left-handed — unique loop layout",
            "Front-runners favoured — hard to come from behind",
            "Course form essential",
        ],
    },
    {
        "track_name": "Nottingham",
        "chaos_rating": 2,
        "pace_bias": "neutral",
        "draw_bias_distances": {
            "5f": "Slight high draw advantage",
            "6f": "Minimal bias",
            "1m": "No significant bias",
            "1m2f": "No significant bias",
            "1m6f": "No significant bias",
        },
        "key_characteristics": [
            "Flat, left-handed — fair track",
            "Good surface — reliable form",
        ],
    },
    {
        "track_name": "Leicester",
        "chaos_rating": 2,
        "pace_bias": "neutral",
        "draw_bias_distances": {
            "5f": "Slight high draw advantage",
            "6f": "Minimal bias",
            "7f": "No significant bias",
            "1m": "No significant bias",
            "1m2f": "No significant bias",
        },
        "key_characteristics": [
            "Stiff, right-handed — undulating",
            "Testing track — stamina required",
        ],
    },
    {
        "track_name": "Windsor",
        "chaos_rating": 2,
        "pace_bias": "front",
        "draw_bias_distances": {
            "5f": "Low draw slight advantage",
            "6f": "Minimal bias",
            "1m": "No significant bias",
            "1m2f": "No significant bias",
        },
        "key_characteristics": [
            "Figure-of-eight course — unique layout",
            "Flat, right-handed finish",
            "Compact track — front-runners hold on",
        ],
    },
    {
        "track_name": "Brighton",
        "chaos_rating": 3,
        "pace_bias": "front",
        "draw_bias_distances": {
            "5f": "Low draw advantage",
            "5f 59y": "Low draw advantage",
            "6f": "Low draw advantage",
            "7f": "Slight low draw advantage",
            "1m": "Minimal bias",
        },
        "key_characteristics": [
            "Undulating, left-handed — unique seaside track",
            "Sharp bends — front-runners advantaged",
            "Can ride very differently in extremes of ground",
        ],
    },
    {
        "track_name": "Folkestone",
        "chaos_rating": 3,
        "pace_bias": "neutral",
        "draw_bias_distances": {},
        "key_characteristics": [
            "Sharp, right-handed — no longer hosting racing",
        ],
    },
    {
        "track_name": "Chepstow",
        "chaos_rating": 2,
        "pace_bias": "neutral",
        "draw_bias_distances": {
            "5f": "Minimal bias",
            "6f": "No significant bias",
            "1m": "No significant bias",
            "1m4f": "No significant bias",
            "2m": "No significant bias",
        },
        "key_characteristics": [
            "Galloping, left-handed — dual-purpose",
            "Undulating with stiff finish",
            "NH and flat racing",
        ],
    },
    {
        "track_name": "Ffos Las",
        "chaos_rating": 2,
        "pace_bias": "neutral",
        "draw_bias_distances": {},
        "key_characteristics": [
            "Left-handed — Welsh NH venue",
            "Galloping track — suits staying types",
        ],
    },
    {
        "track_name": "Exeter",
        "chaos_rating": 2,
        "pace_bias": "neutral",
        "draw_bias_distances": {},
        "key_characteristics": [
            "Right-handed — NH specialist venue",
            "Stiff, undulating — stamina test",
        ],
    },
    {
        "track_name": "Taunton",
        "chaos_rating": 2,
        "pace_bias": "neutral",
        "draw_bias_distances": {},
        "key_characteristics": [
            "Right-handed — NH venue",
            "Flat, galloping track",
        ],
    },
    {
        "track_name": "Wincanton",
        "chaos_rating": 2,
        "pace_bias": "neutral",
        "draw_bias_distances": {},
        "key_characteristics": [
            "Right-handed — NH venue",
            "Flat with easy bends",
        ],
    },
    {
        "track_name": "Huntingdon",
        "chaos_rating": 2,
        "pace_bias": "neutral",
        "draw_bias_distances": {},
        "key_characteristics": [
            "Right-handed — NH venue",
            "Flat, fair — galloping track",
        ],
    },
    {
        "track_name": "Kempton (AW)",
        "chaos_rating": 2,
        "pace_bias": "neutral",
        "draw_bias_distances": {
            "5f": "Slight low draw advantage on straight course",
            "6f": "Slight low draw advantage on straight course",
            "7f": "Minimal bias (round course)",
            "1m": "No significant bias",
            "1m2f": "No significant bias",
            "1m4f": "No significant bias",
        },
        "key_characteristics": [
            "Flat, fair, right-handed — one of the fairest AW tracks",
            "Polytrack surface — consistent and predictable",
        ],
    },
    {
        "track_name": "Lingfield (AW)",
        "chaos_rating": 3,
        "pace_bias": "front",
        "draw_bias_distances": {
            "5f": "Low draw significant advantage",
            "6f": "Low draw moderate advantage",
            "7f": "Slight low draw advantage",
            "1m": "Minimal bias",
            "1m2f": "No significant bias",
            "1m4f": "No significant bias",
        },
        "key_characteristics": [
            "Sharp, left-handed — similar characteristics to Wolverhampton",
            "Sprint races heavily influenced by draw",
        ],
    },
]

# ---------------------------------------------------------------------------
# Keyed lookup dict — O(1) access by track_name
# ---------------------------------------------------------------------------

TRACK_PROFILES: dict[str, dict] = {p["track_name"]: p for p in _PROFILES_RAW}

# API variant → canonical profile key.
# Add here when the Racing API returns a course name that differs from the
# profile key. Direct (AW) entries already exist for Lingfield and Kempton.
_ALIASES: dict[str, str] = {
    "Newcastle (AW)": "Newcastle",
    "Southwell (AW)": "Southwell",
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_track_context(course: str) -> dict:
    """Return profile dict for a course name, or {} if not found.

    Resolves Racing API name variants via _ALIASES before lookup.

    Args:
        course: Race course name as returned by normalize_race() e.g. "Wolverhampton"

    Returns:
        Profile dict with keys: chaos_rating, pace_bias,
        draw_bias_distances, key_characteristics.
        Empty dict on miss — never raises.
    """
    if not course:
        return {}
    key = course.strip()
    key = _ALIASES.get(key, key)
    return TRACK_PROFILES.get(key, {})


def resolve_draw_bias(profile: dict, distance: str) -> Optional[str]:
    """Return distance-specific draw bias note from a profile, or None.

    Matching strategy:
      1. Exact match after whitespace normalisation ("1m 2f" == "1m2f")
      2. Prefix match on leading furlongs token ("7f 14y" hits "7f" key)

    Args:
        profile: Dict returned by get_track_context().
        distance: Distance string from normalize_race() e.g. "7f", "1m2f", "7f 14y"

    Returns:
        Bias description string, or None on miss / empty draw_bias_distances.
    """
    if not profile or not distance:
        return None

    dbd = profile.get("draw_bias_distances") or {}
    if not dbd:
        return None

    def _normalise(s: str) -> str:
        return s.strip().lower().replace(" ", "")

    dist_norm = _normalise(distance)

    # Pass 1 — exact normalised match
    for key, val in dbd.items():
        if _normalise(key) == dist_norm:
            return val

    # Pass 2 — prefix match on leading token (e.g. "7f" from "7f 14y")
    dist_prefix = distance.strip().split()[0].lower()
    for key, val in dbd.items():
        if key.strip().lower().split()[0] == dist_prefix:
            return val

    return None
