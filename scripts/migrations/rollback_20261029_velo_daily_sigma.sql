-- ROLLBACK for supabase/migrations/20261029_001_velo_daily_sigma_racing_horse_runs.sql
-- Restores the definitions captured from production on 2026-10-29 (pg_matviews + cron.job id 3).
-- NOT auto-applied: it lives in scripts/migrations/, not supabase/migrations/.
-- Note: this restores the runner_results-based view, which is a dead source since 2026-04-29, and
-- the old high_conf_miss ('HIGH' vs stored lowercase) behaviour. It does NOT undo the recomputed
-- velo_sigma_history rows; capture those first if you need the pre-migration values.

begin;

drop materialized view if exists public.velo_daily_sigma;

create materialized view public.velo_daily_sigma as
 WITH preds AS (
         SELECT v.id AS verdict_id,
            v.race_id,
            v.generated_at,
            v.top_rank_horse_id,
            v.top_rank_score,
            v.confidence_level
           FROM velo_verdicts v
          WHERE (v.generated_at >= (now() - '30 days'::interval))
        ), results AS (
         SELECT rr.race_id,
            rr.horse_id,
            rr."position",
            rr.is_winner,
            rr.sp_dec
           FROM runner_results rr
          WHERE (rr.race_id IN ( SELECT DISTINCT preds.race_id
                   FROM preds))
        ), races_window AS (
         SELECT r.race_id,
            r.course,
            r.date
           FROM races r
          WHERE ((r.date >= (now() - '30 days'::interval)) AND (r.race_id IN ( SELECT DISTINCT preds.race_id
                   FROM preds)))
        ), race_level AS (
         SELECT p.race_id,
            r.course,
            r.date,
            p.generated_at,
            p.top_rank_horse_id,
            p.top_rank_score,
            p.confidence_level,
            pr."position" AS top_pick_position,
            pr.is_winner AS top_pick_won,
            pr.sp_dec AS top_pick_sp
           FROM ((preds p
             LEFT JOIN results pr ON (((p.race_id = pr.race_id) AND (p.top_rank_horse_id = pr.horse_id))))
             LEFT JOIN races_window r ON ((r.race_id = p.race_id)))
        ), race_metrics AS (
         SELECT rl.race_id,
            rl.course,
            rl.date,
            count(DISTINCT res.horse_id) AS runners_count,
            bool_or((rl.top_pick_won = true)) AS top1_hit,
            bool_or((rl.top_pick_position <= 3)) AS top3_hit,
            max(
                CASE
                    WHEN (rl.top_pick_position > 0) THEN (1.0 / (rl.top_pick_position)::numeric)
                    ELSE (0)::numeric
                END) AS mrr_contrib,
            max(rl.top_pick_sp) AS top_pick_sp,
            bool_or(((rl.confidence_level = 'HIGH'::text) AND (rl.top_pick_won IS DISTINCT FROM true))) AS high_conf_miss
           FROM (race_level rl
             LEFT JOIN results res ON ((res.race_id = rl.race_id)))
          GROUP BY rl.race_id, rl.course, rl.date
        )
 SELECT race_id,
    course,
    (date)::timestamp without time zone AS date,
    (runners_count)::integer AS runners_count,
        CASE
            WHEN top1_hit THEN 1
            ELSE 0
        END AS top1_hit_flag,
        CASE
            WHEN top3_hit THEN 1
            ELSE 0
        END AS top3_hit_flag,
    round(mrr_contrib, 4) AS mrr_contrib,
    top_pick_sp,
    high_conf_miss,
        CASE
            WHEN (top_pick_sp IS NULL) THEN '-1.0'::numeric
            ELSE
            CASE
                WHEN top1_hit THEN (top_pick_sp - 1.0)
                ELSE '-1.0'::numeric
            END
        END AS pnl_per_unit
   FROM race_metrics rm;

create index idx_velo_daily_sigma_race_id on public.velo_daily_sigma using btree (race_id);
create unique index idx_velo_daily_sigma_unique on public.velo_daily_sigma using btree (race_id, date);

revoke all on public.velo_daily_sigma from public, anon, authenticated;
grant all on public.velo_daily_sigma to service_role;

select cron.alter_job(
    job_id  := (select jobid from cron.job where jobname like '%refresh and insert velo_sigma_history%' limit 1),
    command := $cmd$
DO $$ BEGIN
  REFRESH MATERIALIZED VIEW public.velo_daily_sigma;
  INSERT INTO public.velo_sigma_history (snapshot_date, races_count, top1_precision, top3_precision, mean_reciprocal_rank, avg_sp, total_pnl, high_conf_miss_count)
  VALUES (
    CURRENT_DATE - 1,
    (SELECT COUNT(*) FROM public.velo_daily_sigma WHERE race_id <> 'ALL' AND date::date = CURRENT_DATE - 1),
    (SELECT AVG(CASE WHEN top1_hit_flag = 1 THEN 1.0 ELSE 0 END)::numeric FROM public.velo_daily_sigma WHERE race_id <> 'ALL' AND date::date = CURRENT_DATE - 1),
    (SELECT AVG(CASE WHEN top3_hit_flag = 1 THEN 1.0 ELSE 0 END)::numeric FROM public.velo_daily_sigma WHERE race_id <> 'ALL' AND date::date = CURRENT_DATE - 1),
    (SELECT AVG(mrr_contrib)::numeric FROM public.velo_daily_sigma WHERE race_id <> 'ALL' AND date::date = CURRENT_DATE - 1),
    (SELECT AVG(top_pick_sp)::numeric FROM public.velo_daily_sigma WHERE race_id <> 'ALL' AND date::date = CURRENT_DATE - 1),
    (SELECT SUM(pnl_per_unit)::numeric FROM public.velo_daily_sigma WHERE race_id <> 'ALL' AND date::date = CURRENT_DATE - 1),
    COALESCE((SELECT SUM(CASE WHEN high_conf_miss THEN 1 ELSE 0 END) FROM public.velo_daily_sigma WHERE race_id <> 'ALL' AND date::date = CURRENT_DATE - 1),0)
  )
  ON CONFLICT (snapshot_date) DO UPDATE SET
    races_count = EXCLUDED.races_count,
    top1_precision = EXCLUDED.top1_precision,
    top3_precision = EXCLUDED.top3_precision,
    mean_reciprocal_rank = EXCLUDED.mean_reciprocal_rank,
    avg_sp = EXCLUDED.avg_sp,
    total_pnl = EXCLUDED.total_pnl,
    high_conf_miss_count = EXCLUDED.high_conf_miss_count,
    created_at = now();
END $$;
$cmd$
);

drop function if exists public.velo_sigma_snapshot(date);

commit;
