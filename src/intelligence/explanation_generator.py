"""
VÉLØ Natural Language Explanation Generator

Translates sub-quadratic ensemble scores and RPD-C structural intent tags
into human-readable "tipster-style" summaries for the dashboard and podcasts.
"""

def generate_decision_explanation(top_pick: dict, race_context: dict) -> str:
    """
    Generate a 2-3 sentence explanation for why VÉLØ selected this horse.
    """
    horse = top_pick.get("horse", "The selection")
    vp_prob = top_pick.get("velo_prime_prob", 0.0)
    mds = top_pick.get("market_deception_score", 0.0)
    improvement = top_pick.get("improvement_score", 0.0)
    intent_signals = top_pick.get("intent_signals", [])
    
    horse_state = top_pick.get("horse_state", {})
    
    sentences = []

    # 1. The Core Value Anchor
    if vp_prob > 0.25:
        sentences.append(f"{horse} rates as a high-probability value anchor in this field, with underlying metrics outperforming the current market price.")
    else:
        sentences.append(f"In an open race, {horse} emerges as the strongest probabilistic value play.")

    # 2. Context from Horse State (Stable, Jockey, Fitness)
    state_notes = []
    if horse_state.get("stable_heat") in ("hot", "warming"):
        state_notes.append("arrives from an in-form stable")
    if horse_state.get("jockey_signal") == "positive":
        state_notes.append("features a positive jockey booking")
    if horse_state.get("readiness_state") in ("peaking", "ready"):
        state_notes.append("shows a peaking readiness profile")
    
    if state_notes:
        sentences.append(f"The selection {' and '.join(state_notes)}.")

    # 3. The Market Deception / Profile Filter
    if mds > 0.5:
        sentences.append(f"A high Market Deception Score ({mds:.2f}) indicates the current price drift is likely a decoy, masking the true power rating.")
    elif improvement > 0.5:
        sentences.append("Its run-cycle and fitness timing suggest an imminent peak performance, supported by our Improvement Model.")

    # 4. The RPD-C Structural Intent (Old Velo)
    if "SETUP_RUN_CANDIDATE" in intent_signals:
        sentences.append("Structural analysis flags this as a primary target following a series of quiet preparation runs.")
    elif "OR_RISING" in intent_signals:
        sentences.append("The horse is highly progressive and structurally handicapped to win.")
    elif intent_signals:
        sentences.append(f"Forensic intent signals align with the math ({', '.join(intent_signals[:2]).replace('_', ' ').lower()}).")

    # 5. Fallback if no strong secondary signals
    if len(sentences) <= 2:
        sentences.append("Both probabilistic models and deterministic form profiles agree on this selection.")

    return " ".join(sentences)
