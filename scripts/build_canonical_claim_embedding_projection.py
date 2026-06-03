#!/usr/bin/env python3

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evidence.canonical_claim_embedding_projection import (
    build_canonical_claim_embedding_projection,
)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Build v2 canonical claim embedding projection."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate normalized claims without projecting embeddings.",
    )
    mode.add_argument(
        "--project",
        action="store_true",
        help="Project normalized claims into deterministic local embedding space.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    selected_mode = "project" if args.project else "dry-run"
    result = build_canonical_claim_embedding_projection(mode=selected_mode)
    print("== Canonical Claim Embedding Projection v2 summary ==")
    print(f"Mode: {selected_mode}")
    for key, value in result["summary"].items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
