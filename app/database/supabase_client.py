"""
app/database/supabase_client.py — SHIM
=======================================
Compatibility shim. The canonical Supabase client lives at:
    src/data/supabase_client.py

This module re-exports from the canonical source so that
    from app.database.supabase_client import supabase_client
continues to work without modification.

DO NOT add new logic here. Add it to src/data/supabase_client.py instead.
"""

from src.data.supabase_client import (  # noqa: F401
    SupabaseClient,
    get_supabase_client,
)

# Legacy singleton alias used by app/database/__init__.py and other modules.
# Lazily initialised to avoid crashing at import time when env vars are absent.
try:
    supabase_client = get_supabase_client()
except Exception:
    supabase_client = None  # type: ignore[assignment]

__all__ = ["SupabaseClient", "get_supabase_client", "supabase_client"]
