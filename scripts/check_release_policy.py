#!/usr/bin/env python3
"""
Run deterministic Release Policy v1 dry-run.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evidence.release_policy import check_release_policy_dry_run


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate the local-CI release policy dry-run."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate deterministic release-policy metadata only.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.dry_run:
        print("ERROR: Release Policy v1 supports --dry-run only.")
        return 1

    summary = check_release_policy_dry_run()
    print("== Release Policy v1 summary ==")
    print("Mode: dry-run")
    print(f"policy_id: {summary['policy_id']}")
    print(f"policy_status: {summary['policy_status']}")
    print(f"local_ci_authority: {summary['local_ci_authority']}")
    print(f"github_actions_status: {summary['github_actions_status']}")
    print(f"manual_override_allowed: {summary['manual_override_allowed']}")
    print(f"public_ready: {summary['public_ready']}")
    print(f"institutional_ready: {summary['institutional_ready']}")
    print(f"report_ready: {summary['report_ready']}")
    print(f"record_output: {summary['record_output']}")
    print(f"summary_output: {summary['summary_output']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
