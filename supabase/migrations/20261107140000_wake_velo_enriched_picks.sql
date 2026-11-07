-- Today's UK suggestions: Prime's pick from the NEW run beside everything Velo now holds about that horse
-- (WAKE-VELO-DASH-02). One row per race. Read-only, security_invoker, service_role select only.
-- The pick is Prime's. Rich Context has no fitted model, so nothing here re-ranks a runner.
-- runner_prediction_snapshots.rank is 0-BASED (rank 0 = Prime's top pick); canonical scorecards are 1-based.
create or replace view public.wake_velo_enriched_picks
with (security_invoker = true) as
with morning as not materialized (
  select distinct on (race_date, race_id, horse_id)
         race_date, race_id, horse_id, horse, rank, course, off_time,
         velo_prime_prob as p0, sp_dec as price0
  from public.runner_prediction_snapshots
  order by race_date, race_id, horse_id, created_at asc
), latest as not materialized (
  select distinct on (race_date, race_id, horse_id)
         race_date, race_id, horse_id, created_at,
         feature_families::jsonb as ff,
         (feature_families::jsonb -> 'prime_baseline_snapshot' ->> 'velo_prime_prob')::numeric as p1,
         (feature_families::jsonb -> 'prime_baseline_snapshot' ->> 'sp_dec')::numeric as price1
  from public.rich_context_shadow_packets
  order by race_date, race_id, horse_id, created_at desc
), morning_top as not materialized (
  select distinct on (race_date, race_id)
         race_date, race_id, horse_id as morning_horse_id, horse as morning_pick, p0 as morning_prob,
         course, off_time,
         case when off_time ~ '^[0-9]{1,2}[.:][0-9]{2}$' then
           (case when length(split_part(replace(off_time, ':', '.'), '.', 1)) = 1
                 then split_part(replace(off_time, ':', '.'), '.', 1)::int + 12
                 else split_part(replace(off_time, ':', '.'), '.', 1)::int end) * 60
           + split_part(replace(off_time, ':', '.'), '.', 2)::int
         end as off_minutes
  from morning
  order by race_date, race_id, rank, p0 desc
), now_top as not materialized (
  select distinct on (l.race_date, l.race_id)
         l.race_date, l.race_id, l.horse_id as now_horse_id, m.horse as pick, l.p1 as now_prob,
         l.price1 as price, l.created_at as run_at, l.ff
  from latest l
  join morning m using (race_date, race_id, horse_id)
  order by l.race_date, l.race_id, l.p1 desc, m.horse
), sizes as not materialized (
  select mo.race_date, mo.race_id, count(*) as field_morning,
         count(l.horse_id) as field_now,
         count(*) filter (where l.ff ? 'canonical_history') as field_with_history,
         count(*) filter (where l.ff ? 'rp_spotlight_facts') as field_with_spotlight
  from morning mo
  left join latest l using (race_date, race_id, horse_id)
  group by 1, 2
)
select mt.race_date, mt.race_id, mt.course, mt.off_time, mt.off_minutes,
       nt.pick, mt.morning_pick, (nt.now_horse_id <> mt.morning_horse_id) as pick_changed,
       mt.morning_prob, nt.now_prob, (nt.now_prob - mt.morning_prob) as prob_delta,
       nt.price, nt.run_at,
       s.field_morning, s.field_now, (s.field_morning - s.field_now) as withdrawn,
       s.field_with_history, s.field_with_spotlight,
       nt.ff -> 'formfav_raw_facts' ->> 'form' as form,
       jsonb_strip_nulls(jsonb_build_object(
         'runs', nt.ff -> 'canonical_history' -> 'career_history_rows',
         'runs_365d', nt.ff -> 'canonical_history' -> 'runs_365d',
         'win_rate', nt.ff -> 'canonical_history' -> 'win_rate',
         'place_rate', nt.ff -> 'canonical_history' -> 'place_rate',
         'last_position', nt.ff -> 'canonical_history' -> 'last_position',
         'days_since_last_run', nt.ff -> 'canonical_history' -> 'days_since_last_run',
         'course_runs', nt.ff -> 'canonical_history' -> 'course_runs',
         'course_place_rate', nt.ff -> 'canonical_history' -> 'course_place_rate'
       )) as history,
       nt.ff -> 'formfav_pace_context' -> 'speedMap' as pace,
       nt.ff -> 'formfav_class_context' -> 'raceClassFit' as class_fit,
       nt.ff -> 'rp_spotlight_facts' -> 'feature_families' as spotlight_families
from morning_top mt
join now_top nt using (race_date, race_id)
join sizes s using (race_date, race_id);

revoke all on public.wake_velo_enriched_picks from public, anon, authenticated;
grant select on public.wake_velo_enriched_picks to service_role;
