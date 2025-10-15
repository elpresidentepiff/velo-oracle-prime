#!/usr/bin/env python3.11
"""
VÉLØ Daily Scraper
Wrapper around rpscrape to collect daily UK/Ireland racing data
"""

import sys
import os
import subprocess
from datetime import datetime, timedelta
import pandas as pd
import psycopg2
from pathlib import Path

# Add rpscrape to path
sys.path.insert(0, '/home/ubuntu/rpscrape/scripts')

class VeloScraper:
    """Daily racing data scraper for VÉLØ"""
    
    def __init__(self):
        self.rpscrape_dir = '/home/ubuntu/rpscrape/scripts'
        self.output_dir = '/home/ubuntu/velo-oracle/data/scraped'
        self.db_config = {
            'dbname': 'velo_racing',
            'user': 'postgres'
        }
        
        # Create output directory
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)
    
    def scrape_yesterday(self):
        """Scrape yesterday's results"""
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y/%m/%d')
        
        print(f"\n🔮 VÉLØ Scraper - Collecting data for {yesterday}")
        print("="*60)
        
        # Scrape GB (Great Britain)
        print("\nScraping GB results...")
        gb_file = f"{self.output_dir}/gb_{yesterday.replace('/', '_')}.csv"
        cmd = f"cd {self.rpscrape_dir} && python3 rpscrape.py -d {yesterday} gb"
        
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=300)
            if result.returncode == 0:
                print(f"✅ GB results scraped")
            else:
                print(f"⚠️  GB scraping failed: {result.stderr}")
        except subprocess.TimeoutExpired:
            print("⚠️  GB scraping timed out")
        except Exception as e:
            print(f"⚠️  GB scraping error: {e}")
        
        # Scrape IRE (Ireland)
        print("\nScraping IRE results...")
        ire_file = f"{self.output_dir}/ire_{yesterday.replace('/', '_')}.csv"
        cmd = f"cd {self.rpscrape_dir} && python3 rpscrape.py -d {yesterday} ire"
        
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=300)
            if result.returncode == 0:
                print(f"✅ IRE results scraped")
            else:
                print(f"⚠️  IRE scraping failed: {result.stderr}")
        except subprocess.TimeoutExpired:
            print("⚠️  IRE scraping timed out")
        except Exception as e:
            print(f"⚠️  IRE scraping error: {e}")
        
        print("\n" + "="*60)
        print("✅ Scraping complete\n")
    
    def scrape_today_racecards(self):
        """Scrape today's racecards"""
        print(f"\n🔮 VÉLØ Scraper - Collecting today's racecards")
        print("="*60)
        
        cmd = f"cd {self.rpscrape_dir} && python3 racecards.py today"
        
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=300)
            if result.returncode == 0:
                print(f"✅ Racecards scraped")
                print(result.stdout)
            else:
                print(f"⚠️  Racecard scraping failed: {result.stderr}")
        except subprocess.TimeoutExpired:
            print("⚠️  Racecard scraping timed out")
        except Exception as e:
            print(f"⚠️  Racecard scraping error: {e}")
        
        print("\n" + "="*60)
        print("✅ Racecard scraping complete\n")
    
    def import_to_database(self, csv_file):
        """Import scraped CSV to database"""
        if not os.path.exists(csv_file):
            print(f"⚠️  File not found: {csv_file}")
            return
        
        print(f"\nImporting {csv_file} to database...")
        
        try:
            # Read CSV
            df = pd.read_csv(csv_file, low_memory=False)
            
            if len(df) == 0:
                print("⚠️  No data in file")
                return
            
            # Connect to database
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            # Insert data
            imported = 0
            for _, row in df.iterrows():
                try:
                    # Helper function to convert to numeric or None
                    def to_num(val):
                        if pd.isna(val) or val == '-' or val == '–' or val == '':
                            return None
                        try:
                            return float(val)
                        except:
                            return None
                    
                    # Helper function to convert to int or None
                    def to_int(val):
                        if pd.isna(val) or val == '-' or val == '–' or val == '':
                            return None
                        try:
                            return int(float(val))
                        except:
                            return None
                    
                    cursor.execute("""
                        INSERT INTO racing_data (
                            date, course, race_id, off_time, race_name, type, class, pattern,
                            rating_band, age_band, sex_rest, dist, going, ran, num, pos, draw,
                            ovr_btn, btn, horse, age, sex, wgt, hg, time, sp, jockey, trainer,
                            prize, official_rating, rpr, ts, sire, dam, damsire, owner, comment
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                            %s, %s, %s
                        )
                    """, (
                        row.get('date'),
                        row.get('course'),
                        row.get('race_id'),
                        row.get('off'),
                        row.get('race_name'),
                        row.get('type'),
                        row.get('class'),
                        row.get('pattern'),
                        row.get('rating_band'),
                        row.get('age_band'),
                        row.get('sex_rest'),
                        row.get('dist'),
                        row.get('going'),
                        to_int(row.get('ran')),
                        to_num(row.get('num')),
                        str(row.get('pos')) if pd.notna(row.get('pos')) and row.get('pos') != '-' else None,
                        to_int(row.get('draw')),
                        to_num(row.get('ovr_btn')),
                        to_num(row.get('btn')),
                        row.get('horse'),
                        to_int(row.get('age')),
                        row.get('sex') if pd.notna(row.get('sex')) and row.get('sex') != '-' else None,
                        row.get('wgt'),
                        row.get('hg'),
                        row.get('time'),
                        row.get('sp'),
                        row.get('jockey'),
                        row.get('trainer'),
                        str(row.get('prize')) if pd.notna(row.get('prize')) else None,
                        str(row.get('or')) if pd.notna(row.get('or')) and row.get('or') != '–' else None,
                        str(row.get('rpr')) if pd.notna(row.get('rpr')) and row.get('rpr') != '–' else None,
                        str(row.get('ts')) if pd.notna(row.get('ts')) and row.get('ts') != '–' else None,
                        row.get('sire'),
                        row.get('dam'),
                        row.get('damsire'),
                        row.get('owner'),
                        row.get('comment')
                    ))
                    imported += 1
                except Exception as e:
                    # Skip rows with errors
                    continue
            
            conn.commit()
            cursor.close()
            conn.close()
            
            print(f"✅ Imported {imported} rows from {csv_file}")
            
        except Exception as e:
            print(f"⚠️  Import error: {e}")
    
    def run_daily_update(self):
        """Run complete daily update"""
        print("\n" + "="*60)
        print("🔮 VÉLØ DAILY UPDATE")
        print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*60)
        
        # Scrape yesterday's results
        self.scrape_yesterday()
        
        # Scrape today's racecards
        self.scrape_today_racecards()
        
        # Import any new CSV files
        print("\n" + "="*60)
        print("Checking for files to import...")
        print("="*60)
        
        for csv_file in Path(self.output_dir).glob('*.csv'):
            self.import_to_database(str(csv_file))
        
        print("\n" + "="*60)
        print("✅ DAILY UPDATE COMPLETE")
        print(f"Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*60 + "\n")


def main():
    """Main entry point"""
    scraper = VeloScraper()
    
    if len(sys.argv) > 1:
        if sys.argv[1] == 'yesterday':
            scraper.scrape_yesterday()
        elif sys.argv[1] == 'today':
            scraper.scrape_today_racecards()
        elif sys.argv[1] == 'daily':
            scraper.run_daily_update()
        else:
            print("Usage: velo_scraper.py [yesterday|today|daily]")
    else:
        # Default: run daily update
        scraper.run_daily_update()


if __name__ == "__main__":
    main()

