"""
Racing Post Scraper
Fetches daily UK/Ireland horse racing cards from Racing Post
"""

import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import json
import time

class RacingPostScraper:
    def __init__(self, username: Optional[str] = None, password: Optional[str] = None):
        self.base_url = "https://www.racingpost.com"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        self.username = username
        self.password = password
        self.logged_in = False
        
        if username and password:
            self.login()
    
    def login(self) -> bool:
        """Login to Racing Post (for paid features like TS/RPR)"""
        print("🔐 Logging into Racing Post...")
        
        try:
            # Get login page
            login_url = f"{self.base_url}/profile/login"
            response = self.session.get(login_url)
            
            # Submit login form
            login_data = {
                'username': self.username,
                'password': self.password
            }
            
            response = self.session.post(login_url, data=login_data)
            
            if 'logout' in response.text.lower():
                print("✅ Logged in successfully!")
                self.logged_in = True
                return True
            else:
                print("❌ Login failed")
                return False
                
        except Exception as e:
            print(f"❌ Login error: {e}")
            return False
    
    def get_todays_races(self, date: Optional[str] = None) -> List[Dict]:
        """
        Get all UK/Ireland races for a specific date
        
        Args:
            date: Date in YYYY-MM-DD format (default: today)
        
        Returns:
            List of race dictionaries
        """
        if not date:
            date = datetime.now().strftime('%Y-%m-%d')
        
        print(f"\n📅 Fetching races for {date}...")
        
        # Racing Post URL format: /racecards/YYYY-MM-DD
        url = f"{self.base_url}/racecards/{date}"
        
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            races = []
            
            # Find all race cards
            race_cards = soup.find_all('div', class_='RC-courseHeader')
            
            for card in race_cards:
                # Extract course name
                course_elem = card.find('a', class_='RC-courseHeader__name')
                if not course_elem:
                    continue
                
                course = course_elem.text.strip()
                
                # Only UK/Ireland courses
                country_elem = card.find('span', class_='RC-courseHeader__country')
                if country_elem:
                    country = country_elem.text.strip()
                    if country not in ['GB', 'IRE', 'UK', 'Ireland']:
                        continue
                
                # Get race times and links
                race_links = card.find_next_siblings('a', class_='RC-cardItem')
                
                for race_link in race_links:
                    race_time_elem = race_link.find('span', class_='RC-cardItem__time')
                    if not race_time_elem:
                        continue
                    
                    race_time = race_time_elem.text.strip()
                    race_url = self.base_url + race_link.get('href', '')
                    
                    races.append({
                        'date': date,
                        'course': course,
                        'time': race_time,
                        'url': race_url
                    })
            
            print(f"✅ Found {len(races)} races")
            return races
            
        except Exception as e:
            print(f"❌ Error fetching races: {e}")
            return []
    
    def get_race_details(self, race_url: str) -> Optional[Dict]:
        """
        Get detailed information for a specific race
        
        Args:
            race_url: URL of the race card
        
        Returns:
            Dictionary with race details and runners
        """
        try:
            response = self.session.get(race_url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract race info
            race_info = {}
            
            # Race title
            title_elem = soup.find('h1', class_='RC-headerBox__title')
            if title_elem:
                race_info['title'] = title_elem.text.strip()
            
            # Race distance
            distance_elem = soup.find('span', class_='RC-headerBox__distance')
            if distance_elem:
                race_info['distance'] = distance_elem.text.strip()
            
            # Race class
            class_elem = soup.find('span', class_='RC-headerBox__class')
            if class_elem:
                race_info['class'] = class_elem.text.strip()
            
            # Prize money
            prize_elem = soup.find('span', class_='RC-headerBox__prize')
            if prize_elem:
                race_info['prize'] = prize_elem.text.strip()
            
            # Get runners
            runners = []
            
            runner_rows = soup.find_all('div', class_='RC-runnerRow')
            
            for row in runner_rows:
                runner = {}
                
                # Runner number
                num_elem = row.find('span', class_='RC-runnerNumber')
                if num_elem:
                    runner['number'] = num_elem.text.strip()
                
                # Horse name
                name_elem = row.find('a', class_='RC-runnerName')
                if name_elem:
                    runner['name'] = name_elem.text.strip()
                
                # Jockey
                jockey_elem = row.find('a', class_='RC-runnerJockey')
                if jockey_elem:
                    runner['jockey'] = jockey_elem.text.strip()
                
                # Trainer
                trainer_elem = row.find('a', class_='RC-runnerTrainer')
                if trainer_elem:
                    runner['trainer'] = trainer_elem.text.strip()
                
                # Age/Weight
                age_elem = row.find('span', class_='RC-runnerAge')
                if age_elem:
                    runner['age'] = age_elem.text.strip()
                
                # Form
                form_elem = row.find('span', class_='RC-runnerForm')
                if form_elem:
                    runner['form'] = form_elem.text.strip()
                
                # Odds (if available)
                odds_elem = row.find('span', class_='RC-runnerOdds')
                if odds_elem:
                    runner['odds'] = odds_elem.text.strip()
                
                # TS/RPR (if logged in with paid account)
                if self.logged_in:
                    ts_elem = row.find('span', class_='RC-runnerTS')
                    if ts_elem:
                        runner['ts'] = ts_elem.text.strip()
                    
                    rpr_elem = row.find('span', class_='RC-runnerRPR')
                    if rpr_elem:
                        runner['rpr'] = rpr_elem.text.strip()
                
                if runner.get('name'):
                    runners.append(runner)
            
            race_info['runners'] = runners
            race_info['url'] = race_url
            
            return race_info
            
        except Exception as e:
            print(f"⚠️ Error fetching race details: {e}")
            return None
    
    def scrape_todays_cards(self, save_to_file: bool = True) -> List[Dict]:
        """
        Scrape all race cards for today
        
        Args:
            save_to_file: Save results to JSON file
        
        Returns:
            List of complete race cards
        """
        print("\n" + "="*70)
        print("🏇 RACING POST SCRAPER")
        print("="*70)
        
        # Get list of races
        races = self.get_todays_races()
        
        if not races:
            print("\n❌ No races found for today")
            return []
        
        # Get details for each race
        complete_cards = []
        
        for i, race in enumerate(races, 1):
            print(f"\n[{i}/{len(races)}] {race['course']} {race['time']}")
            
            details = self.get_race_details(race['url'])
            
            if details:
                # Merge basic info with details
                complete_race = {**race, **details}
                complete_cards.append(complete_race)
                
                print(f"  ✅ {len(details.get('runners', []))} runners")
            else:
                print(f"  ⚠️ Failed to get details")
            
            # Rate limiting - be nice to Racing Post
            time.sleep(1)
        
        # Save to file
        if save_to_file and complete_cards:
            filename = f"race_cards_{datetime.now().strftime('%Y%m%d')}.json"
            with open(filename, 'w') as f:
                json.dump(complete_cards, f, indent=2)
            
            print(f"\n💾 Saved to {filename}")
        
        print("\n" + "="*70)
        print(f"✅ Scraped {len(complete_cards)} complete race cards")
        print("="*70)
        
        return complete_cards


if __name__ == "__main__":
    # Example usage
    
    # Without login (free data)
    scraper = RacingPostScraper()
    
    # With login (for TS/RPR ratings)
    # scraper = RacingPostScraper(username="your_email", password="your_password")
    
    # Scrape today's cards
    cards = scraper.scrape_todays_cards()
    
    # Print summary
    if cards:
        print(f"\n📊 Summary:")
        print(f"Total races: {len(cards)}")
        print(f"Total runners: {sum(len(card.get('runners', [])) for card in cards)}")
        
        print(f"\n🏇 First race:")
        first_race = cards[0]
        print(f"Course: {first_race.get('course')}")
        print(f"Time: {first_race.get('time')}")
        print(f"Runners: {len(first_race.get('runners', []))}")
