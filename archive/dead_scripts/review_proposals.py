"""
VÉLØ — Governance Proposal Reviewer
=====================================
CLI for human review of PENDING doctrine proposals.

Usage:
    python scripts/review_proposals.py list [--status STATUS] [--type TYPE]
    python scripts/review_proposals.py show <proposal_id>
    python scripts/review_proposals.py accept <proposal_id> --reviewer <id> --rationale "text"
    python scripts/review_proposals.py reject <proposal_id> --reviewer <id> --rationale "text"
    python scripts/review_proposals.py rollback <proposal_id> --reviewer <id> --rationale "text"
    python scripts/review_proposals.py stats
    python scripts/review_proposals.py versions

Hard rules:
- No auto-accept. Every ACCEPT is a deliberate human keypress.
- Every decision is immutably written to governance_ledger.
- Doctrine version bumps only on ACCEPT.
"""
import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

SUPA_URL = os.getenv("SUPABASE_URL", "")
SUPA_KEY = (
    os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    or os.getenv("SUPABASE_SERVICE_KEY")
    or os.getenv("SUPABASE_ANON_KEY", "")
)


# ── Formatting helpers ────────────────────────────────────────────────────────

def _fmt_proposal(p: dict) -> str:
    lines = [
        f"ID:            {p.get('id', '?')}",
        f"Status:        {p.get('status', '?')}",
        f"Severity:      {p.get('severity', '?')}",
        f"Critic type:   {p.get('critic_type', '?')}",
        f"Finding type:  {p.get('finding_type', '?')}",
        f"Description:   {p.get('description', '')}",
        f"Source race:   {p.get('source_race_id') or '(pattern-level)'}",
        f"Pattern name:  {p.get('source_pattern_name') or '(none)'}",
        f"Created at:    {p.get('created_at', '?')}",
    ]
    if p.get("reviewed_at"):
        lines += [
            f"Reviewed at:   {p['reviewed_at']}",
            f"Reviewer:      {p.get('reviewer_id', '?')}",
            f"Rationale:     {p.get('review_rationale', '')}",
            f"Version before:{p.get('doctrine_version_before', '?')}",
            f"Version after: {p.get('doctrine_version_after', '?')}",
        ]
    pc = p.get("proposed_change")
    if pc:
        pc_str = json.dumps(pc, indent=2) if isinstance(pc, dict) else str(pc)
        lines.append(f"\nProposed change:\n{pc_str}")
    ledger = p.get("ledger_history", [])
    if ledger:
        lines.append(f"\nLedger history ({len(ledger)} entries):")
        for e in ledger:
            lines.append(
                f"  [{e.get('timestamp', '?')}] {e.get('action', '?')} "
                f"by {e.get('actor', '?')}: {e.get('rationale', '')}"
            )
    return "\n".join(lines)


def _fmt_list_row(p: dict) -> str:
    return (
        f"  {p.get('id', '?')[:8]}…  "
        f"{p.get('severity', '?'):8s}  "
        f"{p.get('critic_type', '?'):8s}  "
        f"{p.get('finding_type', '?'):30s}  "
        f"{p.get('status', '?')}"
    )


# ── Commands ──────────────────────────────────────────────────────────────────

def cmd_list(gov, args):
    status = getattr(args, "status", None)
    ctype  = getattr(args, "type", None)
    rows   = gov.list_proposals(status=status, critic_type=ctype, limit=200)
    if not rows:
        print("No proposals found.")
        return
    header = f"  {'ID':10s}  {'SEVERITY':8s}  {'CRITIC':8s}  {'FINDING_TYPE':30s}  STATUS"
    print(header)
    print("  " + "─" * 80)
    for p in rows:
        print(_fmt_list_row(p))
    print(f"\nTotal: {len(rows)}")


def cmd_show(gov, args):
    p = gov.get_proposal(args.proposal_id)
    if not p:
        print(f"Proposal {args.proposal_id!r} not found.")
        sys.exit(1)
    print(_fmt_proposal(p))


def cmd_accept(gov, args):
    reviewer = args.reviewer
    rationale = args.rationale
    change_type = getattr(args, "change_type", "MINOR")

    print(f"\n  Accepting proposal {args.proposal_id}")
    print(f"  Reviewer:  {reviewer}")
    print(f"  Rationale: {rationale}")
    print(f"  Change type: {change_type}")
    print()
    confirm = input("  Type YES to confirm: ").strip()
    if confirm != "YES":
        print("  Aborted.")
        sys.exit(0)

    result = gov.accept_proposal(
        proposal_id=args.proposal_id,
        reviewer_id=reviewer,
        rationale=rationale,
        change_type=change_type,
    )
    print(f"\n  ACCEPTED. Doctrine {result['previous_version']} → {result['doctrine_version']}")


def cmd_reject(gov, args):
    result = gov.reject_proposal(
        proposal_id=args.proposal_id,
        reviewer_id=args.reviewer,
        rationale=args.rationale,
    )
    print(f"\n  REJECTED: {result['status']}")


def cmd_rollback(gov, args):
    result = gov.rollback_proposal(
        proposal_id=args.proposal_id,
        reviewer_id=args.reviewer,
        rationale=args.rationale,
    )
    print(f"\n  ROLLED BACK: {result['status']}")


def cmd_stats(gov, _args):
    s = gov.get_stats()
    print("\n  Governance Stats")
    print("  " + "─" * 40)
    print(f"  Active doctrine version : {s['doctrine_version']}")
    print(f"  Total doctrine versions : {s['doctrine_version_count']}")
    print(f"  Proposals DRAFT         : {s['proposals_draft']}")
    print(f"  Proposals PENDING       : {s['proposals_pending']}")
    print(f"  Proposals ACCEPTED      : {s['proposals_accepted']}")
    print(f"  Proposals REJECTED      : {s['proposals_rejected']}")
    print(f"  Proposals ROLLED_BACK   : {s['proposals_rolled_back']}")
    print(f"  Acceptance rate         : {s['acceptance_rate']:.1%}")


def cmd_versions(gov, _args):
    rows = gov.get_doctrine_versions(limit=20)
    if not rows:
        print("No doctrine versions found.")
        return
    print("\n  Doctrine Version History")
    print("  " + "─" * 60)
    for v in rows:
        active_marker = " ← ACTIVE" if v.get("active") else ""
        print(f"  {v.get('version', '?'):10s}  "
              f"{v.get('created_at', '?')[:19]}  "
              f"{v.get('created_by', '?'):15s}  "
              f"{v.get('description', '')[:40]}"
              f"{active_marker}")


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    if not SUPA_URL or not SUPA_KEY:
        raise EnvironmentError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")

    from supabase import create_client
    from src.v13.governance.api import GovernanceAPI

    db  = create_client(SUPA_URL, SUPA_KEY)
    gov = GovernanceAPI(db)

    parser = argparse.ArgumentParser(description="VÉLØ Governance Proposal Reviewer")
    sub    = parser.add_subparsers(dest="command")

    # list
    p_list = sub.add_parser("list", help="List proposals")
    p_list.add_argument("--status", help="Filter by status (DRAFT/PENDING/ACCEPTED/REJECTED)")
    p_list.add_argument("--type",   help="Filter by critic_type (SIGMA/RPD/FEATURE/etc.)")

    # show
    p_show = sub.add_parser("show", help="Show proposal details")
    p_show.add_argument("proposal_id")

    # accept
    p_acc = sub.add_parser("accept", help="Accept a PENDING proposal")
    p_acc.add_argument("proposal_id")
    p_acc.add_argument("--reviewer",    required=True, help="Reviewer ID")
    p_acc.add_argument("--rationale",   required=True, help="Rationale for acceptance")
    p_acc.add_argument("--change-type", default="MINOR",
                       choices=["MAJOR", "MINOR", "PATCH"],
                       help="Doctrine version bump type (default: MINOR)")

    # reject
    p_rej = sub.add_parser("reject", help="Reject a PENDING proposal")
    p_rej.add_argument("proposal_id")
    p_rej.add_argument("--reviewer",  required=True, help="Reviewer ID")
    p_rej.add_argument("--rationale", required=True, help="Rationale for rejection")

    # rollback
    p_rb = sub.add_parser("rollback", help="Roll back an ACCEPTED proposal")
    p_rb.add_argument("proposal_id")
    p_rb.add_argument("--reviewer",  required=True, help="Reviewer ID")
    p_rb.add_argument("--rationale", required=True, help="Rationale for rollback")

    # stats
    sub.add_parser("stats", help="Governance dashboard stats")

    # versions
    sub.add_parser("versions", help="Doctrine version history")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(0)

    dispatch = {
        "list":     cmd_list,
        "show":     cmd_show,
        "accept":   cmd_accept,
        "reject":   cmd_reject,
        "rollback": cmd_rollback,
        "stats":    cmd_stats,
        "versions": cmd_versions,
    }

    try:
        dispatch[args.command](gov, args)
    except ValueError as e:
        print(f"\n  ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
