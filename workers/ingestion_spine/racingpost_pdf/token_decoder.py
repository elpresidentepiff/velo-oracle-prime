"""
Racing Post PDF Parser - Token Decoder
Semantically decode OR/TS tokens like '80(1)', '82(1-2)', '75(v)'.
Handles both explicit bracket format and compact concatenated format.
"""

import re
from typing import Any


class TokenDecoder:
    """
    Decodes Racing Post history tokens.
    """
    
    # Matches '80(1)', '82(1-2)', '75(v)'
    EXPLICIT_RE = re.compile(r"^(?P<or>\d+)(?:\((?P<extra>.*?)\))?$")
    
    # Matches compact '180', '282' (Pos 1 OR 80, Pos 2 OR 82)
    # Positions are 1-9, OR marks are 40-180
    COMPACT_RE = re.compile(r"^(?P<pos>\d)(?P<or>(?:[4-9]\d|1[0-7]\d|180))(?P<tail>.*)$")
    
    def decode(self, token: str) -> dict[str, Any]:
        """
        Decode a single token.
        Returns: {or_mark: int, position: int | None, gear: str | None, is_win: bool}
        """
        if not token:
            return {"or_mark": None, "position": None, "gear": None, "is_win": False}
            
        cleaned = token.strip().lower()
        
        # Try explicit bracket format first
        match = self.EXPLICIT_RE.match(cleaned)
        if match and "(" in cleaned:
            or_mark = int(match.group("or"))
            extra = match.group("extra") or ""
            
            position = None
            gear = None
            is_win = False
            
            pos_match = re.search(r"(\d+)", extra)
            if pos_match:
                position = int(pos_match.group(1))
                if position == 1:
                    is_win = True
            
            gear_chars = "".join(c for c in extra if c.isalpha())
            if gear_chars:
                gear = gear_chars
                
            return {
                "or_mark": or_mark,
                "position": position,
                "gear": gear,
                "is_win": is_win
            }
            
        # Try compact format (e.g., '180')
        match = self.COMPACT_RE.match(cleaned)
        if match:
            or_mark = int(match.group("or"))
            position = int(match.group("pos"))
            is_win = (position == 1)
            tail = match.group("tail")
            gear = "".join(c for c in tail if c.isalpha()) or None
            
            return {
                "or_mark": or_mark,
                "position": position,
                "gear": gear,
                "is_win": is_win
            }
            
        # Fallback
        nums = re.findall(r"\d+", cleaned)
        mark = int(nums[0]) if nums else None
        return {"or_mark": mark, "position": None, "gear": None, "is_win": False}

    def infer_best_winning_life(self, tokens: list[str]) -> int | None:
        """Find the highest OR mark where is_win is True."""
        wins = []
        for token in tokens:
            decoded = self.decode(token)
            if decoded["is_win"] and decoded["or_mark"]:
                wins.append(decoded["or_mark"])
        return max(wins) if wins else None
