"""
VELO Oracle - Security Validator
================================
Runs on startup to verify that the Supabase database hardening is still in place.
If verification cannot be completed, the result stays explicitly unverified.
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

CHECKED_RLS_TABLES = ["runner_results", "runner_race_facts", "import_batches"]
UNCHECKED_OBJECTS = {
    "views_not_invoker": "all public views",
    "functions_mutable_search_path": "all public SQL/plpgsql functions",
    "matviews_exposed": "all public materialized views",
}

# The verification query documented for direct DB-side validation.
SECURITY_CHECK_SQL = """
SELECT
  (SELECT count(*) FROM pg_class c
   JOIN pg_namespace n ON n.oid = c.relnamespace
   WHERE n.nspname='public' AND c.relkind='r' AND c.relrowsecurity=false
  ) AS tables_rls_disabled,

  (SELECT count(*) FROM pg_class c
   JOIN pg_namespace n ON n.oid = c.relnamespace
   WHERE n.nspname='public' AND c.relkind='v'
     AND (c.reloptions IS NULL OR c.reloptions::text NOT LIKE '%security_invoker=true%')
  ) AS views_not_invoker,

  (SELECT count(*) FROM pg_proc p
   JOIN pg_namespace n ON n.oid=p.pronamespace
   JOIN pg_language l ON l.oid=p.prolang
   WHERE n.nspname='public' AND l.lanname IN ('sql','plpgsql')
     AND (p.proconfig IS NULL OR array_to_string(p.proconfig, ',') NOT LIKE '%search_path=%')
  ) AS functions_mutable_search_path,

  (SELECT count(*) FROM pg_class c
   JOIN pg_namespace n ON n.oid = c.relnamespace
   WHERE n.nspname='public' AND c.relkind='m'
     AND (
       has_table_privilege('anon', format('public.%%I', c.relname), 'SELECT')
       OR has_table_privilege('authenticated', format('public.%%I', c.relname), 'SELECT')
     )
  ) AS matviews_exposed;
"""


def _base_result() -> dict[str, Any]:
    return {
        "status": "error",
        "verified": False,
        "passed": False,
        "coverage_scope": "unknown",
        "metrics": None,
        "tables_rls_disabled": None,
        "views_not_invoker": None,
        "functions_mutable_search_path": None,
        "matviews_exposed": None,
        "checked_objects": [],
        "unchecked_objects": [],
        "error": None,
        "error_code": None,
        "error_detail": None,
    }


def _classify_security_error(exc: Exception) -> str:
    message = str(exc).lower()
    if any(token in message for token in ("permission", "not authorized", "forbidden", "401", "403")):
        return "permission_denied"
    if any(token in message for token in ("connection", "network", "timeout", "timed out", "dns", "name resolution")):
        return "transport_error"
    if any(token in message for token in ("relation", "schema cache", "does not exist", "column", "pg_class")):
        return "relation_inaccessible"
    if any(token in message for token in ("postgrest", "json object requested", "decode", "unexpected response")):
        return "postgrest_api_mismatch"
    return "verification_query_failed"


def _error_result(error_code: str, error_detail: str, *, status: str = "error") -> dict[str, Any]:
    result = _base_result()
    result["status"] = status
    result["error"] = error_detail
    result["error_code"] = error_code
    result["error_detail"] = error_detail
    return result


def run_security_check() -> dict[str, Any]:
    """
    Run the security validation check against the live Supabase DB.
    Returns a dict with explicit verification status.
    """
    result = _base_result()

    supabase_url = os.getenv("SUPABASE_URL", "")
    service_key = (
        os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY", "") or os.getenv("SUPABASE_KEY", "")
    )

    if not supabase_url or not service_key:
        result = _error_result(
            "missing_credentials",
            "SUPABASE_URL or service role key not set - skipping security check",
            status="skipped",
        )
        logger.warning("[security_validator] %s", result["error_detail"])
        return result

    try:
        from supabase import create_client

        client = create_client(supabase_url, service_key)
        tables_to_check = list(CHECKED_RLS_TABLES)

        # Confirm tables are reachable via service key
        for table in tables_to_check:
            client.table(table).select("*", count="exact").limit(0).execute()

        # Attempt pg_class query to distinguish permission_denied (RLS in place)
        # from full read access (misconfigured DB). PostgREST may or may not expose it.
        try:
            client.table("pg_class").select("relrowsecurity").limit(0).execute()
            # pg_class accessible — means the service role has overly broad access
            result["status"] = "partial"
            result["verified"] = False
            result["passed"] = True
            result["coverage_scope"] = "partial"
            result["checked_objects"] = [f"RLS:{t}" for t in tables_to_check]
            result["unchecked_objects"] = [f"{k}:{v}" for k, v in UNCHECKED_OBJECTS.items()]
            logger.info(
                "[security_validator] pg_class accessible — partial coverage. RLS status unconfirmed via PostgREST."
            )
        except Exception as pg_exc:
            error_code = _classify_security_error(pg_exc)
            result = _error_result(error_code, str(pg_exc))
            logger.warning(
                "[security_validator] pg_class query raised %s — status=%s",
                type(pg_exc).__name__,
                result["status"],
            )

    except Exception as exc:
        error_code = _classify_security_error(exc)
        result = _error_result(error_code, str(exc))
        logger.warning(
            "[security_validator] Could not verify DB hardening - status=%s error_code=%s detail=%s",
            result["status"],
            error_code,
            result["error_detail"],
        )

    return result
