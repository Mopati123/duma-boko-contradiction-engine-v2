#!/usr/bin/env python3
"""
Extract Duma Boko's key statements from all transcripts.
Identifies first-person statements, policy positions, and governance claims.
"""
import json
import re
from pathlib import Path
from collections import Counter
from typing import List, Dict, Tuple

# Keywords that indicate important statements
POLICY_KEYWORDS = [
    'government', 'policy', 'law', 'constitution', 'legal', 'illegal',
    'will', 'must', 'should', 'need to', 'going to', 'plan to',
    'believe', 'think', 'know', 'support', 'oppose', 'against',
    'promise', 'commit', 'ensure', 'guarantee', 'deliver',
    'change', 'reform', 'improve', 'develop', 'build', 'create',
    'people', 'citizens', 'nation', 'country', 'botswana',
    'future', 'vision', 'goal', 'objective', 'priority'
]

# First-person statement indicators
I_STATEMENTS = [
    r'\bi\s+will\b',
    r'\bi\s+am\s+going\s+to\b',
    r'\bi\s+plan\s+to\b',
    r'\bi\s+promise\b',
    r'\bi\s+believe\b',
    r'\bi\s+think\b',
    r'\bi\s+support\b',
    r'\bi\s+oppose\b',
    r'\bmy\s+government\b',
    r'\bmy\s+administration\b',
    r'\bwe\s+will\b',
    r'\bwe\s+are\s+going\s+to\b',
    r'\bwe\s+must\b',
    r'\bwe\s+should\b',
    r'\bour\s+plan\b',
    r'\bour\s+policy\b',
    r'\bthis\s+government\s+will\b',
    r'\bthe\s+government\s+will\b',
]

def load_transcript(transcript_path: Path) -> Dict:
    """Load a transcript JSON file."""
    try:
        with open(transcript_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"  [ERROR] Failed to load {transcript_path}: {e}")
        return {}

def is_i_statement(text: str) -> Tuple[bool, str]:
    """Check if text contains first-person statement indicators."""
    text_lower = text.lower()
    for pattern in I_STATEMENTS:
        if re.search(pattern, text_lower):
            return True, pattern
    return False, ""

def calculate_importance_score(text: str) -> float:
    """Calculate importance score based on keywords and structure."""
    score = 0.0
    text_lower = text.lower()
    
    # Policy keyword matches
    for keyword in POLICY_KEYWORDS:
        if keyword in text_lower:
            score += 1.0
    
    # First-person bonus
    if re.search(r'\b(i|we|my|our)\s+(will|must|should|going\s+to|plan\s+to|promise|commit)\b', text_lower):
        score += 5.0
    
    # Complete sentence bonus
    if text.strip().endswith('.') or text.strip().endswith('!') or text.strip().endswith('?'):
        score += 2.0
    
    # Length bonus (not too short, not too long)
    words = len(text.split())
    if 8 <= words <= 40:
        score += 3.0
    elif words > 40:
        score += 1.0
    
    # Governance terms bonus
    governance_terms = ['government', 'policy', 'law', 'constitution', 'reform', 'change', 'future']
    for term in governance_terms:
        if term in text_lower:
            score += 2.0
    
    return score

def extract_statements_from_transcript(transcript_data: Dict, video_id: str) -> List[Dict]:
    """Extract important statements from a single transcript."""
    statements = []
    transcript = transcript_data.get('transcript', [])
    
    for segment in transcript:
        text = segment.get('text', '').strip()
        if not text:
            continue
        
        # Check if it's an I-statement
        is_i, pattern = is_i_statement(text)
        
        # Calculate importance
        importance = calculate_importance_score(text)
        
        # Only keep statements with sufficient importance
        if importance >= 5.0:
            statement = {
                'text': text,
                'video_id': video_id,
                'timestamp': f"{segment.get('start', 0):.1f}",
                'is_i_statement': is_i,
                'pattern_matched': pattern if is_i else '',
                'importance_score': importance,
                'word_count': len(text.split())
            }
            statements.append(statement)
    
    return statements

def deduplicate_statements(statements: List[Dict]) -> List[Dict]:
    """Remove duplicate or very similar statements."""
    unique = []
    seen_texts = set()
    
    for stmt in sorted(statements, key=lambda x: x['importance_score'], reverse=True):
        # Normalize text for comparison
        normalized = ' '.join(stmt['text'].lower().split())[:100]
        
        # Check if similar to already-seen
        is_duplicate = False
        for seen in seen_texts:
            # Simple similarity check
            if normalized in seen or seen in normalized:
                is_duplicate = True
                break
        
        if not is_duplicate:
            unique.append(stmt)
            seen_texts.add(normalized)
    
    return unique

def extract_all_statements():
    """Extract statements from all transcripts."""
    print("="*70)
    print("EXTRACTING DUMA BOKO'S STATEMENTS FROM ALL TRANSCRIPTS")
    print("="*70)
    
    transcript_dir = Path("downloads/TRANSCRIPTS")
    output_file = Path("duma_statements_extracted.json")
    
    if not transcript_dir.exists():
        print(f"[ERROR] Transcript directory not found: {transcript_dir}")
        return
    
    # Find all transcript files
    transcript_files = list(transcript_dir.glob("*.transcript.json"))
    print(f"\nFound {len(transcript_files)} transcript files")
    
    all_statements = []
    
    for i, transcript_file in enumerate(transcript_files, 1):
        print(f"\n[{i}/{len(transcript_files)}] Processing {transcript_file.name}...")
        
        # Load transcript
        data = load_transcript(transcript_file)
        if not data:
            continue
        
        video_id = data.get('video_id', transcript_file.stem.replace('.transcript', ''))
        
        # Extract statements
        statements = extract_statements_from_transcript(data, video_id)
        
        if statements:
            print(f"  [FOUND] {len(statements)} statements")
            all_statements.extend(statements)
        else:
            print(f"  [OK] No statements found")
    
    # Deduplicate
    print(f"\n{'='*70}")
    print("DEDUPLICATING STATEMENTS")
    print(f"{'='*70}")
    
    unique_statements = deduplicate_statements(all_statements)
    print(f"Total statements: {len(all_statements)}")
    print(f"After deduplication: {len(unique_statements)}")
    
    # Sort by importance
    unique_statements.sort(key=lambda x: x['importance_score'], reverse=True)
    
    # Save to JSON
    output_data = {
        'extraction_date': str(Path(__file__).stat().st_mtime),
        'total_videos_processed': len(transcript_files),
        'total_statements_found': len(all_statements),
        'unique_statements': len(unique_statements),
        'top_30_statements': unique_statements[:30],
        'all_statements': unique_statements
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    print(f"\n[SAVED] {len(unique_statements)} statements to {output_file}")
    
    # Display top 20
    print(f"\n{'='*70}")
    print("TOP 20 STATEMENTS (Review these for contradiction targets)")
    print(f"{'='*70}")
    
    for i, stmt in enumerate(unique_statements[:20], 1):
        print(f"\n{i}. [Score: {stmt['importance_score']:.1f}] [{stmt['video_id']} @ {stmt['timestamp']}s]")
        print(f"   {stmt['text']}")
        if stmt['is_i_statement']:
            print(f"   [I-STATEMENT: {stmt['pattern_matched']}]")
    
    # Summary
    print(f"\n{'='*70}")
    print("EXTRACTION COMPLETE")
    print(f"{'='*70}")
    print(f"\nNext Steps:")
    print(f"1. Review {output_file} - top 30 statements")
    print(f"2. Select 5-10 most important for contradiction targets")
    print(f"3. Add any known statements you want to track")
    print(f"4. Run contradiction analysis with combined targets")
    print(f"\nTotal ready for analysis: {len(unique_statements)} statements")

if __name__ == "__main__":
    extract_all_statements()
