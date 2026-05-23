#!/usr/bin/env python3
"""
Build the normalized EvidenceObject index from seed records.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evidence.evidence_loader import DEFAULT_INDEX_PATH, build_evidence_index


def main() -> int:
    index = build_evidence_index()
    count = index["metadata"]["total_evidence_records"]
    print(f"Wrote {count} evidence records to {DEFAULT_INDEX_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
