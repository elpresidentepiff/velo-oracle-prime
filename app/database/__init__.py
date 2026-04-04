"""Database layer — re-exports from the canonical client at src/data/supabase_client.py"""

from app.database.supabase_client import supabase_client

__all__ = ["supabase_client"]
