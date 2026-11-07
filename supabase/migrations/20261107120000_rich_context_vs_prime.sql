-- Read-only per-race Rich Context evidence coverage for the dashboard "WAKE VELO" panel (WAKE-VELO-DASH-01).
-- The panel reads only the coverage columns; the all-models picks live in wake_velo_model_picks.
-- One row per UK/IRE race: Prime's top pick next to the No-RPR shadow's top pick, the settled
-- outcome of each once sigma has run, and how much Rich Context evidence existed for the field
-- in the FIRST packet batch of the day versus the LATEST (the rescore after the off-time fix).
-- Shadow only. No table is changed and nothing here feeds Prime.
create or replace view public.rich_context_vs_prime
with (security_invoker = true) as
with prime as (
  select distinct on (run_date, race_id)
         run_date as race_date, race_id,
         horse as prime_horse, result_position as prime_position, win as prime_won,
         tie_status as prime_tie_status
  from public.canonical_model_scorecards
  where model_name = 'MAIN_VELO_PRIME'
  order by run_date, race_id, rank, score desc nulls last, horse
), norpr as (
  select distinct on (run_date, race_id)
         run_date as race_date, race_id,
         horse as norpr_horse, result_position as norpr_position, win as norpr_won,
         tie_status as norpr_tie_status
  from public.canonical_model_scorecards
  where model_name = 'SQPE_NO_RPR_SHADOW'
  order by run_date, race_id, rank, score desc nulls last, horse
), meta as (
  select distinct on (race_date, race_id)
         race_date, race_id, course, off_time,
         -- Racing Post prints afternoon times without am/pm ("3.00" = 15:00); a one-digit hour is pm.
         case when off_time ~ '^[0-9]{1,2}[.:][0-9]{2}$' then
           (case when length(split_part(replace(off_time, ':', '.'), '.', 1)) = 1
                 then split_part(replace(off_time, ':', '.'), '.', 1)::int + 12
                 else split_part(replace(off_time, ':', '.'), '.', 1)::int end) * 60
           + split_part(replace(off_time, ':', '.'), '.', 2)::int
         end as off_minutes
  from public.runner_prediction_snapshots
  order by race_date, race_id, created_at desc
), first_pk as (
  select distinct on (race_date, race_id, horse_id)
         race_date, race_id, horse_id, family_coverage::jsonb as fc
  from public.rich_context_shadow_packets
  order by race_date, race_id, horse_id, created_at asc
), last_pk as (
  select distinct on (race_date, race_id, horse_id)
         race_date, race_id, horse_id, family_coverage::jsonb as fc
  from public.rich_context_shadow_packets
  order by race_date, race_id, horse_id, created_at desc
), cov_first as (
  select race_date, race_id,
         count(*) filter (where (fc ->> 'canonical_history')::boolean) as history_before,
         count(*) filter (where (fc ->> 'rp_spotlight_facts')::boolean) as spotlight_before
  from first_pk group by 1, 2
), cov_last as (
  select race_date, race_id, count(*) as runners,
         count(*) filter (where (fc ->> 'canonical_history')::boolean) as history_now,
         count(*) filter (where (fc ->> 'rp_spotlight_facts')::boolean) as spotlight_now,
         count(*) filter (where (fc ->> 'formfav_raw_facts')::boolean) as formfav_now
  from last_pk group by 1, 2
), batches as (
  select race_date, race_id, count(distinct created_at) as packet_batches,
         max(created_at) as latest_packet_at
  from public.rich_context_shadow_packets group by 1, 2
)
select p.race_date, p.race_id, m.course, m.off_time, m.off_minutes,
       p.prime_horse, n.norpr_horse,
       (p.prime_horse is not null and p.prime_horse = n.norpr_horse) as agree_on_top_pick,
       p.prime_position, p.prime_won, n.norpr_position, n.norpr_won,
       (p.prime_position is not null) as result_known,
       cl.runners, cf.history_before, cl.history_now,
       cf.spotlight_before, cl.spotlight_now, cl.formfav_now,
       b.packet_batches, b.latest_packet_at,
       p.prime_tie_status, n.norpr_tie_status
from prime p
left join norpr n using (race_date, race_id)
left join meta m using (race_date, race_id)
left join cov_first cf using (race_date, race_id)
left join cov_last cl using (race_date, race_id)
left join batches b using (race_date, race_id);

revoke all on public.rich_context_vs_prime from public, anon, authenticated;
grant select on public.rich_context_vs_prime to service_role;
