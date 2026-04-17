# Handover — Playbook G Shadow Multiplier Implementation
**Date:** 2026-04-08
**System:** velo_prime_ensemble.py
**Status:** SHADOW ACTIVE — no live impact

---

## What was done

1. **G state loaded** — `data/sentient_state.json` (restored from backup, 64-race frozen state)
2. **Shadow multiplier added** to `src/intelligence/velo_prime_ensemble.py`:
   - `_G_SHADOW_MODE = True` (default, safe)
   - New fields on `VeloPrimePrediction`: `horse_id`, `g_base_prob`, `g_shadow_multiplier`, `g_shadow_flags`
   - `_g_shadow_adjustment()` computes a multiplier from G's state
   - `compute()` saves base prob, logs G flags, does NOT modify `velo_prime_prob` in shadow mode
   - `to_dict()` exposes all G fields for observability

3. **Horse-specific pain rule matching** — pain rules only fire for the specific `horse_id` named in the rule, not blanket MPI suppression

4. **`sentient_state.json` restored** — was missing, restored from backup

---

## G State — Current Status

| Attribute | Value | Implication |
|-----------|-------|-------------|
| Races observed | 64 / 558 (11.5%) | G has only evolved on 64 races |
| Doctrine strengths | ALL 1.0 (default) | No differentiation learned yet |
| Structural drift | ALL 0 | No structural patterns accumulated |
| Doctrine threshold | 1.0 → effective 0.6 | G will fire once evolved |
| Emotion laws | 4 pain rules, 13 triumph rules | Only 4 horse-specific pain flags |
| Pain rules | Specific to hrs_52710350, hrs_56559419, hrs_34457038, hrs_57878156 | Only fire for those specific horses |

---

## Shadow Behavior (Right Now)

| Scenario | Shadow multiplier | Flag | velo_prime_prob |
|----------|-------------------|------|-----------------|
| Fav + MDS > 0.55 | 0.93x | `g_fav_liability:0.93` | UNCHANGED |
| Non-fav + specific horse_id match | 0.85x | `g_pain_rule:high_mpi_narrative_trap:0.85` | UNCHANGED |
| No match | 1.0 | `g_shadow:applied_not_live` | UNCHANGED |

---

## What G Needs Before Live

**P0: Run `close_sigma_loops.py` on ALL 558 race dates**
- This will evolve G on the full archive
- Doctrine strengths will drop below 1.0 for losing doctrines
- Structural drift will show actual patterns
- Emotion laws will grow beyond 4 pain rules

**P1: After full evolution, check:**
- Doctrine strengths: expect LAY_THE_STORY < 1.0 if it's been losing
- Structural drift: expect off_pace_wins, hidden_improver_wins to be non-zero
- Appetite state: expect doctrine_firing_threshold to be < 1.0

**P2: Shadow test vs sigma_audits**
- Run predictions with G shadow ON
- Measure: mid_priced_won reduction, Tier A stability, strike rate change
- Compare `g_base_prob` vs actual outcomes

**P3: Promote to live**
- Set `_G_SHADOW_MODE = False` in velo_prime_ensemble.py
- G multiplier now ACTUALLY modifies `velo_prime_prob`

---

## Files Modified

- `src/intelligence/velo_prime_ensemble.py` — G shadow system added
- `data/sentient_state.json` — restored from backup (was missing)

## Files Written

- `docs/system_audits/2026-04-08_archive_analytics_and_oracle_gate.md`
- `docs/system_audits/2026-04-08_playbook_priority_audit.md`
- `docs/agent_handoffs/2026-04-08_playbook_g_shadow_implementation.md`
