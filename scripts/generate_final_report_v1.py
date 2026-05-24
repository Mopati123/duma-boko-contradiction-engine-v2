#!/usr/bin/env python3
"""
Generate a review-only Final Report v1 artifact from deterministic fixtures.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evidence.final_report_v1 import generate_final_report_fixture_only


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a review-only fixture report artifact."
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
        print("ERROR: Final Report Generation v1 supports --fixtures-only only.")
        return 1

    summary = generate_final_report_fixture_only()
    print("== Final Report Generation v1 summary ==")
    print("Mode: fixtures-only")
    print(f"report_id: {summary['report_id']}")
    print(f"report_status: {summary['report_status']}")
    print(f"sections_included: {summary['sections_included']}")
    print(f"evidence_ids_represented: {summary['evidence_ids_represented']}")
    print(f"output_docx: {summary['output_docx']}")
    print(f"output_payload: {summary['output_payload']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
