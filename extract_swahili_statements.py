#!/usr/bin/env python3
"""
Extract statements from Swahili transcripts.
Uses Swahili governance keywords and patterns.
"""
import json
import re
from pathlib import Path
from typing import List, Dict, Tuple

# Swahili governance/policy keywords
SWAHILI_KEYWORDS = [
    'serikali',  # government
    'rais',      # president
    'bunge',     # parliament
    'sheria',    # law
    'katiba',    # constitution
    'haki',      # right/justice
    'maendeleo', # development
    'uchumi',    # economy
    'elimu',     # education
    'afya',      # health
    'usawa',     # equality
    'amani',     # peace
    'ushirikiano', # cooperation
    'utawala',   # governance
    'mabadiliko', # change
    'mpango',    # plan
    'dhamira',   # intention/promise
    'lazima',    # must/should
    'tuta',      # we will (future tense)
    'nita',      # I will
    'tunataka',  # we want
    'ninataka',  # I want
    'tunasema',  # we say
    'ninasema',  # I say
    'tunahitaji', # we need
    'ninahitaji', # I need
]

def load_transcript(transcript_path: Path) -> Dict:
    """Load a transcript JSON file."""
    try:
        with open(transcript_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"  [ERROR] Failed to load {transcript_path}: {e}")
        return {}

def is_important_statement(text: str) -> Tuple[bool, float]:
    """Check if Swahili text contains important governance keywords."""
    text_lower = text.lower()
    score = 0.0
    matched_keywords = []
    
    for keyword in SWAHILI_KEYWORDS:
        if keyword in text_lower:
            score += 2.0
            matched_keywords.append(keyword)
    
    # Bonus for first-person future tense (indicates promises/commitments)
    if re.search(r'\b(nita|tuta|nitak|tutak)\w+\b', text_lower):
        score += 5.0
        matched_keywords.append('[FUTURE_TENSE: promise/commitment]')
    
    # Bonus for complete sentences
    if text.strip().endswith('.') or '?' in text or '!' in text:
        score += 2.0
    
    # Reasonable length
    words = len(text.split())
    if 5 <= words <= 30:
        score += 2.0
    
    return score >= 6.0, score

def extract_statements():
    """Extract important statements from all Swahili transcripts."""
    print("="*70)
    print("EXTRACTING STATEMENTS FROM SWAHILI TRANSCRIPTS")
    print("="*70)
    
    transcript_dir = Path("downloads/TRANSCRIPTS")
    output_file = Path("swahili_statements_extracted.json")
    
    if not transcript_dir.exists():
        print(f"[ERROR] Transcript directory not found")
        return
    
    transcript_files = list(transcript_dir.glob("*.transcript.json"))
    print(f"Found {len(transcript_files)} transcript files\n")
    
    all_statements = []
    
    for i, transcript_file in enumerate(transcript_files, 1):
        print(f"[{i}/{len(transcript_files)}] Processing {transcript_file.name}...")
        
        data = load_transcript(transcript_file)
        if not data:
            continue
        
        video_id = data.get('video_id', transcript_file.stem.replace('.transcript', ''))
        transcript = data.get('transcript', [])
        
        found_count = 0
        for segment in transcript:
            text = segment.get('text', '').strip()
            if not text:
                continue
            
            is_important, score = is_important_statement(text)
            
            if is_important:
                statement = {
                    'text': text,
                    'video_id': video_id,
                    'timestamp': f"{segment.get('start', 0):.1f}",
                    'importance_score': score,
                    'word_count': len(text.split()),
                    'language': data.get('language', 'unknown')
                }
                all_statements.append(statement)
                found_count += 1
        
        if found_count > 0:
            print(f"  [FOUND] {found_count} statements")
        else:
            print(f"  [OK] No statements found")
    
    # Sort by importance
    all_statements.sort(key=lambda x: x['importance_score'], reverse=True)
    
    # Deduplicate
    seen = set()
    unique = []
    for stmt in all_statements:
        text_key = stmt['text'][:50].lower()
        if text_key not in seen:
            unique.append(stmt)
            seen.add(text_key)
    
    # Save results
    output_data = {
        'language': 'swahili',
        'total_transcripts': len(transcript_files),
        'total_statements': len(all_statements),
        'unique_statements': len(unique),
        'top_30_statements': unique[:30],
        'all_statements': unique
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    print(f"\n{'='*70}")
    print("EXTRACTION COMPLETE")
    print(f"{'='*70}")
    print(f"Total statements: {len(all_statements)}")
    print(f"Unique statements: {len(unique)}")
    print(f"Saved to: {output_file}")
    
    # Display top 15
    print(f"\n{'='*70}")
    print("TOP 15 SWAHILI STATEMENTS")
    print(f"{'='*70}")
    
    for i, stmt in enumerate(unique[:15], 1):
        print(f"\n{i}. [Score: {stmt['importance_score']:.1f}] [{stmt['video_id']} @ {stmt['timestamp']}s]")
        print(f"   {stmt['text']}")
    
    print(f"\n{'='*70}")
    print("NOTE: These statements are in Swahili.")
    print("Options:")
    print("1. Provide Swahili target phrases to find contradictions")
    print("2. Translate key statements to English first")
    print("3. Manual review by Swahili speaker")
    print(f"{'='*70}")

if __name__ == "__main__":
    extract_statements()
