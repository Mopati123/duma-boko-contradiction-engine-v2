#!/usr/bin/env python3
"""
claim_extractor.py - Extract political claims from translated segments.

Input: outputs/claims/translated_segments.json
Output: outputs/claims/claims.json

Extracts ONLY political claims:
- Promises, denials, policy positions, reversals
- Obligations, accusations, commitments
- Delivery claims, economic claims, healthcare claims
- Employment claims, governance claims, corruption claims
- Constitutional/legal claims

Does NOT extract random sentences or general statements.
"""

import os
import sys
import json
import re
import argparse
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from evidence.evidence_schema import Claim, save_json, load_json


# Claim type detection patterns
CLAIM_PATTERNS = {
    'promise': {
        'keywords': [
            'will', 'shall', 'promise', 'pledge', 'commit', 'commitment',
            'guarantee', 'assure', 'undertake', 'vow', 'swear',
            'deliver', 'provide', 'give', 'offer', 'ensure',
            'my government will', 'we will', 'i will', 'going to'
        ],
        'patterns': [
            r'\b(will|shall)\s+\w+',
            r'\b(promise|pledge|commit)\w*\b',
            r'\b(guarantee|assure)\w*\b',
            r'\b(deliver|provide)\s+(?:the|a|an|this|that|these|those|our|my)\b',
            r'\bwe\s+(?:will|shall|are\s+going\s+to)\s+\w+',
            r'\bmy\s+government\s+(?:will|shall)\s+\w+',
            r'\bcommitted\s+to\s+\w+',
        ],
        'first_person_required': False,
        'min_confidence': 0.5
    },
    'denial': {
        'keywords': [
            'deny', 'reject', 'refuse', 'not', 'never', 'no',
            'disagree', 'oppose', 'against', 'not true', 'false',
            'impossible', 'cannot', 'unable', 'will not', 'won\'t'
        ],
        'patterns': [
            r'\b(deny|reject|refuse)\w*\b',
            r'\b(not|never)\s+\w+',
            r'\b(no\s+(?:way|how|one))\b',
            r'\b(disagree|opposed?|against)\b',
            r'\b(not\s+(?:true|correct|accurate))\b',
            r'\b(impossible|cannot|can\'t|unable)\b',
            r'\bwill\s+not\b',
        ],
        'first_person_required': False,
        'min_confidence': 0.5
    },
    'policy_position': {
        'keywords': [
            'policy', 'position', 'stand', 'stance', 'view',
            'believe', 'think', 'consider', 'support', 'favor',
            'approach', 'strategy', 'plan', 'framework',
            'we support', 'we favor', 'our position', 'my view'
        ],
        'patterns': [
            r'\b(policy|position|stance)\w*\b',
            r'\b(stand|view)\s+on\s+\w+',
            r'\b(believe|think|consider)\s+that\b',
            r'\b(support|favor|endorse)\w*\b',
            r'\b(approach|strategy|plan)\s+(?:is|to)\b',
            r'\bwe\s+(?:support|favor|endorse)\b',
            r'\bour\s+(?:position|stance|view)\s+(?:is|on)\b',
        ],
        'first_person_required': False,
        'min_confidence': 0.5
    },
    'reversal': {
        'keywords': [
            'reversed', 'changed', 'shifted', 'flip', 'backtrack',
            'retract', 'withdraw', 'no longer', 'used to', 'before',
            'previously', 'now', 'different', 'revised'
        ],
        'patterns': [
            r'\b(reversed?|changed?|shifted?|flip)\w*\b',
            r'\b(backtrack|retract|withdraw)\w*\b',
            r'\bno\s+longer\b',
            r'\bused\s+to\b',
            r'\b(previously|before)\b.*\b(now|today)\b',
            r'\brevised\s+\w+',
            r'\bdifferent\s+(?:position|stance|view)\b',
        ],
        'first_person_required': False,
        'min_confidence': 0.6  # Higher threshold for reversals
    },
    'justification': {
        'keywords': [
            'because', 'since', 'as', 'due to', 'owing to',
            'reason', 'explain', 'justify', 'defend', 'rationale',
            'basis', 'ground', 'why', 'the reason'
        ],
        'patterns': [
            r'\b(because|since|as)\s+\w+',
            r'\b(due|owing)\s+to\b',
            r'\b(reason|explain|justify)\w*\b',
            r'\b(defend|rationale|basis|ground)\w*\b',
            r'\bthis\s+(?:is|was)\s+because\b',
            r'\bthe\s+reason\s+(?:is|was)\b',
        ],
        'first_person_required': False,
        'min_confidence': 0.4
    },
    'accusation': {
        'keywords': [
            'accuse', 'blame', 'fault', 'responsible', 'guilty',
            'failed', 'wrong', 'mistake', 'error', 'problem',
            'they failed', 'their fault', 'because of them'
        ],
        'patterns': [
            r'\b(accuse|blame)\w*\b',
            r'\b(fault|responsible|guilty)\b',
            r'\bfailed?\s+(?:to|the|in)\b',
            r'\b(wrong|mistake|error)\b',
            r'\bthey\s+(?:failed?|caused?|did)\b',
            r'\b(their|previous|former)\s+(?:fault|failure|mistake)\b',
        ],
        'first_person_required': False,
        'min_confidence': 0.5
    },
    'outcome_claim': {
        'keywords': [
            'achieved', 'accomplished', 'done', 'completed',
            'success', 'successful', 'result', 'outcome',
            'delivered', 'fulfilled', 'met', 'satisfied'
        ],
        'patterns': [
            r'\b(achieved?|accomplished?|done?|completed?)\b',
            r'\b(success|successful|result|outcome)\b',
            r'\bdelivered?\s+(?:on|the|what)\b',
            r'\bfulfilled?\s+(?:promise|commitment|pledge)\b',
            r'\bmet\s+(?:target|goal|objective)\b',
            r'\bsatisfied\s+(?:requirement|need)\b',
        ],
        'first_person_required': False,
        'min_confidence': 0.5
    }
}

# Governance/political keywords to boost confidence
POLITICAL_KEYWORDS = [
    'government', 'president', 'minister', 'policy', 'election', 'vote',
    'campaign', 'mandate', 'constitution', 'law', 'legal', 'legislation',
    'economy', 'jobs', 'employment', 'health', 'education', 'corruption',
    'development', 'nation', 'country', 'citizens', 'people'
]


# First-person indicators (for speaker detection)
FIRST_PERSON_INDICATORS = [
    'i ', 'i\'', 'we ', 'we\'', 'my ', 'our ', 'myself', 'ourselves',
    'me ', 'us '
]


def detect_speaker(text: str) -> str:
    """
    Detect speaker from text.
    Returns 'Duma Boko' if first-person patterns match, else 'Unknown'.
    """
    text_lower = text.lower()
    
    # Check for first-person indicators
    for indicator in FIRST_PERSON_INDICATORS:
        if indicator in text_lower:
            # Additional check: should sound like a leader/politician
            if any(kw in text_lower for kw in ['government', 'will', 'shall', 'promise', 'commit', 'we', 'my']):
                return 'Duma Boko'
    
    return 'Unknown'


def score_claim(text: str, claim_type: str, patterns: Dict) -> Tuple[float, List[str]]:
    """
    Score a text for being a specific claim type.
    
    Returns:
        (confidence_score, matched_keywords)
    """
    text_lower = text.lower()
    score = 0.0
    matched_keywords = []
    
    # Keyword matching
    for keyword in patterns['keywords']:
        if keyword.lower() in text_lower:
            score += 0.1
            matched_keywords.append(keyword)
    
    # Pattern matching
    for pattern in patterns['patterns']:
        if re.search(pattern, text_lower):
            score += 0.2
    
    # Boost for political context
    for keyword in POLITICAL_KEYWORDS:
        if keyword in text_lower:
            score += 0.05
    
    # Cap at 1.0
    score = min(score, 1.0)
    
    return score, matched_keywords


def extract_claims_from_segment(
    segment: Dict[str, Any],
    min_confidence: float = 0.5
) -> List[Claim]:
    """
    Extract all claims from a single segment.
    
    A segment can contain multiple claims of different types.
    """
    claims = []
    text = segment.get('translated_text', '')
    original_text = segment.get('original_text', '')
    
    if not text or len(text.strip()) < 10:
        return claims  # Too short to be a meaningful claim
    
    # Detect speaker
    speaker = detect_speaker(text)
    
    # Check each claim type
    for claim_type, patterns in CLAIM_PATTERNS.items():
        score, matched_keywords = score_claim(text, claim_type, patterns)
        
        # Apply type-specific minimum confidence
        min_type_confidence = patterns.get('min_confidence', 0.5)
        
        if score >= min_type_confidence and score >= min_confidence:
            claim = Claim(
                claim_id=f"{segment['segment_id']}_{claim_type}",
                segment_id=segment['segment_id'],
                source_video_id=segment['source_video_id'],
                source_transcript_file=segment['source_transcript_file'],
                start=segment['start'],
                end=segment['end'],
                speaker=speaker,
                topic='',  # Will be assigned by topic_clusterer
                claim_type=claim_type,
                original_text=original_text,
                translated_text=text,
                normalized_claim=text.strip(),
                confidence=round(score, 3),
                extraction_method='pattern_matching',
                keywords_matched=matched_keywords,
                metadata={
                    'translation_status': segment.get('translation_status', 'unknown'),
                    'language': segment.get('language', 'unknown')
                }
            )
            claims.append(claim)
    
    return claims


def extract_all_claims(
    translated_segments_path: Path,
    output_path: Path,
    min_confidence: float = 0.5,
    test_mode: bool = False
) -> Dict[str, Any]:
    """
    Extract claims from all translated segments.
    
    Args:
        translated_segments_path: Path to translated_segments.json
        output_path: Where to save claims.json
        min_confidence: Minimum confidence to include claim
        test_mode: If True, process only first 10 segments
    
    Returns:
        Dictionary with processing results and statistics
    """
    # Load translated segments
    data = load_json(translated_segments_path)
    segments = data.get('segments', [])
    
    print(f"Loaded {len(segments)} translated segments")
    
    if test_mode:
        segments = segments[:10]
        print(f"[TEST MODE] Processing only first {len(segments)} segments")
    
    all_claims = []
    stats = {
        'total_segments': len(segments),
        'segments_with_claims': 0,
        'total_claims': 0,
        'claims_by_type': {}
    }
    
    print(f"\nExtracting claims (min_confidence={min_confidence})...")
    
    for i, seg in enumerate(segments):
        claims = extract_claims_from_segment(seg, min_confidence)
        
        if claims:
            all_claims.extend(claims)
            stats['segments_with_claims'] += 1
            
            # Count by type
            for claim in claims:
                claim_type = claim.claim_type
                stats['claims_by_type'][claim_type] = stats['claims_by_type'].get(claim_type, 0) + 1
        
        stats['total_claims'] = len(all_claims)
        
        # Progress update
        if (i + 1) % 100 == 0 or i == len(segments) - 1:
            print(f"  Processed {i + 1}/{len(segments)} segments, found {len(all_claims)} claims...")
    
    # Build output
    output = {
        'metadata': {
            'created_at': datetime.now().isoformat(),
            'pipeline_stage': 'claim_extraction',
            'version': '1.0',
            'test_mode': test_mode,
            'min_confidence': min_confidence
        },
        'statistics': stats,
        'claims': [claim.to_dict() for claim in all_claims]
    }
    
    # Save output
    os.makedirs(output_path.parent, exist_ok=True)
    save_json(output, str(output_path))
    
    print(f"\n✓ Claim extraction complete")
    print(f"  Segments processed: {stats['total_segments']}")
    print(f"  Segments with claims: {stats['segments_with_claims']}")
    print(f"  Total claims found: {stats['total_claims']}")
    print(f"  Claims by type: {stats['claims_by_type']}")
    print(f"  Output: {output_path}")
    
    return output


def main():
    parser = argparse.ArgumentParser(
        description='Extract political claims from translated segments'
    )
    parser.add_argument(
        '--input',
        type=str,
        default='outputs/claims/translated_segments.json',
        help='Input translated segments file'
    )
    parser.add_argument(
        '--output',
        type=str,
        default='outputs/claims/claims.json',
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
        help='Process only first 10 segments (test mode)'
    )
    
    args = parser.parse_args()
    
    input_path = Path(args.input)
    output_path = Path(args.output)
    
    if not input_path.exists():
        print(f"ERROR: Input file not found: {input_path}")
        print("Run translator.py first.")
        sys.exit(1)
    
    result = extract_all_claims(
        input_path,
        output_path,
        min_confidence=args.min_confidence,
        test_mode=args.test_one
    )
    
    # Return success if we found at least one claim
    if result['statistics']['total_claims'] > 0:
        sys.exit(0)
    else:
        print("WARNING: No claims found")
        # Still success - empty is valid, just warn
        sys.exit(0)


if __name__ == '__main__':
    main()
