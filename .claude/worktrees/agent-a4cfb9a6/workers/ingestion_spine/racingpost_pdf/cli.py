"""
Racing Post PDF Parser - CLI
Command-line interface for parsing PDFs.

Usage:
    python -m racingpost_pdf parse --inputs fixtures/WOL_*.pdf --out meeting.json
"""

import argparse
import json
import sys
from pathlib import Path

from . import parse_meeting


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(description="Racing Post PDF Parser")
    
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Parse command
    parse_parser = subparsers.add_parser("parse", help="Parse PDF files")
    parse_parser.add_argument(
        "--inputs",
        nargs="+",
        required=True,
        help="Input PDF files (XX, OR, TS, PM)"
    )
    parse_parser.add_argument(
        "--out",
        required=True,
        help="Output JSON file path"
    )
    parse_parser.add_argument(
        "--no-validate",
        action="store_true",
        help="Skip validation gates"
    )
    
    args = parser.parse_args()
    
    if args.command == "parse":
        # Parse PDFs
        print(f"Parsing {len(args.inputs)} PDF files...")
        
        report = parse_meeting(args.inputs, validate_output=not args.no_validate)
        
        if report.success:
            print(f"✅ Parse successful!")
            print(f"   Races: {report.stats.get('races_count', 0)}")
            print(f"   Runners: {report.stats.get('runners_count', 0)}")
            
            # Write output
            output_path = Path(args.out)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_path, "w") as f:
                # Serialize meeting to JSON
                if report.meeting:
                    json.dump(report.meeting.dict(), f, indent=2, default=str)
            
            print(f"   Output: {output_path}")
            
            # Write parse report
            report_path = output_path.with_suffix(".report.json")
            with open(report_path, "w") as f:
                json.dump(report.dict(exclude={"meeting"}), f, indent=2, default=str)
            
            print(f"   Report: {report_path}")
            
            sys.exit(0)
        else:
            print(f"❌ Parse failed!")
            print(f"   Errors: {len(report.errors)}")
            
            for error in report.errors:
                print(f"   - [{error.severity}] {error.message}")
                if error.location:
                    print(f"     Location: {error.location}")
            
            sys.exit(1)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
