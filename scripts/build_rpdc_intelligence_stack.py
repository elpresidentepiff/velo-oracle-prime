"""
Backfill deterministic RPD-C base tags across 2024 and 2025 intelligence stacks.

Creates:
    intelligence.rpdc_tags_2025  — 84,049 rows tagged
    intelligence.rpdc_tags_2024  — 169,702 rows tagged

Tags are derived ONLY from the existing 5-layer intelligence stack.
No LLM. No SQLite. No jockey/gear data (live-only context).

Output columns per row:
    run_id, entity_id, horse_name_raw, trainer, date,
    rpdc_tag_base, rpdc_confidence, rpdc_evidence, rpdc_blockers, rpdc_explanation

Run:
    python scripts/build_rpdc_intelligence_stack.py
    python scripts/build_rpdc_intelligence_stack.py --year 2025
    python scripts/build_rpdc_intelligence_stack.py --year 2024
"""
import os
import sys
import json
import argparse
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.rpd.rpdc_rules import tag_from_intelligence_row

TOKEN = os.getenv("SUPABASE_ACCESS_TOKEN")
REF   = os.getenv("SUPABASE_URL", "").split("//")[-1].split(".")[0]

BATCH_SIZE = 500  # rows per upsert


def sql(q, timeout=120):
    r = requests.post(
        f"https://api.supabase.com/v1/projects/{REF}/database/query",
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
        json={"query": q}, timeout=timeout,
    )
    result = r.json()
    if isinstance(result, dict) and "message" in result:
        raise ValueError(result["message"])
    return result


def create_table(year: int):
    """Create intelligence.rpdc_tags_YYYY if not exists."""
    print(f"  Creating intelligence.rpdc_tags_{year}...")
    sql(f"""
        DROP TABLE IF EXISTS intelligence.rpdc_tags_{year};

        CREATE TABLE intelligence.rpdc_tags_{year} (
            tag_id          BIGSERIAL   PRIMARY KEY,
            run_id          BIGINT      NOT NULL UNIQUE,
            entity_id       UUID        NOT NULL,
            horse_name_raw  TEXT        NOT NULL,
            trainer         TEXT,
            date            DATE        NOT NULL,
            rpdc_tag_base   TEXT        NOT NULL,   -- T / H / S / P / E
            rpdc_confidence TEXT        NOT NULL,   -- high / medium / low
            rpdc_evidence   TEXT[]      NOT NULL,   -- evidence codes that fired
            rpdc_blockers   TEXT[]      NOT NULL,   -- blocker codes triggered
            rpdc_explanation TEXT                   -- human-readable (for VOX)
        );

        CREATE INDEX ON intelligence.rpdc_tags_{year} (run_id);
        CREATE INDEX ON intelligence.rpdc_tags_{year} (entity_id);
        CREATE INDEX ON intelligence.rpdc_tags_{year} (horse_name_raw);
        CREATE INDEX ON intelligence.rpdc_tags_{year} (rpdc_tag_base);
        CREATE INDEX ON intelligence.rpdc_tags_{year} (date);
    """, timeout=60)
    print("    OK")


def fetch_rows(year: int, offset: int, limit: int) -> list:
    """Fetch a batch of intelligence rows for tagging."""
    run_num_col = f"h.run_number_{year}"
    return sql(f"""
        SELECT
            p.run_id, p.entity_id, p.horse_name_raw, p.trainer, p.date,
            -- identity
            p.identity_confidence, p.ambiguity_flag,
            -- plot flags
            p.manual_review_priority, p.plot_pressure_flag,
            p.plot_reason_codes,
            -- layoff
            p.layoff_flag, p.long_layoff_flag, p.days_since_last_run,
            -- candidate flags
            p.mark_restore_candidate, p.setup_restore_candidate,
            p.reactivation_candidate, p.compression_plus_restore,
            p.post_drop_restore, p.full_restore_live,
            -- OR data
            p.or_rating_num, p.or_change, p.current_vs_last_winning_or,
            p.or_treadmill_flag, p.mark_compression_flag,
            -- handicap trajectory (joined)
            t.career_peak_or_to_date, t.last_winning_or_to_date,
            -- setup restore (joined)
            s.trip_restore_flag, s.course_restore_flag,
            -- run history (joined)
            h.is_win,
            {run_num_col} AS run_number
        FROM intelligence.plot_candidate_flags_{year} p
        LEFT JOIN intelligence.handicap_trajectory_{year} t ON t.run_id = p.run_id
        LEFT JOIN intelligence.setup_restore_events_{year} s ON s.run_id = p.run_id
        LEFT JOIN intelligence.horse_run_history_{year} h ON h.run_id = p.run_id
        ORDER BY p.run_id
        LIMIT {limit} OFFSET {offset}
    """, timeout=180)


def insert_batch(year: int, tagged_rows: list):
    """Insert a batch of tagged rows into intelligence.rpdc_tags_YYYY."""
    values = []
    for r in tagged_rows:
        ev  = "{" + ",".join(f'"{e}"' for e in r["rpdc_evidence"])  + "}"
        blk = "{" + ",".join(f'"{b}"' for b in r["rpdc_blockers"]) + "}"
        expl = r["rpdc_explanation"].replace("'", "''")
        values.append(
            f"({r['run_id']}, '{r['entity_id']}', "
            f"$${r['horse_name_raw']}$$, "
            f"$${r['trainer'] or ''}$$, "
            f"'{r['date']}',"
            f"'{r['rpdc_tag_base']}', '{r['rpdc_confidence']}', "
            f"'{ev}', '{blk}', "
            f"$${expl}$$)"
        )
    sql(f"""
        INSERT INTO intelligence.rpdc_tags_{year}
            (run_id, entity_id, horse_name_raw, trainer, date,
             rpdc_tag_base, rpdc_confidence, rpdc_evidence, rpdc_blockers, rpdc_explanation)
        VALUES {', '.join(values)}
        ON CONFLICT (run_id) DO UPDATE SET
            rpdc_tag_base   = EXCLUDED.rpdc_tag_base,
            rpdc_confidence = EXCLUDED.rpdc_confidence,
            rpdc_evidence   = EXCLUDED.rpdc_evidence,
            rpdc_blockers   = EXCLUDED.rpdc_blockers,
            rpdc_explanation = EXCLUDED.rpdc_explanation
    """, timeout=120)


def run_year(year: int):
    print(f"\n{'='*60}")
    print(f"Building intelligence.rpdc_tags_{year}")
    print(f"{'='*60}")

    # Get total count
    count_r = sql(f"SELECT COUNT(*) AS n FROM intelligence.plot_candidate_flags_{year}")
    total = count_r[0]["n"]
    print(f"Total rows to tag: {total:,}")

    create_table(year)

    tag_counts = {"T": 0, "H": 0, "S": 0, "P": 0, "E": 0}
    conf_counts = {"high": 0, "medium": 0, "low": 0}
    processed = 0
    offset = 0

    while offset < total:
        batch = fetch_rows(year, offset, BATCH_SIZE)
        if not batch:
            break

        tagged = []
        for row in batch:
            result = tag_from_intelligence_row(row)
            tagged.append({
                "run_id":          row["run_id"],
                "entity_id":       row["entity_id"],
                "horse_name_raw":  row["horse_name_raw"],
                "trainer":         row["trainer"],
                "date":            str(row["date"]),
                "rpdc_tag_base":   result.rpdc_tag_base,
                "rpdc_confidence": result.rpdc_confidence,
                "rpdc_evidence":   result.rpdc_evidence,
                "rpdc_blockers":   result.rpdc_blockers,
                "rpdc_explanation": result.rpdc_explanation,
            })
            tag_counts[result.rpdc_tag_base] = tag_counts.get(result.rpdc_tag_base, 0) + 1
            conf_counts[result.rpdc_confidence] = conf_counts.get(result.rpdc_confidence, 0) + 1

        insert_batch(year, tagged)
        processed += len(batch)
        offset += BATCH_SIZE
        pct = processed / total * 100
        print(f"  {processed:>7,} / {total:,}  ({pct:.1f}%)  T:{tag_counts['T']} H:{tag_counts['H']} S:{tag_counts['S']} P:{tag_counts['P']} E:{tag_counts['E']}")

    # Final summary
    print(f"\n── {year} Summary ──────────────────────────────────")
    print(f"  Total tagged:  {processed:,}")
    for tag, n in tag_counts.items():
        pct = n / processed * 100 if processed else 0
        print(f"  {tag}: {n:>7,}  ({pct:.1f}%)")
    print(f"\n  Confidence breakdown:")
    for conf, n in conf_counts.items():
        pct = n / processed * 100 if processed else 0
        print(f"  {conf}: {n:>7,}  ({pct:.1f}%)")

    # Verify
    verify = sql(f"""
        SELECT rpdc_tag_base, rpdc_confidence, COUNT(*) AS n
        FROM intelligence.rpdc_tags_{year}
        GROUP BY rpdc_tag_base, rpdc_confidence
        ORDER BY rpdc_tag_base, rpdc_confidence
    """)
    print(f"\n  DB verification:")
    for row in verify:
        print(f"    {row['rpdc_tag_base']} / {row['rpdc_confidence']}: {row['n']:,}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, choices=[2024, 2025], default=None,
                        help="Year to process (default: both 2025 and 2024)")
    args = parser.parse_args()

    years = [args.year] if args.year else [2025, 2024]
    for year in years:
        run_year(year)

    print("\nAll done.")


if __name__ == "__main__":
    main()
