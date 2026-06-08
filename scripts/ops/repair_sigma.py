import sys
import re
import json
from pathlib import Path

path = Path("scripts/ops/run_results_sigma.py")
code = path.read_text()

# 1. Add module-level helper
if "def _norm_course" not in code:
    helper = """
def _norm_course(value: str) -> str:
    \"\"\"Canonical normalized course name.\"\"\"
    import re as _re
    v = str(value or "").strip().lower()
    v = v.replace("(aw)", "").replace("aw", "").strip()
    return _re.sub(r"[^a-z]", "", v)
"""
    code = "import sys as _sys\n" + helper + code

# 2. Support --source cache in main
# We look for the STEP 2 print as an anchor
old_step2_header = '    print("\\nSTEP 2: Fetch results from Racing API")'
# The block continues for quite a few lines, let us use a regex to find the whole try/except or while loop
# Actually, let us just find the start and end of that section.

lines = code.splitlines()
start = -1
for i, l in enumerate(lines):
    if "STEP 2: Fetch results from Racing API" in l:
        start = i - 1 # include the comment
        break

if start != -1:
    end = -1
    for i in range(start, len(lines)):
        if "STEP 3:" in lines[i]:
            end = i
            break
    
    if end != -1:
        new_step2 = [
            "    # ── STEP 2: Load results ─────────────────────────────────",
            "    print(\"\\nSTEP 2: Load results\")",
            "    source = \"api\"",
            "    for i, arg in enumerate(_sys.argv):",
            "        if arg == \"--source\" and i+1 < len(_sys.argv): source = _sys.argv[i+1]",
            "    ",
            "    if source == \"cache\":",
            "        results_path = ROOT / \"data\" / \"results\" / f\"rp_results_{race_date.replace('-', '_')}.json\"",
            "        print(f\"  Loading from cache: {results_path}\")",
            "        if not results_path.exists():",
            "             print(f\"  FAILED: local results not found at {results_path}\")",
            "             _sys.exit(1)",
            "        import json as _json",
            "        results_list = _json.loads(results_path.read_text())",
            "        print(f\"  Results loaded: {len(results_list)}\")",
            "    else:",
            "        print(\"  Fetching from API...\")",
            "        results_list = []",
            "        skip = 0",
            "        page_size = 50",
            "        while True:",
            "            d = racing_get(f\"/results?start_date={race_date}&end_date={race_date}&limit={page_size}&skip={skip}\")",
            "            page = d if isinstance(d, list) else d.get(\"results\", [])",
            "            results_list.extend(page)",
            "            if len(page) < page_size: break",
            "            skip += page_size"
        ]
        lines[start:end] = new_step2
        code = "\n".join(lines) + "\n"

# 3. Add results_by_id indexing
code = code.replace('    print("\\nSTEP 3: Reconcile predictions vs actuals")', 
                   '    print("\\nSTEP 3: Reconcile predictions vs actuals")\n    results_by_id = {str(r.get("race_id")): r for r in results_list if r.get("race_id")}')

path.write_text(code)
print("Repaired run_results_sigma.py properly via script.")
