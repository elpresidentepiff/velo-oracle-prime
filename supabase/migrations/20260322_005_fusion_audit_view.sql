-- 20260322_005_fusion_audit_view.sql
-- Live queryable view exposing specialist vs ensemble tension per runner.
-- Detects: deception_on_pick_not_winner | place_suppressed_sqpe_signal | near_miss | deep_miss | correct
-- Query: SELECT * FROM velo_fusion_audit WHERE fusion_flag != 'ok';

CREATE OR REPLACE VIEW velo_fusion_audit AS
WITH runner_scores AS (
  SELECT
    v.race_id,
    v.id AS verdict_id,
    v.generated_at AS scored_at,
    r_data->>'horse_id'                          AS horse_id,
    r_data->>'horse'                              AS horse_name,
    (r_data->>'velo_prime_prob')::numeric        AS velo_prime_prob,
    (r_data->>'place_prob')::numeric             AS place_prob,
    (r_data->>'longshot_prob')::numeric          AS longshot_prob,
    (r_data->>'sqpe_v17_prob')::numeric          AS sqpe_v17_prob,
    (r_data->>'market_deception_score')::numeric AS market_deception_score,
    (r_data->>'improvement_score')::numeric      AS improvement_score,
    (r_data->>'macro_chaos_mode')::boolean       AS macro_chaos_mode,
    r_data->>'favourite_trap_risk'               AS favourite_trap_risk,
    ROW_NUMBER() OVER (
      PARTITION BY v.race_id
      ORDER BY (r_data->>'velo_prime_prob')::numeric DESC
    ) AS ensemble_rank
  FROM velo_verdicts v
  CROSS JOIN LATERAL jsonb_array_elements(v.full_analysis) AS r_data
  WHERE jsonb_typeof(v.full_analysis) = 'array'
),
winners AS (
  SELECT race_id, horse_id, sp_dec::numeric AS winner_sp
  FROM runner_results
  WHERE is_winner = TRUE
),
top_picks AS (
  SELECT race_id,
         horse_id               AS top_pick_horse_id,
         velo_prime_prob        AS top_pick_prob,
         place_prob             AS top_pick_place_prob,
         market_deception_score AS top_pick_deception_score
  FROM runner_scores WHERE ensemble_rank = 1
),
field_avg AS (
  SELECT race_id, AVG(sqpe_v17_prob) AS avg_sqpe
  FROM runner_scores GROUP BY race_id
)
SELECT
  rs.race_id,
  rs.scored_at,
  rs.horse_name,
  rs.horse_id,
  rs.ensemble_rank,
  rs.velo_prime_prob,
  rs.place_prob,
  rs.longshot_prob,
  rs.sqpe_v17_prob,
  rs.market_deception_score,
  rs.favourite_trap_risk,
  rs.macro_chaos_mode,
  w.winner_sp,
  tp.top_pick_horse_id,
  tp.top_pick_prob,
  tp.top_pick_place_prob,
  tp.top_pick_deception_score,
  CASE
    WHEN w.horse_id = rs.horse_id THEN 'winner'
    WHEN rs.ensemble_rank = 1     THEN 'top_pick'
    ELSE 'other'
  END AS horse_role,
  CASE
    WHEN w.horse_id = rs.horse_id AND rs.ensemble_rank = 1
      THEN 'correct'
    WHEN w.horse_id = rs.horse_id AND rs.ensemble_rank > 1
         AND tp.top_pick_deception_score > rs.market_deception_score
      THEN 'deception_on_pick_not_winner'
    WHEN w.horse_id = rs.horse_id AND rs.ensemble_rank > 1
         AND rs.sqpe_v17_prob > fa.avg_sqpe
         AND rs.place_prob < tp.top_pick_place_prob * 0.5
      THEN 'place_suppressed_sqpe_signal'
    WHEN w.horse_id = rs.horse_id AND rs.ensemble_rank > 3
      THEN 'deep_miss'
    WHEN w.horse_id = rs.horse_id AND rs.ensemble_rank IN (2, 3)
      THEN 'near_miss'
    ELSE 'ok'
  END AS fusion_flag
FROM runner_scores rs
LEFT JOIN winners  w  ON w.race_id  = rs.race_id AND w.horse_id  = rs.horse_id
LEFT JOIN top_picks tp ON tp.race_id = rs.race_id
LEFT JOIN field_avg fa ON fa.race_id = rs.race_id
ORDER BY rs.race_id, rs.ensemble_rank;
