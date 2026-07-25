import json
from pathlib import Path
ROOT = Path(r"C:\Users\puror\velo-oracle-prime")
pp_path = ROOT / "data/new_build/passports/horse_passports_v1.jsonl"
passport_uids = set()
for line in pp_path.read_text(encoding="utf-8").splitlines():
    if line.strip():
        d = json.loads(line)
        uid = d.get("horse_rp_uid")
        if uid:
            passport_uids.add(str(uid))
print(f"Passport bank: {len(passport_uids)} horses")
for date_label, ri_file in [
    ("2026-06-24", "live-full-racepages-2026-06-24"),
    ("2026-06-25", "live-full-racepages-2026-06-25"),
    ("2026-06-26", "live-full-racepages-2026-06-26"),
]:
    ri_p = ROOT / "data/racing_post_account_parsed" / ri_file / "racecard_injection.json"
    ri2 = json.loads(ri_p.read_text(encoding="utf-8"))
    races2 = ri2 if isinstance(ri2, list) else ri2.get("races", ri2.get("racecards", []))
    total = 0; have = 0; missing_uids = []
    for race in races2:
        for r in (race.get("runners") or race.get("runners_data") or []):
            uid = str(r.get("horse_rp_uid") or r.get("rp_uid") or "")
            name = r.get("horse_name") or r.get("horse") or ""
            total += 1
            if uid and uid in passport_uids:
                have += 1
            else:
                missing_uids.append((uid, name))
    pct = 100 * have / total if total else 0
    print(f"{date_label}: {have}/{total} ({pct:.1f}%) - missing {len(missing_uids)}")
