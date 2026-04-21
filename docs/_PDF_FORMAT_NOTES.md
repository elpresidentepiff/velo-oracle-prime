# Racing Post PDF Format Notes

## Official Ratings (F_0015_OR)

Structure per race:
- Header: off_time, class, race type
- Sub-header: "Last 9 outings (pos,rating,beaten/winning distance)"
- Columns: Horse | Wgt | OR | future | Best winning (12mth, Ssn, Life) | Highest entered (12mth, Ssn, Life) | Lowest win (Ssn, Life) | RPR Master

Key data points:
- **OR**: Current official rating
- **Best winning**: Best OR when winning (12 months, season, lifetime)
- **Highest entered**: Highest OR entered at
- **Lowest win**: Lowest OR when winning (season, lifetime)
- **RPR Master**: Racing Post Rating master
- **Last 9 outings**: Position and rating in last 9 runs (left of horse name)
- **future**: Future engagement indicator

This is GOLD for handicap plot detection:
- Compare current OR to "Best winning Life" = how far from winning mark
- Compare current OR to "Lowest win Life" = is horse at its lowest winning mark
- "Highest entered" vs current OR = has horse been dropped

## Top Speed (F_0032_TS)

Structure per race:
- Header: off_time, class, race type
- Sub-header: "Last 8 outings"
- Columns: Horse | Wgt | OR | future | Ltst | Dist | Crs | Best ratings (Cls+Gf-Hd) | G | Gs-Hv | 6-11m | Base | Master

Key data points:
- **Ltst**: Latest TS rating
- **Dist**: Best TS at today's distance
- **Crs**: Best TS at today's course
- **Best ratings**: Best TS by class/going/headgear combination
- **G**: Best on Good
- **Gs-Hv**: Best on Good-to-Soft through Heavy
- **6-11m**: Best at 6-11 months ago
- **Base**: Base TS rating
- **Master**: Master TS rating (adjusted)
- **Last 8 outings**: TS figures for last 8 runs (left of horse name)

This tells us:
- Whether the horse has proven speed at this course/distance/going
- Whether TS is improving or declining (trend from last 8)
- The gap between current ability and peak ability
