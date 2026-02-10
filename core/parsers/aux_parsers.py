import re
import pdfplumber

class BaseAuxParser:
    def parse(self, file_path):
        """Returns {time: {horse_name: value}}"""
        data = {}
        current_time = None
        
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if not text: continue
                
                lines = text.split('\n')
                for line in lines:
                    # Detect Race Header (e.g., "12.48 7f 1y...")
                    # Regex: Start with Time (d.dd)
                    time_match = re.match(r'^(\d{1,2}\.\d{2})', line)
                    if time_match:
                        # Convert 12.48 to 12:48 for consistency with XX parser
                        raw_time = time_match.group(1)
                        current_time = raw_time.replace('.', ':')
                        data[current_time] = {}
                        continue
                    
                    if current_time:
                        self._parse_line(line, data[current_time])
        return data

    def _parse_line(self, line, race_data):
        raise NotImplementedError

class ORParser(BaseAuxParser):
    def _parse_line(self, line, race_data):
        # Pattern: [Form] [Name] [Weight] [OR] ...
        # Look for Weight (d-d)
        # Example: ... Profit Street 9-9 55 ...
        match = re.search(r'(\d+-\d+)\s+(\d+)', line)
        if match:
            weight_start = match.start()
            or_val = int(match.group(2))
            
            # Text before weight contains Form + Name
            pre_text = line[:weight_start].strip()
            
            # Split Form from Name
            # Form usually ends with a digit or fraction or code. Name starts with Text.
            # Heuristic: Find the last space that is preceded by a digit/fraction? 
            # Better: The Name is the text at the end of pre_text.
            # Let's split by spaces and take the last N words until we hit a "Form-like" string
            
            words = pre_text.split()
            name_parts = []
            for w in reversed(words):
                # If word looks like form (contains digits, /, -, or is just 1-2 chars like 'sd'), stop?
                # Actually, names can be "Elements Of Fire".
                # Form strings are usually long blocks like "65671/4".
                if re.search(r'\d', w) or len(w) > 15: # Form strings are dense
                    break
                name_parts.insert(0, w)
            
            if name_parts:
                name = " ".join(name_parts)
                race_data[name] = or_val

class TSParser(BaseAuxParser):
    def _parse_line(self, line, race_data):
        # Pattern: [Last Outings] [Name] [Weight] [TS]
        # Example: ... Freda 8-13 54 ...
        # TS can be '-' or missing
        match = re.search(r'(\d+-\d+)\s+(\d+|-)', line)
        if match:
            weight_start = match.start()
            ts_str = match.group(2)
            ts_val = int(ts_str) if ts_str.isdigit() else None
            
            pre_text = line[:weight_start].strip()
            words = pre_text.split()
            name_parts = []
            for w in reversed(words):
                if re.search(r'\d', w): # Form has digits
                    break
                name_parts.insert(0, w)
            
            if name_parts:
                name = " ".join(name_parts)
                race_data[name] = ts_val

class PMParser(BaseAuxParser):
    def _parse_line(self, line, race_data):
        # Pattern: [Last Outings] [Name] [Weight] [RPR]
        # Example: ... Elements Of Fire 9-11 87 ...
        match = re.search(r'(\d+-\d+)\s+(\d+)', line)
        if match:
            weight_start = match.start()
            rpr_val = int(match.group(2))
            
            pre_text = line[:weight_start].strip()
            words = pre_text.split()
            name_parts = []
            for w in reversed(words):
                if re.search(r'\d', w):
                    break
                name_parts.insert(0, w)
            
            if name_parts:
                name = " ".join(name_parts)
                race_data[name] = rpr_val
