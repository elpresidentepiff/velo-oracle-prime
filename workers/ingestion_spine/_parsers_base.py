"""
VÉLØ Phase 1: Racing Post File Parsers
CSV parsing with strict validation - no "best effort" nonsense

Date: 2026-01-04
"""

import csv
import io
import logging
from typing import List, Dict, Any, Optional
from datetime import date, time, datetime
from .models import RaceData, RunnerData, FormLineData

logger = logging.getLogger(__name__)

# ============================================================================
# BASE PARSER
# ============================================================================

class BaseParser:
    """Base class for CSV parsers with common functionality"""
    
    def __init__(self):
        self.errors = []
    
    def parse_csv(self, data: bytes) -> List[Dict[str, Any]]:
        """
        Parse CSV data into list of dictionaries.
        
        Args:
            data: CSV file content as bytes
        
        Returns:
            List of row dictionaries
        """
        try:
            # Decode bytes to string
            text = data.decode('utf-8-sig')  # Handle BOM if present
            
            # Parse CSV
            reader = csv.DictReader(io.StringIO(text))
            rows = list(reader)
            
            logger.info(f"Parsed {len(rows)} rows from CSV")
            return rows
        
        except Exception as e:
            logger.error(f"CSV parsing error: {e}")
            raise ValueError(f"Failed to parse CSV: {str(e)}")
    
    def safe_int(self, value: Any, default: Optional[int] = None) -> Optional[int]:
        """Safely convert value to int"""
        if value is None or value == '':
            return default
        try:
            return int(value)
        except (ValueError, TypeError):
            return default
    
    def safe_str(self, value: Any, default: str = '') -> str:
        """Safely convert value to string"""
        if value is None:
            return default
        return str(value).strip()
    
    def parse_time(self, time_str: str) -> Optional[time]:
        """Parse time string (HH:MM or HH:MM:SS)"""
        if not time_str:
            return None
        
        try:
            # Try HH:MM:SS format
            if time_str.count(':') == 2:
                return datetime.strptime(time_str, '%H:%M:%S').time()
            # Try HH:MM format
            elif time_str.count(':') == 1:
                return datetime.strptime(time_str, '%H:%M').time()
            else:
                logger.warning(f"Invalid time format: {time_str}")
                return None
        except ValueError as e:
            logger.warning(f"Failed to parse time '{time_str}': {e}")
            return None
    
    def parse_date(self, date_str: str) -> Optional[date]:
        """Parse date string (YYYY-MM-DD or DD/MM/YYYY)"""
        if not date_str:
            return None
        
        try:
            # Try YYYY-MM-DD format
            return datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            try:
                # Try DD/MM/YYYY format
                return datetime.strptime(date_str, '%d/%m/%Y').date()
            except ValueError as e:
                logger.warning(f"Failed to parse date '{date_str}': {e}")
                return None

# ============================================================================
# RACECARDS PARSER
# ============================================================================

class RacecardsParser(BaseParser):
    """
    Parser for racecards.csv
    
    Expected columns:
    - course
    - off_time
    - race_name (optional)
    - race_type
    - distance
    - class_band
    - going
    - field_size
    - prize
    """
    
    def parse(self, data: bytes) -> List[Dict[str, Any]]:
        """
        Parse racecards CSV into list of race dictionaries.
        
        Returns:
            List of race data dictionaries with join_key
        """
        rows = self.parse_csv(data)
        
        if not rows:
            raise ValueError("Racecards file is empty")
        
        races = []
        for idx, row in enumerate(rows, start=1):
            try:
                race = self._parse_race_row(row)
                races.append(race)
            except Exception as e:
                error_msg = f"Row {idx}: {str(e)}"
                self.errors.append(error_msg)
                logger.error(error_msg)
                # Don't skip - fail hard
                raise ValueError(f"Failed to parse race row {idx}: {str(e)}")
        
        logger.info(f"✅ Parsed {len(races)} races from racecards")
        return races
    
    def _parse_race_row(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """Parse a single race row"""
        # Required fields
        course = self.safe_str(row.get('course'))
        off_time_str = self.safe_str(row.get('off_time'))
        
        if not course:
            raise ValueError("Missing required field: course")
        if not off_time_str:
            raise ValueError("Missing required field: off_time")
        
        # Parse off_time
        off_time = self.parse_time(off_time_str)
        if not off_time:
            raise ValueError(f"Invalid off_time: {off_time_str}")
        
        # Optional fields
        race_name = self.safe_str(row.get('race_name'), None)
        race_type = self.safe_str(row.get('race_type'), None)
        distance = self.safe_str(row.get('distance'), None)
        class_band = self.safe_str(row.get('class_band'), None)
        going = self.safe_str(row.get('going'), None)
        field_size = self.safe_int(row.get('field_size'))
        prize = self.safe_str(row.get('prize'), None)
        
        # Generate join_key
        # Format: "{course}|{off_time}|{race_name_or_distance}|{race_type}"
        # Note: import_date will be added by the caller
        race_identifier = race_name if race_name else f"{distance}|{class_band}"
        join_key_base = f"{course}|{off_time}|{race_identifier}|{race_type}"
        
        return {
            'course': course,
            'off_time': off_time,
            'race_name': race_name,
            'race_type': race_type,
            'distance': distance,
            'class_band': class_band,
            'going': going,
            'field_size': field_size,
            'prize': prize,
            'join_key_base': join_key_base,  # Will be prefixed with import_date
            'raw': row  # Store original row for debugging
        }

# ============================================================================
# RUNNERS PARSER
# ============================================================================

class RunnersParser(BaseParser):
    """
    Parser for runners.csv
    
    Expected columns:
    - race_join_key (or components to build it)
    - cloth_no
    - horse_name
    - age
    - sex
    - weight
    - or_rating (OR)
    - rpr (RPR)
    - ts (TS/Topspeed)
    - trainer
    - jockey
    - owner
    - draw
    - headgear
    - form_figures
    """
    
    def parse(self, data: bytes) -> List[Dict[str, Any]]:
        """
        Parse runners CSV into list of runner dictionaries.
        
        Returns:
            List of runner data dictionaries with race_join_key
        """
        rows = self.parse_csv(data)
        
        if not rows:
            raise ValueError("Runners file is empty")
        
        runners = []
        for idx, row in enumerate(rows, start=1):
            try:
                runner = self._parse_runner_row(row)
                runners.append(runner)
            except Exception as e:
                error_msg = f"Row {idx}: {str(e)}"
                self.errors.append(error_msg)
                logger.error(error_msg)
                # Don't skip - fail hard
                raise ValueError(f"Failed to parse runner row {idx}: {str(e)}")
        
        logger.info(f"✅ Parsed {len(runners)} runners")
        return runners
    
    def _parse_runner_row(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """Parse a single runner row"""
        # Required fields
        horse_name = self.safe_str(row.get('horse_name'))
        
        if not horse_name:
            raise ValueError("Missing required field: horse_name")
        
        # Race join key (must be provided or buildable)
        race_join_key = self.safe_str(row.get('race_join_key'))
        
        if not race_join_key:
            # Try to build from components
            course = self.safe_str(row.get('course'))
            off_time_str = self.safe_str(row.get('off_time'))
            race_name = self.safe_str(row.get('race_name'), None)
            distance = self.safe_str(row.get('distance'), None)
            class_band = self.safe_str(row.get('class_band'), None)
            race_type = self.safe_str(row.get('race_type'), None)
            
            if course and off_time_str:
                off_time = self.parse_time(off_time_str)
                if off_time:
                    race_identifier = race_name if race_name else f"{distance}|{class_band}"
                    race_join_key = f"{course}|{off_time}|{race_identifier}|{race_type}"
        
        if not race_join_key:
            raise ValueError("Missing or invalid race_join_key")
        
        # Optional fields
        cloth_no = self.safe_int(row.get('cloth_no'))
        age = self.safe_int(row.get('age'))
        sex = self.safe_str(row.get('sex'), None)
        weight = self.safe_str(row.get('weight'), None)
        or_rating = self.safe_int(row.get('or_rating') or row.get('or') or row.get('OR'))
        rpr = self.safe_int(row.get('rpr') or row.get('RPR'))
        ts = self.safe_int(row.get('ts') or row.get('TS') or row.get('topspeed'))
        trainer = self.safe_str(row.get('trainer'), None)
        jockey = self.safe_str(row.get('jockey'), None)
        owner = self.safe_str(row.get('owner'), None)
        draw = self.safe_int(row.get('draw'))
        headgear = self.safe_str(row.get('headgear'), None)
        form_figures = self.safe_str(row.get('form_figures') or row.get('form'), None)
        
        return {
            'race_join_key': race_join_key,
            'cloth_no': cloth_no,
            'horse_name': horse_name,
            'age': age,
            'sex': sex,
            'weight': weight,
            'or_rating': or_rating,
            'rpr': rpr,
            'ts': ts,
            'trainer': trainer,
            'jockey': jockey,
            'owner': owner,
            'draw': draw,
            'headgear': headgear,
            'form_figures': form_figures,
            'raw': row  # Store original row for debugging
        }

# ============================================================================
# FORM PARSER
# ============================================================================

class FormParser(BaseParser):
    """
    Parser for form.csv (optional in Phase 1)
    
    Expected columns:
    - horse_name (to link back to runner)
    - run_date
    - course
    - distance
    - going
    - position
    - rpr
    - ts
    - or_rating
    - notes
    """
    
    def parse(self, data: bytes) -> List[Dict[str, Any]]:
        """
        Parse form CSV into list of form line dictionaries.
        
        Returns:
            List of form line data dictionaries
        """
        rows = self.parse_csv(data)
        
        if not rows:
            logger.warning("Form file is empty")
            return []
        
        form_lines = []
        for idx, row in enumerate(rows, start=1):
            try:
                form_line = self._parse_form_row(row)
                form_lines.append(form_line)
            except Exception as e:
                error_msg = f"Row {idx}: {str(e)}"
                self.errors.append(error_msg)
                logger.warning(error_msg)
                # For form, we can be more lenient - skip bad rows
                continue
        
        logger.info(f"✅ Parsed {len(form_lines)} form lines")
        return form_lines
    
    def _parse_form_row(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """Parse a single form row"""
        # Required field
        horse_name = self.safe_str(row.get('horse_name'))
        
        if not horse_name:
            raise ValueError("Missing required field: horse_name")
        
        # Optional fields
        run_date_str = self.safe_str(row.get('run_date'), None)
        run_date = self.parse_date(run_date_str) if run_date_str else None
        
        course = self.safe_str(row.get('course'), None)
        distance = self.safe_str(row.get('distance'), None)
        going = self.safe_str(row.get('going'), None)
        position = self.safe_str(row.get('position'), None)
        rpr = self.safe_int(row.get('rpr') or row.get('RPR'))
        ts = self.safe_int(row.get('ts') or row.get('TS'))
        or_rating = self.safe_int(row.get('or_rating') or row.get('or') or row.get('OR'))
        notes = self.safe_str(row.get('notes'), None)
        
        return {
            'horse_name': horse_name,
            'run_date': run_date,
            'course': course,
            'distance': distance,
            'going': going,
            'position': position,
            'rpr': rpr,
            'ts': ts,
            'or_rating': or_rating,
            'notes': notes,
            'raw': row  # Store original row for debugging
        }

# ============================================================================
# PARSER VALIDATION
# ============================================================================

def validate_race_data(race: Dict[str, Any]) -> bool:
    """Validate race data structure"""
    required = ['course', 'off_time', 'join_key_base']
    return all(race.get(field) for field in required)

def validate_runner_data(runner: Dict[str, Any]) -> bool:
    """Validate runner data structure"""
    required = ['horse_name', 'race_join_key']
    return all(runner.get(field) for field in required)

def validate_form_data(form: Dict[str, Any]) -> bool:
    """Validate form data structure"""
    required = ['horse_name']
    return all(form.get(field) for field in required)
