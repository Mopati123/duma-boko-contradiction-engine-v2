#!/usr/bin/env python3
"""
Run deterministic Final Report Hardening v1 dry-run.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evidence.final_report_hardening import harden_final_report_dry_run


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate review-draft final report hardening metadata."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate deterministic hardening metadata only.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.dry_run:
        print("ERROR: Final Report Hardening v1 supports --dry-run only.")
        return 1

    summary = harden_final_report_dry_run()
    print("== Final Report Hardening v1 summary ==")
    print("Mode: dry-run")
    print(f"hardening_id: {summary['hardening_id']}")
    print(f"report_id: {summary['report_id']}")
    print(f"hardening_status: {summary['hardening_status']}")
    print(f"release_status: {summary['release_status']}")
    print(f"public_ready: {summary['public_ready']}")
    print(f"institutional_ready: {summary['institutional_ready']}")
    print(f"report_ready: {summary['report_ready']}")
    print(f"record_output: {summary['record_output']}")
    print(f"summary_output: {summary['summary_output']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
