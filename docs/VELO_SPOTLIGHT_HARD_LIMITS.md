# VÉLØ ARCHITECTURAL RULE
## Spotlight Comment Layer — Permitted Role and Hard Limits
### Version 1.0 | Canonical Doctrine | Enforced at Code Level

> **A spotlight comment cannot generate a selection. It can only modify one.**

This rule is enforced in `workers/spotlight_parser.py` and `app/playbooks/playbook_orchestrator.py`. Any modification to those files must preserve this constraint.

---

## The Rule

The spotlight layer is signal enrichment. It feeds flags into existing scoring engines. It does not drive verdict assembly independently. A horse that scores poorly across the structural layers — ratings, regime, stamina, market, PJI — cannot be rescued into a chassis by a favourable spotlight comment alone. Equally, a horse that scores well across the structural layers is not automatically elevated to strike because the spotlight text is positive.

---

## What the Spotlight Layer Is Permitted To Do

| Permitted Action | Engine Target | Effect |
|---|---|---|
| Fire `flag_excuse_last` | PJI Setup Mismatch Score | +points to component C |
| Fire `flag_stamina_pos` | Stamina Score | +modifier |
| Fire `flag_stamina_risk` | Stamina Score | -modifier, possible `LIKELY NON-STAYER` tag |
| Fire `flag_peak_timing` | Day Classification Engine | Pushes toward CASH — but does not set it |
| Fire `flag_setup_run` | Day Classification Engine | Pushes toward SETUP — but does not set it |
| Fire `flag_pji_signal` | Concealed Effort Score | +points to component A |
| Fire `flag_behaviour` | Survivability Score | +/- modifier |
| Fire `flag_trainer_note` | TIE engine | Amplifier only — requires corroborating structural signal |
| Fire `flag_market_note` | Market Behaviour Layer | Trigger for further investigation — not a selection signal |
| Fire `flag_intent_today` | TIE engine | Intent confirmation — requires 1+ corroborating structural signal to activate |

---

## What the Spotlight Layer Is NOT Permitted To Do

1. **Generate a chassis inclusion by itself.** A horse must qualify through the structural layers first. The spotlight can add modifier points to an existing score. It cannot create a score from zero.

2. **Override a regime block.** If the Race Regime Override has tagged a horse `TS_DISTANCE_INVALID` or `STAMINA: LIKELY NON-STAYER`, a positive spotlight comment does not lift that block. The block holds.

3. **Substitute for missing ratings data.** In bumpers and maiden races where OR/TS/RPR are absent, a positive spotlight comment does not fill the data gap. The race regime defaults to CHAOS and the Unknown Ceiling Doctrine applies regardless of what the comment says.

4. **Elevate sentiment alone into a selection signal.** A sentiment score of +2 on a structurally weak horse is not a reason to include that horse. Sentiment is a soft modifier, not a hard qualifier.

5. **Be used as the primary justification text in any output.** The engine output may reference a spotlight flag only as a secondary annotation after the structural case has been made from ratings, regime, stamina, survivability, and market layers. The format must always be: structural case first, spotlight confirmation second.

---

## The Correct Integration Sequence

```
STEP 1: Run structural layers (Class, Differential, Setup, Stamina, Survivability)
         → These produce a preliminary chassis with scored candidates

STEP 2: Run Intent Override and Market layers
         → These may upgrade or suppress candidates based on non-spotlight signals

STEP 3: Run Spotlight NLP pass
         → Flags modify existing scores only
         → A candidate already in the chassis may rise or fall
         → No new candidate enters the chassis solely because of spotlight flags
         → A suppressed candidate (DISGUISE, STAMINA FAILURE, regime block)
           stays suppressed regardless of spotlight flags

STEP 4: Run Day Classification Engine
         → Spotlight flags are one input among several
         → Day Type is set by the convergence of structural + spotlight signals
         → Spotlight alone cannot set DAY_TYPE: CASH

STEP 5: Assemble verdict
         → Structural case is the primary text
         → Spotlight flags are cited as supporting annotations only
         → No selection justified by spotlight text alone
```

---

## The Output Discipline Rule

Every selection in a VÉLØ output must be supportable by removing all spotlight flags entirely and still surviving as a viable chassis inclusion based on the structural layers alone.

If removing the spotlight flags collapses the case for a horse, that horse was never a genuine VÉLØ selection. It was a spotlight-driven tip wearing a VÉLØ chassis. That is exactly what VÉLØ was built to prevent.

---

## Code Enforcement

This rule is enforced via the `SpotlightGate` class in `workers/spotlight_parser.py`:

- `SpotlightGate.is_structurally_qualified(runner)` — returns `True` only if the runner has passed the structural scoring gate (minimum structural score threshold met, no active regime blocks).
- `SpotlightGate.apply_modifiers(runner, spotlight_record)` — applies spotlight flag modifiers **only** if `is_structurally_qualified` returns `True`. If the runner is not structurally qualified, modifiers are silently discarded and a `SPOTLIGHT_BLOCKED` log entry is written.
- The orchestrator calls `SpotlightGate.apply_modifiers` at Step 3 of the integration sequence, after structural layers and intent/market layers have run.

*This rule is canonical and permanent. It may not be overridden by any downstream prompt, instruction, or analysis output.*
