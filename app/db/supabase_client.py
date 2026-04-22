"""
app/db/supabase_client.py — SHIM
==================================
Compatibility shim. The canonical Supabase client lives at:
    src/data/supabase_client.py

This module previously provided a REST-based SupabaseClient that used
app.config.supabase_config. It is now a thin re-export so that any code
still importing from this path continues to work.

DO NOT add new logic here. Add it to src/data/supabase_client.py instead.
"""

from src.data.supabase_client import (  # noqa: F401
    SupabaseClient,
    get_supabase_client,
)

# Legacy alias: some older modules call get_client() from this path
get_client = get_supabase_client

__all__ = ["SupabaseClient", "get_supabase_client", "get_client"]
