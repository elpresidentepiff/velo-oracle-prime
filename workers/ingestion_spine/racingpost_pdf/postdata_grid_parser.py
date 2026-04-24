"""
Racing Post PDF Parser - Postdata Grid Parser
Semantically map the tick/cross grid to specific columns (Trainer, Going, etc.).
"""

from typing import Any


class PostdataGridParser:
    """
    Parses the 0011 Postdata summary grid.
    """
    
    # Standard layout: Trainer | Going | Dist | Course | Draw | Ability
    COLS = ["trainer", "going", "distance", "course", "draw", "ability"]
    
    def map_flags(self, flags_text: str) -> dict[str, Any]:
        """
        Map a raw string of ✓, ✘, ? into specific columns.
        Example: '✓ ✓ ✘ ✓ ? ✓'
        """
        if not flags_text:
            return {}
            
        # Standard tokens in Postdata grid
        tokens = flags_text.strip().split()
        
        result = {}
        for i, token in enumerate(tokens):
            if i < len(self.COLS):
                col_name = self.COLS[i]
                if "✓" in token:
                    val = "positive"
                elif "✘" in token:
                    val = "negative"
                elif "?" in token:
                    val = "unknown"
                else:
                    val = "neutral"
                result[f"{col_name}_flag"] = val
                    
        return result

    def get_trainer_signal(self, flags: dict[str, Any]) -> str:
        """Isolate the specific trainer form signal."""
        return flags.get("trainer_flag", "neutral")

    def is_cold_stable_plot(self, flags: dict[str, Any], release_window: bool) -> bool:
        """Logic: Trainer is cold (✘) but horse is in OR release window."""
        return flags.get("trainer_flag") == "negative" and release_window
