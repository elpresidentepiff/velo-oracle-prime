import re
from pathlib import Path

def test_extraction():
    # Read the fresh index HTML
    index_folders = sorted(Path('data/racing_post_account_raw').glob('index-2026-06-07*'))
    if not index_folders:
        print('FAIL: No index folders for 2026-06-07')
        return
    index_folder = index_folders[-1]
    # Handle both flat and nested structures (some captures vary)
    html_files = list(index_folder.glob('**/*.html'))
    print(f'Index folder: {index_folder.name}')
    print(f'HTML files found: {len(html_files)}')

    target_date = '2026-06-07'
    all_urls = set()
    for f in html_files:
        html = f.read_text(encoding='utf-8', errors='replace')
        # Direct URL pattern match — ignore JSON index keys
        pattern = rf'(?:https?://(?:www\.)?racingpost\.com)?/racecards/(\d+)/([^/\" ]+)/{re.escape(target_date)}/(\d+)'
        for m in re.finditer(pattern, html):
            course_id, slug, race_id = m.groups()
            url = f'https://www.racingpost.com/racecards/{course_id}/{slug}/{target_date}/{race_id}'
            all_urls.add(url)

    urls = sorted(all_urls)
    print(f'TOTAL UNIQUE URLS: {len(urls)}')
    by_venue = {}
    for u in urls:
        slug = u.split('/')[5]
        by_venue[slug] = by_venue.get(slug, 0) + 1
    for v in sorted(by_venue):
        print(f'  {v}: {by_venue[v]} races')

    out = Path('data/racing_post_url_lists/rp_racecards_2026-06-07_TRUE.txt')
    out.write_text('\n'.join(urls) + '\n', encoding='utf-8')
    print(f'Written: {out}')

if __name__ == "__main__":
    test_extraction()
