#!/usr/bin/env python3
"""
Assemble report-section payloads from deterministic fixtures.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evidence.report_section_assembly import assemble_report_sections_fixture_only


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Assemble report sections without final report generation."
    )
    parser.add_argument(
        "--fixtures-only",
        action="store_true",
        help="Use deterministic test fixtures only.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.fixtures_only:
        print("ERROR: Report Section Assembly v1 supports --fixtures-only only.")
        return 1

    summary = assemble_report_sections_fixture_only()
    print("== Report section assembly summary ==")
    print("Mode: fixtures-only")
    print(f"Total case links processed: {summary['processed']}")
    print(f"sections_candidate: {summary['sections_candidate']}")
    print(f"sections_verified: {summary['sections_verified']}")
    print(f"sections_rejected: {summary['sections_rejected']}")
    print(f"sections_unavailable: {summary['sections_unavailable']}")
    print(f"cases_represented: {summary['cases_represented']}")
    print(f"evidence_ids_represented: {summary['evidence_ids_represented']}")
    print(f"Output: {summary['output_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
