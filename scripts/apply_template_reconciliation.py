#!/usr/bin/env python3

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evidence.template_reconciliation_action import (
    run_reconciliation,
)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Apply governed template reconciliation actions."
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry-run only.",
    )

    parser.add_argument(
        "--write",
        action="store_true",
        help="Apply reconciliation writes.",
    )

    parser.add_argument(
        "--evidence-id",
        help="Optional evidence ID filter.",
    )

    return parser.parse_args()


def main() -> int:

    args = parse_args()

    if args.write and args.dry_run:
        raise ValueError("--write and --dry-run are mutually exclusive")

    write = bool(args.write)

    result = run_reconciliation(
        evidence_id=args.evidence_id,
        write=write,
    )

    summary = result["summary"]

    print("== Explicit Template Reconciliation Action v1 summary ==")

    print(
        "Mode:",
        "write" if write else "dry-run",
    )

    if args.evidence_id:
        print("evidence_id:", args.evidence_id)

    for key, value in summary.items():
        print(f"{key}: {value}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())