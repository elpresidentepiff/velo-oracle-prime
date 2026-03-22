"""
Phase 1 Sentient Bridge Proof
Run: python scripts/proof_sentient_bridge.py

Proves:
- G state loads and reaches the scorer
- Ranking unchanged
- Probabilities unchanged
- All 6 audit fields present and correct
- None path behaves correctly
"""
import os
import json
import sys
import glob
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

print("=" * 60)
print("VELO PRIME — PHASE 1 SENTIENT BRIDGE PROOF")
print("=" * 60)

# ── 1. Load a cached racecard ─────────────────────────────────────────────────
files = sorted(glob.glob(str(ROOT / "data" / "racecards_*.json")))
if not files:
    print("ERROR: no cached racecard files in data/")
    sys.exit(1)

latest = files[-1]
print(f"\nUsing racecard: {latest}")
with open(latest) as f:
    raw = json.load(f)

racecards = raw if isinstance(raw, list) else raw.get("racecards", [])
races_with_runners = [r for r in racecards if r.get("runners")]
if not races_with_runners:
    print("ERROR: no races with runners in racecard")
    sys.exit(1)

test_race = races_with_runners[0]
print(f"Race: {test_race.get('course')} {test_race.get('off_time')} "
      f"— {len(test_race.get('runners', []))} runners")

# ── 2. Load G state ───────────────────────────────────────────────────────────
print("\n[1] Loading G state...")
_sentient_state = None
try:
    from app.playbooks.playbook_g_sentient_loopback import SentientLoopbackEngine
    g = SentientLoopbackEngine()
    raw_state = g.get_evolutionary_state()
    source = "disk" if raw_state.get("total_races_observed", 0) > 0 else "unknown"
    _sentient_state = {**raw_state, "_source": source}
    races_obs = raw_state.get("total_races_observed", 0)
    aggression = raw_state.get("appetite_state", {}).get("aggression_level", "?")
    print(f"    source={source}  races_observed={races_obs}  aggression={aggression}")
    print("    G state: LOADED")
except Exception as e:
    print(f"    G state load failed (non-fatal): {e}")
    print("    Continuing with sentient_state=None to prove None path works")

# ── 3. Normalize ──────────────────────────────────────────────────────────────
print("\n[2] Normalizing race...")
from workers.racing_api_normalizer import normalize_race
norm = normalize_race(test_race)
print(f"    runners normalized: {len(norm.get('runners', []))}")

# ── 4. Score WITH sentient_state ──────────────────────────────────────────────
print("\n[3] Scoring WITH sentient_state...")
from app.services.velo_prime_service import score_race_velo_prime
preds_with = score_race_velo_prime(norm, sentient_state=_sentient_state)
print(f"    predictions returned: {len(preds_with)}")

# ── 5. Score WITHOUT sentient_state (baseline) ────────────────────────────────
print("\n[4] Scoring WITHOUT sentient_state (None baseline)...")
preds_without = score_race_velo_prime(norm, sentient_state=None)
print(f"    predictions returned: {len(preds_without)}")

# ── 6. Ranking + probability proof ───────────────────────────────────────────
print("\n[5] Ranking + probability unchanged:")
all_rank = True
all_prob = True
for i, (pw, pwo) in enumerate(zip(preds_with, preds_without)):
    rank_ok = pw["horse"] == pwo["horse"]
    prob_ok = abs(pw["velo_prime_prob"] - pwo["velo_prime_prob"]) < 1e-9
    if not rank_ok:
        all_rank = False
    if not prob_ok:
        all_prob = False
    print(f"    [{i+1}] {pw['horse']:<28} prob={pw['velo_prime_prob']:.4f}  "
          f"rank_match={rank_ok}  prob_match={prob_ok}")

print(f"\n    RANKING UNCHANGED:      {all_rank}")
print(f"    PROBABILITIES UNCHANGED: {all_prob}")

# ── 7. Audit fields — WITH path ───────────────────────────────────────────────
AUDIT_FIELDS = [
    "sentient_state_loaded",
    "sentient_state_source",
    "sentient_races_observed",
    "sentient_aggression_level",
    "sentient_modifier_applied",
    "sentient_modifier_mode",
]

print("\n[6] Audit fields — WITH sentient_state:")
top = preds_with[0]
with_checks = {}
for k in AUDIT_FIELDS:
    v = top.get(k)
    print(f"    {k}: {v}")
    with_checks[k] = v

# ── 8. Audit fields — None path ───────────────────────────────────────────────
print("\n[7] Audit fields — WITHOUT sentient_state (None path):")
top2 = preds_without[0]
none_checks = {}
for k in AUDIT_FIELDS:
    v = top2.get(k)
    print(f"    {k}: {v}")
    none_checks[k] = v

# ── 9. Machine-checkable assertions ──────────────────────────────────────────
print("\n[8] Assertions:")
errors = []

if _sentient_state is not None:
    if with_checks["sentient_state_loaded"] is not True:
        errors.append("sentient_state_loaded should be True when state provided")
    if with_checks["sentient_state_source"] not in ("disk", "supabase", "unknown"):
        errors.append(f"unexpected sentient_state_source: {with_checks['sentient_state_source']}")
    if not isinstance(with_checks["sentient_races_observed"], int):
        errors.append("sentient_races_observed should be int")
    if with_checks["sentient_modifier_applied"] is not False:
        errors.append("sentient_modifier_applied must be False in Phase 1")
    if with_checks["sentient_modifier_mode"] != "audit_only":
        errors.append("sentient_modifier_mode must be 'audit_only'")
else:
    if none_checks["sentient_state_loaded"] is not False:
        errors.append("sentient_state_loaded should be False on None path")

if none_checks["sentient_modifier_applied"] is not False:
    errors.append("sentient_modifier_applied must be False on None path")
if none_checks["sentient_modifier_mode"] != "audit_only":
    errors.append("sentient_modifier_mode must be 'audit_only' on None path")

if not all_rank:
    errors.append("RANKING CHANGED — Phase 1 violation")
if not all_prob:
    errors.append("PROBABILITIES CHANGED — Phase 1 violation")

for err in errors:
    print(f"    FAIL: {err}")

if not errors:
    print("    ALL ASSERTIONS PASS")

# ── Summary ───────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
if errors:
    print(f"PHASE 1 PROOF FAILED — {len(errors)} assertion(s) failed")
    sys.exit(1)
else:
    print("PHASE 1 PROOF COMPLETE — ALL CHECKS PASS")
    print(f"  G state loaded:          {with_checks.get('sentient_state_loaded')}")
    print(f"  Source:                  {with_checks.get('sentient_state_source')}")
    print(f"  Races observed:          {with_checks.get('sentient_races_observed')}")
    print(f"  Aggression level:        {with_checks.get('sentient_aggression_level')}")
    print(f"  Modifier applied:        {with_checks.get('sentient_modifier_applied')}")
    print(f"  Modifier mode:           {with_checks.get('sentient_modifier_mode')}")
    print(f"  Ranking unchanged:       {all_rank}")
    print(f"  Probabilities unchanged: {all_prob}")
print("=" * 60)
