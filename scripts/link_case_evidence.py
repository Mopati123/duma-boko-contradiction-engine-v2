#!/usr/bin/env python3
"""
Link quote candidates to case evidence objects from deterministic fixtures.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evidence.case_evidence_linking import link_case_evidence_fixture_only


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Link case evidence without live network access."
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
        print("ERROR: Case Evidence Linking v1 supports --fixtures-only only.")
        return 1

    summary = link_case_evidence_fixture_only()
    print("== Case evidence linking summary ==")
    print("Mode: fixtures-only")
    print(f"Total quote candidates processed: {summary['processed']}")
    print(f"link_candidate: {summary['link_candidate']}")
    print(f"link_verified: {summary['link_verified']}")
    print(f"link_rejected: {summary['link_rejected']}")
    print(f"link_unavailable: {summary['link_unavailable']}")
    print(f"cases_built: {summary['cases_built']}")
    print(f"claims_built: {summary['claims_built']}")
    print(f"report_sections_built: {summary['report_sections_built']}")
    print(f"Output: {summary['output_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
