#!/usr/bin/env python3
"""
Run deterministic Manual Review v1 dry-run records.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evidence.manual_review import manual_review_dry_run


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate conservative manual-review records."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate deterministic manual-review records only.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.dry_run:
        print("ERROR: Manual Review v1 supports --dry-run only.")
        return 1

    summary = manual_review_dry_run()
    print("== Manual Review v1 summary ==")
    print("Mode: dry-run")
    print(
        "total_evidence_records_reviewed: "
        f"{summary['total_evidence_records_reviewed']}"
    )
    print(f"pending_review: {summary['pending_review']}")
    print(f"reviewed_with_concerns: {summary['reviewed_with_concerns']}")
    print(f"reviewed_rejected: {summary['reviewed_rejected']}")
    print(f"reviewed_candidate: {summary['reviewed_candidate']}")
    print(f"public_ready: {summary['public_ready']}")
    print(f"report_ready: {summary['report_ready']}")
    print(f"records_output: {summary['records_output']}")
    print(f"summary_output: {summary['summary_output']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
