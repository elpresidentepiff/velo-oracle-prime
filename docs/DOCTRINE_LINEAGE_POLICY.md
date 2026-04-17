# Doctrine Lineage Policy

## Ownership

- `sigma_audits` owns doctrine review timing.
- Canonical doctrine review clock: `sigma_audits.created_at`.
- Supporting tables do not define review windows independently.

## Grain

- `doctrine_event_id` is a deterministic race-level lineage key derived from `race_id`.
- Selection-level precision remains in `horse_id`.
- Practical join model:
  - race-level joins: `doctrine_event_id`
  - selection-level joins: `(doctrine_event_id, horse_id)`

## Creation Point

- Primary creation point: whenever a sigma audit row is written for a race.
- Current backfill-safe rule: `doctrine_event_id = doctrine_event_uuid(race_id)`.
- Null is preserved when `race_id` is absent or blank.

## Propagation Rules

- `sigma_audits`: receives the deterministic race event id from `race_id`
- `race_truth_audits`: propagates the same race event id from `race_id`
- `runner_release_candidates`: propagates the same race event id from `race_id`; horse-level lineage is then `(doctrine_event_id, horse_id)`
- `today_rpdc_tags`: propagates the same race event id from `race_id`; horse-level lineage is then `(doctrine_event_id, horse_id)`

## Sidecar Join Rules

- Board, miner, and longshot simulation start from the sigma review set.
- Truth joins prefer `doctrine_event_id`; `race_id` is fallback only.
- RPDC joins prefer `(doctrine_event_id, horse_id)`; `(race_id, horse_id)` is fallback only.
- Fallback usage must be surfaced in output notes.

## Known Limitation

- `today_rpdc_tags` still lacks a freshness field like `generated_at`.
- Tag counts therefore remain approximate even with `doctrine_event_id` present.
- Current approximation:
  - reviewed sigma race set
  - `today_rpdc_tags.run_date = review_date`
  - `doctrine_event_id` / `race_id` intersection
