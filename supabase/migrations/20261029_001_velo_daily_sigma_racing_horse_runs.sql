-- 2026-10-29: repoint velo_daily_sigma at racing_horse_runs and stop writing false zeros.
--
-- WHY. velo_daily_sigma LEFT JOINed velo_verdicts to runner_results. runner_results was fed by the
-- Racing API, decommissioned 2026-05-14; its last populated race date is 2026-04-29. Since then no
-- verdict race has had a joined result, so every hit flag was 0 and pg_cron job 3 ("02:00 UTC -
-- refresh and insert velo_sigma_history") wrote top1_precision = 0.000 every night with a non-zero
-- races_count. That is a false zero from a dead source, not a measurement.
-- Current results live in racing_horse_runs (RP-era, numeric rp_uid horse_id; Step 13 of the EOD
-- procedure). Verified read-only on 2026-10-29 that verdicts join to it by (race_id, horse_id).
--
-- WHAT CHANGES.
--  1. velo_daily_sigma reads racing_horse_runs. Same columns, types, indexes and grants as before,
--     so nothing that reads the view needs to change (no dependent views/functions existed).
--  2. A race with NO result rows now yields NULL hit flags / mrr / high_conf_miss / pnl instead of
--     0 / -1.0 / true. Absence of results is "no evidence", not a loss. A race that HAS results but
--     whose top pick is missing from them (e.g. non-runner) is still counted as a miss, unchanged.
--  3. The nightly insert moves into velo_sigma_snapshot(date). Days with scored races but zero
--     results write NULL precision and notes = 'NO_RESULTS_FOR_DATE (...)' instead of 0.000.
--  4. One-time recompute of the last 30 days (the view's window), then older rows from the dead-source
--     era are annotated (notes only; numbers untouched).
--  5. Separate latent bug fixed in the same view: confidence_level is stored lowercase
--     ('high'/'normal'/'low') but high_conf_miss compared to 'HIGH', so it could never be true and
--     high_conf_miss_count was always 0. The comparison is now case-insensitive. Expect this metric to
--     become non-zero; that is the metric starting to work, not a regression.
--
-- NOT CHANGED. No scoring, model, ledger or staking path reads this view. Frozen-weights and
-- SIM-only laws are unaffected. Racing API is not used.
--
-- ROLLBACK. Recreate the view from the previous definition (runner_results join) and restore the
-- previous cron command; both previous definitions are quoted in the PR description.
-- Apply on a Supabase branch first and compare 2026-10-25..27 against the numbers in the PR.

begin;

drop materialized view if exists public.velo_daily_sigma;

create materialized view public.velo_daily_sigma as
with preds as (
    select v.id as verdict_id,
           v.race_id,
           v.generated_at,
           v.top_rank_horse_id,
           v.top_rank_score,
           v.confidence_level
    from public.velo_verdicts v
    where v.generated_at >= (now() - interval '30 days')
), results as (
    select h.race_id,
           h.horse_id,
           h.position_int as "position",
           h.is_win       as is_winner,
           h.sp_dec
    from public.racing_horse_runs h
    where h.run_date >= (current_date - 31)
      and h.race_id in (select distinct p.race_id from preds p)
), races_window as (
    select r.race_id, r.course, r.date
    from public.races r
    where r.date >= (now() - interval '30 days')
      and r.race_id in (select distinct p.race_id from preds p)
), race_level as (
    select p.race_id,
           r.course,
           r.date,
           p.generated_at,
           p.top_rank_horse_id,
           p.top_rank_score,
           p.confidence_level,
           pr."position"  as top_pick_position,
           pr.is_winner   as top_pick_won,
           pr.sp_dec      as top_pick_sp
    from preds p
    left join results pr
           on p.race_id = pr.race_id
          and p.top_rank_horse_id::text = pr.horse_id::text
    left join races_window r on r.race_id = p.race_id
), race_metrics as (
    select rl.race_id,
           rl.course,
           rl.date,
           count(distinct res.horse_id)                                   as runners_count,
           bool_or(rl.top_pick_won = true)                                as top1_hit,
           bool_or(rl.top_pick_position <= 3)                             as top3_hit,
           max(case when rl.top_pick_position > 0
                    then 1.0 / rl.top_pick_position::numeric
                    else 0::numeric end)                                  as mrr_contrib,
           max(rl.top_pick_sp)                                            as top_pick_sp,
           bool_or(lower(rl.confidence_level) = 'high'
                   and rl.top_pick_won is distinct from true)             as high_conf_miss
    from race_level rl
    left join results res on res.race_id = rl.race_id
    group by rl.race_id, rl.course, rl.date
)
select race_id,
       course,
       (date)::timestamp without time zone as date,
       (runners_count)::integer            as runners_count,
       case when runners_count = 0 then null when top1_hit then 1 else 0 end as top1_hit_flag,
       case when runners_count = 0 then null when top3_hit then 1 else 0 end as top3_hit_flag,
       case when runners_count = 0 then null else round(mrr_contrib, 4) end  as mrr_contrib,
       top_pick_sp,
       case when runners_count = 0 then null else high_conf_miss end         as high_conf_miss,
       case when runners_count = 0 then null
            when top_pick_sp is null then -1.0
            when top1_hit then top_pick_sp - 1.0
            else -1.0 end                                                    as pnl_per_unit
from race_metrics rm;

-- Same indexes as before. The UNIQUE one is required by `REFRESH ... CONCURRENTLY` (cron job 4, hourly).
create index idx_velo_daily_sigma_race_id on public.velo_daily_sigma using btree (race_id);
create unique index idx_velo_daily_sigma_unique on public.velo_daily_sigma using btree (race_id, date);

-- Same access as before: owner + service_role only (no anon / authenticated).
revoke all on public.velo_daily_sigma from public, anon, authenticated;
grant all on public.velo_daily_sigma to service_role;

-- One snapshot row per day. Used by the nightly cron and by the one-time recompute below.
create or replace function public.velo_sigma_snapshot(p_date date)
returns void
language sql
as $fn$
    with d as (
        select * from public.velo_daily_sigma
        where race_id <> 'ALL' and date::date = p_date
    ), agg as (
        select count(*)                                              as scored,
               count(*) filter (where top1_hit_flag is not null)     as resulted,
               avg(top1_hit_flag)::numeric                           as top1,
               avg(top3_hit_flag)::numeric                           as top3,
               avg(mrr_contrib)::numeric                             as mrr,
               avg(top_pick_sp)::numeric                             as avg_sp,
               sum(pnl_per_unit)::numeric                            as pnl,
               coalesce(sum(case when high_conf_miss then 1 else 0 end), 0) as hcm
        from d
    )
    insert into public.velo_sigma_history
        (snapshot_date, races_count, top1_precision, top3_precision, mean_reciprocal_rank,
         avg_sp, total_pnl, high_conf_miss_count, notes)
    select p_date, resulted, top1, top3, mrr, avg_sp, pnl, hcm,
           case when scored > 0 and resulted = 0
                then 'NO_RESULTS_FOR_DATE (' || scored || ' scored races unresulted)'
                else '' end
    from agg
    on conflict (snapshot_date) do update set
        races_count          = excluded.races_count,
        top1_precision       = excluded.top1_precision,
        top3_precision       = excluded.top3_precision,
        mean_reciprocal_rank = excluded.mean_reciprocal_rank,
        avg_sp               = excluded.avg_sp,
        total_pnl            = excluded.total_pnl,
        high_conf_miss_count = excluded.high_conf_miss_count,
        notes                = excluded.notes,
        created_at           = now();
$fn$;

-- Not an RPC: keep it away from PostgREST callers.
revoke execute on function public.velo_sigma_snapshot(date) from public, anon, authenticated;
grant execute on function public.velo_sigma_snapshot(date) to service_role;

-- Nightly job 3: same schedule (0 2 * * *), now calls the function.
select cron.alter_job(
    job_id  := (select jobid from cron.job where jobname like '%refresh and insert velo_sigma_history%' limit 1),
    command := $cmd$
DO $$ BEGIN
  REFRESH MATERIALIZED VIEW public.velo_daily_sigma;
  PERFORM public.velo_sigma_snapshot(CURRENT_DATE - 1);
END $$;
$cmd$
);

-- One-time: recompute the window the view covers, replacing the false zeros.
select public.velo_sigma_snapshot(d::date)
from generate_series(current_date - 30, current_date - 1, interval '1 day') d;

-- Older rows from the dead-source era (2026-04-30 onward, outside the view window): annotate only.
update public.velo_sigma_history
set notes = 'INVALID_FALSE_ZERO: runner_results source dead since 2026-04-29; ' || coalesce(notes, '')
where snapshot_date >= date '2026-04-30'
  and snapshot_date < current_date - 30
  and coalesce(top1_precision, 0) = 0
  and coalesce(notes, '') not like 'INVALID_FALSE_ZERO%';

commit;
