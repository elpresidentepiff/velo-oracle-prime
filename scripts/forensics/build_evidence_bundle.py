#!/usr/bin/env python3
"""
P0-16: build the committed, immutable evidence bundle at
data/evidence/race_day_14_2026_07_14/ sufficient to reproduce every
headline result in this mission WITHOUT relying on the uncommitted
evidence_staging/ directory or the primary repo.

Small/medium files (<~350KB) are copied verbatim. Large, mutable,
cross-date ledgers (model_comparison_ledger.csv, the innovation protocol
dedup dataset, New Build's raw per-runner feature JSONL) are replaced with
immutable filtered extracts specific to 2026-07-14, with the extract law
and the full source file's SHA-256 recorded so a reviewer can independently
confirm the extract is a faithful subset of the source.

Reads only from evidence_staging/2026-07-14/ (itself already hash-verified
against the primary repo by copy_evidence.py). Writes only under
data/evidence/race_day_14_2026_07_14/ in this clean worktree.
"""
import csv
import hashlib
import json
import os
import shutil

ROOT = "/mnt/c/Users/puror/velo-race-day-14-proof"
STAGE = os.path.join(ROOT, "evidence_staging", "2026-07-14")
BUNDLE = os.path.join(ROOT, "data", "evidence", "race_day_14_2026_07_14")


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_of_bytes(b):
    return hashlib.sha256(b).hexdigest()


os.makedirs(BUNDLE, exist_ok=True)
manifest_entries = []

# ---------------------------------------------------------------------------
# 1) Verbatim copies (small/medium files, load-bearing for headline claims)
# ---------------------------------------------------------------------------
VERBATIM = [
    "data/velo_prime_verdicts_2026_07_14.json",
    "data/results/rp_results_2026_07_14.json",
    "data/sigma_results/sigma_results_2026_07_14.json",
    "data/mission_control/2026-07-14_mission_control.json",
    "data/nightly_eod_learning_status_2026_07_14.json",
    "data/nightly_eod_learning_council_audit_2026_07_14.json",
    "data/council_packets/council_packet_2026-07-14.json",
    "data/council_reports/velo_council_report_2026-07-14.md",
    "data/council_runs/council_run_2026-07-14.json",
    "data/router_shadow_audit_runs/router_shadow_audit_20260714_231325.csv",
    "data/router_shadow_audit_runs/router_shadow_audit_20260714_231325.md",
    "data/router_shadow_audit_ledger.csv",
    "data/router_shadow_audit_latest.csv",
    "data/racing_post_account_raw/2026-07-14/manifest.json",
    "data/racing_post_url_lists/rp_results_2026-07-14.txt",
    "data/new_build/reports/current_card_passport_feed_2026_07_14.json",
    "data/new_build/reports/current_card_passport_feed_2026_07_14.md",
    "data/new_build/reports/current_card_intent_features_2026_07_14_audit.json",
    "data/new_build/reports/two_lane_readiness_2026_07_14.json",
    "data/new_build/reports/two_lane_readiness_2026_07_14.md",
    "_evidence_import_manifest.json",
]

for rel in VERBATIM:
    src = os.path.join(STAGE, rel)
    dst_rel = rel if not rel.startswith("_") else rel  # keep as-is
    dst = os.path.join(BUNDLE, dst_rel)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy2(src, dst)
    manifest_entries.append({
        "bundle_relative_path": os.path.relpath(dst, ROOT),
        "type": "VERBATIM_COPY",
        "source_within_evidence_staging": rel,
        "sha256": sha256_of(dst),
        "size_bytes": os.path.getsize(dst),
    })

# ---------------------------------------------------------------------------
# 2) Racecard compact canonical extract (from the full 1.1MB racecard file --
#    race-level fields only, runner detail omitted since verdicts/results
#    already carry the per-horse identity+outcome needed for every headline
#    claim; this extract exists to prove the 43-race/7-course universe).
# ---------------------------------------------------------------------------
rc_src = os.path.join(STAGE, "data/racecards_2026_07_14_standard.json")
rc_src_hash = sha256_of(rc_src)
with open(rc_src) as f:
    racecards = json.load(f)

compact_rows = []
for r in racecards:
    compact_rows.append({
        "race_id": r["race_id"], "course": r["course"], "course_id": r.get("course_id", ""),
        "date": r["date"], "off_time": r["off_time"], "race_name": r["race_name"],
        "distance": r.get("distance", ""), "distance_f": r.get("distance_f", ""),
        "going": r.get("going", ""), "surface": r.get("surface", ""), "type": r.get("type", ""),
        "race_class": r.get("race_class", ""), "rating_band": r.get("rating_band", ""),
        "field_size": r.get("field_size", ""), "region": r.get("region", ""),
        "runner_count_in_source": len(r.get("runners", [])),
    })
compact_path = os.path.join(BUNDLE, "data", "racecards_2026_07_14_race_level_extract.csv")
os.makedirs(os.path.dirname(compact_path), exist_ok=True)
with open(compact_path, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(compact_rows[0].keys()))
    w.writeheader()
    w.writerows(compact_rows)
manifest_entries.append({
    "bundle_relative_path": os.path.relpath(compact_path, ROOT),
    "type": "FILTERED_EXTRACT",
    "extract_law": "One row per race (43 rows) with race-level fields only (course/off/distance/going/class/field_size/region). Runner-level detail (odds, form, spotlight text, trainer/jockey identity) is intentionally omitted from this extract because velo_prime_verdicts_2026_07_14.json and rp_results_2026_07_14.json (both committed verbatim above) already carry the per-horse identity and outcome fields needed to reproduce every headline claim in this mission.",
    "full_source_path_in_evidence_staging": "data/racecards_2026_07_14_standard.json",
    "full_source_sha256": rc_src_hash,
    "full_source_size_bytes": os.path.getsize(rc_src),
    "extract_sha256": sha256_of(compact_path),
    "extract_size_bytes": os.path.getsize(compact_path),
    "extract_row_count": len(compact_rows),
    "generator": "scripts/forensics/build_evidence_bundle.py (this script, section 2)",
})

# ---------------------------------------------------------------------------
# 3) model_comparison_ledger.csv -> two immutable extracts:
#    (a) the 42-row 2026-07-14 slice (per-race four-model source data)
#    (b) the 37-day daily-aggregate ranking (already built as a report --
#        referenced here, not duplicated, but its generator+source hash
#        is recorded so the ranking is independently reproducible)
# ---------------------------------------------------------------------------
ledger_src = os.path.join(STAGE, "data/model_comparison_ledger.csv")
ledger_src_hash = sha256_of(ledger_src)
with open(ledger_src) as f:
    all_rows = list(csv.DictReader(f))
slice_rows = [r for r in all_rows if r["date"] == "2026-07-14"]
slice_path = os.path.join(BUNDLE, "data", "model_comparison_ledger_2026_07_14_slice.csv")
with open(slice_path, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(slice_rows[0].keys()))
    w.writeheader()
    w.writerows(slice_rows)
manifest_entries.append({
    "bundle_relative_path": os.path.relpath(slice_path, ROOT),
    "type": "FILTERED_EXTRACT",
    "extract_law": "WHERE date == '2026-07-14' on the full 1279-row/37-date append-only model_comparison_ledger.csv. All 27 columns preserved verbatim (no column subsetting) for the 42 matching rows.",
    "full_source_path_in_evidence_staging": "data/model_comparison_ledger.csv",
    "full_source_sha256": ledger_src_hash,
    "full_source_size_bytes": os.path.getsize(ledger_src),
    "full_source_row_count": len(all_rows),
    "full_source_date_count": len(set(r["date"] for r in all_rows)),
    "extract_sha256": sha256_of(slice_path),
    "extract_size_bytes": os.path.getsize(slice_path),
    "extract_row_count": len(slice_rows),
    "generator": "scripts/forensics/build_evidence_bundle.py (this script, section 3)",
})
note_37day = (
    "The 37-day daily-aggregate ranking used for the Phase 6 'best day' comparison is "
    "already committed at data/reports/race_day_14_historical_day_ranking_2026_07_14.csv "
    "(one row per date: eligible_races, wins, strike_rate_pct, frames, frame_rate_pct, "
    "avg_winner_sp, theoretical_sp_roi_pct, sp_data_available, result_completeness, "
    "timing_proof_status). It was generated by scripts/forensics/build_race_day_14_report.py "
    f"from the SAME full ledger file hashed above (sha256={ledger_src_hash}), grouping by date "
    "and computing wins/frames/SR/frame-rate/ROI per date across all 37 dates present in the "
    "ledger. Every date's timing_proof_status is explicitly marked NOT_RE_VERIFIED_THIS_MISSION "
    "except 2026-07-14 itself (PROVEN) -- prior dates were read from ledger aggregates only, not "
    "independently re-forensically audited in this mission."
)

# ---------------------------------------------------------------------------
# 4) New Build raw per-runner feature JSONL (1.1MB) -> row-count/schema
#    fingerprint extract, since the readiness reports (copied verbatim above)
#    already state races_scored=43/runners_scored=368 and the quality gates;
#    the raw JSONL itself is not load-bearing for any headline claim (it
#    proves only that Lane A feature-building ran, which the reports already
#    state authoritatively).
# ---------------------------------------------------------------------------
nb_files = [
    "data/new_build/current_cards/current_card_passport_feed_2026_07_14.jsonl",
    "data/new_build/current_cards/current_card_intent_features_2026_07_14.jsonl",
]
nb_fingerprints = []
for rel in nb_files:
    p = os.path.join(STAGE, rel)
    with open(p, "rb") as f:
        lines = f.readlines()
    nb_fingerprints.append({
        "source_path_in_evidence_staging": rel,
        "sha256": sha256_of(p),
        "size_bytes": os.path.getsize(p),
        "line_count": len(lines),
        "first_line_sha256": sha256_of_bytes(lines[0]) if lines else None,
        "last_line_sha256": sha256_of_bytes(lines[-1]) if lines else None,
    })
fp_path = os.path.join(BUNDLE, "data", "new_build_raw_feature_jsonl_fingerprint.json")
with open(fp_path, "w") as f:
    json.dump({
        "note": (
            "The raw per-runner feature JSONL files (368 runners x 2 files, ~1.1MB combined) "
            "are NOT duplicated into this evidence bundle because they are not load-bearing for "
            "any headline claim in this mission -- the readiness reports committed verbatim above "
            "(two_lane_readiness_2026_07_14.json/.md, current_card_passport_feed_2026_07_14.json/.md) "
            "already state races_scored=43, runners_scored=368, and all quality-gate results "
            "authoritatively. This fingerprint (full-file SHA-256, line count, first/last line "
            "hash) lets a reviewer confirm the source file identity if the primary repo copy is "
            "later inspected, without committing the full feature dump here."
        ),
        "fingerprints": nb_fingerprints,
    }, f, indent=2)
manifest_entries.append({
    "bundle_relative_path": os.path.relpath(fp_path, ROOT),
    "type": "FINGERPRINT_ONLY_NOT_LOAD_BEARING",
    "full_sources_fingerprinted": nb_files,
    "generator": "scripts/forensics/build_evidence_bundle.py (this script, section 4)",
})

# ---------------------------------------------------------------------------
# 5) raw HTML inventory -- pull straight out of _evidence_import_manifest.json
#    (already copied verbatim in section 1) into its own standalone CSV for
#    easy review (filename, canonical URL, size, sha256, dir).
# ---------------------------------------------------------------------------
with open(os.path.join(STAGE, "_evidence_import_manifest.json")) as f:
    import_manifest = json.load(f)
html_rows = []
for e in import_manifest["raw_html_inventory"]:
    if e.get("filename", "").endswith(".html"):
        html_rows.append({
            "dir": e["dir"], "filename": e["filename"], "size_bytes": e["size_bytes"],
            "mtime_utc": e["mtime_utc"], "sha256": e.get("sha256"),
            "canonical_url": e.get("canonical_url"),
        })
html_inv_path = os.path.join(BUNDLE, "data", "raw_html_inventory_2026_07_14.csv")
with open(html_inv_path, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(html_rows[0].keys()))
    w.writeheader()
    w.writerows(html_rows)
manifest_entries.append({
    "bundle_relative_path": os.path.relpath(html_inv_path, ROOT),
    "type": "DERIVED_FROM_VERBATIM_COPY",
    "source": "_evidence_import_manifest.json (raw_html_inventory field, .html entries only)",
    "row_count": len(html_rows),
    "sha256": sha256_of(html_inv_path),
})

# ---------------------------------------------------------------------------
# Write the bundle manifest
# ---------------------------------------------------------------------------
bundle_manifest = {
    "mission": "RACE-DAY-14-BEST-DAY-PROOF-01 (P0-16 correction pass)",
    "purpose": (
        "Immutable, committed evidence bundle sufficient to reproduce every "
        "headline result in race_day_14_best_day_proof_2026_07_14.{json,md} "
        "WITHOUT relying on the uncommitted evidence_staging/ directory or "
        "the primary repo at /mnt/c/Users/puror/velo-oracle-prime."
    ),
    "entries": manifest_entries,
    "cross_date_ledger_extract_note": note_37day,
    "reproduction_command": "PYTHONPATH=. python3 scripts/forensics/build_race_day_14_report.py -- but note this script as originally written reads from evidence_staging/2026-07-14/, NOT from data/evidence/race_day_14_2026_07_14/. See scripts/forensics/verify_evidence_bundle.py for the clean-checkout verification path that reads ONLY from this committed bundle.",
}
manifest_path = os.path.join(BUNDLE, "_bundle_manifest.json")
with open(manifest_path, "w") as f:
    json.dump(bundle_manifest, f, indent=2)

print(f"Bundle written to {BUNDLE}")
print(f"{len(manifest_entries)} entries, manifest at {manifest_path}")
import subprocess
print(subprocess.run(["du", "-sh", BUNDLE], capture_output=True, text=True).stdout)
