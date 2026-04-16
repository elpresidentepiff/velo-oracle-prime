-- Recover sigma_audits.horse_id only where the reviewed selection identity is provable.
-- Confidence criteria:
--   * join on race_id only
--   * source is velo_verdicts.top_rank_horse_id, which is written from the reviewed top selection
--   * exactly one distinct non-blank top_rank_horse_id must exist for the race
--   * NULL is preserved when the source is missing or ambiguous

WITH provable_source AS (
    SELECT
        race_id,
        MIN(top_rank_horse_id) AS top_rank_horse_id
    FROM public.velo_verdicts
    WHERE top_rank_horse_id IS NOT NULL
      AND btrim(top_rank_horse_id) <> ''
      AND race_id IS NOT NULL
      AND btrim(race_id) <> ''
    GROUP BY race_id
    HAVING COUNT(DISTINCT top_rank_horse_id) = 1
),
eligible_sigma AS (
    SELECT
        s.id,
        p.top_rank_horse_id
    FROM public.sigma_audits s
    JOIN provable_source p
      ON p.race_id = s.race_id
    WHERE (s.horse_id IS NULL OR btrim(s.horse_id) = '')
)
UPDATE public.sigma_audits AS s
SET horse_id = e.top_rank_horse_id
FROM eligible_sigma e
WHERE s.id = e.id;
