#!/usr/bin/env python3

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evidence.anchor_verification_engine import build_anchor_verification


def parse_args():
    parser = argparse.ArgumentParser(
        description="Build anchor verification records."
    )
    parser.add_argument("--dry-run", action="store_true", help="Dry-run only.")
    parser.add_argument("--publication-root", help="Expected publication root.")
    parser.add_argument("--receipt-hash", help="Expected publication receipt hash.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    result = build_anchor_verification(
        expected_publication_root=args.publication_root,
        expected_receipt_hash=args.receipt_hash,
    )
    summary = result["summary"]

    print("== Anchor Verification Engine v1 summary ==")
    print("Mode: dry-run")

    for key, value in summary.items():
        print(f"{key}: {value}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())