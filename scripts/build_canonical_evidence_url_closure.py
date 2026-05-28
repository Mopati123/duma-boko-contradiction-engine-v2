#!/usr/bin/env python3

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evidence.canonical_evidence_url_closure import build_canonical_evidence_url_closure


def parse_args():
    parser = argparse.ArgumentParser(
        description="Build canonical evidence URL closure records."
    )
    parser.add_argument("--dry-run", action="store_true", help="Dry-run only.")
    parser.add_argument("--evidence-id", help="Optional evidence ID filter.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    result = build_canonical_evidence_url_closure(evidence_id=args.evidence_id)
    summary = result["summary"]

    print("== Canonical Evidence URL Closure Engine v1 summary ==")
    print("Mode: dry-run")

    if args.evidence_id:
        print("evidence_id:", args.evidence_id)

    for key, value in summary.items():
        print(f"{key}: {value}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())