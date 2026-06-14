import re
import json

html_file = "data/racing_post_account_raw/index_2026_05_27/2026-05-27/001_racecards_2026_05_27_af66fea80c60.html"
with open(html_file, "r") as f:
    text = f.read()

targets = ["hamilton", "beverley", "newton-abbot", "newton", "kempton", "cartmel", "wexford"]
urls = set()

# Pattern 1: Embedded JSON state
json_matches = re.finditer(r'"raceId":"(\d+)","courseUid":(\d+),"courseName":"([^"]+)"', text)
for m in json_matches:
    race_id = m.group(1)
    course_uid = m.group(2)
    course_name = m.group(3).lower().replace(" ", "-").replace("'", "")
    for t in targets:
        if t in course_name:
            urls.add(f"https://www.racingpost.com/racecards/{course_uid}/{course_name}/2026-05-27/{race_id}/")

# Pattern 2: Feed strings
feed_matches = re.finditer(r'"feed":"HORSES/2026-05-27/([A-Z_-]+)/([^/]+)/#RACESTATUS".*?"raceId":"(\d+)"', text)
for m in feed_matches:
    course = m.group(1).lower().replace("_", "-")
    race_id = m.group(3)
    for t in targets:
        if t in course:
            urls.add(f"https://www.racingpost.com/racecards/0/{course}/2026-05-27/{race_id}/")

# Pattern 3: direct hrefs
links = re.finditer(r'href="(/racecards/\d+/[^/]+/2026-05-27/\d+)[/?"]', text)
for m in links:
    href = m.group(1)
    for t in targets:
        if t in href.lower():
            urls.add("https://www.racingpost.com" + href + "/")

out_file = "data/racing_post_url_lists/rp_racecards_2026_05_27_explicit.txt"
with open(out_file, "w") as f:
    for u in sorted(list(urls)):
        # Normalize double slashes in paths, except for https://
        clean_u = u.replace("com//", "com/").replace("/0/", "/22/") # guess 22 if 0
        f.write(clean_u + "\n")

print(f"Extracted {len(urls)} URLs to {out_file}")
for u in sorted(list(urls)):
    print(u)
