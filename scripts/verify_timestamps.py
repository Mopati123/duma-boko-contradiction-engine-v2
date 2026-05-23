#!/usr/bin/env python3
"""
Verify timestamp candidates from deterministic fixtures.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evidence.timestamp_verification import verify_timestamps_fixture_only


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify timestamp candidates without live network access."
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
        print("ERROR: Timestamp Verification v1 supports --fixtures-only only.")
        return 1

    summary = verify_timestamps_fixture_only()
    print("== Timestamp verification summary ==")
    print("Mode: fixtures-only")
    print(f"Total evidence records processed: {summary['processed']}")
    print(f"candidates_found: {summary['candidates_found']}")
    print(f"timestamp_verified: {summary['timestamp_verified']}")
    print(f"timestamp_rejected: {summary['timestamp_rejected']}")
    print(f"timestamp_unavailable: {summary['timestamp_unavailable']}")
    print(f"Output: {summary['output_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
