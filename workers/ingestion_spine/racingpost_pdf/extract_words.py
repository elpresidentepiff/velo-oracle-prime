"""
Racing Post PDF Parser - Word Extraction Helpers
pdfplumber helpers for word geometry and column clustering.
"""

from typing import Dict, List, Tuple, Any
import pdfplumber


def extract_page_words(page: pdfplumber.page.Page) -> List[Dict[str, Any]]:
    """
    Extract words from a PDF page with geometry.
    
    Args:
        page: pdfplumber page object
        
    Returns:
        List of word dictionaries with keys:
        - text: word text
        - x0: left x coordinate
        - x1: right x coordinate
        - top: top y coordinate
        - bottom: bottom y coordinate
    """
    words = page.extract_words()
    return words


def cluster_by_x_position(words: List[Dict[str, Any]], tolerance: float = 10.0) -> Dict[float, List[Dict[str, Any]]]:
    """
    Cluster words into columns by x position.
    
    Args:
        words: List of word dictionaries
        tolerance: X-position tolerance for clustering
        
    Returns:
        Dictionary mapping x position to list of words in that column
    """
    columns = {}
    
    for word in words:
        x0 = word["x0"]
        
        # Find existing column within tolerance
        found_column = None
        for col_x in columns.keys():
            if abs(x0 - col_x) <= tolerance:
                found_column = col_x
                break
        
        if found_column is not None:
            columns[found_column].append(word)
        else:
            columns[x0] = [word]
    
    return columns


def find_runner_anchors(words: List[Dict[str, Any]], y_tolerance: float = 5.0) -> List[Dict[str, Any]]:
    """
    Find runner number anchors (start of each runner block).
    Runner numbers are typically small integers (1, 2, 3, ...) at the start of a line.
    
    Args:
        words: List of word dictionaries
        y_tolerance: Y-position tolerance for same-line detection
        
    Returns:
        List of anchor words (runner numbers)
    """
    anchors = []
    
    for word in words:
        text = word["text"].strip()
        
        # Check if word is a small integer (1-30 for runner numbers)
        if text.isdigit() and 1 <= int(text) <= 30:
            # Check if this is at the start of a line (low x position)
            if word["x0"] < 100:  # Arbitrary threshold for "start of line"
                anchors.append(word)
    
    return anchors


def extract_block_words(words: List[Dict[str, Any]], anchor: Dict[str, Any], max_height: float = 50.0) -> List[Dict[str, Any]]:
    """
    Extract all words in a vertical block starting from an anchor.
    
    Args:
        words: List of all words on page
        anchor: Anchor word (e.g., runner number)
        max_height: Maximum vertical distance from anchor
        
    Returns:
        List of words in the block
    """
    block_words = []
    
    anchor_top = anchor["top"]
    anchor_bottom = anchor_top + max_height
    anchor_x0 = anchor["x0"]
    
    for word in words:
        # Check if word is in vertical range
        if anchor_top <= word["top"] <= anchor_bottom:
            # Check if word is to the right of or near anchor
            if word["x0"] >= anchor_x0 - 10:
                block_words.append(word)
    
    # Sort by top, then x0
    block_words.sort(key=lambda w: (w["top"], w["x0"]))
    
    return block_words


def group_words_by_line(words: List[Dict[str, Any]], y_tolerance: float = 5.0) -> List[List[Dict[str, Any]]]:
    """
    Group words into lines based on y position.
    
    Args:
        words: List of word dictionaries
        y_tolerance: Y-position tolerance for same-line detection
        
    Returns:
        List of lines, where each line is a list of words
    """
    if not words:
        return []
    
    # Sort by top position
    sorted_words = sorted(words, key=lambda w: w["top"])
    
    lines = []
    current_line = [sorted_words[0]]
    current_y = sorted_words[0]["top"]
    
    for word in sorted_words[1:]:
        if abs(word["top"] - current_y) <= y_tolerance:
            # Same line
            current_line.append(word)
        else:
            # New line
            lines.append(current_line)
            current_line = [word]
            current_y = word["top"]
    
    # Add last line
    if current_line:
        lines.append(current_line)
    
    return lines


def extract_text_from_line(line: List[Dict[str, Any]]) -> str:
    """
    Extract text from a line of words.
    
    Args:
        line: List of word dictionaries
        
    Returns:
        Combined text string
    """
    # Sort by x position
    sorted_words = sorted(line, key=lambda w: w["x0"])
    
    # Join text with spaces
    return " ".join(w["text"] for w in sorted_words)
