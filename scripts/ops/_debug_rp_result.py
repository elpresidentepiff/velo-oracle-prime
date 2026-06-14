import re
from pathlib import Path

html_path = Path("data/racing_post_account_raw/rp-results-2026-06-04-final/002_results_22_hamilton_2026_06_04_919998_70c9f4199b37.html")
html = html_path.read_text(encoding="utf-8", errors="replace")
print("HTML length:", len(html))
print("Has __NEXT_DATA__:", "__NEXT_DATA__" in html)
print("Has NEXT_DATA (no underscore):", "NEXT_DATA" in html)
# Check what script tags exist
scripts = re.findall(r'<script[^>]*id="([^"]*)"', html)
print("Script ids:", scripts[:10])
# Show first 2000 chars
print("\nFirst 1000 chars:")
print(html[:1000])
