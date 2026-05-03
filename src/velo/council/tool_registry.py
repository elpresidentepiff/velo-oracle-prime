# Tool Registry for VÉLØ LLM Council
# Whitelisted scripts that the council can reference or trigger (in shadow mode)

WHITELISTED_TOOLS = {
    "vp30_operator_card": "scripts/place_signal_operator_card.py",
    "racing_api_enrichment_operator_card": "scripts/racing_api_enrichment_operator_card.py",
    "cashrun_detector": "scripts/cashrun_detector.py",
    "signal_promotion_board": "scripts/signal_promotion_board.py",
    "router_shadow_audit": "scripts/router_shadow_audit.py",
    "race_metadata_resolver": "src/velo/race_metadata_resolver.py",
}

def get_tool_path(tool_name):
    return WHITELISTED_TOOLS.get(tool_name)
