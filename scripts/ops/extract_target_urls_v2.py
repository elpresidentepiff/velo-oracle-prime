import re
import json

html_file = "data/racing_post_account_raw/index_2026_05_27/2026-05-27/001_racecards_2026_05_27_af66fea80c60.html"
with open(html_file, "r") as f:
    text = f.read()

# Targets from user
targets = ["hamilton", "beverley", "newton-abbot", "kempton", "cartmel", "wexford"]
urls = set()

# The HTML contains JSON blocks like "raceUrl":"/racecards/1079/kempton-aw/2026-05-27/919104"
matches = re.finditer(r'"raceUrl":"(/racecards/\d+/[^/]+/2026-05-27/\d+)"', text)
for m in matches:
    path = m.group(1)
    # Check if any target is in the path
    for t in targets:
        if t in path.lower():
            urls.add("https://www.racingpost.com" + path + "/")

out_file = "data/racing_post_url_lists/rp_racecards_2026_05_27_explicit_v5.txt"
with open(out_file, "w") as f:
    for u in sorted(list(urls)):
        f.write(u + "\n")

print(f"Extracted {len(urls)} URLs to {out_file}")
for u in sorted(list(urls)):
    print(u)
