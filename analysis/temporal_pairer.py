#!/usr/bin/env python3
"""
temporal_pairer.py - Pair claims temporally within the same topic.

Input: outputs/claims/topic_clustered_claims.json
Output: outputs/pairs/candidate_pairs.json

Pairs claims only when:
- Same or related topic
- Same speaker or speaker unknown
- Claim A occurs before Claim B (temporal order)
- Both claims have sufficient confidence
"""

import os
import sys
import argparse
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from evidence.evidence_schema import ClaimPair, save_json, load_json


def get_related_topics(topic: str) -> List[str]:
    """
    Get list of related topics for pairing.
    
    Related topics can form contradiction pairs even if not identical.
    """
    # Define topic relationships
    topic_relationships = {
        'governance': ['law', 'constitution', 'public_services', 'national_development'],
        'campaign_promises': ['governance', 'economy', 'jobs', 'national_development'],
        'economy': ['jobs', 'cost_of_living', 'mining', 'national_development'],
        'jobs': ['economy', 'youth', 'cost_of_living'],
        'healthcare': ['public_services', 'cost_of_living'],
        'corruption': ['governance', 'law', 'constitution'],
        'constitution': ['law', 'governance'],
        'law': ['constitution', 'governance', 'corruption'],
        'public_services': ['governance', 'healthcare', 'education'],
        'education': ['youth', 'public_services', 'national_development'],
        'cost_of_living': ['economy', 'jobs'],
        'mining': ['economy', 'national_development'],
        'youth': ['education', 'jobs'],
        'national_development': ['governance', 'economy', 'education']
    }
    
    # Return related topics plus the topic itself
    related = topic_relationships.get(topic, [])
    return [topic] + related


def can_pair_claims(
    claim_a: Dict[str, Any],
    claim_b: Dict[str, Any],
    min_confidence: float = 0.5,
    require_temporal_order: bool = True
) -> tuple:
    """
    Check if two claims can be paired.
    
    Returns:
        (can_pair: bool, reason: str, temporal_valid: bool)
    """
    # Check confidence thresholds
    if claim_a.get('confidence', 0) < min_confidence:
        return False, 'low_confidence_a', False
    
    if claim_b.get('confidence', 0) < min_confidence:
        return False, 'low_confidence_b', False
    
    # Check topic match
    topic_a = claim_a.get('topic', 'uncategorized')
    topic_b = claim_b.get('topic', 'uncategorized')
    
    # Get related topics for claim A
    related_topics = get_related_topics(topic_a)
    
    if topic_b not in related_topics:
        return False, 'topic_mismatch', False
    
    # Check speaker match
    speaker_a = claim_a.get('speaker', 'Unknown')
    speaker_b = claim_b.get('speaker', 'Unknown')
    
    # Allow pairing if same speaker OR if one is Unknown
    speaker_match = (speaker_a == speaker_b) or (speaker_a == 'Unknown') or (speaker_b == 'Unknown')
    
    if not speaker_match:
        return False, 'speaker_mismatch', False
    
    # Check temporal order (Claim A must be before Claim B)
    start_a = claim_a.get('start', 0)
    start_b = claim_b.get('start', 0)
    
    temporal_valid = start_a < start_b
    
    if require_temporal_order and not temporal_valid:
        return False, 'temporal_order_invalid', False
    
    # All checks passed
    reason = 'same_topic_temporal_candidate'
    if topic_a != topic_b:
        reason = 'related_topic_temporal_candidate'
    
    return True, reason, temporal_valid


def pair_claims(
    clustered_claims_path: Path,
    output_path: Path,
    min_confidence: float = 0.5,
    test_mode: bool = False
) -> Dict[str, Any]:
    """
    Create candidate claim pairs.
    
    Args:
        clustered_claims_path: Path to topic_clustered_claims.json
        output_path: Where to save candidate_pairs.json
        min_confidence: Minimum confidence for claims
        test_mode: If True, process only first 20 claims
    
    Returns:
        Dictionary with processing results and statistics
    """
    # Load clustered claims
    data = load_json(clustered_claims_path)
    claims = data.get('claims', [])
    
    print(f"Loaded {len(claims)} clustered claims")
    
    if test_mode and len(claims) > 20:
        claims = claims[:20]
        print(f"[TEST MODE] Processing only first {len(claims)} claims")
    
    candidate_pairs = []
    stats = {
        'total_claims': len(claims),
        'pairs_evaluated': 0,
        'pairs_created': 0,
        'pairs_by_topic': {},
        'rejection_reasons': {}
    }
    
    print(f"\nPairing claims (min_confidence={min_confidence})...")
    
    # Compare each claim with every other claim
    for i, claim_a in enumerate(claims):
        for j, claim_b in enumerate(claims):
            if i >= j:
                continue  # Avoid duplicates and self-pairs
            
            stats['pairs_evaluated'] += 1
            
            can_pair, reason, temporal_valid = can_pair_claims(
                claim_a, claim_b, min_confidence
            )
            
            if can_pair:
                pair = ClaimPair(
                    pair_id=f"pair_{claim_a['claim_id']}_{claim_b['claim_id']}",
                    claim_a_id=claim_a['claim_id'],
                    claim_b_id=claim_b['claim_id'],
                    topic=claim_a['topic'],  # Primary topic
                    temporal_order_valid=temporal_valid,
                    pair_reason=reason,
                    speaker_match=(claim_a.get('speaker') == claim_b.get('speaker')),
                    confidence_a=claim_a.get('confidence', 0),
                    confidence_b=claim_b.get('confidence', 0),
                    metadata={
                        'claim_a_type': claim_a.get('claim_type'),
                        'claim_b_type': claim_b.get('claim_type'),
                        'claim_a_speaker': claim_a.get('speaker'),
                        'claim_b_speaker': claim_b.get('speaker'),
                        'claim_a_preview': claim_a.get('translated_text', '')[:100],
                        'claim_b_preview': claim_b.get('translated_text', '')[:100]
                    }
                )
                
                candidate_pairs.append(pair)
                
                # Update stats
                topic = claim_a['topic']
                stats['pairs_by_topic'][topic] = stats['pairs_by_topic'].get(topic, 0) + 1
                stats['pairs_created'] += 1
            else:
                # Track rejection reason
                stats['rejection_reasons'][reason] = stats['rejection_reasons'].get(reason, 0) + 1
        
        # Progress
        if (i + 1) % 10 == 0 or i == len(claims) - 1:
            print(f"  Processed claim {i + 1}/{len(claims)}, created {len(candidate_pairs)} pairs...")
    
    # Build output
    output = {
        'metadata': {
            'created_at': datetime.now().isoformat(),
            'pipeline_stage': 'temporal_pairing',
            'version': '1.0',
            'test_mode': test_mode,
            'min_confidence': min_confidence
        },
        'statistics': stats,
        'pairs': [pair.to_dict() for pair in candidate_pairs]
    }
    
    # Save output
    os.makedirs(output_path.parent, exist_ok=True)
    save_json(output, str(output_path))
    
    print(f"\n✓ Temporal pairing complete")
    print(f"  Total claims: {stats['total_claims']}")
    print(f"  Pairs evaluated: {stats['pairs_evaluated']}")
    print(f"  Pairs created: {stats['pairs_created']}")
    print(f"  Pairs by topic: {stats['pairs_by_topic']}")
    print(f"  Rejection reasons: {stats['rejection_reasons']}")
    print(f"  Output: {output_path}")
    
    return output


def main():
    parser = argparse.ArgumentParser(
        description='Pair claims temporally within topics'
    )
    parser.add_argument(
        '--input',
        type=str,
        default='outputs/claims/topic_clustered_claims.json',
        help='Input clustered claims file'
    )
    parser.add_argument(
        '--output',
        type=str,
        default='outputs/pairs/candidate_pairs.json',
        help='Output file path'
    )
    parser.add_argument(
        '--min-confidence',
        type=float,
        default=0.5,
        help='Minimum confidence threshold for claims'
    )
    parser.add_argument(
        '--test-one',
        action='store_true',
        help='Process only first 20 claims (test mode)'
    )
    
    args = parser.parse_args()
    
    input_path = Path(args.input)
    output_path = Path(args.output)
    
    if not input_path.exists():
        print(f"ERROR: Input file not found: {input_path}")
        print("Run topic_clusterer.py first.")
        sys.exit(1)
    
    result = pair_claims(
        input_path,
        output_path,
        min_confidence=args.min_confidence,
        test_mode=args.test_one
    )
    
    # Return success
    sys.exit(0)


if __name__ == '__main__':
    main()
