#!/usr/bin/env python3
"""
contradiction_engine.py - Detect contradictions in paired claims.

Input: outputs/pairs/candidate_pairs.json, config/contradiction_targets.yaml
Output: outputs/pairs/scored_pairs.json

Implements hybrid contradiction scoring:
- Rule-based: lexical opposition, topic agreement, claim type opposition
- Optional: HuggingFace NLI model if available (facebook/bart-large-mnli)

Works without NLI - rule-based is primary.
"""

import os
import sys
import yaml
import re
import argparse
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from evidence.evidence_schema import ContradictionScore, save_json, load_json


# Load NLI model (optional)
NLI_MODEL_NAME = "facebook/bart-large-mnli"
nli_model = None


def load_nli_model():
    """Attempt to load HuggingFace NLI model. Returns None if unavailable."""
    global nli_model
    if nli_model is not None:
        return nli_model
    
    try:
        from transformers import pipeline
        print(f"Loading NLI model: {NLI_MODEL_NAME}")
        nli_model = pipeline("zero-shot-classification", model=NLI_MODEL_NAME, device=-1)
        print(f"  ✓ NLI model loaded")
        return nli_model
    except ImportError:
        print("  ⚠ transformers not installed. Using rule-based only.")
        return None
    except Exception as e:
        print(f"  ⚠ Failed to load NLI model: {e}")
        return None


def load_contradiction_config(config_path: Path) -> Dict[str, Any]:
    """Load contradiction detection configuration."""
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def calculate_lexical_opposition(
    claim_a: Dict[str, Any],
    claim_b: Dict[str, Any],
    config: Dict[str, Any]
) -> Tuple[float, str]:
    """
    Calculate lexical opposition score based on keyword patterns.
    
    Returns:
        (score, reasoning)
    """
    text_a = claim_a.get('translated_text', '').lower()
    text_b = claim_b.get('translated_text', '').lower()
    
    contradiction_types = config.get('contradiction_types', {})
    
    best_score = 0.0
    best_type = None
    best_reason = "No lexical opposition detected"
    
    for contra_type, type_config in contradiction_types.items():
        score = 0.0
        matched = []
        
        # Check indicators from claim A
        indicators_a = type_config.get('lexical_indicators_a', [])
        for indicator in indicators_a:
            if indicator.lower() in text_a:
                score += 0.15
                matched.append(f"A:{indicator}")
        
        # Check indicators from claim B
        indicators_b = type_config.get('lexical_indicators_b', [])
        for indicator in indicators_b:
            if indicator.lower() in text_b:
                score += 0.15
                matched.append(f"B:{indicator}")
        
        # Check claim type match
        claim_a_types = type_config.get('claim_a_types', [])
        claim_b_types = type_config.get('claim_b_types', [])
        
        if claim_a.get('claim_type') in claim_a_types:
            score += 0.2
            matched.append(f"type_A:{claim_a.get('claim_type')}")
        
        if claim_b.get('claim_type') in claim_b_types:
            score += 0.2
            matched.append(f"type_B:{claim_b.get('claim_type')}")
        
        if score > best_score:
            best_score = score
            best_type = contra_type
            best_reason = f"{contra_type}: matched {', '.join(matched)}" if matched else f"{contra_type}: type match"
    
    return min(best_score, 1.0), best_reason


def calculate_topic_agreement(
    pair: Dict[str, Any],
    claim_a: Dict[str, Any],
    claim_b: Dict[str, Any]
) -> Tuple[float, str]:
    """Calculate topic agreement score."""
    topic_a = claim_a.get('topic', 'uncategorized')
    topic_b = claim_b.get('topic', 'uncategorized')
    pair_topic = pair.get('topic', 'uncategorized')
    
    if topic_a == topic_b == pair_topic:
        return 1.0, f"Same topic: {topic_a}"
    elif topic_a == topic_b:
        return 0.8, f"Related topics: {topic_a}"
    else:
        return 0.5, f"Different topics: {topic_a} vs {topic_b}"


def calculate_type_opposition(
    claim_a: Dict[str, Any],
    claim_b: Dict[str, Any],
    config: Dict[str, Any]
) -> Tuple[float, str]:
    """Calculate claim type opposition score."""
    type_a = claim_a.get('claim_type', '')
    type_b = claim_b.get('claim_type', '')
    
    contradiction_types = config.get('contradiction_types', {})
    
    # Check if this type pair matches any contradiction pattern
    for contra_type, type_config in contradiction_types.items():
        claim_a_types = type_config.get('claim_a_types', [])
        claim_b_types = type_config.get('claim_b_types', [])
        
        if type_a in claim_a_types and type_b in claim_b_types:
            return 1.0, f"Type opposition: {type_a} vs {type_b} ({contra_type})"
    
    # Some type pairs are inherently oppositional
    opposition_pairs = [
        ('promise', 'denial'),
        ('promise', 'reversal'),
        ('policy_position', 'reversal'),
        ('accusation', 'justification')
    ]
    
    if (type_a, type_b) in opposition_pairs:
        return 0.8, f"Oppositional types: {type_a} vs {type_b}"
    
    return 0.3, f"Types: {type_a} vs {type_b}"


def calculate_nli_score(
    claim_a: Dict[str, Any],
    claim_b: Dict[str, Any],
    model
) -> Tuple[Optional[float], Optional[str]]:
    """
    Calculate NLI contradiction score using HuggingFace model.
    
    Returns:
        (score, model_name) or (None, None) if model unavailable
    """
    if model is None:
        return None, None
    
    try:
        text_a = claim_a.get('translated_text', '')
        text_b = claim_b.get('translated_text', '')
        
        # Create hypothesis from claim B
        hypothesis = f"This contradicts: {text_b}"
        
        # Run NLI
        result = model(text_a, candidate_labels=["contradiction", "entailment", "neutral"])
        
        # Extract contradiction score
        labels = result.get('labels', [])
        scores = result.get('scores', [])
        
        if 'contradiction' in labels:
            idx = labels.index('contradiction')
            contra_score = scores[idx]
            return contra_score, NLI_MODEL_NAME
        
        return None, None
        
    except Exception as e:
        print(f"  NLI error: {e}")
        return None, None


def determine_evidence_strength(score: float, config: Dict[str, Any]) -> str:
    """Determine evidence strength from contradiction score."""
    thresholds = config.get('thresholds', {})
    
    high = thresholds.get('high_threshold', 0.7)
    medium = thresholds.get('medium_threshold', 0.5)
    low = thresholds.get('low_threshold', 0.3)
    
    if score >= high:
        return 'high'
    elif score >= medium:
        return 'medium'
    else:
        return 'low'


def detect_contradictions(
    candidate_pairs_path: Path,
    config_path: Path,
    output_path: Path,
    min_contradiction_score: float = 0.3,
    use_nli: bool = True,
    test_mode: bool = False
) -> Dict[str, Any]:
    """
    Detect contradictions in candidate pairs.
    
    Args:
        candidate_pairs_path: Path to candidate_pairs.json
        config_path: Path to contradiction_targets.yaml
        output_path: Where to save scored_pairs.json
        min_contradiction_score: Minimum score to include
        use_nli: Whether to attempt NLI scoring
        test_mode: If True, process only first 10 pairs
    
    Returns:
        Dictionary with processing results and statistics
    """
    # Load candidate pairs
    data = load_json(candidate_pairs_path)
    pairs = data.get('pairs', [])
    
    print(f"Loaded {len(pairs)} candidate pairs")
    
    # Load contradiction config
    config = load_contradiction_config(config_path)
    print(f"Loaded contradiction patterns: {len(config.get('contradiction_types', {}))} types")
    
    # Load NLI model if requested
    nli_model = None
    if use_nli:
        nli_model = load_nli_model()
    
    if test_mode and len(pairs) > 10:
        pairs = pairs[:10]
        print(f"[TEST MODE] Processing only first {len(pairs)} pairs")
    
    scored_pairs = []
    stats = {
        'total_pairs': len(pairs),
        'contradictions_found': 0,
        'by_strength': {'low': 0, 'medium': 0, 'high': 0},
        'by_type': {},
        'nli_used': 0,
        'nli_failed': 0
    }
    
    # Load claims lookup for reference
    # Note: We need to load claims to get full text for contradiction detection
    claims_lookup = {}
    
    print(f"\nDetecting contradictions (min_score={min_contradiction_score})...")
    
    for i, pair in enumerate(pairs):
        # Get claim previews from metadata
        metadata = pair.get('metadata', {})
        claim_a_preview = {
            'claim_type': metadata.get('claim_a_type'),
            'topic': pair.get('topic'),
            'speaker': metadata.get('claim_a_speaker'),
            'translated_text': metadata.get('claim_a_preview', ''),
            'confidence': pair.get('confidence_a', 0)
        }
        claim_b_preview = {
            'claim_type': metadata.get('claim_b_type'),
            'topic': pair.get('topic'),
            'speaker': metadata.get('claim_b_speaker'),
            'translated_text': metadata.get('claim_b_preview', ''),
            'confidence': pair.get('confidence_b', 0)
        }
        
        # Calculate component scores
        lexical_score, lexical_reason = calculate_lexical_opposition(
            claim_a_preview, claim_b_preview, config
        )
        topic_score, topic_reason = calculate_topic_agreement(
            pair, claim_a_preview, claim_b_preview
        )
        type_score, type_reason = calculate_type_opposition(
            claim_a_preview, claim_b_preview, config
        )
        
        # Calculate NLI score if available
        nli_score, nli_model_used = None, None
        if use_nli and nli_model:
            nli_score, nli_model_used = calculate_nli_score(
                claim_a_preview, claim_b_preview, nli_model
            )
            if nli_score is not None:
                stats['nli_used'] += 1
            else:
                stats['nli_failed'] += 1
        
        # Get scoring weights
        weights = config.get('scoring_weights', {})
        w_lexical = weights.get('lexical_opposition', 0.30)
        w_topic = weights.get('topic_agreement', 0.20)
        w_type = weights.get('type_opposition', 0.20)
        w_nli = weights.get('nli_score', 0.30)
        
        # Calculate final score
        if nli_score is not None:
            final_score = (
                lexical_score * w_lexical +
                topic_score * w_topic +
                type_score * w_type +
                nli_score * w_nli
            )
        else:
            # Normalize rule-based weights when NLI unavailable
            total_rule_weight = w_lexical + w_topic + w_type
            scale = 1.0 / total_rule_weight if total_rule_weight > 0 else 1.0
            final_score = (
                lexical_score * w_lexical * scale +
                topic_score * w_topic * scale +
                type_score * w_type * scale
            )
        
        final_score = round(final_score, 3)
        
        # Skip if below threshold
        if final_score < min_contradiction_score:
            continue
        
        # Determine contradiction type and strength
        # Extract type from lexical reason
        contra_type = lexical_reason.split(':')[0] if ':' in lexical_reason else 'unknown'
        strength = determine_evidence_strength(final_score, config)
        
        # Build reasoning
        reasoning_parts = [
            f"Lexical: {lexical_reason} (score: {lexical_score:.2f})",
            f"Topic: {topic_reason} (score: {topic_score:.2f})",
            f"Type: {type_reason} (score: {type_score:.2f})"
        ]
        if nli_score is not None:
            reasoning_parts.append(f"NLI: score {nli_score:.2f}")
        
        reasoning = " | ".join(reasoning_parts)
        
        # Create scored pair
        scored = ContradictionScore(
            pair_id=pair['pair_id'],
            claim_a_id=pair['claim_a_id'],
            claim_b_id=pair['claim_b_id'],
            contradiction_score=final_score,
            contradiction_type=contra_type,
            evidence_strength=strength,
            reasoning=reasoning,
            requires_manual_review=True,  # Always true for legal evidence
            lexical_score=round(lexical_score, 3),
            topic_agreement_score=round(topic_score, 3),
            type_opposition_score=round(type_score, 3),
            nli_score=round(nli_score, 3) if nli_score else None,
            nli_model_used=nli_model_used,
            claim_a_preview=claim_a_preview,
            claim_b_preview=claim_b_preview
        )
        
        scored_pairs.append(scored)
        
        # Update stats
        stats['contradictions_found'] += 1
        stats['by_strength'][strength] += 1
        stats['by_type'][contra_type] = stats['by_type'].get(contra_type, 0) + 1
        
        # Progress
        if (i + 1) % 100 == 0 or i == len(pairs) - 1:
            print(f"  Processed {i + 1}/{len(pairs)} pairs, found {len(scored_pairs)} contradictions...")
    
    # Build output
    output = {
        'metadata': {
            'created_at': datetime.now().isoformat(),
            'pipeline_stage': 'contradiction_detection',
            'version': '1.0',
            'test_mode': test_mode,
            'min_contradiction_score': min_contradiction_score,
            'nli_available': nli_model is not None
        },
        'statistics': stats,
        'scored_pairs': [pair.to_dict() for pair in scored_pairs]
    }
    
    # Save output
    os.makedirs(output_path.parent, exist_ok=True)
    save_json(output, str(output_path))
    
    print(f"\n✓ Contradiction detection complete")
    print(f"  Total pairs evaluated: {stats['total_pairs']}")
    print(f"  Contradictions found: {stats['contradictions_found']}")
    print(f"  By strength: {stats['by_strength']}")
    print(f"  By type: {stats['by_type']}")
    print(f"  NLI used: {stats['nli_used']}, failed: {stats['nli_failed']}")
    print(f"  Output: {output_path}")
    
    return output


def main():
    parser = argparse.ArgumentParser(
        description='Detect contradictions in claim pairs'
    )
    parser.add_argument(
        '--input',
        type=str,
        default='outputs/pairs/candidate_pairs.json',
        help='Input candidate pairs file'
    )
    parser.add_argument(
        '--config',
        type=str,
        default='config/contradiction_targets.yaml',
        help='Contradiction config YAML file'
    )
    parser.add_argument(
        '--output',
        type=str,
        default='outputs/pairs/scored_pairs.json',
        help='Output file path'
    )
    parser.add_argument(
        '--min-contradiction-score',
        type=float,
        default=0.3,
        help='Minimum contradiction score threshold'
    )
    parser.add_argument(
        '--test-one',
        action='store_true',
        help='Process only first 10 pairs (test mode)'
    )
    parser.add_argument(
        '--no-nli',
        action='store_true',
        help='Disable NLI scoring (rule-based only)'
    )
    
    args = parser.parse_args()
    
    input_path = Path(args.input)
    config_path = Path(args.config)
    output_path = Path(args.output)
    
    if not input_path.exists():
        print(f"ERROR: Input file not found: {input_path}")
        print("Run temporal_pairer.py first.")
        sys.exit(1)
    
    if not config_path.exists():
        print(f"ERROR: Config file not found: {config_path}")
        sys.exit(1)
    
    result = detect_contradictions(
        input_path,
        config_path,
        output_path,
        min_contradiction_score=args.min_contradiction_score,
        use_nli=not args.no_nli,
        test_mode=args.test_one
    )
    
    # Return success
    sys.exit(0)


if __name__ == '__main__':
    main()
