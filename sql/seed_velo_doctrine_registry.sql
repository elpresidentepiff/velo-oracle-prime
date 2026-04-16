-- Seed: initial Doctrine Layer registry rows
-- Apply after 20260415_001_velo_doctrine_registry.sql

INSERT INTO velo_doctrine_registry (
    doctrine_key,
    family,
    rule_type,
    status,
    condition_json,
    evidence_summary,
    sample_size,
    win_pct,
    place_pct,
    applies_to,
    effective_from,
    next_review_date,
    owner_note
)
VALUES
(
    'mark_ready_requires_trainer_authority',
    'rpdc_readiness',
    'promoter',
    'proposed',
    jsonb_build_object(
        'requires', jsonb_build_array('MARK_READY', 'trainer_authority'),
        'rejects', jsonb_build_array('mark_ready_without_trainer_authority'),
        'thesis', 'MARK_READY only promotes when trainer authority confirms intent'
    ),
    'Observed founder doctrine: MARK_READY signal should be promoted only when trainer authority is present.',
    NULL,
    NULL,
    NULL,
    ARRAY['shadow', 'rpdc'],
    DATE '2026-04-15',
    DATE '2026-04-22',
    'Initial doctrine seed from founder direction; hold as proposed until evidence board confirms sample.'
),
(
    'headgear_intro_low_authority_suppressor',
    'rpdc_headgear',
    'suppressor',
    'proposed',
    jsonb_build_object(
        'requires', jsonb_build_array('headgear_intro'),
        'trainer_authority_band', 'low',
        'thesis', 'Headgear intro without trainer authority is a suppressor'
    ),
    'Observed founder doctrine: first-time headgear should suppress when trainer headgear authority is weak.',
    NULL,
    NULL,
    NULL,
    ARRAY['shadow', 'rpdc'],
    DATE '2026-04-15',
    DATE '2026-04-22',
    'Do not operationalize in scoring yet; evidence-layer only.'
),
(
    'class_drop_requires_trainer_authority',
    'rpdc_class_drop',
    'promoter',
    'proposed',
    jsonb_build_object(
        'requires', jsonb_build_array('class_drop', 'trainer_authority'),
        'rejects', jsonb_build_array('class_drop_without_trainer_authority'),
        'thesis', 'Class drop should only promote when trainer class-drop authority is proven'
    ),
    'Observed founder doctrine: class-drop signal requires trainer authority before promotion.',
    NULL,
    NULL,
    NULL,
    ARRAY['shadow', 'rpdc'],
    DATE '2026-04-15',
    DATE '2026-04-22',
    'Initial registry load; waiting for contradiction miner counts.'
),
(
    'a_tier_weak_place_watch',
    'a_tier_quality',
    'watch',
    'watch',
    jsonb_build_object(
        'requires', jsonb_build_array('decision_tier=A', 'weak_place_support'),
        'thesis', 'A-tier picks with weak place support should be watched as suspect cohort'
    ),
    'Weak A-place cohort is acknowledged as real but not yet promoted to blocker.',
    NULL,
    NULL,
    NULL,
    ARRAY['live', 'shadow', 'review'],
    DATE '2026-04-15',
    DATE '2026-04-22',
    'Watch-only until enough race truth accumulates.'
),
(
    'longshot_block_allowed_watch_only',
    'blocker_truth',
    'watch',
    'watch',
    jsonb_build_object(
        'requires', jsonb_build_array('longshot_risk_flag'),
        'thesis', 'Longshot blocker may remain allowed but only under watch until blocker truth stabilizes'
    ),
    'Longshot blocker is acknowledged, but truth posture is watch-only rather than fully active doctrine.',
    NULL,
    NULL,
    NULL,
    ARRAY['blocker', 'review'],
    DATE '2026-04-15',
    DATE '2026-04-22',
    'Do not tighten blocker policy until evidence board shows help/hurt stability.'
),
(
    'market_decoy_signal_active',
    'market_decoy',
    'blocker',
    'active',
    jsonb_build_object(
        'requires', jsonb_build_array('market_decoy_signal'),
        'thesis', 'Market decoy signal remains active as a doctrine-level blocker/watch axis'
    ),
    'Market decoy work is considered real and active in doctrine discussions; registry reflects current active stance.',
    NULL,
    NULL,
    NULL,
    ARRAY['live', 'shadow', 'blocker', 'review'],
    DATE '2026-04-15',
    DATE '2026-04-22',
    'Marked active because the signal family is already in live doctrine conversation, but this seed does not change scoring.'
),
(
    'longshot_block_allowed_aw_watch',
    'blocker_regime',
    'watch',
    'watch',
    jsonb_build_object(
        'requires', jsonb_build_array('longshot_block_allowed', 'aw_regime'),
        'focus', jsonb_build_array('Southwell (AW)', 'Kempton (AW)', 'Dundalk (AW) (IRE)'),
        'thesis', 'Longshot blocker shows concentrated review pressure in AW-heavy regimes'
    ),
    'Observed doctrine pressure: longshot_block_allowed appears locally toxic in AW-heavy conditions and should be watched as a separate regime.',
    NULL,
    NULL,
    NULL,
    ARRAY['live', 'blocker', 'review'],
    DATE '2026-04-16',
    DATE '2026-04-23',
    'Sidecar review row only; do not relax blocker logic until AW regime evidence remains stable.'
),
(
    'longshot_block_allowed_shortfav_aw_relax_candidate',
    'blocker_regime',
    'watch',
    'proposed',
    jsonb_build_object(
        'requires', jsonb_build_array('longshot_block_allowed', 'aw_regime', 'actual_winner_short_price'),
        'winner_sp_bucket', '<=3.0',
        'thesis', 'Longshot blocker may need regime-specific relaxation when AW races are won by short-priced runners'
    ),
    'Observed doctrine pressure: longshot_block_allowed is suppressing short-priced AW winners often enough to justify a regime-specific relax candidate review.',
    NULL,
    NULL,
    NULL,
    ARRAY['live', 'blocker', 'review'],
    DATE '2026-04-16',
    DATE '2026-04-23',
    'Proposed only; evidence board should confirm AW concentration before any blocker change is considered.'
)
ON CONFLICT (doctrine_key) DO UPDATE
SET
    family = EXCLUDED.family,
    rule_type = EXCLUDED.rule_type,
    status = EXCLUDED.status,
    condition_json = EXCLUDED.condition_json,
    evidence_summary = EXCLUDED.evidence_summary,
    sample_size = EXCLUDED.sample_size,
    win_pct = EXCLUDED.win_pct,
    place_pct = EXCLUDED.place_pct,
    applies_to = EXCLUDED.applies_to,
    effective_from = EXCLUDED.effective_from,
    next_review_date = EXCLUDED.next_review_date,
    owner_note = EXCLUDED.owner_note,
    updated_at = NOW();
