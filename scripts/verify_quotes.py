#!/usr/bin/env python3
"""
Verify quote candidates from deterministic fixtures.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evidence.quote_verification import verify_quotes_fixture_only


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify quote candidates without live network access."
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
        print("ERROR: Quote Verification v1 supports --fixtures-only only.")
        return 1

    summary = verify_quotes_fixture_only()
    print("== Quote verification summary ==")
    print("Mode: fixtures-only")
    print(f"Total timestamp candidates processed: {summary['processed']}")
    print(f"quote_candidate_found: {summary['quote_candidate_found']}")
    print(f"quote_verified: {summary['quote_verified']}")
    print(f"quote_rejected: {summary['quote_rejected']}")
    print(f"quote_unavailable: {summary['quote_unavailable']}")
    print(f"Output: {summary['output_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
