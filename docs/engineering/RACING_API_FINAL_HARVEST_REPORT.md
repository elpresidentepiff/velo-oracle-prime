# Racing API Final Harvest Report

- Started (UTC): `2026-05-14T01:51:48Z`
- Finished (UTC): `2026-05-14T01:53:06Z`
- Scope: `2026-05-07` to `2026-05-13`
- Normalization: `Raw capture only. Normalization skipped under corrected contained scope.`

## Capability Map

- Accessible endpoints: `19`
- Blocked endpoints: `6`

| Endpoint | Status | HTTP | Pagination | Plan message |
|---|---|---:|---|---|
| `/v1/racecards/free` | `accessible` | `200` | `True` | `` |
| `/v1/racecards/basic` | `accessible` | `200` | `True` | `` |
| `/v1/racecards/standard` | `accessible` | `200` | `True` | `` |
| `/v1/racecards/pro` | `blocked` | `401` | `True` | `Pro Plan required` |
| `/v1/racecards/{race_id}/standard` | `accessible` | `200` | `False` | `` |
| `/v1/results` | `accessible` | `200` | `True` | `` |
| `/v1/results/today` | `accessible` | `200` | `True` | `` |
| `/v1/results/today/free` | `accessible` | `200` | `True` | `` |
| `/v1/odds/{race_id}/{horse_id}` | `blocked` | `401` | `False` | `Pro Plan required` |
| `/v1/horses/search` | `accessible` | `200` | `False` | `` |
| `/v1/horses/{horse_id}/results` | `blocked` | `401` | `True` | `Pro Plan required` |
| `/v1/horses/{horse_id}/standard` | `accessible` | `200` | `False` | `` |
| `/v1/horses/{horse_id}/pro` | `blocked` | `401` | `False` | `Pro Plan required` |
| `/v1/jockeys/search` | `accessible` | `200` | `False` | `` |
| `/v1/jockeys/{jockey_id}/results` | `blocked` | `401` | `True` | `Pro Plan required` |
| `/v1/jockeys/{jockey_id}/analysis/courses` | `accessible` | `200` | `False` | `` |
| `/v1/jockeys/{jockey_id}/analysis/distances` | `accessible` | `200` | `False` | `` |
| `/v1/jockeys/{jockey_id}/analysis/trainers` | `accessible` | `200` | `False` | `` |
| `/v1/trainers/search` | `accessible` | `200` | `False` | `` |
| `/v1/trainers/{trainer_id}/results` | `blocked` | `401` | `True` | `Pro Plan required` |
| `/v1/trainers/{trainer_id}/analysis/courses` | `accessible` | `200` | `False` | `` |
| `/v1/trainers/{trainer_id}/analysis/distances` | `accessible` | `200` | `False` | `` |
| `/v1/trainers/{trainer_id}/analysis/jockeys` | `accessible` | `200` | `False` | `` |
| `/v1/courses` | `accessible` | `200` | `False` | `` |
| `/v1/courses/regions` | `accessible` | `200` | `False` | `` |

## Results Gap-Fill

| Date | Pages | Rows | Statuses |
|---|---:|---:|---|
| `2026-05-07` | 1 | 49 | `[200]` |
| `2026-05-08` | 1 | 50 | `[200]` |
| `2026-05-09` | 1 | 90 | `[200]` |
| `2026-05-10` | 1 | 35 | `[200]` |
| `2026-05-11` | 1 | 43 | `[200]` |
| `2026-05-12` | 1 | 48 | `[200]` |
| `2026-05-13` | 1 | 59 | `[200]` |

## Racecards

| Endpoint | Day | HTTP | Races | Runners |
|---|---|---:|---:|---:|
| `racecards/free` | `today` | 200 | 39 | 430 |
| `racecards/basic` | `today` | 200 | 39 | 430 |
| `racecards/standard` | `today` | 200 | 39 | 430 |
| `racecards/free` | `tomorrow` | 200 | 52 | 601 |
| `racecards/basic` | `tomorrow` | 200 | 52 | 601 |
| `racecards/standard` | `tomorrow` | 200 | 52 | 601 |

## Courses / Regions

| Endpoint | HTTP | Count |
|---|---:|---:|
| `courses` | 200 | 979 |
| `courses/regions` | 200 | 55 |

## Targeted Entity Analysis

- Trainers selected: `20` of `399`
- Jockeys selected: `20` of `424`
- Horses selected: `20` of `1242`

## Raw Response Counts

- `schema`: `1`
- `capability_map`: `23`
- `results`: `7`
- `racecards`: `6`
- `courses`: `1`
- `regions`: `1`
- `trainers`: `60`
- `jockeys`: `60`
- `horses`: `20`
- `errors`: `0`
