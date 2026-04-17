-- Doctrine event lineage upgrade
-- Policy:
--   * doctrine_event_id is a deterministic race-level lineage key derived from race_id
--   * sigma_audits owns the doctrine review clock; supporting tables propagate the same race event id
--   * horse-level precision stays in horse_id on selection tables
--   * rows without a provable race_id remain NULL rather than receiving fake lineage

CREATE OR REPLACE FUNCTION public.doctrine_event_uuid(source_race_id TEXT)
RETURNS UUID
LANGUAGE SQL
IMMUTABLE
AS $$
    SELECT CASE
        WHEN source_race_id IS NULL OR btrim(source_race_id) = '' THEN NULL
        ELSE (
            substr(md5('velo:doctrine:' || source_race_id), 1, 8) || '-' ||
            substr(md5('velo:doctrine:' || source_race_id), 9, 4) || '-' ||
            substr(md5('velo:doctrine:' || source_race_id), 13, 4) || '-' ||
            substr(md5('velo:doctrine:' || source_race_id), 17, 4) || '-' ||
            substr(md5('velo:doctrine:' || source_race_id), 21, 12)
        )::UUID
    END
$$;

UPDATE public.sigma_audits
SET doctrine_event_id = public.doctrine_event_uuid(race_id)
WHERE doctrine_event_id IS NULL
  AND race_id IS NOT NULL
  AND btrim(race_id) <> '';

UPDATE public.race_truth_audits
SET doctrine_event_id = public.doctrine_event_uuid(race_id)
WHERE doctrine_event_id IS NULL
  AND race_id IS NOT NULL
  AND btrim(race_id) <> '';

UPDATE public.runner_release_candidates
SET doctrine_event_id = public.doctrine_event_uuid(race_id)
WHERE doctrine_event_id IS NULL
  AND race_id IS NOT NULL
  AND btrim(race_id) <> '';

UPDATE public.today_rpdc_tags
SET doctrine_event_id = public.doctrine_event_uuid(race_id)
WHERE doctrine_event_id IS NULL
  AND race_id IS NOT NULL
  AND btrim(race_id) <> '';
