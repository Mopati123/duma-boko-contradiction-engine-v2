#!/usr/bin/env python3

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evidence.case_graph_normalization import build_case_graph_normalization


def parse_args():
    parser = argparse.ArgumentParser(
        description="Build case graph normalization candidates."
    )
    parser.add_argument("--dry-run", action="store_true", help="Dry-run only.")
    parser.add_argument("--evidence-id", help="Optional evidence ID filter.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    result = build_case_graph_normalization(evidence_id=args.evidence_id)
    summary = result["summary"]

    print("== Case Graph Normalization Engine v1 summary ==")
    print("Mode: dry-run")

    if args.evidence_id:
        print("evidence_id:", args.evidence_id)

    for key, value in summary.items():
        print(f"{key}: {value}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())