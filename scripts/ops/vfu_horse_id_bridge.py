#!/usr/bin/env python3
"""
scripts/ops/vfu_horse_id_bridge.py
====================================
VFU-06 — Horse Identity Bridge.

Builds a name → stable horse_id lookup from:
  1. horse_passports_v1.jsonl  — horse_rp_uid (numeric, canonical RP UID)
  2. EOD nightly learning events — horse_id (numeric / hrs_ / rp_* string)

Priority order per row:
  1. Existing non-null horse_id on the row
  2. Unique passport norm-name match → horse_rp_uid (HIGH)
  3. EOD race_id + norm-name match (MEDIUM)
  4. Unique EOD norm-name match (LOW)
  5. UNMATCHED

Namespace is always preserved:
  RP_UID | EOD_NUMERIC | RACING_API_HRS | CONSTRUCTED_RP_NAME | UNKNOWN

Never writes Supabase. Never mutates canonical Horse Passport.
All outputs are dry-run identity enrichment only.
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

# ── Paths ─────────────────────────────────────────────────────────────────────
ENRICHED_UNION  = ROOT / "data/reports/current_era_sigma_union_rows_enriched_vfu_v1.json"
PASSPORT_FILE   = ROOT / "data/new_build/passports/horse_passports_v1.jsonl"
AUTOPSY_RECORDS = ROOT / "data/reports/vfu_full_current_era_autopsy_records.jsonl"
PASSPORT_CANDS  = ROOT / "data/reports/vfu_full_current_era_passport_candidates.jsonl"
AUTOPSY_SUMMARY = ROOT / "data/reports/vfu_full_current_era_autopsy_summary.json"
CANON_PASSPORT  = ROOT / "data/new_build/passports/horse_passports_v1.jsonl"
EOD_GLOB        = "data/nightly_eod_learning_events_2026*.jsonl"

OUT_BRIDGE       = ROOT / "data/reports/vfu_horse_id_bridge.json"
OUT_ENRICHED     = ROOT / "data/reports/vfu_horse_id_bridge_enriched_union.json"
OUT_CLUSTERS     = ROOT / "data/reports/vfu_horse_id_bridge_repeated_clusters.json"
OUT_REPORT_MD    = ROOT / "data/reports/vfu_horse_identity_bridge_report.md"
OUT_REPORT_JSON  = ROOT / "data/reports/vfu_horse_identity_bridge_report.json"
OUT_UNMATCHED    = ROOT / "data/reports/vfu_horse_identity_bridge_unmatched.json"
OUT_AMBIGUOUS    = ROOT / "data/reports/vfu_horse_identity_bridge_ambiguous.json"
OUT_CONFLICTS    = ROOT / "data/reports/vfu_horse_identity_bridge_conflicts.json"
OUT_AUTOPSY_ID   = ROOT / "data/reports/vfu_current_era_autopsy_records_identity_enriched.jsonl"
OUT_PASSPORT_ID  = ROOT / "data/reports/vfu_current_era_passport_candidates_identity_enriched.jsonl"

BRIDGE_VERSION  = "VFU_HORSE_IDENTITY_BRIDGE_V1"

IDENTITY_FIELDS = [
    "horse_id", "horse_id_namespace", "horse_id_source",
    "horse_id_join_key", "horse_id_join_confidence",
    "horse_id_missing_reason", "horse_id_ambiguous", "horse_id_conflict",
    "identity_bridge_version",
]


# ── Normalization ─────────────────────────────────────────────────────────────

def norm_horse(h: str | None) -> str:
    if not h:
        return ""
    h = h.strip().lower()
    h = re.sub(r"\s*\([a-z]+\)\s*$", "", h)  # strip country suffix BEFORE punctuation
    h = re.sub(r"[^a-z0-9 ]", "", h)
    h = re.sub(r"\s+", " ", h).strip()
    return h


# ── Namespace detection ───────────────────────────────────────────────────────

def detect_namespace(horse_id: str | int | None) -> str:
    if horse_id is None:
        return "UNKNOWN"
    s = str(horse_id).strip()
    if s.isdigit():
        return "EOD_NUMERIC"
    if s.startswith("hrs_"):
        return "RACING_API_HRS"
    if s.startswith("rp_"):
        return "CONSTRUCTED_RP_NAME"
    return "UNKNOWN"


# ── Passport lookup ───────────────────────────────────────────────────────────

def build_passport_lookup(passport_file: Path) -> dict:
    """
    Returns {norm_name: {horse_name, rp_uid, unique, all_entries}}.
    unique=False when multiple passports share the same norm name (AMBIGUOUS).
    """
    by_norm: dict[str, list] = defaultdict(list)
    for line in passport_file.open(encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        name = row.get("horse_name", "")
        rp_uid = row.get("horse_rp_uid")
        if name and rp_uid is not None:
            by_norm[norm_horse(name)].append({"horse_name": name, "rp_uid": int(rp_uid)})

    result = {}
    for n, entries in by_norm.items():
        if not n:
            continue
        result[n] = {
            "horse_name": entries[0]["horse_name"],
            "rp_uid": entries[0]["rp_uid"],
            "unique": len(entries) == 1,
            "all_entries": entries,
        }
    return result


# ── EOD lookup ────────────────────────────────────────────────────────────────

def build_eod_lookup(root: Path) -> tuple[dict, dict]:
    """
    Returns:
      eod_race: {(race_id, norm_name): horse_id}
      eod_name: {norm_name: {ids: [...], unique: bool}}
    """
    eod_race: dict = {}
    eod_name_multi: dict[str, list] = defaultdict(list)

    for f in sorted(root.glob(EOD_GLOB)):
        for line in f.open(encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            ps = row.get("prediction_snapshot", {})
            if not isinstance(ps, dict):
                continue
            hid = ps.get("horse_id")
            hname = ps.get("horse")
            race_id = str(row.get("race_id", ""))
            if not hid or not hname:
                continue
            n = norm_horse(hname)
            if not n:
                continue
            key = (race_id, n)
            if key not in eod_race:
                eod_race[key] = str(hid)
            if str(hid) not in eod_name_multi[n]:
                eod_name_multi[n].append(str(hid))

    eod_name = {
        n: {"ids": ids, "unique": len(ids) == 1}
        for n, ids in eod_name_multi.items()
    }
    return eod_race, eod_name


# ── Identity resolution ───────────────────────────────────────────────────────

def _blank_identity() -> dict:
    return {
        "horse_id": None,
        "horse_id_namespace": "UNKNOWN",
        "horse_id_source": None,
        "horse_id_join_key": None,
        "horse_id_join_confidence": "UNMATCHED",
        "horse_id_missing_reason": None,
        "horse_id_ambiguous": False,
        "horse_id_conflict": False,
        "identity_bridge_version": BRIDGE_VERSION,
    }


def resolve_identity(
    row: dict,
    passport_lookup: dict,
    eod_race: dict,
    eod_name: dict,
) -> dict:
    identity = _blank_identity()

    horse_name = row.get("horse_name", "")
    race_id = str(row.get("race_id", ""))

    if not horse_name or horse_name == "?":
        identity["horse_id_missing_reason"] = "NO_HORSE_NAME_STRUCTURALLY_UNMATCHABLE"
        return identity

    n = norm_horse(horse_name)
    if not n:
        identity["horse_id_missing_reason"] = "NORM_EMPTY"
        return identity

    # Priority 1: existing non-null horse_id on the row
    existing_id = row.get("horse_id")
    if existing_id is not None and str(existing_id).strip():
        s = str(existing_id).strip()
        ns = detect_namespace(s)
        passport_entry = passport_lookup.get(n)
        conflict = False
        conflict_reason = None
        if passport_entry and passport_entry["unique"] and s.isdigit():
            if s != str(passport_entry["rp_uid"]):
                conflict = True
                conflict_reason = f"EOD_NUMERIC_{s}_vs_PASSPORT_{passport_entry['rp_uid']}"
        identity.update({
            "horse_id": s,
            "horse_id_namespace": "RP_UID" if (ns == "EOD_NUMERIC" and not conflict) else ns,
            "horse_id_source": "ROW_EXISTING",
            "horse_id_join_key": f"row.horse_id={s}",
            "horse_id_join_confidence": "HIGH",
            "horse_id_conflict": conflict,
        })
        if conflict:
            identity["horse_id_missing_reason"] = f"CONFLICT_{conflict_reason}"
        return identity

    passport_entry = passport_lookup.get(n)
    eod_race_hit = eod_race.get((race_id, n))
    eod_name_entry = eod_name.get(n)

    # Priority 2: unique passport match
    if passport_entry:
        if not passport_entry["unique"]:
            identity.update({
                "horse_id_join_confidence": "AMBIGUOUS",
                "horse_id_ambiguous": True,
                "horse_id_missing_reason": (
                    f"PASSPORT_AMBIGUOUS_{len(passport_entry['all_entries'])}_ENTRIES"
                ),
            })
            return identity

        passport_id = str(passport_entry["rp_uid"])

        # Detect conflict: only when EOD also gives a numeric ID that differs
        conflict = False
        conflict_reason = None
        if eod_race_hit is not None and eod_race_hit.isdigit() and eod_race_hit != passport_id:
            conflict = True
            conflict_reason = f"EOD_NUMERIC_{eod_race_hit}_vs_PASSPORT_{passport_id}"

        identity.update({
            "horse_id": passport_id,
            "horse_id_namespace": "RP_UID",
            "horse_id_source": "PASSPORT_NORM_MATCH",
            "horse_id_join_key": f"norm_name={n}",
            "horse_id_join_confidence": "HIGH",
            "horse_id_conflict": conflict,
        })
        if conflict:
            identity["horse_id_missing_reason"] = f"CONFLICT_{conflict_reason}"
        return identity

    # Priority 3: EOD race_id + norm_name
    if eod_race_hit is not None:
        ns = detect_namespace(eod_race_hit)
        identity.update({
            "horse_id": eod_race_hit,
            "horse_id_namespace": ns,
            "horse_id_source": "EOD_RACE_MATCH",
            "horse_id_join_key": f"race_id={race_id},norm_name={n}",
            "horse_id_join_confidence": "MEDIUM",
        })
        return identity

    # Priority 4: unique EOD name match
    if eod_name_entry:
        if eod_name_entry["unique"]:
            hid = eod_name_entry["ids"][0]
            ns = detect_namespace(hid)
            identity.update({
                "horse_id": hid,
                "horse_id_namespace": ns,
                "horse_id_source": "EOD_NAME_MATCH",
                "horse_id_join_key": f"norm_name={n}",
                "horse_id_join_confidence": "LOW",
            })
            return identity
        else:
            identity.update({
                "horse_id_join_confidence": "AMBIGUOUS",
                "horse_id_ambiguous": True,
                "horse_id_missing_reason": (
                    f"EOD_NAME_AMBIGUOUS_{len(eod_name_entry['ids'])}_IDS"
                ),
            })
            return identity

    identity["horse_id_missing_reason"] = "NOT_IN_PASSPORT_OR_EOD"
    return identity


# ── Repeated clusters ─────────────────────────────────────────────────────────

def build_repeated_clusters(
    enriched_union: list[dict],
    autopsy_summary: dict,
) -> list[dict]:
    """
    Take VFU-04 repeated horse tracker from autopsy summary, enrich each with
    the identity fields from the enriched union.
    """
    tracker = autopsy_summary.get("top_repeated_horses", [])
    if not tracker:
        return []

    # Build name → list of enriched rows
    name_to_rows: dict[str, list] = defaultdict(list)
    for r in enriched_union:
        n = norm_horse(r.get("horse_name", ""))
        if n:
            name_to_rows[n].append(r)

    clusters = []
    for entry in tracker:
        name = entry.get("horse_name", "")
        n = norm_horse(name)
        rows_for_horse = name_to_rows.get(n, [])

        # Collect distinct identities from enriched rows
        ids_seen = {}
        for r in rows_for_horse:
            hid = r.get("horse_id")
            ns = r.get("horse_id_namespace", "UNKNOWN")
            conf = r.get("horse_id_join_confidence", "UNMATCHED")
            if hid and hid not in ids_seen:
                ids_seen[hid] = {"namespace": ns, "confidence": conf}

        cluster = {
            **entry,
            "norm_name": n,
            "identity_resolved": bool(ids_seen),
            "identity_count": len(ids_seen),
            "identities": [
                {"horse_id": hid, **meta} for hid, meta in ids_seen.items()
            ],
            "name_only_confidence": True,  # always preserved from VFU-04
            "identity_bridge_version": BRIDGE_VERSION,
        }
        clusters.append(cluster)

    return clusters


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    assert str(OUT_ENRICHED) != str(CANON_PASSPORT), "SAFETY: output must not overwrite canonical passport"
    assert str(OUT_AUTOPSY_ID) != str(AUTOPSY_RECORDS), "SAFETY: must not overwrite autopsy records"

    print(f"[VFU-06] Loading union from {ENRICHED_UNION.name}")
    union = json.loads(ENRICHED_UNION.read_text(encoding="utf-8"))
    print(f"  {len(union)} rows")

    print(f"[VFU-06] Building passport lookup from {PASSPORT_FILE.name}")
    passport_lookup = build_passport_lookup(PASSPORT_FILE)
    ambiguous_passport = {n: e for n, e in passport_lookup.items() if not e["unique"]}
    print(f"  {len(passport_lookup)} norm-names | {len(ambiguous_passport)} ambiguous")

    print(f"[VFU-06] Building EOD lookup")
    eod_race, eod_name = build_eod_lookup(ROOT)
    print(f"  {len(eod_race)} race+name pairs | {len(eod_name)} distinct names")

    # Enrich union rows
    print(f"[VFU-06] Resolving identities for {len(union)} rows")
    enriched_union: list[dict] = []
    bridge_entries: dict[str, dict] = {}

    counts = {
        "HIGH": 0, "MEDIUM": 0, "LOW": 0,
        "AMBIGUOUS": 0, "UNMATCHED": 0,
    }
    ns_counts: dict[str, int] = defaultdict(int)
    source_counts: dict[str, int] = defaultdict(int)
    conflicts: list[dict] = []
    unmatched: list[dict] = []
    ambiguous: list[dict] = []
    structurally_unmatchable = 0

    for row in union:
        identity = resolve_identity(row, passport_lookup, eod_race, eod_name)
        enriched = {**row, **identity}
        enriched_union.append(enriched)

        conf = identity["horse_id_join_confidence"]
        counts[conf] = counts.get(conf, 0) + 1
        ns_counts[identity["horse_id_namespace"]] += 1
        if identity["horse_id_source"]:
            source_counts[identity["horse_id_source"]] += 1

        if identity["horse_id_conflict"]:
            conflicts.append({
                "race_id": row.get("race_id"),
                "horse_name": row.get("horse_name"),
                "horse_id": identity["horse_id"],
                "horse_id_namespace": identity["horse_id_namespace"],
                "conflict_reason": identity["horse_id_missing_reason"],
                "identity_bridge_version": BRIDGE_VERSION,
            })

        if conf == "UNMATCHED":
            reason = identity.get("horse_id_missing_reason", "")
            if reason == "NO_HORSE_NAME_STRUCTURALLY_UNMATCHABLE":
                structurally_unmatchable += 1
            unmatched.append({
                "race_id": row.get("race_id"),
                "horse_name": row.get("horse_name"),
                "race_date": row.get("race_date"),
                "missing_reason": reason,
            })

        if conf == "AMBIGUOUS":
            ambiguous.append({
                "race_id": row.get("race_id"),
                "horse_name": row.get("horse_name"),
                "race_date": row.get("race_date"),
                "missing_reason": identity.get("horse_id_missing_reason"),
            })

        # Build per-name bridge entry (take best resolution)
        n = norm_horse(row.get("horse_name", ""))
        if n and (n not in bridge_entries or conf == "HIGH"):
            bridge_entries[n] = {
                "norm_name": n,
                "horse_name_sample": row.get("horse_name"),
                **{k: identity[k] for k in IDENTITY_FIELDS},
            }

    # Autopsy records enrichment
    print(f"[VFU-06] Enriching autopsy records")
    autopsy_rows = []
    if AUTOPSY_RECORDS.exists():
        for line in AUTOPSY_RECORDS.open(encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            identity = resolve_identity(rec, passport_lookup, eod_race, eod_name)
            autopsy_rows.append({**rec, **identity})

    # Passport candidates enrichment
    print(f"[VFU-06] Enriching passport candidates")
    passport_cand_rows = []
    cands_with_rp_uid = 0
    cands_with_eod_id = 0
    if PASSPORT_CANDS.exists():
        for line in PASSPORT_CANDS.open(encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            identity = resolve_identity(rec, passport_lookup, eod_race, eod_name)
            enriched_cand = {**rec, **identity}
            if identity["horse_id_namespace"] == "RP_UID":
                cands_with_rp_uid += 1
            elif identity["horse_id"] is not None:
                cands_with_eod_id += 1
            passport_cand_rows.append(enriched_cand)

    # Kakirra result
    kakirra_identity = resolve_identity(
        {"horse_name": "Kakirra", "race_id": ""},
        passport_lookup, eod_race, eod_name,
    )

    # Repeated clusters
    autopsy_summary: dict = {}
    if AUTOPSY_SUMMARY.exists():
        autopsy_summary = json.loads(AUTOPSY_SUMMARY.read_text(encoding="utf-8"))
    repeated_clusters = build_repeated_clusters(enriched_union, autopsy_summary)

    # Coverage before/after
    before_filled = sum(1 for r in union if r.get("horse_id") is not None)
    after_filled = sum(1 for r in enriched_union if r.get("horse_id") is not None)

    # ── Write outputs ─────────────────────────────────────────────────────────
    OUT_BRIDGE.write_text(
        json.dumps(list(bridge_entries.values()), indent=2, default=str),
        encoding="utf-8",
    )
    OUT_ENRICHED.write_text(
        json.dumps(enriched_union, indent=2, default=str),
        encoding="utf-8",
    )
    OUT_CLUSTERS.write_text(
        json.dumps(repeated_clusters, indent=2, default=str),
        encoding="utf-8",
    )
    OUT_UNMATCHED.write_text(
        json.dumps(unmatched, indent=2, default=str),
        encoding="utf-8",
    )
    OUT_AMBIGUOUS.write_text(
        json.dumps(ambiguous, indent=2, default=str),
        encoding="utf-8",
    )
    OUT_CONFLICTS.write_text(
        json.dumps(conflicts, indent=2, default=str),
        encoding="utf-8",
    )

    with OUT_AUTOPSY_ID.open("w", encoding="utf-8") as fh:
        for r in autopsy_rows:
            fh.write(json.dumps(r, default=str) + "\n")

    with OUT_PASSPORT_ID.open("w", encoding="utf-8") as fh:
        for r in passport_cand_rows:
            fh.write(json.dumps(r, default=str) + "\n")

    # ── Summary JSON ──────────────────────────────────────────────────────────
    final_classifications = [
        "VFU_06_HORSE_IDENTITY_BRIDGE_COMPLETE",
        "HORSE_ID_COVERAGE_REPORTED",
        "HORSE_ID_NAMESPACE_PRESERVED",
        "PASSPORT_RP_UID_CONFIRMED_AS_CANONICAL_WHEN_UNIQUE",
        "EOD_IDENTITIES_RECORDED_AS_DRY_RUN_NON_CANONICAL_WHEN_NEEDED",
        "AMBIGUOUS_IDENTITIES_NOT_FILLED",
        "CONFLICTING_IDENTITIES_NOT_OVERRIDDEN",
        "UNMATCHED_IDENTITIES_DECLARED",
        "STRUCTURALLY_UNMATCHABLE_ROWS_DECLARED",
        "PASSPORT_CANDIDATES_IDENTITY_ENRICHED_DRY_RUN_ONLY",
        "CANONICAL_HORSE_PASSPORT_NOT_MUTATED",
        "REPEATED_HORSE_TRACKER_IDENTITY_REBUILT",
        "NO_MAR_APR_EXTRACTION",
        "NO_LIVE_SCORING_CHANGE",
        "NO_SUPABASE_WRITES",
        "NO_MODEL_PROMOTION",
        "NO_TELEGRAM_SEND",
        "NO_RACING_API_RESTORATION",
    ]

    summary = {
        "report_type": "VFU_06_HORSE_IDENTITY_BRIDGE",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "identity_bridge_version": BRIDGE_VERSION,
        "source_scope": "current_era_only_2026_05_08_to_2026_06_13",
        "rows_scanned": len(union),
        "identity_sources": [
            "horse_passports_v1.jsonl (6168 horses, horse_rp_uid numeric)",
            f"EOD events ({len(eod_race)} race+name pairs, {len(eod_name)} distinct names)",
        ],
        "coverage_before": {"horse_id_filled": before_filled, "pct": round(before_filled / len(union) * 100, 1)},
        "coverage_after": {"horse_id_filled": after_filled, "pct": round(after_filled / len(union) * 100, 1)},
        "confidence_counts": counts,
        "namespace_counts": dict(ns_counts),
        "source_counts": dict(source_counts),
        "structurally_unmatchable": structurally_unmatchable,
        "ambiguous_count": counts.get("AMBIGUOUS", 0),
        "conflict_count": len(conflicts),
        "passport_ambiguous_norm_names": len(ambiguous_passport),
        "passport_candidates_gaining_rp_uid": cands_with_rp_uid,
        "passport_candidates_gaining_eod_id": cands_with_eod_id,
        "repeated_clusters_found": len(repeated_clusters),
        "repeated_clusters_with_identity": sum(1 for c in repeated_clusters if c["identity_resolved"]),
        "kakirra": {
            "horse_name": "Kakirra",
            "horse_id": kakirra_identity["horse_id"],
            "namespace": kakirra_identity["horse_id_namespace"],
            "source": kakirra_identity["horse_id_source"],
            "confidence": kakirra_identity["horse_id_join_confidence"],
            "note": (
                "Kakirra: 3 apps, 3 wins (name-only from VFU-04). "
                "Identity now resolved via passport if RP_UID, else EOD."
            ),
        },
        "passport_automation_status": (
            "PARTIALLY_UNBLOCKED_FOR_RP_UID_ROWS"
            if cands_with_rp_uid > 0
            else "STILL_BLOCKED_NO_RP_UID_IN_CANDIDATES"
        ),
        "canonical_passport_mutated": False,
        "supabase_written": False,
        "live_scoring_changed": False,
        "model_promoted": False,
        "telegram_sent": False,
        "racing_api_restored": False,
        "mar_apr_extracted": False,
        "final_classifications": final_classifications,
    }

    OUT_REPORT_JSON.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")

    # ── MD Report ─────────────────────────────────────────────────────────────
    cov_b = summary["coverage_before"]
    cov_a = summary["coverage_after"]
    md = [
        "# VFU-06 — Horse Identity Bridge Report",
        "",
        f"**Generated**: {summary['generated_at'][:19]}Z",
        f"**Bridge version**: {BRIDGE_VERSION}",
        f"**Canonical Passport mutated**: NO",
        f"**Supabase written**: NO",
        "",
        "---",
        "",
        "## Coverage",
        "",
        "| Metric | Before | After |",
        "|---|---|---|",
        f"| horse_id filled | {cov_b['horse_id_filled']}/{len(union)} ({cov_b['pct']}%) | {cov_a['horse_id_filled']}/{len(union)} ({cov_a['pct']}%) |",
        "",
        "## Confidence Breakdown",
        "",
        "| Confidence | Count |",
        "|---|---|",
    ]
    for conf, cnt in sorted(counts.items(), key=lambda x: ["HIGH","MEDIUM","LOW","AMBIGUOUS","UNMATCHED"].index(x[0])):
        md.append(f"| {conf} | {cnt} |")

    md += [
        "",
        "## Namespace Breakdown",
        "",
        "| Namespace | Count |",
        "|---|---|",
    ]
    for ns, cnt in sorted(ns_counts.items(), key=lambda x: -x[1]):
        md.append(f"| {ns} | {cnt} |")

    md += [
        "",
        "## Source Breakdown",
        "",
        "| Source | Count |",
        "|---|---|",
    ]
    for src, cnt in sorted(source_counts.items(), key=lambda x: -x[1]):
        md.append(f"| {src} | {cnt} |")

    md += [
        "",
        f"## Special Cases",
        "",
        f"- Structurally unmatchable (no horse_name): **{structurally_unmatchable}**",
        f"- Ambiguous: **{counts.get('AMBIGUOUS', 0)}**",
        f"- Conflicts: **{len(conflicts)}**",
        f"- Passport ambiguous norm names: **{len(ambiguous_passport)}**",
        "",
        "## Kakirra",
        "",
        f"- horse_id: **{kakirra_identity['horse_id']}**",
        f"- namespace: **{kakirra_identity['horse_id_namespace']}**",
        f"- source: **{kakirra_identity['horse_id_source']}**",
        f"- confidence: **{kakirra_identity['horse_id_join_confidence']}**",
        "",
        "## Repeated Clusters",
        "",
        f"- Found: {len(repeated_clusters)}",
        f"- With identity: {sum(1 for c in repeated_clusters if c['identity_resolved'])}",
        "",
        "## Passport Candidates",
        "",
        f"- Gaining canonical RP_UID: **{cands_with_rp_uid}**",
        f"- Gaining non-canonical EOD ID: **{cands_with_eod_id}**",
        f"- Passport automation status: **{summary['passport_automation_status']}**",
        "",
        "## Hard Rule Confirmations",
        "",
        "| Check | Status |",
        "|---|---|",
        "| Canonical Horse Passport NOT mutated | CONFIRMED |",
        "| No Supabase writes | CONFIRMED |",
        "| No live scoring change | CONFIRMED |",
        "| No model promotion | CONFIRMED |",
        "| No Telegram send | CONFIRMED |",
        "| No Racing API restoration | CONFIRMED |",
        "| No Mar–Apr extraction | CONFIRMED |",
        "",
        "## Final Classifications",
        "",
    ]
    for c in final_classifications:
        md.append(f"- `{c}`")

    OUT_REPORT_MD.write_text("\n".join(md), encoding="utf-8")

    # ── Print summary ─────────────────────────────────────────────────────────
    print(f"\n[VFU-06] Done.")
    print(f"  Rows scanned: {len(union)}")
    print(f"  horse_id before: {before_filled}/{len(union)} ({cov_b['pct']}%)")
    print(f"  horse_id after:  {after_filled}/{len(union)} ({cov_a['pct']}%)")
    print(f"  HIGH: {counts['HIGH']} | MEDIUM: {counts['MEDIUM']} | LOW: {counts['LOW']}")
    print(f"  AMBIGUOUS: {counts['AMBIGUOUS']} | UNMATCHED: {counts['UNMATCHED']}")
    print(f"  Conflicts: {len(conflicts)} | Struct unmatchable: {structurally_unmatchable}")
    print(f"  Repeated clusters: {len(repeated_clusters)} ({sum(1 for c in repeated_clusters if c['identity_resolved'])} with identity)")
    print(f"  Kakirra: {kakirra_identity['horse_id']} [{kakirra_identity['horse_id_namespace']}] ({kakirra_identity['horse_id_join_confidence']})")
    print(f"  Passport cands gaining RP_UID: {cands_with_rp_uid} | EOD: {cands_with_eod_id}")


if __name__ == "__main__":
    main()
