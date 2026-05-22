#!/usr/bin/env python3
"""
Analyze contradictions using extracted statements as targets.
Compares all segments against key Duma Boko statements.
"""
import json
import re
from pathlib import Path
from typing import List, Dict, Tuple
from difflib import SequenceMatcher

# Key Duma Boko statements extracted from transcripts (TARGETS)
TARGET_STATEMENTS = [
    {
        "id": 1,
        "text": "So that when you go to the next election, a member of parliament, you can then say to the people, I deliver that",
        "theme": "elections_promises",
        "video": "AittyT1pssk",
        "keywords": ["election", "parliament", "deliver", "promise"]
    },
    {
        "id": 2,
        "text": "Things are going to be done. They are going to be done very quickly. They are going to be done very efficiently",
        "theme": "efficiency_action",
        "video": "AittyT1pssk",
        "keywords": ["done", "quickly", "efficiently", "action"]
    },
    {
        "id": 3,
        "text": "And the people protest. I say go ahead and protest. Make it known that you're angry",
        "theme": "protest_rights",
        "video": "AittyT1pssk",
        "keywords": ["protest", "angry", "people"]
    },
    {
        "id": 4,
        "text": "So I don't have the time to waste. The people of this country don't have time to wait",
        "theme": "urgency",
        "video": "AittyT1pssk",
        "keywords": ["time", "waste", "wait", "urgent"]
    },
    {
        "id": 5,
        "text": "It is the how. It is the strategy. Not the vision. It is the strategy that takes us from the east where we are to where we ought to be",
        "theme": "strategy",
        "video": "AittyT1pssk",
        "keywords": ["strategy", "vision", "how"]
    },
    {
        "id": 6,
        "text": "So we will not run short of the materials. And those panels are the best",
        "theme": "resources",
        "video": "AittyT1pssk",
        "keywords": ["materials", "resources", "short"]
    },
    {
        "id": 7,
        "text": "The most honest people on the face of the earth are two categories. People when they are drunk, people when they are angry",
        "theme": "honesty",
        "video": "AittyT1pssk",
        "keywords": ["honest", "drunk", "angry", "truth"]
    }
]

def similarity_score(text1: str, text2: str) -> float:
    """Calculate text similarity (0-1)."""
    return SequenceMatcher(None, text1.lower(), text2.lower()).ratio()

def keyword_overlap(text: str, keywords: List[str]) -> float:
    """Calculate keyword overlap score."""
    text_lower = text.lower()
    matches = sum(1 for kw in keywords if kw.lower() in text_lower)
    return matches / len(keywords) if keywords else 0

def is_contradiction(target: Dict, segment_text: str) -> Tuple[bool, float, str]:
    """
    Determine if segment contradicts target statement.
    Returns: (is_contradiction, confidence_score, reason)
    """
    target_text = target["text"].lower()
    seg_text = segment_text.lower()
    
    # Calculate similarity
    sim = similarity_score(target["text"], segment_text)
    
    # Calculate keyword overlap
    kw_score = keyword_overlap(segment_text, target["keywords"])
    
    # Check for opposite sentiment indicators
    opposite_indicators = [
        ("will", "won't"), ("will", "will not"), ("can", "cannot"),
        ("do", "don't"), ("are", "are not"), ("is", "is not"),
        ("support", "oppose"), ("agree", "disagree"),
        ("yes", "no"), ("true", "false"),
        ("efficient", "inefficient"), ("quick", "slow"),
        ("enough", "shortage"), ("best", "worst")
    ]
    
    opposite_found = False
    for pos, neg in opposite_indicators:
        if pos in target_text and neg in seg_text:
            opposite_found = True
            break
        if neg in target_text and pos in seg_text:
            opposite_found = True
            break
    
    # Contradiction criteria:
    # 1. Similar topic (keyword overlap >= 0.3)
    # 2. Either high similarity with opposite sentiment OR
    #    moderate similarity with clear opposite indicators
    
    if kw_score >= 0.3:
        if opposite_found and sim >= 0.3:
            return True, 0.7, "keyword_match_opposite_indicator"
        elif sim >= 0.5:
            # Similar topic but different position
            return True, 0.5, "similar_topic_different_position"
    
    return False, 0.0, ""

def analyze_contradictions():
    """Analyze all segments for contradictions to target statements."""
    print("="*70)
    print("TARGETED CONTRADICTION ANALYSIS")
    print("="*70)
    print(f"Analyzing {len(TARGET_STATEMENTS)} target statements\n")
    
    # Load extracted segments
    segments_file = Path("extracted_segments.json")
    if not segments_file.exists():
        print("[ERROR] extracted_segments.json not found")
        return
    
    with open(segments_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    all_segments = data.get('all_segments', [])
    print(f"Loaded {len(all_segments)} segments to analyze\n")
    
    contradictions_found = []
    
    for target in TARGET_STATEMENTS:
        print(f"\nAnalyzing Target #{target['id']}: {target['theme']}")
        print(f"  Text: {target['text'][:80]}...")
        print(f"  Keywords: {', '.join(target['keywords'])}")
        
        target_contradictions = []
        
        for segment in all_segments:
            seg_text = segment.get('text', '')
            
            # Skip if same video (avoid self-contradiction within same speech)
            if segment.get('video_id') == target['video']:
                continue
            
            # Check for contradiction
            is_contra, confidence, reason = is_contradiction(target, seg_text)
            
            if is_contra and confidence >= 0.5:
                contradiction = {
                    'target_id': target['id'],
                    'target_theme': target['theme'],
                    'target_text': target['text'],
                    'contradiction_text': seg_text,
                    'contradiction_video': segment.get('video_id'),
                    'contradiction_timestamp': segment.get('timestamp_start'),
                    'confidence': confidence,
                    'reason': reason,
                    'similarity_score': similarity_score(target['text'], seg_text),
                    'keyword_score': keyword_overlap(seg_text, target['keywords'])
                }
                target_contradictions.append(contradiction)
        
        # Sort by confidence
        target_contradictions.sort(key=lambda x: x['confidence'], reverse=True)
        
        print(f"  [FOUND] {len(target_contradictions)} potential contradictions")
        
        if target_contradictions:
            # Show top 3
            for i, contra in enumerate(target_contradictions[:3], 1):
                print(f"    {i}. [{contra['contradiction_video']} @ {contra['contradiction_timestamp']:.1f}s] "
                      f"Confidence: {contra['confidence']:.2f}")
                print(f"       {contra['contradiction_text'][:100]}...")
        
        contradictions_found.extend(target_contradictions)
    
    # Sort all contradictions by confidence
    contradictions_found.sort(key=lambda x: x['confidence'], reverse=True)
    
    # Save results
    output = {
        'analysis_date': '2025-01-23',
        'target_statements_count': len(TARGET_STATEMENTS),
        'total_segments_analyzed': len(all_segments),
        'total_contradictions_found': len(contradictions_found),
        'high_confidence_contradictions': [c for c in contradictions_found if c['confidence'] >= 0.7],
        'medium_confidence_contradictions': [c for c in contradictions_found if 0.5 <= c['confidence'] < 0.7],
        'all_contradictions': contradictions_found
    }
    
    output_file = Path("contradictions_analysis.json")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    # Also create CSV
    import csv
    csv_file = Path("contradictions_evidence.csv")
    with open(csv_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Target Theme', 'Target Statement', 'Contradiction Video', 
                        'Timestamp', 'Contradiction Text', 'Confidence', 'Reason'])
        
        for contra in contradictions_found:
            writer.writerow([
                contra['target_theme'],
                contra['target_text'][:100],
                contra['contradiction_video'],
                f"{contra['contradiction_timestamp']:.1f}s",
                contra['contradiction_text'][:150],
                f"{contra['confidence']:.2f}",
                contra['reason']
            ])
    
    print(f"\n{'='*70}")
    print("ANALYSIS COMPLETE")
    print(f"{'='*70}")
    print(f"Total contradictions found: {len(contradictions_found)}")
    print(f"High confidence (>=0.7): {len(output['high_confidence_contradictions'])}")
    print(f"Medium confidence (0.5-0.7): {len(output['medium_confidence_contradictions'])}")
    print(f"\nFiles saved:")
    print(f"  - contradictions_analysis.json")
    print(f"  - contradictions_evidence.csv")
    
    if contradictions_found:
        print(f"\n{'='*70}")
        print("TOP 10 CONTRADICTIONS (Highest Confidence)")
        print(f"{'='*70}")
        
        for i, contra in enumerate(contradictions_found[:10], 1):
            print(f"\n{i}. Target: {contra['target_theme']}")
            print(f"   Original: {contra['target_text'][:80]}...")
            print(f"   Contradiction: [{contra['contradiction_video']} @ {contra['contradiction_timestamp']:.1f}s]")
            print(f"   Text: {contra['contradiction_text'][:100]}...")
            print(f"   Confidence: {contra['confidence']:.2f} ({contra['reason']})")
    else:
        print(f"\n{'='*70}")
        print("NO CONTRADICTIONS FOUND")
        print(f"{'='*70}")
        print("This could mean:")
        print("  1. Duma Boko's statements are consistent across videos")
        print("  2. Need to add more target statements")
        print("  3. Need to adjust contradiction detection thresholds")
        print("  4. Contradictions may be more subtle/nuanced")

if __name__ == "__main__":
    analyze_contradictions()
