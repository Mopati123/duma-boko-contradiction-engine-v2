#!/usr/bin/env python3

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evidence.proof_carrying_report_assembly import build_proof_carrying_report_assembly


def parse_args():
    parser = argparse.ArgumentParser(
        description="Build proof-carrying report assembly preflight manifest."
    )
    parser.add_argument("--dry-run", action="store_true", help="Dry-run only.")
    parser.add_argument("--case-id", help="Optional case ID filter.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    result = build_proof_carrying_report_assembly(case_id=args.case_id)
    summary = result["summary"]

    print("== Proof-Carrying Report Assembly Engine v1 summary ==")
    print("Mode: dry-run")

    if args.case_id:
        print("case_id:", args.case_id)

    for key, value in summary.items():
        print(f"{key}: {value}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())