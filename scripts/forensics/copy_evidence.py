#!/usr/bin/env python3
"""
RACE-DAY-14-BEST-DAY-PROOF-01 -- Phase 0/3: read-only evidence import.

Reads ONLY from the dirty primary worktree (SRC). Never writes there.
Copies a fixed allowlist of 2026-07-14 evidence files into
evidence_staging/2026-07-14/ inside THIS (clean) worktree, verifying
SHA-256 equality after copy. Raw HTML captures are NOT copied (per
mission Preservation instructions) -- instead they are hashed in place
and recorded in a raw-HTML inventory manifest.
"""
import hashlib
import json
import os
import shutil
import sys
from datetime import datetime, timezone

SRC = "/mnt/c/Users/puror/velo-oracle-prime"
DST_ROOT = "/mnt/c/Users/puror/velo-race-day-14-proof"
STAGING = os.path.join(DST_ROOT, "evidence_staging", "2026-07-14")

# (relative path from SRC, relative subdir under STAGING/data)
COPY_FILES = [
    "data/racecards_2026_07_14_standard.json",
    "data/velo_prime_verdicts_2026_07_14.json",
    "data/racing_post_account_raw/2026-07-14/manifest.json",
    "data/racing_post_url_lists/rp_results_2026-07-14.txt",
    "data/results/rp_results_2026_07_14.json",
    "data/sigma_results/sigma_results_2026_07_14.json",
    "data/model_comparison_ledger.csv",
    "data/mission_control/2026-07-14_mission_control.json",
    "data/router_shadow_audit_runs/router_shadow_audit_20260714_231325.csv",
    "data/router_shadow_audit_runs/router_shadow_audit_20260714_231325.md",
    "data/router_shadow_audit_ledger.csv",
    "data/router_shadow_audit_latest.csv",
    "data/nightly_eod_learning_status_2026_07_14.json",
    "data/nightly_eod_learning_council_audit_2026_07_14.json",
    "data/velo_innovation_protocol_1k_deduped.csv",
    "data/council_packets/council_packet_2026-07-14.json",
    "data/council_reports/velo_council_report_2026-07-14.md",
    "data/council_runs/council_run_2026-07-14.json",
    "data/new_build/current_cards/current_card_intent_features_2026_07_14.jsonl",
    "data/new_build/current_cards/current_card_passport_feed_2026_07_14.jsonl",
    "data/new_build/reports/current_card_intent_features_2026_07_14_audit.json",
    "data/new_build/reports/current_card_passport_feed_2026_07_14.json",
    "data/new_build/reports/current_card_passport_feed_2026_07_14.md",
    "data/new_build/reports/two_lane_readiness_2026_07_14.json",
    "data/new_build/reports/two_lane_readiness_2026_07_14.md",
]

RAW_HTML_DIRS = [
    "data/racing_post_account_raw/2026-07-14",
    "data/racing_post_account_raw/rp-results-2026-07-14",
]


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    os.makedirs(STAGING, exist_ok=True)
    copy_records = []
    mismatches = []

    for rel in COPY_FILES:
        src_path = os.path.join(SRC, rel)
        dst_path = os.path.join(STAGING, rel)
        rec = {
            "original_absolute_path": src_path,
            "copied_relative_path": os.path.relpath(dst_path, DST_ROOT),
        }
        if not os.path.isfile(src_path):
            rec["status"] = "MISSING_IN_SOURCE"
            copy_records.append(rec)
            continue
        orig_hash = sha256_of(src_path)
        orig_size = os.path.getsize(src_path)
        orig_mtime = datetime.fromtimestamp(os.path.getmtime(src_path), tz=timezone.utc).isoformat()
        os.makedirs(os.path.dirname(dst_path), exist_ok=True)
        shutil.copy2(src_path, dst_path)
        copy_hash = sha256_of(dst_path)
        ok = copy_hash == orig_hash
        rec.update({
            "status": "COPIED_VERIFIED" if ok else "HASH_MISMATCH",
            "original_sha256": orig_hash,
            "copied_sha256": copy_hash,
            "original_size_bytes": orig_size,
            "original_mtime_utc": orig_mtime,
        })
        copy_records.append(rec)
        if not ok:
            mismatches.append(rel)

    # Raw HTML inventory (hash in place, do NOT copy bytes)
    raw_html_inventory = []
    for d in RAW_HTML_DIRS:
        full_dir = os.path.join(SRC, d)
        if not os.path.isdir(full_dir):
            raw_html_inventory.append({"dir": d, "status": "MISSING_DIR"})
            continue
        for fn in sorted(os.listdir(full_dir)):
            fp = os.path.join(full_dir, fn)
            if not os.path.isfile(fp):
                continue
            entry = {
                "dir": d,
                "filename": fn,
                "size_bytes": os.path.getsize(fp),
                "mtime_utc": datetime.fromtimestamp(os.path.getmtime(fp), tz=timezone.utc).isoformat(),
                "sha256": sha256_of(fp) if fn.endswith((".html", ".json")) else None,
            }
            if fn.endswith(".html"):
                try:
                    with open(fp, "r", errors="ignore") as fh:
                        content = fh.read()
                    idx = content.find('rel="canonical"')
                    canonical = None
                    if idx != -1:
                        href_idx = content.find('href="', idx)
                        if href_idx != -1:
                            end_idx = content.find('"', href_idx + 6)
                            canonical = content[href_idx + 6:end_idx]
                    entry["canonical_url"] = canonical
                except Exception as e:
                    entry["canonical_url_error"] = str(e)
            raw_html_inventory.append(entry)

    out = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_root": SRC,
        "dest_root": DST_ROOT,
        "note": "Raw HTML bytes NOT copied per mission Preservation instructions -- hashed in place only.",
        "copy_records": copy_records,
        "hash_mismatches": mismatches,
        "raw_html_inventory_count": len(raw_html_inventory),
        "raw_html_inventory": raw_html_inventory,
    }
    out_path = os.path.join(STAGING, "_evidence_import_manifest.json")
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)

    print(f"Copied {sum(1 for r in copy_records if r['status']=='COPIED_VERIFIED')}/{len(COPY_FILES)} files, verified.")
    print(f"Missing in source: {[r['original_absolute_path'] for r in copy_records if r['status']=='MISSING_IN_SOURCE']}")
    print(f"Hash mismatches: {mismatches}")
    print(f"Raw HTML inventory entries: {len(raw_html_inventory)}")
    print(f"Manifest written: {out_path}")
    if mismatches:
        sys.exit(1)


if __name__ == "__main__":
    main()
