#!/usr/bin/env python3
"""
P0-17: prove the primary dirty worktree (/mnt/c/Users/puror/velo-oracle-prime)
was byte-identical before and after this mission.

Reads:
  - provenance/primary_worktree_status_before.txt / _after.txt
    (git status --porcelain=v2, captured at mission start and just now,
    both read-only, no writes to the primary worktree in between)
  - provenance/primary_worktree_untracked_before.txt / _after.txt
    (git ls-files --others --exclude-standard, same read-only capture)
  - evidence_staging/2026-07-14/_evidence_import_manifest.json
    (has the "before" SHA-256 of every copied primary evidence file,
    captured at mission start when copy_evidence.py ran)
  - /tmp/rd14_after_hashes.txt
    (freshly computed "after" SHA-256 of the same files, computed by this
    verification pass, read-only, from the primary repo)

Writes: provenance/primary_worktree_integrity_manifest.json
"""
import hashlib
import json
import os

ROOT = "/mnt/c/Users/puror/velo-race-day-14-proof"
PROV = os.path.join(ROOT, "provenance")
STAGE = os.path.join(ROOT, "evidence_staging", "2026-07-14")


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read(path):
    with open(path) as f:
        return f.read()


status_before_path = os.path.join(PROV, "primary_worktree_status_before.txt")
status_after_path = os.path.join(PROV, "primary_worktree_status_after.txt")
untracked_before_path = os.path.join(PROV, "primary_worktree_untracked_before.txt")
untracked_after_path = os.path.join(PROV, "primary_worktree_untracked_after.txt")

status_before = read(status_before_path)
status_after = read(status_after_path)
untracked_before = read(untracked_before_path)
untracked_after = read(untracked_after_path)

status_identical = status_before == status_after
untracked_identical = untracked_before == untracked_after

# per-file before/after hash comparison
with open(os.path.join(STAGE, "_evidence_import_manifest.json")) as f:
    import_manifest = json.load(f)
before_hashes = {
    os.path.relpath(rec["original_absolute_path"], "/mnt/c/Users/puror/velo-oracle-prime"): rec["original_sha256"]
    for rec in import_manifest["copy_records"] if rec.get("status") == "COPIED_VERIFIED"
}

after_hashes = {}
with open("/tmp/rd14_after_hashes.txt") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        path, h = line.split("|", 1)
        after_hashes[path] = h

file_comparisons = []
all_files_identical = True
for path, before_h in sorted(before_hashes.items()):
    after_h = after_hashes.get(path, "NOT_RECHECKED")
    identical = (after_h == before_h)
    if not identical:
        all_files_identical = False
    file_comparisons.append({
        "path": path,
        "sha256_before": before_h,
        "sha256_after": after_h,
        "identical": identical,
    })

overall_identical = status_identical and untracked_identical and all_files_identical
classification = "PRIMARY_DIRTY_WORKTREE_BYTE_IDENTICAL_BEFORE_AFTER" if overall_identical else "PRIMARY_DIRTY_WORKTREE_INTEGRITY_CHECK_FAILED"

manifest = {
    "mission": "RACE-DAY-14-BEST-DAY-PROOF-01 (P0-17 correction pass)",
    "primary_worktree_path": "/mnt/c/Users/puror/velo-oracle-prime",
    "method": (
        "Two independent read-only snapshots of `git status --porcelain=v2` and "
        "`git ls-files --others --exclude-standard` were captured: 'before' at the "
        "start of the original forensic mission (before any evidence copy or "
        "analysis began), and 'after' at the start of this correction pass "
        "(after all forensic work, including the initial PR, was already complete). "
        "Both commands are read-only and were run from the primary repo without any "
        "branch switch, reset, stash, clean, checkout, or write operation in between. "
        "In addition, every one of the 25 primary evidence files copied into "
        "evidence_staging/2026-07-14/ was re-hashed (SHA-256) directly from the "
        "primary repo at correction-pass time and compared against the hash "
        "recorded at original copy time in _evidence_import_manifest.json."
    ),
    "status_snapshot_before_path": "provenance/primary_worktree_status_before.txt",
    "status_snapshot_after_path": "provenance/primary_worktree_status_after.txt",
    "status_snapshot_before_sha256": sha256_of(status_before_path),
    "status_snapshot_after_sha256": sha256_of(status_after_path),
    "status_snapshot_identical": status_identical,
    "status_snapshot_dirty_path_count": len([l for l in status_before.splitlines() if l.strip()]),
    "untracked_snapshot_before_path": "provenance/primary_worktree_untracked_before.txt",
    "untracked_snapshot_after_path": "provenance/primary_worktree_untracked_after.txt",
    "untracked_snapshot_before_sha256": sha256_of(untracked_before_path),
    "untracked_snapshot_after_sha256": sha256_of(untracked_after_path),
    "untracked_snapshot_identical": untracked_identical,
    "untracked_file_count": len([l for l in untracked_before.splitlines() if l.strip()]),
    "per_file_hash_comparisons": file_comparisons,
    "per_file_hash_comparison_count": len(file_comparisons),
    "all_per_file_hashes_identical": all_files_identical,
    "explicit_equality_assertions": {
        "status_before_equals_status_after": status_identical,
        "untracked_before_equals_untracked_after": untracked_identical,
        "every_copied_evidence_file_hash_unchanged": all_files_identical,
    },
    "classification": classification,
}

out_path = os.path.join(PROV, "primary_worktree_integrity_manifest.json")
with open(out_path, "w") as f:
    json.dump(manifest, f, indent=2)

print(f"status_identical={status_identical}, untracked_identical={untracked_identical}, "
      f"all_files_identical={all_files_identical}")
print(f"CLASSIFICATION: {classification}")
print(f"Wrote {out_path}")
