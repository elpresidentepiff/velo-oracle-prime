"""
Initialize VETP Layer 1 Database

Creates the vetp_events table and populates it with historical events.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import date, time

from app.vetp import Base, VETPEvent, VETPLayer1, VETPEventIn, KeyRival

# Database connection (using SQLite for VETP memory)
DB_PATH = "/home/ubuntu/velo-oracle/data/vetp_memory.db"
engine = create_engine(f"sqlite:///{DB_PATH}")

# Create tables
print("Creating VETP tables...")
Base.metadata.create_all(engine)
print("✅ Tables created")

# Create session
SessionLocal = sessionmaker(bind=engine)
db = SessionLocal()

# Initialize service
vetp = VETPLayer1(db)

print("\n" + "="*60)
print("POPULATING HISTORICAL EVENTS")
print("="*60)

# ========== E1: MESAAFI MELTDOWN ==========
print("\n📝 Logging E1: MESAAFI MELTDOWN...")

mesaafi = VETPEventIn(
    event_id="2025-12-03_KEM_19:40_MESAAFI",
    date=date(2025, 12, 3),
    course="Kempton",
    off_time=time(19, 40),
    code="Flat-AW",
    race_class="C4/5",
    field_size=11,
    
    going="Standard",
    pace_shape_pre="Even / honest",
    pace_shape_actual="Fairly even, no crazy collapse",
    
    fav_name="Mesaafi",
    fav_sp=4.0,
    fav_profile="Ratings horse, good TS/RPR, Rossa Ryan, looked safe win/place",
    key_rivals=[
        KeyRival(name="Carbine Harvester", sp=6.0),
        KeyRival(name="Trouble Man", sp=8.0),
        KeyRival(name="Mr Cool", sp=9.0),
        KeyRival(name="Valley Of The Kings", sp=10.0),
    ],
    
    our_play_type="Bank-heavy back (win + place)",
    our_play_horses=["Mesaafi", "Valley Of The Kings", "Mr Cool", "Trouble Man"],
    our_play_stakes="Overexposed. Emotional all-in.",
    
    winner="Not Mesaafi (field beat him)",
    places=["Unknown", "Unknown", "Unknown"],
    pnl_units=-15.0,
    read_race_right="No",
    
    behaviour_flags=["fake_fav", "non_trier_suspected", "pace_misread", "emotional_stake", "field_too_deep"],
    market_story="Safe jolly with top jockey, strong numbers, low risk place. Smart money on fav.",
    reality_story="Horse never really asked, body language of a non-event; others ridden to win. Evening AW hcp used as money vacuum for overconfident form readers.",
    
    key_learning="Short-priced 'safe' favs in messy evening AW handicaps are NOT insurance, they are designed traps when all the story lines point one way.",
    
    rule_trigger="Code = Flat-AW, Class in C3–C6 hcp, Fav < 2.5, Edge based mainly on historical ratings + big-name jockey, Stable not white-hot & race has 3–5 plausible alternatives",
    rule_action="VÉLØ should downgrade confidence, avoid bank-heavy staking, and actively evaluate 'Fake Fav' probability. Preferred plays: lay fav / play field in place markets / or no bet.",
    rule_confidence="High",
    
    emotion_tag="sickener",
)

vetp.log_event(mesaafi)
print("✅ Mesaafi event logged")

# ========== E2: CASTANEA BREEZE DEMOLITION ==========
print("\n📝 Logging E2: CASTANEA BREEZE DEMOLITION...")

castanea = VETPEventIn(
    event_id="2025-12-04_MR_13:50_CASTANEA",
    date=date(2025, 12, 4),
    course="Market Rasen",
    off_time=time(13, 50),
    code="Hurdle",
    race_class="Hcp hurdle (mid-low)",
    field_size=8,
    
    going="Typical winter jumps (not extreme)",
    pace_shape_pre="Honest / could build",
    pace_shape_actual="Bunched, then decisive move before turn",
    
    fav_name="Castanea Breeze",
    fav_sp=4.0,
    fav_profile="Top TS/RPR cluster; Lucy Wadham in decent nick; Tom Cannon competent. Form showed serious engine; looked like a 'proper horse' in weak contest.",
    key_rivals=[
        KeyRival(name="Harry Bright", sp=5.0, profile="Skelton runner, clear 2nd"),
        KeyRival(name="Mac's Legacy", sp=8.0),
        KeyRival(name="East Eagle", sp=10.0),
    ],
    
    our_play_type="Strong win play",
    our_play_horses=["Castanea Breeze"],
    our_play_stakes="Should have structured win / lay-others / forecast (missed some value)",
    
    winner="Castanea Breeze",
    places=["Castanea Breeze", "Harry Bright", "Mac's Legacy"],
    pnl_units=8.0,
    read_race_right="Yes",
    
    behaviour_flags=["dominant_engine", "fav_not_underpriced", "jockey_did_job", "tactical_move_early"],
    market_story="Open little handicap, fav respected but not bombproof, mixture of triers.",
    reality_story="Fav was simply better. One decisive move before turn and race over. Others outclassed.",
    
    key_learning="When one horse has BOTH the highest engine figures AND the cleanest profile AND the opposition is mostly exposed, that's not 'open', that's domination.",
    
    rule_trigger="TS/RPR cluster: 1 horse clearly top, next 2–3 a step down. That horse has solid last 2–3 runs, no obvious physical red flags. Trainer in acceptable or good form. Jockey competent & not a liability. Field made up of exposed types / inconsistent profiles.",
    rule_action="VÉLØ should allow aggressive pro-fav stance, not automatic lay-fav bias. Preferred plays: strong win, forecast with single clear rival, avoid spreading to noise.",
    rule_confidence="High",
    
    emotion_tag="smug",
)

vetp.log_event(castanea)
print("✅ Castanea event logged")

# ========== E3: CONSTITUTION HILL PATTERN ==========
print("\n📝 Logging E3: SMALL-FIELD HYPE TRAP (Constitution Hill pattern)...")

const_hill = VETPEventIn(
    event_id="2025_GENERIC_BIGRACE_2HORSE_STORY",
    date=date(2025, 11, 15),  # Generic date
    course="Cheltenham",
    off_time=time(14, 30),
    code="Hurdle",
    race_class="G1",
    field_size=5,
    
    going="Good",
    pace_shape_pre="Market assumes straightforward: two class horses, others 'making up numbers'",
    pace_shape_actual="Chaos – over-racing, mistakes, falls",
    
    fav_name="Star Horse (Constitution Hill type)",
    fav_sp=1.3,
    fav_profile="Media monster, assumed bombproof",
    key_rivals=[
        KeyRival(name="2nd Fav", sp=2.5, profile="Main danger"),
        KeyRival(name="Outsider 1", sp=25.0),
        KeyRival(name="Outsider 2", sp=33.0),
    ],
    
    our_play_type="Historically: many punters go all-in on shorty",
    our_play_horses=["Star Horse"],
    our_play_stakes="Previously: overexposed. Future: either oppose or stay out.",
    
    winner="Outsider 1 (25/1)",
    places=["Outsider 1", "Outsider 2", "2nd Fav"],
    pnl_units=-10.0,
    read_race_right="No",
    
    behaviour_flags=["media_hype", "small_field_fall_risk", "underpriced_class_gap", "bookie_marketing_event"],
    market_story="Two-horse race, everything else irrelevant. Free money if you back the star.",
    reality_story="Jumps = risk. Short fields magnify tactical games, pace distortion, and fall probability. The 'irrelevant' outsiders are exactly where the book gets paid.",
    
    key_learning="In small-field graded jumps with a media monster, the price is a marketing number, not a fair reflection of risk. Falls, tactics, and pressure make chaos more likely.",
    
    rule_trigger="Field_Size ≤ 6, 1st + 2nd favs < 3.0 combined implied prob, Big media hype, wall-to-wall coverage",
    rule_action="Default VÉLØ stance: NO all-in, NO 'safe banker'. Consider: lay shorty, back field in w/o markets, or simply pass and watch.",
    rule_confidence="Medium-High",
    
    emotion_tag="rage",
)

vetp.log_event(const_hill)
print("✅ Constitution Hill pattern logged")

# ========== E4: DUKE OF OXFORD / KEMPTON KICKER ==========
print("\n📝 Logging E4: DUKE OF OXFORD - Kempton Kicker Pattern...")

duke = VETPEventIn(
    event_id="2025-12-03_KEM_18:10_DUKE_OXFORD",
    date=date(2025, 12, 3),
    course="Kempton",
    off_time=time(18, 10),
    code="Flat-AW",
    race_class="Hcp",
    field_size=9,
    
    going="Standard",
    pace_shape_pre="Even",
    pace_shape_actual="Bunched, then explosive kick",
    
    fav_name="Duke Of Oxford",
    fav_sp=3.75,
    fav_profile="Held up, turn of foot, suited by track",
    key_rivals=[
        KeyRival(name="Sax Appeal", sp=5.0, profile="One-paced grinder"),
    ],
    
    our_play_type="Back-win",
    our_play_horses=["Duke Of Oxford"],
    our_play_stakes="Moderate",
    
    winner="Duke Of Oxford",
    places=["Duke Of Oxford", "Unknown", "Unknown", "Sax Appeal"],
    pnl_units=6.5,
    read_race_right="Yes",
    
    behaviour_flags=["strong_turn_of_foot", "track_favours_kickers", "one_paced_rival", "pace_collapse_risk"],
    market_story="Competitive handicap, several with chances",
    reality_story="Duke sat mid, then kicked from behind and blew them away. Sax Appeal stuck on for 4th; one-paced when pace lifted.",
    
    key_learning="At Kempton, a horse with true change of gear is worth more than static speed. One-paced grinders look fine on paper but die when the real move comes.",
    
    rule_trigger="Kempton AW, Evidence in videos/sectionals of one runner with genuine late kick, Rivals mostly grinders / front-rank types",
    rule_action="Upgrade the kicker even if rated similar. Downgrade 'honest' one-paced types as place-only or 'top 4 at best'.",
    rule_confidence="Medium",
    
    emotion_tag="masterpiece",
)

vetp.log_event(duke)
print("✅ Duke Of Oxford event logged")

# ========== E5: SPRAY & PRAY DISASTER ==========
print("\n📝 Logging E5: SPRAY & PRAY Multi-Place Attack...")

spray = VETPEventIn(
    event_id="2025-12-03_KEM_19:40_SPRAY_PLACES",
    date=date(2025, 12, 3),
    course="Kempton",
    off_time=time(19, 40),
    code="Flat-AW",
    race_class="C5",
    field_size=11,
    
    going="Standard",
    pace_shape_pre="Unknown",
    pace_shape_actual="Messy",
    
    fav_name="Mesaafi",
    fav_sp=4.0,
    
    our_play_type="Multiple place backs",
    our_play_horses=["Valley Of The Kings", "Mr Cool", "Trouble Man", "Mesaafi"],
    our_play_stakes="Fragmented, emotionally driven 'something must land'",
    
    winner="Unknown",
    places=["None of ours", "None of ours", "None of ours"],
    pnl_units=-8.0,
    read_race_right="No",
    
    behaviour_flags=["no_clear_edge", "emotional_coverage", "overtrading"],
    market_story="Multiple plausible place chances",
    reality_story="None of them delivered. True edge: zero; we liked stories, not structural advantage.",
    
    key_learning="When you can't clearly mark which horse holds the structural edge, you don't have a bet, you have a shopping list.",
    
    rule_trigger=">2 runners backed in same market, Justification mostly narrative, not hard edge (draw/pace/class/intent)",
    rule_action="VÉLØ should flag 'SPRAY MODE' and recommend no bet or one tightly defined angle.",
    rule_confidence="High",
    
    emotion_tag="regret",
)

vetp.log_event(spray)
print("✅ Spray & Pray event logged")

# ========== STATS ==========
print("\n" + "="*60)
print("VETP LAYER 1 STATISTICS")
print("="*60)

stats = vetp.get_stats()
print(f"\n📊 Total Events: {stats['total_events']}")
print(f"✅ Winning Events: {stats['winning_events']}")
print(f"❌ Losing Events: {stats['losing_events']}")
print(f"💰 Total P&L: {stats['total_pnl_units']} units")
print(f"\n😤 Emotion Distribution:")
for emotion, count in stats['emotion_distribution'].items():
    print(f"   {emotion}: {count}")

print("\n" + "="*60)
print("✅ VETP LAYER 1 INITIALIZED")
print("="*60)
print("\nEvery beating and every masterclass is now permanent memory.")
print("VÉLØ can learn. VÉLØ can remember. VÉLØ can evolve.\n")

db.close()
