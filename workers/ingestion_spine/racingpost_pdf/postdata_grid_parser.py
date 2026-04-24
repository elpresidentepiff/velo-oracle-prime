"""
Racing Post PDF Parser - Postdata Grid Parser
Semantically map the tick/cross grid to specific columns (Trainer, Going, etc.).
"""

from typing import Any


class PostdataGridParser:
    """
    Parses the 0011 Postdata summary grid.
    
    The grid typically has columns for:
    - Trainer Form
    - Going
    - Distance
    - Course
    - Ability
    - Recent Form (often combined or near Draw)
    """
    
    def map_flags(self, flags_text: str) -> dict[str, Any]:
        """
        Map a raw string of ✓, ✘, ? into specific columns.
        This is a positional parser based on standard RP layout.
        """
        if not flags_text:
            return {}
            
        # Clean and split into individual characters/tokens
        tokens = flags_text.strip().split()
        
        # Standard layout: Trainer | Going | Dist | Course | Draw | Ability
        # Note: Layout can vary slightly between Flat/Jumps, but usually 5-6 columns.
        cols = ["trainer", "going", "distance", "course", "draw", "ability"]
        
        result = {}
        for i, token in enumerate(tokens):
            if i < len(cols):
                col_name = cols[i]
                if "✓" in token:
                    result[f"{col_name}_flag"] = "positive"
                elif "✘" in token:
                    result[f"{col_name}_flag"] = "negative"
                elif "?" in token:
                    result[f"{col_name}_flag"] = "unknown"
                else:
                    result[f"{col_name}_flag"] = "neutral"
                    
        return result

    def is_cold_stable_plot(self, flags: dict[str, str]) -> bool:
        """Logic: Trainer is cold (✘) but horse is otherwise ready."""
        return flags.get("trainer_flag") == "negative"
