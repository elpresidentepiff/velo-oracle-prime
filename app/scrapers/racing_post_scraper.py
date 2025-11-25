#!/usr/bin/env python3
"""
VELO ORACLE - Racing Post Scraper V3
Uses correct DOM structure (div.RC-runnerRow containers)
"""

import asyncio
import json
import re
from datetime import datetime
from playwright.async_api import async_playwright

async def scrape_race_card(page, race_url, race_info):
    """Scrape race card using correct DOM structure"""
    
    print(f"\n{'='*60}")
    print(f"Scraping: {race_info['display']}")
    print(f"{'='*60}")
    
    try:
        response = await page.goto(race_url, timeout=30000, wait_until='domcontentloaded')
        
        if response.status != 200:
            print(f"❌ Failed: Status {response.status}")
            return None
        
        await asyncio.sleep(3)
        
        # Extract race title
        title_elem = await page.query_selector('h1')
        title = await title_elem.inner_text() if title_elem else "Unknown Race"
        
        # Find all runner containers
        print(f"Extracting runners...")
        runner_containers = await page.query_selector_all('div.RC-runnerRow')
        
        print(f"Found {len(runner_containers)} runner containers")
        
        runners = []
        
        for i, container in enumerate(runner_containers, 1):
            try:
                runner_data = {'position': i}
                
                # Horse name
                horse_elem = await container.query_selector('a[data-test-selector="RC-cardPage-runnerName"]')
                if horse_elem:
                    runner_data['horse'] = (await horse_elem.inner_text()).strip()
                else:
                    continue  # Skip if no horse name
                
                # Draw number
                draw_elem = await container.query_selector('[data-test-selector="RC-cardPage-runnerNumber-draw"]')
                runner_data['draw'] = (await draw_elem.inner_text()).strip() if draw_elem else ''
                
                # Jockey
                jockey_elem = await container.query_selector('[data-test-selector="RC-cardPage-runnerJockey-name"]')
                runner_data['jockey'] = (await jockey_elem.inner_text()).strip() if jockey_elem else ''
                
                # Trainer
                trainer_elem = await container.query_selector('[data-test-selector="RC-cardPage-runnerTrainer-name"]')
                runner_data['trainer'] = (await trainer_elem.inner_text()).strip() if trainer_elem else ''
                
                # Odds/Price
                price_elem = await container.query_selector('[data-test-selector="RC-cardPage-runnerPrice"]')
                runner_data['odds'] = (await price_elem.inner_text()).strip() if price_elem else ''
                
                # Form
                form_elem = await container.query_selector('[data-test-selector="RC-cardPage-runnerForm"]')
                runner_data['form'] = (await form_elem.inner_text()).strip() if form_elem else ''
                
                # Age
                age_elem = await container.query_selector('[data-test-selector="RC-cardPage-runnerAge"]')
                runner_data['age'] = (await age_elem.inner_text()).strip() if age_elem else ''
                
                # Weight
                weight_elem = await container.query_selector('[data-test-selector="RC-cardPage-runnerWgt-carried"]')
                runner_data['weight'] = (await weight_elem.inner_text()).strip() if weight_elem else ''
                
                # TS rating (Topspeed)
                ts_elem = await container.query_selector('[data-test-selector="RC-cardPage-runnerTs"]')
                runner_data['ts'] = (await ts_elem.inner_text()).strip() if ts_elem else ''
                
                # RPR rating
                rpr_elem = await container.query_selector('[data-test-selector="RC-cardPage-runnerRpr"]')
                runner_data['rpr'] = (await rpr_elem.inner_text()).strip() if rpr_elem else ''
                
                # OR (Official Rating)
                or_elem = await container.query_selector('[data-test-selector="RC-cardPage-runnerOr"]')
                runner_data['or'] = (await or_elem.inner_text()).strip() if or_elem else ''
                
                runners.append(runner_data)
                
                # Print formatted output
                print(f"  {i}. {runner_data['horse']:25} {runner_data['jockey']:20} {runner_data['odds']:8} TS:{runner_data['ts']:4} RPR:{runner_data['rpr']:4}")
                
            except Exception as e:
                print(f"  Warning: Error extracting runner {i}: {e}")
                continue
        
        print(f"✅ Extracted {len(runners)} runners")
        
        race_data = {
            'success': True,
            'url': race_url,
            'course': race_info['course'],
            'time': race_info['time'],
            'title': title.strip(),
            'runners': runners,
            'runner_count': len(runners),
            'scraped_at': datetime.now().isoformat()
        }
        
        return race_data
        
    except Exception as e:
        print(f"❌ Error scraping race: {e}")
        return {
            'success': False,
            'url': race_url,
            'error': str(e)
        }

async def get_todays_race_urls(page, date_str):
    """Get all race URLs for today"""
    
    url = f"https://www.racingpost.com/racecards/{date_str}"
    print(f"\n[1/3] Loading race cards for {date_str}...")
    
    try:
        response = await page.goto(url, timeout=30000, wait_until='domcontentloaded')
        
        if response.status != 200:
            print(f"❌ Failed to load: Status {response.status}")
            return []
        
        await asyncio.sleep(2)
        
        print(f"[2/3] Finding race cards...")
        
        # Find all race card links
        race_elements = await page.query_selector_all('a[href*="/racecards/"][href*="/"]')
        
        races = []
        seen_urls = set()
        
        for elem in race_elements:
            href = await elem.get_attribute('href')
            
            if not href or href in seen_urls:
                continue
            
            # Filter for actual race URLs
            if re.match(r'.*/racecards/\d+/[a-z-]+/\d{4}-\d{2}-\d{2}/\d+', href):
                full_url = href if href.startswith('http') else f"https://www.racingpost.com{href}"
                
                # Extract course and time
                match = re.search(r'/racecards/\d+/([a-z-]+)/\d{4}-\d{2}-\d{2}/(\d+)', href)
                if match:
                    course = match.group(1).replace('-', ' ').title()
                    race_id = match.group(2)
                    
                    # Try to get time from page
                    text = await elem.inner_text()
                    time_match = re.search(r'(\d{1,2}):(\d{2})', text)
                    time = time_match.group(0) if time_match else "Unknown"
                    
                    races.append({
                        'url': full_url,
                        'course': course,
                        'time': time,
                        'display': f"{time} {course}",
                        'race_id': race_id
                    })
                    seen_urls.add(href)
        
        print(f"[3/3] Found {len(races)} races")
        for i, race in enumerate(races[:10], 1):
            print(f"  {i}. {race['display']}")
        
        if len(races) > 10:
            print(f"  ... and {len(races) - 10} more")
        
        return races
        
    except Exception as e:
        print(f"❌ Error getting race URLs: {e}")
        return []

async def main():
    """Main scraper function"""
    
    print(f"\n{'#'*60}")
    print(f"VELO ORACLE - Racing Post Scraper V3")
    print(f"{'#'*60}")
    
    today = datetime.now().strftime("%Y-%m-%d")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox'
            ]
        )
        
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        
        page = await context.new_page()
        
        # Get today's race URLs
        races = await get_todays_race_urls(page, today)
        
        if not races:
            print("\n❌ No races found for today")
            await browser.close()
            return
        
        # Scrape first 3 races
        print(f"\n{'='*60}")
        print(f"Scraping first 3 races...")
        print(f"{'='*60}")
        
        all_race_data = []
        
        for i, race in enumerate(races[:3], 1):
            print(f"\n[{i}/3] Processing {race['display']}...")
            
            race_data = await scrape_race_card(page, race['url'], race)
            
            if race_data and race_data.get('success'):
                all_race_data.append(race_data)
            
            # Be polite
            await asyncio.sleep(2)
        
        await browser.close()
        
        # Save results
        output_file = f"/home/ubuntu/velo_races_{today}.json"
        with open(output_file, 'w') as f:
            json.dump({
                'date': today,
                'total_races_found': len(races),
                'races_scraped': len(all_race_data),
                'races': all_race_data
            }, f, indent=2)
        
        print(f"\n{'#'*60}")
        print(f"SCRAPING COMPLETE")
        print(f"{'#'*60}")
        print(f"Total races found: {len(races)}")
        print(f"Races scraped: {len(all_race_data)}")
        print(f"Successful: {sum(1 for r in all_race_data if r.get('success'))}")
        print(f"Output saved to: {output_file}")
        print(f"{'#'*60}\n")

if __name__ == "__main__":
    asyncio.run(main())
