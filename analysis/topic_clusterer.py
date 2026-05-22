#!/usr/bin/env python3
"""
topic_clusterer.py - Group claims into topics using deterministic keyword rules.

Input: outputs/claims/claims.json, config/topics.yaml
Output: outputs/claims/topic_clustered_claims.json

Uses keyword matching from topics.yaml to assign each claim to a topic.
Completely deterministic - no ML models required.
"""

import os
import sys
import yaml
import argparse
from pathlib import Path
from typing import List, Dict, Any, Tuple
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from evidence.evidence_schema import Claim, save_json, load_json


def load_topics(config_path: Path) -> Dict[str, Any]:
    """Load topic definitions from YAML file."""
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def match_topic(
    claim_text: str,
    topics_config: Dict[str, Any]
) -> Tuple[str, int, List[str]]:
    """
    Match claim text to the best topic.
    
    Args:
        claim_text: The claim text to classify
        topics_config: Loaded topics.yaml configuration
    
    Returns:
        (topic_name, match_count, matched_keywords)
    """
    text_lower = claim_text.lower()
    
    topic_scores = {}
    topic_matches = {}
    
    # Score each topic
    for topic_name, topic_data in topics_config.get('topics', {}).items():
        keywords = topic_data.get('keywords', [])
        match_count = 0
        matched_keywords = []
        
        for keyword in keywords:
            keyword_lower = keyword.lower()
            # Check for whole word match
            if keyword_lower in text_lower:
                match_count += 1
                matched_keywords.append(keyword)
        
        topic_scores[topic_name] = match_count
        topic_matches[topic_name] = matched_keywords
    
    # Find best match
    best_topic = 'uncategorized'
    best_score = 0
    best_keywords = []
    
    matching_config = topics_config.get('matching', {})
    min_matches = matching_config.get('min_matches', 1)
    tiebreaker = matching_config.get('tiebreaker', 'highest_count')
    
    for topic_name, score in topic_scores.items():
        if score >= min_matches and score > best_score:
            best_topic = topic_name
            best_score = score
            best_keywords = topic_matches[topic_name]
        elif score >= min_matches and score == best_score and score > 0:
            # Tiebreaker
            if tiebreaker == 'highest_priority':
                # Lower priority number wins
                current_priority = topics_config['topics'].get(topic_name, {}).get('priority', 99)
                best_priority = topics_config['topics'].get(best_topic, {}).get('priority', 99)
                if current_priority < best_priority:
                    best_topic = topic_name
                    best_keywords = topic_matches[topic_name]
    
    return best_topic, best_score, best_keywords


def cluster_claims(
    claims_path: Path,
    topics_config_path: Path,
    output_path: Path,
    test_mode: bool = False
) -> Dict[str, Any]:
    """
    Cluster all claims into topics.
    
    Args:
        claims_path: Path to claims.json
        topics_config_path: Path to topics.yaml
        output_path: Where to save topic_clustered_claims.json
        test_mode: If True, process only first 10 claims
    
    Returns:
        Dictionary with processing results and statistics
    """
    # Load claims
    data = load_json(claims_path)
    claims_data = data.get('claims', [])
    
    print(f"Loaded {len(claims_data)} claims")
    
    # Load topics configuration
    topics_config = load_topics(topics_config_path)
    print(f"Loaded {len(topics_config.get('topics', {}))} topic definitions")
    
    if test_mode and claims_data:
        claims_data = claims_data[:10]
        print(f"[TEST MODE] Processing only first {len(claims_data)} claims")
    
    clustered_claims = []
    stats = {
        'total_claims': len(claims_data),
        'clustered_claims': 0,
        'uncategorized_claims': 0,
        'claims_by_topic': {}
    }
    
    print(f"\nClustering claims...")
    
    for i, claim_dict in enumerate(claims_data):
        # Match topic
        topic, match_count, matched_keywords = match_topic(
            claim_dict.get('translated_text', ''),
            topics_config
        )
        
        # Update claim with topic
        claim_dict['topic'] = topic
        claim_dict['topic_match_count'] = match_count
        claim_dict['topic_matched_keywords'] = matched_keywords
        
        clustered_claims.append(claim_dict)
        
        # Update stats
        stats['clustered_claims'] += 1
        if topic == 'uncategorized':
            stats['uncategorized_claims'] += 1
        
        stats['claims_by_topic'][topic] = stats['claims_by_topic'].get(topic, 0) + 1
        
        # Progress
        if (i + 1) % 100 == 0 or i == len(claims_data) - 1:
            print(f"  Processed {i + 1}/{len(claims_data)} claims...")
    
    # Build output
    output = {
        'metadata': {
            'created_at': datetime.now().isoformat(),
            'pipeline_stage': 'topic_clustering',
            'version': '1.0',
            'test_mode': test_mode,
            'topics_config': str(topics_config_path)
        },
        'statistics': stats,
        'claims': clustered_claims
    }
    
    # Save output
    os.makedirs(output_path.parent, exist_ok=True)
    save_json(output, str(output_path))
    
    print(f"\n✓ Topic clustering complete")
    print(f"  Total claims: {stats['total_claims']}")
    print(f"  Clustered: {stats['clustered_claims']}")
    print(f"  Uncategorized: {stats['uncategorized_claims']}")
    print(f"  Topics found: {len(stats['claims_by_topic'])}")
    print(f"  Claims by topic: {stats['claims_by_topic']}")
    print(f"  Output: {output_path}")
    
    return output


def main():
    parser = argparse.ArgumentParser(
        description='Cluster claims into topics using keyword rules'
    )
    parser.add_argument(
        '--input',
        type=str,
        default='outputs/claims/claims.json',
        help='Input claims file'
    )
    parser.add_argument(
        '--topics-config',
        type=str,
        default='config/topics.yaml',
        help='Topics configuration YAML file'
    )
    parser.add_argument(
        '--output',
        type=str,
        default='outputs/claims/topic_clustered_claims.json',
        help='Output file path'
    )
    parser.add_argument(
        '--test-one',
        action='store_true',
        help='Process only first 10 claims (test mode)'
    )
    
    args = parser.parse_args()
    
    claims_path = Path(args.input)
    topics_config_path = Path(args.topics_config)
    output_path = Path(args.output)
    
    if not claims_path.exists():
        print(f"ERROR: Input file not found: {claims_path}")
        print("Run claim_extractor.py first.")
        sys.exit(1)
    
    if not topics_config_path.exists():
        print(f"ERROR: Topics config not found: {topics_config_path}")
        sys.exit(1)
    
    result = cluster_claims(
        claims_path,
        topics_config_path,
        output_path,
        test_mode=args.test_one
    )
    
    # Return success
    sys.exit(0)


if __name__ == '__main__':
    main()
