"""
Racing Post PDF Parser - Token Decoder
Semantically decode OR/TS tokens like '80(1)', '82(1-2)', '75(v)'.
"""

import re
from typing import Any


class TokenDecoder:
    """
    Decodes Racing Post history tokens.
    
    Format example:
    - '80(1)': Position 1, OR 80
    - '82(1-2)': Position 2, OR 82
    - '75(v)': OR 75, Wearing Visor (v)
    """
    
    TOKEN_RE = re.compile(r"^(?P<or>\d+)(?:\((?P<extra>.*?)\))?$")
    
    def decode(self, token: str) -> dict[str, Any]:
        """
        Decode a single token.
        Returns: {or_mark: int, position: int | None, gear: str | None, is_win: bool}
        """
        if not token:
            return {"or_mark": None, "position": None, "gear": None, "is_win": False}
            
        match = self.TOKEN_RE.match(token.strip())
        if not match:
            # Fallback for tokens without brackets or non-standard ones
            nums = re.findall(r"\d+", token)
            mark = int(nums[0]) if nums else None
            return {"or_mark": mark, "position": None, "gear": None, "is_win": False}
            
        or_mark = int(match.group("or"))
        extra = match.group("extra") or ""
        
        position = None
        gear = None
        is_win = False
        
        if extra:
            # Check for position patterns like '1', '2', '1-2'
            pos_match = re.search(r"(\d+)", extra)
            if pos_match:
                position = int(pos_match.group(1))
                if position == 1:
                    is_win = True
            
            # Check for gear characters (usually lowercase letters)
            gear_chars = "".join(c for c in extra if c.isalpha())
            if gear_chars:
                gear = gear_chars
                
        return {
            "or_mark": or_mark,
            "position": position,
            "gear": gear,
            "is_win": is_win
        }

    def infer_best_winning_life(self, tokens: list[str]) -> int | None:
        """Find the highest OR mark where is_win is True."""
        wins = []
        for token in tokens:
            decoded = self.decode(token)
            if decoded["is_win"] and decoded["or_mark"]:
                wins.append(decoded["or_mark"])
        return max(wins) if wins else None
