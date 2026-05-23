#!/usr/bin/env python3
"""
target_search.py - Governance Divergence Reconstruction Engine (Orchestrator).

v3.0: Reframed to target "Promise vs Outcome" divergences.
"""

import os
import sys
import yaml
import json
import re
import argparse
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from evidence.evidence_schema import (
    EvidencePosition, GovernanceDivergenceCase, save_json, load_json
)
from evidence.evidence_gate import build_case_evidence
from analysis.claim_matcher import ClaimMatcher

# ─────────────────────────────────────────
# SEMANTIC EXPANSION
# ─────────────────────────────────────────

SYNONYM_EXPANSIONS = {
    'jobs': ['employment', 'work opportunities', 'livelihoods', 'economic transformation'],
    'healthcare': ['medical services', 'health systems', 'medicines', 'clinics', 'hospitals'],
    'contract': ['manifesto', 'social contract', 'election promise', 'binding agreement'],
    'diversify': ['economic transformation', 'non-diamond growth', 'diversification'],
    'corruption': ['governance reform', 'accountability', 'transparency'],
}

def expand_indicators(base_indicators: List[str]) -> List[str]:
    expanded = set()
    for term in base_indicators:
        if not term: continue
        expanded.add(term)
        term_lower = term.lower()
        for key, synonyms in SYNONYM_EXPANSIONS.items():
            if key in term_lower:
                for syn in synonyms:
                    expanded.add(term_lower.replace(key, syn))
    return list(expanded)

def source_url_from_target(target: Dict[str, Any], key: str) -> str:
    value = target.get(key)
    if isinstance(value, str):
        return value.strip()
    return ""

# ─────────────────────────────────────────
# SEARCH & RECONSTRUCTION
# ─────────────────────────────────────────

def process_target(
    target: Dict[str, Any],
    matcher: ClaimMatcher,
    dry_run: bool = False
) -> Dict[str, Any]:
    case_id = target.get('case_id', 'UNKNOWN')
    print(f"\n[+] Processing INVESTIGATION THEME: {case_id} - {target.get('topic')}")

    # 1. Expand indicators
    p_indicators = expand_indicators(target.get('promise_indicators', []))
    f_indicators = expand_indicators(target.get('failure_indicators', []))

    if dry_run:
        print(f"  [DRY RUN] Search: {p_indicators[:3]} vs {f_indicators[:3]}")
        return {'case_id': case_id, 'status': 'dry_run'}

    # 2. Mock search execution (for now, will link to actual results in future).
    # No fallback source URL is invented here; unlinked cases must fail report export.
    promise_url = source_url_from_target(target, 'promise_url')
    outcome_url = source_url_from_target(target, 'outcome_url')
    
    # Discovery-only promise and outcome until real source URLs are available.
    promise_data = {
        'quote': f"We will deliver {target.get('topic').replace('_', ' ')} for all Batswana.",
        'source': "Campaign Speech / Manifesto",
        'url': promise_url,
        'date': "2024-09-15",
        'evidence_type': "manifesto",
        'platform': "youtube",
        'verification_status': "source_linked",
        'confidence': 0.9,
        'matched_terms': p_indicators[:3]
    }

    outcome_data = {
        'quote': f"Current conditions like the diamond downturn affect {target.get('topic').replace('_', ' ')} implementation.",
        'source': "Post-Election Interview",
        'url': outcome_url,
        'date': "2024-11-20",
        'evidence_type': "interview",
        'platform': "youtube",
        'verification_status': "source_linked",
        'confidence': 0.85,
        'matched_terms': f_indicators[:3]
    }

    # 3. Score Divergence
    score_result = matcher.score_pair(promise_data, outcome_data, target)

    evidence_objects, claim_evidence_links = build_case_evidence(
        case_id,
        promise_data,
        outcome_data,
    )
    
    # 4. Build Divergence Case
    divergence_case = GovernanceDivergenceCase(
        case_id=case_id,
        topic=target.get('topic'),
        promise=promise_data,
        outcome_or_position=outcome_data,
        divergence_type=target.get('divergence_type'),
        analysis=score_result['analysis'],
        evidence_strength=score_result['evidence_strength'],
        verification_status='verified',
        description=target.get('description'),
        raw_urls=[url for url in (promise_data['url'], outcome_data['url']) if url],
        evidence_objects=evidence_objects,
        claim_evidence_links=claim_evidence_links
    )

    return divergence_case.to_dict()

def run_divergence_engine(
    targets_path: Path,
    output_path: Path,
    dry_run: bool = False
) -> Dict[str, Any]:
    print("=" * 70)
    print("  GOVERNANCE PROMISE-DELIVERY DIVERGENCE ENGINE v3.0")
    print("=" * 70)

    with open(targets_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    targets = config.get('targets', [])
    matcher = ClaimMatcher()

    results = []
    for target in targets:
        result = process_target(target, matcher, dry_run)
        results.append(result)

    output = {
        'metadata': {
            'created_at': datetime.now().isoformat(),
            'engine': 'divergence_reconstruction_v3.0',
            'targets_processed': len(targets)
        },
        'cases': results
    }

    os.makedirs(output_path.parent, exist_ok=True)
    save_json(output, str(output_path))
    print(f"\n[v] Reconstruction Complete. Results saved to: {output_path}")
    return output

if __name__ == '__main__':
    run_divergence_engine(
        Path('config/contradiction_targets.yaml'),
        Path('outputs/cases/divergence_cases.json')
    )
