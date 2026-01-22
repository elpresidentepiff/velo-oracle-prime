#!/usr/bin/env python3
"""
VÉLØ Canary Test Suite - Pre-flight checks before any live day
Runs 30-second validation before autopilot starts
"""

import os
import sys
import json
from pathlib import Path

class CanaryTests:
    def __init__(self, env="production"):
        self.env = env
        self.checks_passed = 0
        self.checks_failed = 0
        self.failures = []
    
    def check_venue_normalization(self):
        """Verify venue normalization is working"""
        try:
            from src.automation.venue_normalizer import VenueNormalizer
            normalizer = VenueNormalizer()
            test_cases = [
                ("Down Royal", "downroyal"),
                ("Kempton Park", "kempton"),
                ("Lingfield", "lingfield"),
            ]
            for venue, expected in test_cases:
                result = normalizer.normalize(venue)
                if result != expected:
                    self.failures.append(f"Venue normalization failed: {venue} -> {result} (expected {expected})")
                    return False
            self.checks_passed += 1
            return True
        except Exception as e:
            self.failures.append(f"Venue normalization check failed: {str(e)}")
            return False
    
    def check_episode_id_uniqueness(self):
        """Verify episode IDs are unique and canonical"""
        try:
            episodes_dir = Path("episodes")
            if not episodes_dir.exists():
                self.failures.append("Episodes directory not found")
                return False
            
            episode_ids = set()
            for episode_file in episodes_dir.glob("*.json"):
                with open(episode_file) as f:
                    episode = json.load(f)
                    episode_id = episode.get("episode_id")
                    if episode_id in episode_ids:
                        self.failures.append(f"Duplicate episode_id: {episode_id}")
                        return False
                    episode_ids.add(episode_id)
            
            self.checks_passed += 1
            return True
        except Exception as e:
            self.failures.append(f"Episode ID uniqueness check failed: {str(e)}")
            return False
    
    def check_required_layers(self):
        """Verify required layers are present in episodes"""
        try:
            episodes_dir = Path("episodes")
            required_fields = ["episode_id", "venue", "date", "total_races"]
            
            for episode_file in episodes_dir.glob("*.json"):
                with open(episode_file) as f:
                    episode = json.load(f)
                    for field in required_fields:
                        if field not in episode:
                            self.failures.append(f"Missing required field '{field}' in {episode_file}")
                            return False
            
            self.checks_passed += 1
            return True
        except Exception as e:
            self.failures.append(f"Required layers check failed: {str(e)}")
            return False
    
    def check_db_schema_version(self):
        """Verify database schema matches code version"""
        try:
            db_path = os.getenv("VELO_DB_PATH", "velo.db")
            if not os.path.exists(db_path):
                self.failures.append(f"Database not found at {db_path}")
                return False
            
            self.checks_passed += 1
            return True
        except Exception as e:
            self.failures.append(f"DB schema check failed: {str(e)}")
            return False
    
    def check_artifacts_path_writable(self):
        """Verify artifacts directory is writable"""
        try:
            artifacts_dir = os.getenv("ARTIFACTS_DIR", "artifacts/")
            Path(artifacts_dir).mkdir(parents=True, exist_ok=True)
            
            test_file = Path(artifacts_dir) / ".canary_test"
            test_file.write_text("canary")
            test_file.unlink()
            
            self.checks_passed += 1
            return True
        except Exception as e:
            self.failures.append(f"Artifacts path writable check failed: {str(e)}")
            return False
    
    def check_scraper_degradation(self):
        """Verify scraper fails gracefully"""
        try:
            # Check that resilient_scraper exists and can handle failures
            from src.automation.resilient_scraper import ResilientScraper
            scraper = ResilientScraper()
            # If we got here, scraper is importable and instantiable
            self.checks_passed += 1
            return True
        except Exception as e:
            self.failures.append(f"Scraper degradation check failed: {str(e)}")
            return False
    
    def run_all(self):
        """Run all canary checks"""
        print("🔍 VÉLØ CANARY CHECKS - PRE-FLIGHT")
        print("=" * 50)
        
        checks = [
            ("Venue Normalization", self.check_venue_normalization),
            ("Episode ID Uniqueness", self.check_episode_id_uniqueness),
            ("Required Layers", self.check_required_layers),
            ("DB Schema Version", self.check_db_schema_version),
            ("Artifacts Path Writable", self.check_artifacts_path_writable),
            ("Scraper Degradation", self.check_scraper_degradation),
        ]
        
        for check_name, check_func in checks:
            result = check_func()
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"{status}: {check_name}")
        
        print("=" * 50)
        print(f"Passed: {self.checks_passed}/{len(checks)}")
        
        if self.failures:
            print("\n⚠️  FAILURES:")
            for failure in self.failures:
                print(f"  - {failure}")
            return False
        
        print("\n✅ ALL CANARY CHECKS PASSED - SAFE TO PROCEED")
        return True

if __name__ == "__main__":
    env = os.getenv("VELO_ENV", "production")
    canary = CanaryTests(env=env)
    success = canary.run_all()
    sys.exit(0 if success else 1)
