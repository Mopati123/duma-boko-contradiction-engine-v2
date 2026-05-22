#!/usr/bin/env python3
"""
case_builder.py - Build contradiction cases from scored pairs.

Supports both legacy semantic pipeline and new target-driven v2.0 pipeline.
"""

import os
import sys
import csv
import json
import argparse
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from evidence.evidence_schema import (
    ContradictionCase, TargetedContradictionCase, save_json, load_json
)


def build_targeted_cases(
    target_results_path: Path,
    output_path: Path
) -> List[Dict[str, Any]]:
    """
    Build TargetedContradictionCase objects from target_search results.
    
    Args:
        target_results_path: Path to target_search_results.json
        output_path: Path to save contradiction_cases_v2.json
        
    Returns:
        List of TargetedContradictionCase as dicts
    """
    print("\n" + "="*70)
    print("  BUILDING TARGETED CONTRADICTION CASES v2.0")
    print("="*70)
    
    if not target_results_path.exists():
        print(f"ERROR: Target results not found: {target_results_path}")
        return []
        
    data = load_json(target_results_path)
    target_results = data.get('target_results', [])
    
    cases = []
    
    for result in target_results:
        case_id = result.get('case_id')
        target = result.get('target', {})
        
        # Build the case object
        case = TargetedContradictionCase(
            case_id=case_id,
            topic=result.get('topic') or target.get('topic', 'unknown'),
            earlier_position=result.get('earlier_position') or {},
            later_position=result.get('later_position') or {},
            contradiction_type=result.get('contradiction_type') or target.get('contradiction_type', 'unknown'),
            analysis=result.get('analysis') or result.get('score_result', {}).get('analysis', ''),
            evidence_strength=result.get('evidence_strength', 'low'),
            status=result.get('status', 'pending'),
            description=target.get('description', ''),
            missing_evidence=result.get('missing_evidence', []),
            all_earlier_sources=result.get('all_earlier_sources', []),
            all_later_sources=result.get('all_later_sources', []),
            raw_urls=result.get('raw_urls', [])
        )
        
        cases.append(case.to_dict())
        print(f"  [v] Case {case_id} built: {case.status} ({case.evidence_strength})")
        
    # Save output
    output_json = {
        'metadata': {
            'created_at': datetime.now().isoformat(),
            'pipeline_stage': 'targeted_case_building',
            'version': '2.0',
            'total_cases': len(cases)
        },
        'cases': cases
    }
    
    os.makedirs(output_path.parent, exist_ok=True)
    save_json(output_json, str(output_path))
    print(f"\n[v] Saved {len(cases)} targeted cases to {output_path}")
    
    return cases


def build_legacy_cases(
    scored_pairs_path: Path,
    claims_path: Path,
    output_json_path: Path,
    output_csv_path: Path,
    test_mode: bool = False
) -> Dict[str, Any]:
    """Legacy build_cases implementation preserved for backward compatibility."""
    # Load scored pairs
    scored_data = load_json(scored_pairs_path)
    scored_pairs = scored_data.get('scored_pairs', [])
    
    # Load claims for full details
    claims_data = load_json(claims_path)
    claims_list = claims_data.get('claims', [])
    
    # Build claims lookup by claim_id
    claims_lookup = {claim['claim_id']: claim for claim in claims_list}
    
    cases = []
    for i, pair in enumerate(scored_pairs):
        claim_a = claims_lookup.get(pair['claim_a_id'], pair.get('claim_a_preview', {}))
        claim_b = claims_lookup.get(pair['claim_b_id'], pair.get('claim_b_preview', {}))
        
        case = ContradictionCase(
            case_id=f"LEGACY_{i + 1:04d}",
            pair_id=pair['pair_id'],
            claim_a_id=pair['claim_a_id'],
            claim_a_type=claim_a.get('claim_type', 'unknown'),
            claim_a_topic=claim_a.get('topic', 'uncategorized'),
            claim_a_original_text=claim_a.get('original_text', ''),
            claim_a_translated_text=claim_a.get('translated_text', ''),
            claim_a_source_video=claim_a.get('source_video_id', 'unknown'),
            claim_a_start=claim_a.get('start', 0.0),
            claim_a_end=claim_a.get('end', 0.0),
            claim_b_id=pair['claim_b_id'],
            claim_b_type=claim_b.get('claim_type', 'unknown'),
            claim_b_topic=claim_b.get('topic', 'uncategorized'),
            claim_b_original_text=claim_b.get('original_text', ''),
            claim_b_translated_text=claim_b.get('translated_text', ''),
            claim_b_source_video=claim_b.get('source_video_id', 'unknown'),
            claim_b_start=claim_b.get('start', 0.0),
            claim_b_end=claim_b.get('end', 0.0),
            contradiction_type=pair['contradiction_type'],
            contradiction_score=pair['contradiction_score'],
            evidence_strength=pair['evidence_strength'],
            reasoning=pair['reasoning'],
            metadata=pair.get('metadata', {})
        )
        cases.append(case.to_dict())
        
    output_json = {
        'metadata': {'total_cases': len(cases)},
        'cases': cases
    }
    save_json(output_json, str(output_json_path))
    return output_json


def main():
    parser = argparse.ArgumentParser(description='Build contradiction cases')
    parser.add_argument('--targeted', action='store_true', help='Use targeted v2.0 pipeline')
    parser.add_argument('--input', type=str, help='Input file path')
    parser.add_argument('--output', type=str, help='Output file path')
    
    args = parser.parse_args()
    
    if args.targeted:
        input_path = Path(args.input or 'outputs/target_search_results.json')
        output_path = Path(args.output or 'outputs/cases/targeted_cases.json')
        build_targeted_cases(input_path, output_path)
    else:
        # Legacy CLI logic
        pass

if __name__ == '__main__':
    main()
