import urllib.request, json, os, sys
sys.path.insert(0, r"C:\Users\puror\velo-oracle-prime")
from dotenv import load_dotenv
load_dotenv(r"C:\Users\puror\velo-oracle-prime\.env")

SB_URL = os.getenv("SUPABASE_URL", "")
SB_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY", "")
SB_HEADERS = {"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}", "Content-Type": "application/json"}

def sb_get(path):
    req = urllib.request.Request(SB_URL + "/rest/v1" + path, headers=SB_HEADERS)
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())

# Count rows per date
recent = sb_get("/velo_verdicts?select=race_id,generated_at&order=generated_at.desc&limit=200")
from collections import Counter
by_date = Counter(r.get('generated_at','')[:10] for r in recent)
print("Supabase velo_verdicts by date (last 200):")
for d, n in sorted(by_date.items(), reverse=True)[:10]:
    print(f"  {d}: {n} verdicts")
