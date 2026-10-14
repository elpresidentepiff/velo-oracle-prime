-- Where is VELO winning? Strike rate and calibration by country x confidence x
-- top-pick probability band, over races with a usable winner. SHADOW ONLY.
-- `final` and `provisional` are separate columns, never blended. A segment is
-- only trustworthy once `enough_sample` is true (>= 30 final races); until then
-- it is a lead to watch, not an edge.
create or replace view public.formfav_sigma_edges
with (security_invoker = true) as
select
    country,
    confidence,
    case
        when top1_win_prob < 0.15 then '1: <15%'
        when top1_win_prob < 0.25 then '2: 15-25%'
        when top1_win_prob < 0.35 then '3: 25-35%'
        else '4: 35%+'
    end                                                          as top1_prob_band,
    count(*) filter (where basis = 'final')                      as final_races,
    count(*) filter (where basis = 'final' and top1_hit)         as final_top1_wins,
    round(100.0 * count(*) filter (where basis = 'final' and top1_hit)
          / nullif(count(*) filter (where basis = 'final'), 0), 1) as final_strike_pct,
    count(*) filter (where basis = 'provisional')                as provisional_races,
    count(*) filter (where basis = 'provisional' and top1_hit)   as provisional_top1_wins,
    round(100.0 * count(*) filter (where basis = 'provisional' and top1_hit)
          / nullif(count(*) filter (where basis = 'provisional'), 0), 1) as provisional_strike_pct,
    round(100.0 * avg(top1_win_prob), 1)                         as avg_predicted_win_pct,
    count(*) filter (where basis = 'final') >= 30                as enough_sample,
    min(race_date)                                               as first_date,
    max(race_date)                                               as last_date
from public.formfav_sigma_audits
where basis in ('final', 'provisional') and not top1_scratched
group by 1, 2, 3;
