import re

def parse_racing_post_pdf(text):
    """
    Extracts structured data from Racing Post PDF text.
    Returns a list of runner dictionaries.
    """
    runners = []
    
    # Regex patterns for common data points
    # Note: PDF text extraction is messy. These are "best effort" patterns.
    
    # Pattern to find ratings (e.g., "OR 123", "TS 88", "RPR 135")
    # This is a simplified example. Real parsing requires complex line-by-line analysis.
    
    lines = text.split('\n')
    current_runner = {}
    
    for line in lines:
        # Heuristic: Lines with a lot of caps might be horse names
        # But for now, let's look for the ratings which are distinct.
        
        # Extract OR (Official Rating)
        or_match = re.search(r'OR\s*(\d{2,3})', line)
        if or_match:
            current_runner['or_rating'] = int(or_match.group(1))
            
        # Extract TS (Top Speed)
        ts_match = re.search(r'TS\s*(\d{2,3})', line)
        if ts_match:
            current_runner['ts_rating'] = int(ts_match.group(1))
            
        # Extract RPR (Racing Post Rating)
        rpr_match = re.search(r'RPR\s*(\d{2,3})', line)
        if rpr_match:
            current_runner['rpr_rating'] = int(rpr_match.group(1))
            
        # If we found some data, assume it's a runner and add it
        if 'or_rating' in current_runner or 'ts_rating' in current_runner:
            # Try to find a name in the previous lines (very rough heuristic)
            # In a real production system, we'd use layout analysis.
            current_runner['raw_text_snippet'] = line[:50] 
            runners.append(current_runner)
            current_runner = {} # Reset
            
    return runners
