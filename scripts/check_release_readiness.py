#!/usr/bin/env python3
"""
Run deterministic Release Readiness v1 dry-run.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evidence.release_readiness import check_release_readiness_dry_run


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate conservative public/institutional release readiness."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate deterministic release-readiness metadata only.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.dry_run:
        print("ERROR: Release Readiness v1 supports --dry-run only.")
        return 1

    summary = check_release_readiness_dry_run()
    print("== Release Readiness v1 summary ==")
    print("Mode: dry-run")
    print(f"readiness_id: {summary['readiness_id']}")
    print(f"report_id: {summary['report_id']}")
    print(f"release_status: {summary['release_status']}")
    print(f"release_blocked: {summary['release_blocked']}")
    print(f"public_ready: {summary['public_ready']}")
    print(f"institutional_ready: {summary['institutional_ready']}")
    print(f"report_ready: {summary['report_ready']}")
    print(f"blocker_count: {summary['blocker_count']}")
    print(f"record_output: {summary['record_output']}")
    print(f"summary_output: {summary['summary_output']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
