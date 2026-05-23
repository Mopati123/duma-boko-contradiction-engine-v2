#!/usr/bin/env python3
"""
Acquire transcript artifacts for seed EvidenceObjects.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evidence.transcript_acquisition import acquire_transcripts


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Acquire transcript artifacts for seed EvidenceObjects."
    )
    parser.add_argument(
        "--fixtures-only",
        action="store_true",
        help="Use deterministic fixture outcomes and do not contact YouTube.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = acquire_transcripts(fixtures_only=args.fixtures_only)

    print("== Transcript acquisition summary ==")
    print(f"Mode: {'fixtures-only' if args.fixtures_only else 'live'}")
    print(f"Total evidence records processed: {summary['processed']}")
    print(f"transcript_found: {summary['transcript_found']}")
    print(f"transcript_unavailable: {summary['transcript_unavailable']}")
    print(f"acquisition_failed: {summary['acquisition_failed']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
